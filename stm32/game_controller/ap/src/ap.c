#include "ap.h"
#include "esp01.h"
#include "server_parser.h"
#include "button.h"
#include "servo.h"
#include "led.h"
#include <stdio.h>

static uint32_t last_1sec_tick = 0;
static uint32_t sec_count = 0;

void ap_init(void)
{
    printf("Start main() - wifi\r\n");

    // 1. 버튼 초기화 (PB4, PB5)
    button_init();

    // 2. 서보모터 초기화 (TIM3 CH1, PA6, 초기 각도 0도 대기)
    servo_init();

    // 3. RGB LED 초기화 (TIM1 PWM, 초기 색상: GREEN)
    rgb_led_init();

    // 4. LCD 및 서버 파서 초기화 (전원 인가 시 "게임 대기중" 화면 표시)
    server_parser_init();

    // 4. UART2 디버그 수신 시작 및 ESP01 Wi-Fi 초기화
    drv_uart_init();
    if (drv_esp_init() != 0)
    {
        printf("Esp response error\r\n");
    }

    // 5. Wi-Fi AP 접속 및 TCP 서버 연결/로그인
    AiotClient_Init();
}

void ap_loop(void)
{
    // 1. 서버 수신 버퍼 파싱 및 이벤트 처리 (esp_event, START 5분 카운트다운, MOTOR@FRONT 등)
    server_parser_loop();

    // 2. 버튼 2개 감지 (채터링 방지, 상승 에지 감지)
    button_loop();

    // 3. 서보모터 FSM 처리 ([STM]MOTOR@FRONT -> 180도 회전 -> [PI]MOTOR@OK & RED -> 2~5초 랜덤 -> 0도 복귀 -> [PI]MOTOR@REAR & GREEN)
    servo_loop();

    // 4. RGB LED 루프
    rgb_led_loop();

    // 4. PC 터미널(USART2) 디버그 메시지 수신 처리 (시리얼 터미널에서도 [STM]START 등 테스트 가능)
    if (rx2Flag)
    {
        printf("recv2 : %s\r\n", (char *)rx2Data);
        if (rx2Data[0] == '[')
        {
            server_parser_esp_event((char *)rx2Data);
        }
        rx2Flag = 0;
    }

    // 5. 1초 주기 타이머 및 10초 주기 서버 상태 점검 / 재연결
    uint32_t current_tick = HAL_GetTick();
    if (current_tick - last_1sec_tick >= 1000)
    {
        last_1sec_tick = current_tick;
        sec_count++;

        // 10초마다 서버 연결 상태 확인 후 끊김 발생 시 재접속
        if ((sec_count % 10) == 0)
        {
            if (esp_get_status() != 0)
            {
                printf("server connecting ...\r\n");
                esp_client_conn();
            }
        }
    }
}
