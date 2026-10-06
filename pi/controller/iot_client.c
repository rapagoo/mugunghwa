/* PI controller: Jetson COUNT -> MCU commands, MCU APPLIED -> Jetson.
 * Test controller only; game state decisions are not implemented yet. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <time.h>
#include <arpa/inet.h>
#include <sys/socket.h>
#include <sys/time.h>

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

static void fail(const char *message)
{
    fprintf(stderr, "%s\n", message);
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

static void handle_line(int sock, char *line, int target_mask)
{
    char *closing = strchr(line, ']');
    if(line[0] != '[' || !closing) { puts("IGNORE malformed message"); return; }
    *closing = '\0';
    const char *sender = line + 1, *payload = closing + 1;
    int counts[3];
    double now = monotonic_seconds();
    for(int i = 0; i < PENDING_SIZE; i++)
        if(pending[i].active && now - pending[i].sent_at > 30) pending[i].active = 0;
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
    if(argc != 4 && argc != 6)
        fail("Usage: iot_client <IP> <port> PI [--target BOTH|ARD|STM]");
    if(strcmp(argv[3], "PI")) fail("Pi controller must log in as PI");
    if(argc == 6) {
        if(strcmp(argv[4], "--target")) fail("Unknown option");
        if(!strcmp(argv[5], "ARD")) target_mask = 1;
        else if(!strcmp(argv[5], "STM")) target_mask = 2;
        else if(strcmp(argv[5], "BOTH")) fail("Target must be BOTH, ARD or STM");
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
    while(1) {
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
