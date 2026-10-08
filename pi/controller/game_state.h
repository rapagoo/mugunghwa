/* Pi is the only authority. Track IDs are frozen per game, never reassigned. */
#include <math.h>
#include <sys/stat.h>
#include <fcntl.h>
static int game_enabled, game_active, game_joining, game_join_expected = -1;
static int game_count, game_ids[32], game_status[32], game_duration = 180, game_targets = 3;
static int game_remaining, game_last_remaining = -1, game_no_writer;
static unsigned int game_join_token;
static long game_epoch, game_revision;
static unsigned long game_version;
static double game_end, game_join_deadline, game_move_until, game_move_seconds = 5;
static double game_hold_min=2, game_hold_max=5;
static int game_audio;
static int game_audio_pending;
static double game_audio_due;
static unsigned int game_audio_token;
static char game_id[33], game_started[32], game_journal[1024], game_repo[1024];
static volatile sig_atomic_t game_shutdown;
static char game_device_ack[3][101], game_device_at[3][32];
static const char *game_phase = "waiting", *game_reason = "";
static void cycle_phase(int, const char *, int);
static void cycle_motor(int, const char *, int);
static void cycle_recover(int);
static void cycle_start(int);

static void game_utc(char out[32])
{
    struct timespec ts; clock_gettime(CLOCK_REALTIME,&ts);
    struct tm tm; gmtime_r(&ts.tv_sec, &tm);
    char date[24]; strftime(date,sizeof(date),"%Y-%m-%dT%H:%M:%S",&tm);
    snprintf(out,32,"%s.%03dZ",date,(int)(ts.tv_nsec/1000000));
}

static void game_save(const char *kind, int participant)
{
    char now[32]; game_utc(now);
    FILE *f = fopen(game_journal,"a");
    if(!f) fail("Game journal unavailable; controller stopped");
    fprintf(f,"{\"id\":\"%s\",\"version\":%lu,\"phase\":\"%s\",\"reason\":\"%s\","
        "\"started_at\":\"%s\",\"updated_at\":\"%s\",\"remaining\":%d,\"duration\":%d,"
        "\"epoch\":%ld,\"kind\":\"%s\",\"participant\":%d,\"players\":[",
        game_id,++game_version,game_phase,game_reason,game_started,now,
        game_remaining,game_duration,game_epoch,kind,participant);
    for(int i=0;i<game_count;i++) fprintf(f,"%s{\"track_id\":%d,\"status\":\"%s\"}",i?",":"",
        game_ids[i],game_status[i]==1?"passed":game_status[i]==2?"failed":"playing");
    fputs("],\"devices\":[",f);
    for(int i=0;i<3;i++) fprintf(f,"%s{\"id\":\"%s\",\"ack\":\"%s\",\"at\":\"%s\"}",i?",":"",
        i==0?"JETSON":i==1?"STM":"ARD",game_device_ack[i],game_device_at[i]);
    fputs("]}\n",f);
    if(fflush(f) || fsync(fileno(f))) fail("Game journal write failed");
    if(fclose(f)) fail("Game journal close failed");
}

static void game_device_seen(const char *sender, const char *payload)
{
    if(!game_enabled) return;
    int i=!strcmp(sender,"JETSON")?0:!strcmp(sender,"STM")?1:!strcmp(sender,"ARD")?2:-1;
    if(i<0 || strlen(payload)>100) return;
    /* Only protocol-safe text is serialized, never arbitrary incoming JSON. */
    for(const char *p=payload;*p;p++) if(!((*p>='A'&&*p<='Z') || (*p>='a'&&*p<='z') ||
        (*p>='0'&&*p<='9') || *p=='@' || *p=='_')) return;
    strcpy(game_device_ack[i],payload); game_utc(game_device_at[i]);
    if(game_active && i>0 && (!strncmp(payload,"APPLIED@",8) || !strncmp(payload,"MOTOR@",6))) game_save("device_ack",0);
}

static void game_exit_record(void)
{
    if(!game_active) return;
    game_active=0; game_phase="aborted"; game_reason="controller_disconnected";
    game_save("game_ended",0);
}

static void game_signal(int number) { (void)number; game_shutdown=1; }

static void game_lcd(int sock)
{
    static int last_total=-1, last_passed=-1, last_failed=-1;
    static double last_count_sent;
    int passed=0, failed=0;
    for(int i=0;i<game_count;i++) { passed+=game_status[i]==1; failed+=game_status[i]==2; }
    double now=monotonic_seconds();
    int counts_changed=game_count!=last_total || passed!=last_passed || failed!=last_failed || now-last_count_sent>=5;
    for(int t=0;t<2;t++) if(game_targets & (1<<t)) {
        char msg[LINE_SIZE];
        if(counts_changed) {
            snprintf(msg,sizeof(msg),"[%s]COUNT@%d@%d@%d\n",targets[t],game_count,passed,failed);
            send_all(sock,msg);
        }
        snprintf(msg,sizeof(msg),"[%s]TIME@%d\n",targets[t],game_remaining); send_all(sock,msg);
    }
    if(counts_changed) { last_total=game_count;last_passed=passed;last_failed=failed;last_count_sent=now; }
    printf("GAME COUNTS total=%d passed=%d failed=%d remaining=%d\n",game_count,passed,failed,game_remaining);
}

static void game_shot(int sock, int participant)
{
    if(!game_audio) return;
    char msg[LINE_SIZE];
    snprintf(msg,sizeof(msg),"[JETSON]SOUND@%s@FAIL@%d\n",game_id,participant);
    send_all(sock,msg);
}

static void game_finish(int sock, const char *reason, int timeout)
{
    if(!game_active) { game_joining=0; return; }
    if(timeout) for(int i=0;i<game_count;i++) if(!game_status[i]) {
        game_status[i]=2; game_save("timeout_failed",i+1); game_shot(sock,i+1);
    }
    game_active=0; game_phase=!strcmp(reason,"all_resolved") || timeout?"finished":"aborted";
    game_reason=reason; if(timeout) game_remaining=0;
    game_save("game_ended",0); game_lcd(sock);
    send_all(sock,"[JETSON]GAME@END\n"); cycle_recover(sock);
}

static int game_begin(int sock)
{
    if(!game_enabled) return 0;
    if(game_active || game_joining) return 1;
    game_joining=1; game_join_expected=-1; game_count=0;
    game_join_token=++cycle_request; game_join_deadline=monotonic_seconds()+3;
    char msg[LINE_SIZE]; snprintf(msg,sizeof(msg),"[JETSON]JOIN@%08x\n",game_join_token); send_all(sock,msg);
    puts("GAME ENROLL requesting current ROI participants"); return 1;
}

static void game_move(int sock)
{
    cycle_state=C_PLAY_MOVE; game_move_until=monotonic_seconds()+game_move_seconds;
    game_phase="move"; game_save("move",0); cycle_report(sock,monotonic_seconds());
    if(game_audio) {
        double delay=.5+1.5*((double)rand()/RAND_MAX);
        game_audio_pending=1; game_audio_token=cycle_request;
        game_audio_due=monotonic_seconds()+delay;
        game_move_until=game_audio_due+30;
        printf("GAME AUDIO delay %.3fs token=%08x\n",delay,game_audio_token);
    }
}

static int game_line(int sock, const char *sender, const char *payload)
{
    if(!game_enabled || strcmp(sender,"JETSON")) return 0;
    unsigned int token; int n, consumed=0; long epoch, revision;
    char audio_id[33], audio_result[8];
    if(sscanf(payload,"AUDIO@%32[0-9a-f]@%8x@%7[A-Z]%n",audio_id,&token,audio_result,&consumed)==3 && !payload[consumed]) {
        if(game_audio && !game_audio_pending && game_active && cycle_state==C_PLAY_MOVE && !strcmp(audio_id,game_id) && token==game_audio_token) {
            if(monotonic_seconds()>=game_end) game_finish(sock,"timeout",1);
            else if(!strcmp(audio_result,"DONE")) {
                game_phase="front_wait"; game_save("front_wait",0); cycle_motor(sock,"FRONT",C_FRONT);
            } else if(!strcmp(audio_result,"ERROR")) game_finish(sock,"audio_error",0);
        }
        return 1;
    }
    consumed=0;
    if(game_joining && sscanf(payload,"JOIN_BEGIN@%8x@%d@%ld@%ld%n",&token,&n,&epoch,&revision,&consumed)==4 && !payload[consumed]) {
        if(token==game_join_token && n>0 && n<=32) {
            game_join_expected=n; game_count=0; game_epoch=epoch; game_revision=revision;
        } else if(token==game_join_token) { game_joining=0; puts("GAME ENROLL rejected: empty/too many participants"); }
        return 1;
    }
    consumed=0;
    if(game_joining && sscanf(payload,"JOIN_PERSON@%8x@%d%n",&token,&n,&consumed)==2 && !payload[consumed]) {
        if(token==game_join_token && game_join_expected>0 && n>0 && game_count<game_join_expected) {
            for(int i=0;i<game_count;i++) if(game_ids[i]==n) return 1;
            game_ids[game_count]=n; game_status[game_count++]=0;
        }
        return 1;
    }
    consumed=0;
    if(game_joining && sscanf(payload,"JOIN_END@%8x%n",&token,&consumed)==1 && !payload[consumed]) {
        if(token!=game_join_token || game_join_expected<=0 || game_count!=game_join_expected) return 1;
        game_joining=0;
        if(cycle_home_required || monotonic_seconds()-cycle_ready>3) return 1;
        unsigned char random[16]; int fd=open("/dev/urandom",O_RDONLY);
        if(fd<0 || read(fd,random,sizeof(random))!=sizeof(random)) fail("Game ID generation failed");
        close(fd); for(int i=0;i<16;i++) snprintf(game_id+i*2,3,"%02x",random[i]);
        game_version=0; game_remaining=game_duration; game_last_remaining=game_remaining;
        game_end=monotonic_seconds()+game_duration; game_utc(game_started);
        game_active=1; game_phase="move_preparing"; game_reason="";
        game_save("game_started",0); game_lcd(sock);
        char msg[LINE_SIZE]; snprintf(msg,sizeof(msg),"[JETSON]GAME@%s@%ld@%ld\n",game_id,game_epoch,game_revision);
        send_all(sock,msg); cycle_phase(sock,"MOVE",C_MOVE); return 1;
    }
    if(!strcmp(payload,"GAME_ERROR")) {
        game_finish(sock,"source_changed",0); return 1;
    }
    char id[33], result[8]; consumed=0;
    if(sscanf(payload,"OBS@%32[0-9a-f]@%8x@%d@%7[A-Z]@%ld@%ld%n",id,&token,&n,result,&epoch,&revision,&consumed)==6 && !payload[consumed]) {
        if(!game_active || strcmp(id,game_id) || token!=cycle_request || epoch!=game_epoch || revision!=game_revision) return 1;
        if(monotonic_seconds()>=game_end) { game_finish(sock,"timeout",1); return 1; }
        int verdict=(!strcmp(result,"PASS") && (cycle_state==C_PLAY_MOVE || cycle_state==C_FRONT))?1:
            (!strcmp(result,"FAIL") && (cycle_state==C_HOLD || cycle_state==C_REAR))?2:0;
        if(!verdict) return 1;
        int unfinished=0;
        for(int i=0;i<game_count;i++) {
            if(game_ids[i]==n && !game_status[i]) { game_status[i]=verdict; game_save(verdict==1?"passed":"failed",i+1); game_lcd(sock); if(verdict==2) game_shot(sock,i+1); }
            unfinished+=!game_status[i];
        }
        if(!unfinished) game_finish(sock,"all_resolved",0);
        return 1;
    }
    /* Legacy test counts cannot overwrite authoritative game counts. */
    return !strncmp(payload,"COUNT@",6);
}

static void game_tick(int sock, double now)
{
    if(!game_enabled) return;
    if(game_joining && now>=game_join_deadline) { game_joining=0; puts("GAME ENROLL timeout; press START again"); }
    if(!game_active) return;
    if(now>=game_end) { game_finish(sock,"timeout",1); return; }
    game_remaining=(int)ceil(game_end-now);
    if(game_remaining!=game_last_remaining) { game_last_remaining=game_remaining; game_save("tick",0); game_lcd(sock); }
    if(game_audio && game_audio_pending && cycle_state==C_PLAY_MOVE && now>=game_audio_due) {
        char msg[LINE_SIZE]; game_audio_pending=0; game_move_until=now+30;
        snprintf(msg,sizeof(msg),"[JETSON]AUDIO@%s@%08x@CHANT\n",game_id,game_audio_token);
        send_all(sock,msg); printf("GAME AUDIO request %08x\n",game_audio_token);
    }
    if(cycle_state==C_PLAY_MOVE && now>=game_move_until) {
        if(game_audio) { game_finish(sock,"audio_timeout",0); return; }
        game_phase="front_wait"; game_save("front_wait",0); cycle_motor(sock,"FRONT",C_FRONT);
    }
}

static void game_setup(int sock)
{
    srand((unsigned int)time(NULL) ^ (unsigned int)getpid());
    signal(SIGTERM,game_signal); signal(SIGINT,game_signal);
    char exe[1024]; ssize_t length=readlink("/proc/self/exe",exe,sizeof(exe)-1);
    if(length<0 || length>900) fail("Cannot locate repository or path too long");
    exe[length]=0;
    char *p=strrchr(exe,'/'); if(!p) fail("Invalid executable path"); *p=0;
    p=strrchr(exe,'/'); if(!p) fail("Invalid executable path"); *p=0;
    p=strrchr(exe,'/'); if(!p) fail("Invalid executable path"); *p=0;
    snprintf(game_repo,sizeof(game_repo),"%s",exe);
    char dir[1200]; snprintf(dir,sizeof(dir),"%s/.runtime",exe); if(mkdir(dir,0700) && errno!=EEXIST) fail("Cannot create runtime");
    snprintf(dir,sizeof(dir),"%s/.runtime/game",exe); if(mkdir(dir,0700) && errno!=EEXIST) fail("Cannot create game directory");
    if(!*game_journal) { strcpy(game_journal,exe); strcat(game_journal,"/.runtime/game/events.jsonl"); }
    FILE *f=fopen(game_journal,"a"); if(!f) fail("Cannot open game journal"); fclose(f);
    if(game_no_writer) return;
    pid_t child=fork(); if(child<0) fail("DB writer launch failed");
    if(!child) {
        close(sock); setsid();
        snprintf(dir,sizeof(dir),"%s/.runtime/game/writer.log",exe);
        int log=open(dir,O_WRONLY|O_CREAT|O_APPEND,0600); if(log<0) _exit(1);
        dup2(log,STDOUT_FILENO); dup2(log,STDERR_FILENO); close(log);
        int null=open("/dev/null",O_RDONLY); dup2(null,STDIN_FILENO); close(null);
        char script[1200], config[1200]; snprintf(script,sizeof(script),"%s/pi/game_db_writer.py",exe);
        snprintf(config,sizeof(config),"%s/.runtime/db/writer.json",exe);
        execlp("python3","python3","-u",script,"--journal",game_journal,"--config",config,(char*)NULL); _exit(1);
    }
}
