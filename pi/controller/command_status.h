/* Read-only command/ACK monitoring; never changes game decisions. */
static void send_all(int, const char *);
typedef struct { int pending; double since; char expected[101]; } COMMAND_LANE;
static COMMAND_LANE command_lanes[2][3];
static int command_ever[2], command_last_kind[2];
static long command_ack_time[2];
static int command_kind(const char *p) {
    return !strncmp(p,"COUNT@",6)?0:!strncmp(p,"TIME@",5)?1:!strncmp(p,"MOTOR@",6)?2:-1;
}
static void command_sent(const char *message) {
    int board=!strncmp(message,"[ARD]",5)?0:!strncmp(message,"[STM]",5)?1:-1;
    if(board<0)return;
    const char *p=message+5; int kind=command_kind(p); if(kind<0)return;
    char payload[80]; size_t n=strcspn(p,"\r\n"); if(n>=sizeof(payload))return;
    memcpy(payload,p,n);payload[n]=0;
    COMMAND_LANE *lane=&command_lanes[board][kind];
    if(!lane->pending)lane->since=monotonic_seconds();
    lane->pending=1;command_ever[board]=1;
    if(kind==2)snprintf(lane->expected,sizeof(lane->expected),"%s@OK",payload);
    else snprintf(lane->expected,sizeof(lane->expected),"APPLIED@%s",payload);
}
static void command_received(const char *sender,const char *payload) {
    int board=!strcmp(sender,"ARD")?0:!strcmp(sender,"STM")?1:-1;if(board<0)return;
    for(int kind=0;kind<3;kind++) {
        COMMAND_LANE *lane=&command_lanes[board][kind];
        if(lane->pending&&!strcmp(payload,lane->expected)) {
            lane->pending=0;command_last_kind[board]=kind;command_ack_time[board]=(long)time(NULL);
        }
    }
}
static void command_report(int sock) {
    static double reported=-1; double now=monotonic_seconds();if(now-reported<1)return;reported=now;
    const char *kinds[]={"COUNT","TIME","MOTOR"};
    for(int board=0;board<2;board++) {
        int oldest=-1;
        for(int kind=0;kind<3;kind++)if(command_lanes[board][kind].pending&&
           (oldest<0||command_lanes[board][kind].since<command_lanes[board][oldest].since))oldest=kind;
        const char *state=oldest>=0?(now-command_lanes[board][oldest].since>=10?"TIMEOUT":"WAIT"):
            command_ever[board]?"DONE":"NONE";
        char line[101];snprintf(line,sizeof(line),"[JETSON]DEVICE@%s@%s@%s@%ld\n",board?"STM":"ARD",state,
            command_ever[board]?kinds[oldest>=0?oldest:command_last_kind[board]]:"NONE",command_ack_time[board]);
        send_all(sock,line);
    }
}
