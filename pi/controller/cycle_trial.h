/* Explicit opt-in, single-cycle trial. Included after socket helpers. */
enum { C_IDLE, C_MOVE, C_FRONT, C_STOP, C_HOLD, C_REAR, C_RESUME, C_DONE, C_ERROR };
static int cycle_enabled, cycle_state;
static double cycle_hold = 5, cycle_timeout = 10, cycle_deadline, cycle_hold_until;
static double cycle_ready;
static double cycle_ping;
static unsigned int cycle_request;
static char cycle_expected[80];

static void cycle_phase(int sock, const char *phase, int next)
{
    char message[LINE_SIZE];
    ++cycle_request;
    snprintf(message, sizeof(message), "[JETSON]PHASE@%s@%08x\n", phase, cycle_request);
    snprintf(cycle_expected, sizeof(cycle_expected), "PHASE@%s@%08x@OK", phase, cycle_request);
    send_all(sock, message);
    cycle_state = next;
    cycle_deadline = monotonic_seconds() + cycle_timeout;
    printf("CYCLE TX %s", message);
}

static void cycle_abort(int sock, const char *reason)
{
    cycle_phase(sock, "IDLE", C_ERROR);
    printf("CYCLE ABORT %s; no further motor commands\n", reason);
}

static void cycle_start(int sock)
{
    if(cycle_state != C_IDLE && cycle_state != C_DONE && cycle_state != C_ERROR) {
        puts("CYCLE IGNORE start while active"); return;
    }
    if(!cycle_ready || monotonic_seconds()-cycle_ready > 3) {
        puts("CYCLE NOT_READY Jetson fresh inference required"); return;
    }
    printf("CYCLE START hold=%.2fs timeout=%.2fs\n", cycle_hold, cycle_timeout);
    cycle_phase(sock, "MOVE", C_MOVE);
}

static void cycle_motor(int sock, const char *direction, int next)
{
    char message[LINE_SIZE];
    snprintf(message, sizeof(message), "[STM]MOTOR@%s\n", direction);
    send_all(sock, message);
    cycle_state = next;
    cycle_deadline = monotonic_seconds() + cycle_timeout;
    printf("CYCLE TX %s", message);
}

static int cycle_line(int sock, const char *sender, const char *payload)
{
    if(!cycle_enabled) return 0;
    if(!strcmp(sender, "JETSON") && !strcmp(payload, "TRIAL@READY")) {
        cycle_ready = monotonic_seconds(); return 1;
    }
    if(!strcmp(sender, "JETSON") && !strcmp(payload, "TRIAL@ERROR")) {
        cycle_ready = 0;
        if(cycle_state >= C_MOVE && cycle_state <= C_RESUME) cycle_abort(sock, "Jetson unavailable");
        return 1;
    }
    if(!strcmp(sender, "STM") && !strcmp(payload, "START")) { cycle_start(sock); return 1; }
    if(!strcmp(sender, "STM") && !strcmp(payload, "STOP")) { cycle_abort(sock, "STM stop"); return 1; }
    if(!strcmp(sender, "JETSON") && !strcmp(payload, cycle_expected)) {
        if(cycle_state == C_MOVE) cycle_motor(sock, "FRONT", C_FRONT);
        else if(cycle_state == C_STOP) { cycle_state = C_HOLD; puts("CYCLE STOP confirmed by Jetson"); }
        else if(cycle_state == C_RESUME) { cycle_state = C_DONE; puts("CYCLE DONE movement allowed; one cycle complete"); }
        return 1;
    }
    if(!strcmp(sender, "STM") && !strcmp(payload, "MOTOR@FRONT@OK") && cycle_state == C_FRONT) {
        cycle_hold_until = monotonic_seconds() + cycle_hold;
        cycle_phase(sock, "STOP", C_STOP); return 1;
    }
    if(!strcmp(sender, "STM") && !strcmp(payload, "MOTOR@REAR@OK") && cycle_state == C_REAR) {
        cycle_phase(sock, "MOVE", C_RESUME); return 1;
    }
    return 0;
}

static void cycle_tick(int sock)
{
    if(!cycle_enabled) return;
    double now = monotonic_seconds();
    if(now-cycle_ping >= 1) { send_all(sock,"[JETSON]TRIAL@PING\n"); cycle_ping=now; }
    if(cycle_state < C_MOVE || cycle_state > C_RESUME) return;
    if(now-cycle_ready > 3) { cycle_abort(sock, "Jetson heartbeat lost"); return; }
    if(cycle_state == C_HOLD) {
        if(now >= cycle_hold_until) cycle_motor(sock, "REAR", C_REAR);
    } else if(now >= cycle_deadline) cycle_abort(sock, "completion timeout");
}
