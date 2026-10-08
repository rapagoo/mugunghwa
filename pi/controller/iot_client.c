/* PI controller: Jetson observations -> PI, COUNT -> MCU, APPLIED -> Jetson.
 * --game freezes participants and owns time, results, LCD and a durable DB journal. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <time.h>
#include <arpa/inet.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <sys/select.h>
#include <signal.h>

#define LINE_SIZE 101
#define PENDING_SIZE 32

typedef struct {
    int active, target, counts[3];
    double sent_at;
    unsigned long order;
} PENDING;

static const char *targets[] = {"ARD", "STM"};
static PENDING pending[PENDING_SIZE];
static unsigned long order;
static void game_exit_record(void);

static void fail(const char *message)
{
    fprintf(stderr, "%s\n", message);
    game_exit_record();
    exit(EXIT_FAILURE);
}

static double monotonic_seconds(void)
{
    struct timespec now;
    if(clock_gettime(CLOCK_MONOTONIC, &now)) fail("clock_gettime failed");
    return now.tv_sec + now.tv_nsec / 1e9;
}

static void send_all(int sock, const char *message)
{
    size_t offset = 0, length = strlen(message);
    while(offset < length) {
        ssize_t n = send(sock, message + offset, length - offset, MSG_NOSIGNAL);
        if(n < 0 && errno == EINTR) continue;
        if(n <= 0) fail("send failed");
        offset += (size_t)n;
    }
}

/* Accept exactly three decimal fields, each 0..99, with no extra characters. */
static int parse_counts(const char *payload, const char *prefix, int counts[3])
{
    size_t prefix_length = strlen(prefix);
    if(strncmp(payload, prefix, prefix_length)) return 0;
    const char *p = payload + prefix_length;
    for(int field = 0; field < 3; field++) {
        int digits = 0, value = 0;
        while(*p >= '0' && *p <= '9') {
            if(++digits > 2) return 0;
            value = value * 10 + (*p++ - '0');
        }
        if(!digits) return 0;
        counts[field] = value;
        if(field < 2) {
            if(*p++ != '@') return 0;
        } else if(*p) return 0;
    }
    return counts[1] + counts[2] <= counts[0];
}

static void remember(int target, const int counts[3], double now)
{
    int slot = 0;
    for(int i = 0; i < PENDING_SIZE; i++) {
        if(!pending[i].active) { slot = i; break; }
        if(pending[i].order < pending[slot].order) slot = i;
    }
    pending[slot].active = 1;
    pending[slot].target = target;
    memcpy(pending[slot].counts, counts, sizeof(pending[slot].counts));
    pending[slot].sent_at = now;
    pending[slot].order = ++order;
}

/* Experimental camera observations. No game decisions or MCU commands here. */
static int observation(int sock, const char *payload)
{
    int summary = !strncmp(payload, "VISION@", 7);
    if(!summary && strncmp(payload, "POSITION@", 9)) return 0;
    const char *p = payload + (summary ? 7 : 9);
    char boot[9];
    for(int i = 0; i < 8; i++) {
        if(!((*p >= '0' && *p <= '9') || (*p >= 'a' && *p <= 'f'))) return 0;
        boot[i] = *p++;
    }
    boot[8] = '\0';
    if(*p++ != '@') return 0;
    unsigned long values[4] = {0};
    int fields = summary ? 3 : 4;
    for(int i = 0; i < fields; i++) {
        unsigned long limit = i == 0 || (!summary && i == 1) ? 2147483647UL :
                              summary ? 999UL : 1000UL;
        int digits = 0;
        while(*p >= '0' && *p <= '9') {
            unsigned long digit = (unsigned long)(*p++ - '0');
            if(++digits > 10 || values[i] > (limit - digit) / 10) return 0;
            values[i] = values[i] * 10 + digit;
            if(values[i] > limit) return 0;
        }
        if(!digits) return 0;
        if(i < fields - 1) { if(*p++ != '@') return 0; }
        else if(*p) return 0;
    }
    if(!values[0] || (summary ? values[2] > values[1] : !values[1])) return 0;
    printf("OBSERVATION [JETSON]%s\n", payload);
    if(summary) {
        char outgoing[LINE_SIZE];
        snprintf(outgoing, sizeof(outgoing), "[JETSON]VISION_ACK@%s@%lu\n", boot, values[0]);
        send_all(sock, outgoing);
    }
    return 1;
}

#include "cycle_trial.h"

static void handle_line(int sock, char *line, int target_mask)
{
    char *closing = strchr(line, ']');
    if(line[0] != '[' || !closing) { puts("IGNORE malformed message"); return; }
    *closing = '\0';
    const char *sender = line + 1, *payload = closing + 1;
    game_device_seen(sender,payload);
    if(cycle_line(sock, sender, payload)) return;
    int counts[3];
    double now = monotonic_seconds();
    for(int i = 0; i < PENDING_SIZE; i++)
        if(pending[i].active && now - pending[i].sent_at > 30) pending[i].active = 0;
    if(!strcmp(sender, "JETSON") && observation(sock, payload)) return;
    if(!strcmp(sender, "JETSON") && parse_counts(payload, "COUNT@", counts)) {
        for(int target = 0; target < 2; target++) {
            if(!(target_mask & (1 << target))) continue;
            char outgoing[LINE_SIZE];
            snprintf(outgoing, sizeof(outgoing), "[%s]COUNT@%d@%d@%d\n",
                     targets[target], counts[0], counts[1], counts[2]);
            send_all(sock, outgoing);
            remember(target, counts, now);
            printf("RX [JETSON]%s -> TX %s", payload, outgoing);
        }
        return;
    }
    if(parse_counts(payload, "APPLIED@COUNT@", counts)) {
        int match = -1;
        for(int i = 0; i < PENDING_SIZE; i++) {
            if(pending[i].active && !strcmp(sender, targets[pending[i].target]) &&
               !memcmp(pending[i].counts, counts, sizeof(counts)) &&
               (match < 0 || pending[i].order < pending[match].order)) match = i;
        }
        if(match >= 0) {
            char outgoing[LINE_SIZE];
            pending[match].active = 0;
            snprintf(outgoing, sizeof(outgoing), "[JETSON]APPLIED@COUNT@%d@%d@%d\n",
                     counts[0], counts[1], counts[2]);
            send_all(sock, outgoing);
            printf("RX [%s]%s -> TX %s", sender, payload, outgoing);
            return;
        }
    }
    printf("IGNORE [%s]%s\n", sender, payload);
}

int main(int argc, char *argv[])
{
    int target_mask = 3;
    if(argc < 4)
        fail("Usage: iot_client <IP> <port> PI [--target BOTH|ARD|STM] [--cycle-test] [--hold-seconds 5] [--ack-timeout 10]");
    if(strcmp(argv[3], "PI")) fail("Pi controller must log in as PI");
    for(int i=4; i<argc; i++) {
        if(!strcmp(argv[i], "--game")) { game_enabled=cycle_enabled=1; continue; }
        if(!strcmp(argv[i], "--no-db-writer")) { game_no_writer=1; continue; }
        if(!strcmp(argv[i], "--cycle-test")) { cycle_enabled = 1; continue; }
        if(i+1 >= argc) fail("Missing option value");
        const char *option = argv[i], *value = argv[++i];
        if(!strcmp(option,"--journal")) { if(strlen(value)>=sizeof(game_journal)) fail("Journal path too long"); strcpy(game_journal,value); }
        else if(!strcmp(option,"--duration")) { char *tail; long n=strtol(value,&tail,10); if(!*value || *tail || n<1 || n>3600) fail("Duration must be 1..3600"); game_duration=(int)n; }
        else if(!strcmp(option,"--move-seconds")) { char *tail; double n=strtod(value,&tail); if(!*value || *tail || !isfinite(n) || n<.2 || n>120) fail("Move duration invalid"); game_move_seconds=n; }
        else if(!strcmp(option, "--target")) {
            if(!strcmp(value, "ARD")) target_mask = 1;
            else if(!strcmp(value, "STM")) target_mask = 2;
            else if(strcmp(value, "BOTH")) fail("Target must be BOTH, ARD or STM");
        } else if(!strcmp(option,"--hold-seconds") || !strcmp(option,"--ack-timeout")) {
            char *tail; double n = strtod(value, &tail);
            if(!*value || *tail || !(n >= .2 && n <= 120)) fail("Duration must be 0.2..120 seconds");
            if(!strcmp(option,"--hold-seconds")) { cycle_hold=n; game_hold_min=game_hold_max=n; } else cycle_timeout=n;
        } else fail("Unknown option");
    }
    char *end;
    errno = 0;
    long port = strtol(argv[2], &end, 10);
    if(errno || !*argv[2] || *end || port < 1 || port > 65535) fail("Invalid port");
    struct sockaddr_in address = {0};
    address.sin_family = AF_INET;
    address.sin_port = htons((unsigned short)port);
    if(inet_pton(AF_INET, argv[1], &address.sin_addr) != 1) fail("Invalid IPv4 address");
    int sock = socket(AF_INET, SOCK_STREAM, 0);
    if(sock < 0 || connect(sock, (struct sockaddr *)&address, sizeof(address))) fail("connect failed");
    struct timeval timeout = {5, 0};
    if(setsockopt(sock, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout))) fail("setsockopt failed");
    send_all(sock, "[PI:PASSWD]");
    char line[LINE_SIZE];
    size_t used = 0;
    while(1) {
        char byte;
        ssize_t n = recv(sock, &byte, 1, 0);
        if(n < 0 && errno == EINTR) continue;
        if(n <= 0 || used >= sizeof(line) - 1 || byte == '\0') fail("Login reply failed or too long");
        line[used++] = byte;
        if(byte == '\n') break;
    }
    line[used] = '\0';
    if(!strstr(line, "[PI] New connected!")) fail("PI login rejected");
    fputs(line, stdout);
    timeout.tv_sec = 0;
    if(setsockopt(sock, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout))) fail("setsockopt failed");
    printf("CONTROLLER_READY JETSON -> PI -> %s\n",
           target_mask == 3 ? "ARD,STM" : targets[target_mask == 1 ? 0 : 1]);
    fflush(stdout);
    used = 0;
    int input_active = cycle_enabled;
    size_t input_used = 0;
    char input_line[32];
    game_targets=target_mask;
    if(game_enabled) game_setup(sock);
    cycle_request = (unsigned int)time(NULL) ^ (unsigned int)getpid();
    if(cycle_enabled) {
        puts(game_enabled ? "GAME READY: START freezes ROI players; 180s default; stop returns rear" : "CYCLE READY: STM START or type start; stop returns rear; no audio/results");
        cycle_recover(sock);
    }
    fflush(stdout);
    while(1) {
        if(game_shutdown) { game_finish(sock,"operator_stop",0); close(sock); return 0; }
        if(cycle_enabled) {
            fd_set readers; FD_ZERO(&readers); FD_SET(sock,&readers);
            if(input_active) FD_SET(STDIN_FILENO,&readers);
            struct timeval tick = {0,100000};
            int ready = select(sock+1,&readers,NULL,NULL,&tick);
            if(ready < 0 && errno == EINTR) continue;
            if(ready < 0) fail("select failed");
            if(input_active && FD_ISSET(STDIN_FILENO,&readers)) {
                char c; ssize_t n = read(STDIN_FILENO,&c,1);
                if(n <= 0) input_active=0;
                else if(c=='\n') {
                    input_line[input_used]='\0';
                    if(!strcmp(input_line,"start")) cycle_start(sock);
                    else if(!strcmp(input_line,"stop")) cycle_abort(sock,"operator stop");
                    input_used=0;
                } else if(c!='\r' && input_used < sizeof(input_line)-1) input_line[input_used++]=c;
            }
            cycle_tick(sock); fflush(stdout);
            if(!FD_ISSET(sock,&readers)) continue;
        }
        char buffer[256];
        ssize_t n = recv(sock, buffer, sizeof(buffer), 0);
        if(n < 0 && errno == EINTR) continue;
        if(n <= 0) fail("Server disconnected");
        for(ssize_t i = 0; i < n; i++) {
            if(buffer[i] == '\r') continue;
            if(buffer[i] == '\0' || used >= sizeof(line) - 1) fail("Invalid or oversized TCP line");
            if(buffer[i] == '\n') {
                line[used] = '\0';
                handle_line(sock, line, target_mask);
                used = 0;
                fflush(stdout);
            } else line[used++] = buffer[i];
        }
    }
}
