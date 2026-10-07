/* Explicit opt-in, single-cycle trial. Included after socket helpers. */
enum { C_IDLE, C_MOVE, C_FRONT, C_STOP, C_HOLD, C_REAR, C_RESUME, C_DONE, C_ERROR,
       C_RECOVER, C_RECOVERY_WAIT, C_HOME };
static int cycle_enabled, cycle_state;
static double cycle_hold = 5, cycle_timeout = 10, cycle_deadline, cycle_hold_until;
static double cycle_ready;
static double cycle_ping;
static unsigned int cycle_request;
static char cycle_expected[80];
static const char *cycle_motor_state = "UNKNOWN", *cycle_error = "NONE";
static double cycle_reported;
static double cycle_idle_sent;
static int cycle_home_required = 1, cycle_rear_confirmed, cycle_idle_confirmed;
static void cycle_recover(int sock);

static void cycle_report(int sock, double now)
{
    static const char *states[] = {"IDLE", "MOVE_PREP", "FRONT_WAIT", "STOP_APPLY",
        "HOLD", "REAR_WAIT", "MOVE_APPLY", "DONE", "ERROR",
        "RECOVER", "RECOVERY_WAIT", "HOME"};
    int remaining = 0;
    if(cycle_state == C_HOLD || cycle_state == C_STOP)
        remaining = (int)((cycle_hold_until-now)*1000);
    if(remaining < 0) remaining = 0;
    char message[LINE_SIZE];
    snprintf(message, sizeof(message), "[JETSON]CYCLE@%08x@%s@%s@%d@%s\n",
        cycle_request, states[cycle_state], cycle_motor_state, remaining, cycle_error);
    send_all(sock, message);
}

static void cycle_phase(int sock, const char *phase, int next)
{
    char message[LINE_SIZE];
    ++cycle_request;
    snprintf(message, sizeof(message), "[JETSON]PHASE@%s@%08x\n", phase, cycle_request);
    snprintf(cycle_expected, sizeof(cycle_expected), "PHASE@%s@%08x@OK", phase, cycle_request);
    send_all(sock, message);
    cycle_state = next;
    cycle_deadline = monotonic_seconds() + cycle_timeout;
    if(!strcmp(phase,"IDLE")) cycle_idle_sent = monotonic_seconds();
    printf("CYCLE TX %s", message);
    cycle_report(sock,monotonic_seconds());
}

static void cycle_abort(int sock, const char *reason)
{
    cycle_error = !strcmp(reason,"STM stop") ? "STM_STOP" :
        !strcmp(reason,"operator stop") ? "OPERATOR_STOP" :
        !strcmp(reason,"completion timeout") ? "ACK_TIMEOUT" :
        !strcmp(reason,"Jetson heartbeat lost") ? "HEARTBEAT_LOST" : "JETSON_ERROR";
    printf("CYCLE ABORT %s; returning doll to rear\n", reason);
    if(cycle_state == C_RECOVER || cycle_state == C_RECOVERY_WAIT) return;
    cycle_recover(sock);
}

static void cycle_start(int sock)
{
    if(cycle_home_required) {
        puts("CYCLE START_BLOCKED rear recovery required; press start again after HOME");
        if(cycle_state != C_RECOVER && cycle_state != C_RECOVERY_WAIT) cycle_recover(sock);
        return;
    }
    if(cycle_state != C_IDLE && cycle_state != C_DONE && cycle_state != C_ERROR && cycle_state != C_HOME) {
        puts("CYCLE IGNORE start while active"); return;
    }
    if(!cycle_ready || monotonic_seconds()-cycle_ready > 3) {
        puts("CYCLE NOT_READY Jetson fresh inference required"); return;
    }
    printf("CYCLE START hold=%.2fs timeout=%.2fs\n", cycle_hold, cycle_timeout);
    cycle_error = "NONE";
    cycle_phase(sock, "MOVE", C_MOVE);
}

static void cycle_motor(int sock, const char *direction, int next)
{
    char message[LINE_SIZE];
    snprintf(message, sizeof(message), "[STM]MOTOR@%s\n", direction);
    send_all(sock, message);
    cycle_motor_state = !strcmp(direction,"FRONT") ? "FRONT_WAIT" : "REAR_WAIT";
    cycle_state = next;
    cycle_deadline = monotonic_seconds() + cycle_timeout;
    printf("CYCLE TX %s", message);
    cycle_report(sock,monotonic_seconds());
}

static void cycle_recover(int sock)
{
    cycle_home_required = 1;
    cycle_rear_confirmed = cycle_idle_confirmed = 0;
    cycle_phase(sock, "IDLE", C_RECOVER);
    cycle_motor(sock, "REAR", C_RECOVER);
    puts("CYCLE RECOVERY waiting for STM REAR OK and Jetson IDLE OK");
}

static void cycle_home(int sock)
{
    if(!cycle_rear_confirmed || !cycle_idle_confirmed) return;
    cycle_home_required = 0;
    cycle_error = "NONE";
    cycle_state = C_HOME;
    puts("CYCLE HOME rear recovery confirmed; next start enabled");
    cycle_report(sock,monotonic_seconds());
}

static int cycle_line(int sock, const char *sender, const char *payload)
{
    if(!cycle_enabled) return 0;
    if(!strcmp(sender, "JETSON") && !strcmp(payload, "TRIAL@READY")) {
        cycle_ready = monotonic_seconds();
        /* Startup IDLE may precede the bridge login. Retry it without extending motor timeout. */
        if((cycle_state == C_RECOVER || cycle_state == C_RECOVERY_WAIT) &&
           !cycle_idle_confirmed && cycle_ready-cycle_idle_sent >= 1) {
            double deadline = cycle_deadline;
            cycle_phase(sock,"IDLE",cycle_state);
            cycle_deadline = deadline;
        }
        return 1;
    }
    if(!strcmp(sender, "JETSON") && !strcmp(payload, "TRIAL@ERROR")) {
        cycle_ready = 0;
        if(cycle_state >= C_MOVE && cycle_state <= C_RESUME) cycle_abort(sock, "Jetson unavailable");
        return 1;
    }
    if(!strcmp(sender, "STM") && !strcmp(payload, "START")) { cycle_start(sock); return 1; }
    if(!strcmp(sender, "STM") && !strcmp(payload, "STOP")) { cycle_abort(sock, "STM stop"); return 1; }
    if(!strcmp(sender, "JETSON") && !strcmp(payload, cycle_expected)) {
        if(cycle_state == C_RECOVER || cycle_state == C_RECOVERY_WAIT) {
            cycle_idle_confirmed = 1; cycle_home(sock); return 1;
        }
        if(cycle_state == C_MOVE) cycle_motor(sock, "FRONT", C_FRONT);
        else if(cycle_state == C_STOP) { cycle_state = C_HOLD; puts("CYCLE STOP confirmed by Jetson"); cycle_report(sock,monotonic_seconds()); }
        else if(cycle_state == C_RESUME) { cycle_state = C_DONE; puts("CYCLE DONE movement allowed; one cycle complete"); cycle_report(sock,monotonic_seconds()); }
        return 1;
    }
    if(!strcmp(sender, "STM") && !strcmp(payload, "MOTOR@FRONT@OK") && cycle_state == C_FRONT) {
        cycle_motor_state = "FRONT_OK";
        cycle_hold_until = monotonic_seconds() + cycle_hold;
        cycle_phase(sock, "STOP", C_STOP); return 1;
    }
    if(!strcmp(sender, "STM") && !strcmp(payload, "MOTOR@REAR@OK") && cycle_state == C_REAR) {
        cycle_motor_state = "REAR_OK";
        cycle_phase(sock, "MOVE", C_RESUME); return 1;
    }
    if(!strcmp(sender,"STM") && !strcmp(payload,"MOTOR@REAR@OK") &&
       (cycle_state == C_RECOVER || cycle_state == C_RECOVERY_WAIT)) {
        cycle_motor_state = "REAR_OK";
        cycle_rear_confirmed = 1; cycle_home(sock);
        cycle_report(sock,monotonic_seconds()); return 1;
    }
    return 0;
}

static void cycle_tick(int sock)
{
    if(!cycle_enabled) return;
    double now = monotonic_seconds();
    if(now-cycle_ping >= 1) { send_all(sock,"[JETSON]TRIAL@PING\n"); cycle_ping=now; }
    if(now-cycle_reported >= .5) { cycle_report(sock,now); cycle_reported=now; }
    if(cycle_state == C_RECOVER && now >= cycle_deadline) {
        cycle_state = C_RECOVERY_WAIT; cycle_error = "RECOVERY_TIMEOUT";
        cycle_deadline = now+5;
        puts("CYCLE RECOVERY_TIMEOUT start blocked; retry in 5 seconds");
        cycle_report(sock,now); return;
    }
    if(cycle_state == C_RECOVERY_WAIT && now >= cycle_deadline) {
        cycle_recover(sock); return;
    }
    if(cycle_state < C_MOVE || cycle_state > C_RESUME) return;
    if(now-cycle_ready > 3) { cycle_abort(sock, "Jetson heartbeat lost"); return; }
    if(cycle_state == C_HOLD) {
        if(now >= cycle_hold_until) cycle_motor(sock, "REAR", C_REAR);
    } else if(now >= cycle_deadline) cycle_abort(sock, "completion timeout");
}
