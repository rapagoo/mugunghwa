#include "server_parser.h"
#include "lcd1602.h"
#include "esp01.h"
#include "servo.h"
#include "led.h"
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

#define ARR_CNT 8
#define PACKET_BUF_SIZE 128

// 게임 및 시간 제어 변수
static bool s_game_active = false;          // 게임 진행 여부
static uint32_t s_remaining_seconds = 0;    // PI에서 수신한 남은 초
static bool s_time_received = false;        // PI로부터 시간을 수신했는지 여부

// 인원수 저장 버퍼 (2자리 + NULL: -- 또는 00~99)
static char s_total_str[3] = "--";
static char s_pass_str[3]  = "--";
static char s_fail_str[3]  = "--";

/**
 * @brief 인원수 문자열 포맷팅
 * - 들어온 사람 숫자가 없거나('-') 비어 있으면: "--"로 표시
 * - 한 자릿수(0~9) 또는 두 자릿수가 들어오면: 십의 자리를 0으로 채워 "00", "01", "09", "10" 등으로 표시
 */
static void format_count_value(char *dst, size_t dst_size, const char *src)
{
    if (src == NULL || src[0] == '\0' || src[0] == '-')
    {
        snprintf(dst, dst_size, "--");
    }
    else
    {
        int val = atoi(src);
        snprintf(dst, dst_size, "%02d", val);
    }
}

/**
 * @brief 시간 (0~6열) 화면 출력 함수: "T:MM:SS" (PI에서 보내온 초만 분,초로 변환하여 표시)
 */
static void print_time_display(void)
{
    char time_buf[16];
    if (s_time_received)
    {
        uint32_t min = s_remaining_seconds / 60;
        uint32_t sec = s_remaining_seconds % 60;
        snprintf(time_buf, sizeof(time_buf), "T:%02lu:%02lu", (unsigned long)min, (unsigned long)sec);
    }
    else
    {
        snprintf(time_buf, sizeof(time_buf), "T:--:--");
    }

    lcd_set_cursor(0, 0);
    lcd_print(time_buf);
}

/**
 * @brief "게임 대기중" 화면 표시 (전원 켜졌을 때 / 리셋 시 호출)
 */
void server_parser_show_waiting_screen(void)
{
    s_game_active = false;
    s_time_received = false;
    s_remaining_seconds = 0;

    strcpy(s_total_str, "--");
    strcpy(s_pass_str,  "--");
    strcpy(s_fail_str,  "--");

    lcd_clear();
    lcd_set_cursor(0, 0);
    lcd_print("  GAME WAITING  ");
    lcd_set_cursor(4, 1);
    lcd_print(" READY!  ");

    printf("[LCD] Waiting Screen: GAME WAITING / READY!\r\n");
}

/**
 * @brief 게임 시작 및 화면 표시 ([STM]START 수신 시 호출)
 */
void server_parser_start_game(void)
{
    s_game_active = true;

    // START 수신 시 LED를 녹색(GREEN - 게임 진행/안전 상태)으로 변경
    rgb_led_set_color(RGB_COLOR_GREEN);

    lcd_clear();

    // 1행 왼쪽: PI에서 수신된 시간(또는 T:00:00) 표시
    print_time_display();

    // 1행 오른쪽: "TOTAL:00"
    char total_buf[9];
    snprintf(total_buf, sizeof(total_buf), "TOTAL:%s", s_total_str);
    lcd_set_cursor(8, 0);
    lcd_print(total_buf);

    // 2행 전체: "PASS:00  FAIL:00"
    char line2[17];
    snprintf(line2, sizeof(line2), "PASS:%s  FAIL:%s", s_pass_str, s_fail_str);
    lcd_set_cursor(0, 1);
    lcd_print(line2);

    printf("[GAME] Started -> Waiting for PI TIME updates (Local countdown disabled)\r\n");
}

void server_parser_reset_game(void)
{
    server_parser_show_waiting_screen();
}

/**
 * @brief 게임 일시 정지 (STOP 시 호출)
 */
void server_parser_stop_game(void)
{
    printf("[GAME] Stopped\r\n");
}

/**
 * @brief 서버에서 수신된 문자열 파싱 및 이벤트 처리 (esp_event)
 */
void server_parser_esp_event(char *recvBuf)
{
    int i = 0;
    char *pToken;
    char *pArray[ARR_CNT] = {0};

    // 개행 문자 ('\r', '\n') 제거
    size_t len = strlen(recvBuf);
    while (len > 0 && (recvBuf[len - 1] == '\n' || recvBuf[len - 1] == '\r'))
    {
        recvBuf[--len] = '\0';
    }

    printf("\r\n[RECV RAW] %s\r\n", recvBuf);

    // '[' 및 ']', '@' 기준으로 토큰 분리
    // 예: "[STM]MOTOR@FRONT" -> pArray[0]="STM", pArray[1]="MOTOR", pArray[2]="FRONT"
    
    // 예: "[STM]START"       -> pArray[0]="STM", pArray[1]="START"
    // 예: "[STM]STOP"        -> pArray[0]="STM", pArray[1]="STOP"
    // 예: "[STM]COUNT@10@8@2"-> pArray[0]="STM", pArray[1]="COUNT", pArray[2]="10", pArray[3]="8", pArray[4]="2"
    pToken = strtok(recvBuf, "[@]");
    while (pToken != NULL)
    {
        pArray[i] = pToken;
        if (++i >= ARR_CNT)
            break;
        pToken = strtok(NULL, "[@]");
    }

    if (pArray[1] == NULL)
    {
        return;
    }

    // 1. 모터 제어 명령 ([STM]MOTOR@FRONT)
    if (!strcmp(pArray[1], "MOTOR"))
    {
        if (pArray[2] != NULL && !strcmp(pArray[2], "FRONT"))
        {
            // 모터 180도 회전 시작 + LED YELLOW 점등
            // (180도 도달 시 [PI]MOTOR@OK 전송 + LED RED + 2~5초 랜덤 대기 후 0도 복귀 + [PI]MOTOR@REAR 전송 + LED GREEN)
            servo_trigger_front();
        }
        else if (pArray[2] != NULL && !strcmp(pArray[2], "REAR"))
        {
            servo_trigger_rear();
        }
        return;
    }
    // 3. 서버 접속 상태 메시지
    else if (!strncmp(pArray[1], " New conn", 8))
    {
        return;
    }
    else if (!strncmp(pArray[1], " Already log", 8))
    {
        esp_client_conn();
        return;
    }
    // 4. START 명령: 5분 카운트다운 시작 + 모터 0도 리셋 + LED GREEN
    else if (!strcmp(pArray[1], "START"))
    {
        servo_reset();
        server_parser_start_game();
        return;
    }
    // 5. RESET 명령: 게임 대기 화면으로 복귀 + 모터 0도 리셋 + LED YELLOW (대기 상태)
    else if (!strcmp(pArray[1], "RESET"))
    {
        servo_reset();
        rgb_led_set_color(RGB_COLOR_YELLOW);
        server_parser_show_waiting_screen();
        return;
    }
    // 6. STOP 명령: 게임 일시정지 (화면 유지)
    else if (!strcmp(pArray[1], "STOP"))
    {
        server_parser_stop_game();
        printf("[EVENT] STOP -> Game stopped (Screen maintained)\r\n");
        return;
    }
    // 7. COUNT 패킷 ([ID]COUNT@total@pass@fail): 인원수 갱신
    else if (!strcmp(pArray[1], "COUNT"))
    {
        if (pArray[2] != NULL && pArray[3] != NULL && pArray[4] != NULL)
        {
            // 들어온 사람 숫자가 없으면 '--', 숫자가 들어오면 십의 자리를 0으로 채워 항상 2자리(00~99)로 포맷팅
            format_count_value(s_total_str, sizeof(s_total_str), pArray[2]);
            format_count_value(s_pass_str,  sizeof(s_pass_str),  pArray[3]);
            format_count_value(s_fail_str,  sizeof(s_fail_str),  pArray[4]);

            // 게임 화면 표시 중일 때 인원수 화면 업데이트
            if (s_game_active)
            {
                // LCD 1행 오른쪽: "TOTAL:00"
                char total_buf[9];
                snprintf(total_buf, sizeof(total_buf), "TOTAL:%s", s_total_str);
                lcd_set_cursor(8, 0);
                lcd_print(total_buf);

                // LCD 2행 전체: "PASS:00  FAIL:00"
                char line2[17];
                snprintf(line2, sizeof(line2), "PASS:%s  FAIL:%s", s_pass_str, s_fail_str);
                lcd_set_cursor(0, 1);
                lcd_print(line2);
            }

            // PI에게 APPLIED 응답 송신 ([PI]APPLIED@COUNT@전체@통과@탈락)
            char resp_count[64];
            snprintf(resp_count, sizeof(resp_count), "[PI]APPLIED@COUNT@%s@%s@%s\n", pArray[2], pArray[3], pArray[4]);
            esp_send_data(resp_count);

            printf("[EVENT] COUNT -> TOTAL:%s PASS:%s FAIL:%s, Sent: %s", s_total_str, s_pass_str, s_fail_str, resp_count);
            return;
        }
    }
    // 8. TIME 패킷 ([ID]TIME@남은초): PI로부터 남은 시간(초)을 수신하여 LCD 왼쪽 위(0,0)에 분,초 표시
    else if (!strcmp(pArray[1], "TIME"))
    {
        if (pArray[2] != NULL)
        {
            uint32_t sec_val = (uint32_t)strtoul(pArray[2], NULL, 10);
            s_remaining_seconds = sec_val;
            s_time_received = true;

            if (s_game_active)
            {
                print_time_display();
            }
            else
            {
                // 대기 화면 중이라도 TIME 패킷이 수신되면 게임 화면으로 전환하여 시간 표시
                server_parser_start_game();
            }

            // PI에게 APPLIED 응답 송신 ([PI]APPLIED@TIME@남은초)
            char resp_time[64];
            snprintf(resp_time, sizeof(resp_time), "[PI]APPLIED@TIME@%s\n", pArray[2]);
            esp_send_data(resp_time);

            printf("[EVENT] TIME -> Updated from PI: %02lu:%02lu (%lu sec), Sent: %s",
                   (unsigned long)(s_remaining_seconds / 60),
                   (unsigned long)(s_remaining_seconds % 60),
                   (unsigned long)s_remaining_seconds,
                   resp_time);
            return;
        }
    }
}

/**
 * @brief 전원 켜졌을 때 LCD 초기화 및 대기화면 표시
 */
void server_parser_init(void)
{
    // LCD 하드웨어 초기화 및 백라이트 ON
    lcd_init();
    lcd_backlight(true);

    // 전원 켜지면 LCD에 "게임 대기중" 화면 표시
    server_parser_show_waiting_screen();
}

void server_parser_loop(void)
{
    // 1. ESP01 수신 버퍼에서 +IPD 패킷 감지 및 파싱 처리
    if (cb_data.length > 0)
    {
        char *ipd = strstr((char *)cb_data.buf, "+IPD");
        if (ipd != NULL)
        {
            char *bracket = strchr(ipd, '[');
            char *colon   = strchr(ipd, ':');

            if (bracket != NULL)
            {
                int ipd_len = 0;
                if (colon != NULL)
                {
                    if (sscanf(ipd, "+IPD,%*d,%d:", &ipd_len) != 1)
                    {
                        sscanf(ipd, "+IPD,%d:", &ipd_len);
                    }
                }

                char *newline = strpbrk(bracket, "\r\n");

                bool packet_ready = false;
                // 개행문자가 수신되었거나, IPD에 명시된 데이터 바이트 수만큼 모두 수신되었을 때만 완성으로 판정
                if (newline != NULL)
                {
                    packet_ready = true;
                }
                else if (colon != NULL && ipd_len > 0 &&
                         (size_t)((char *)&cb_data.buf[cb_data.length] - (colon + 1)) >= (size_t)ipd_len)
                {
                    packet_ready = true;
                }

                if (packet_ready)
                {
                    char strBuff[MAX_ESP_COMMAND_LEN] = {0};
                    size_t copy_len = 0;

                    if (newline != NULL)
                    {
                        copy_len = (size_t)(newline - bracket);
                    }
                    else if (colon != NULL && ipd_len > 0)
                    {
                        copy_len = (size_t)ipd_len - (size_t)(bracket - (colon + 1));
                    }
                    else
                    {
                        copy_len = strlen(bracket);
                    }

                    if (copy_len >= sizeof(strBuff))
                    {
                        copy_len = sizeof(strBuff) - 1;
                    }

                    strncpy(strBuff, bracket, copy_len);
                    strBuff[copy_len] = '\0';

                    memset(cb_data.buf, 0, sizeof(cb_data.buf));
                    cb_data.length = 0;

                    server_parser_esp_event(strBuff);
                }
            }
        }
        else if (cb_data.length >= MAX_ESP_RX_BUFFER - 32)
        {
            memset(cb_data.buf, 0, sizeof(cb_data.buf));
            cb_data.length = 0;
        }
    }

    // 자체 로컬 카운트다운 비활성화: 시간은 PI로부터 [STM]TIME@초 수신 시에만 분,초로 갱신됩니다.
}
