#include "servo.h"
#include "led.h"
#include "esp01.h"
#include <stdio.h>
#include <stdbool.h>

extern TIM_HandleTypeDef htim3;

static volatile uint8_t current_angle = 0;
static volatile uint8_t s_target_angle = 0;
static volatile uint32_t s_step_delay_ms = SERVO_STEP_DELAY_MS;
static volatile bool s_servo_initialized = false;
static volatile servo_state_t s_servo_state = SERVO_STATE_IDLE_REAR;

static volatile uint16_t s_step_cnt = 0;
static volatile uint32_t s_move_start_tick = 0;

/**
 * @brief 서보모터 초기화 (0도 설정 및 대기 상태)
 */
void servo_init(void)
{
    // TIM3 Channel 1 (PA6) PWM 글리치 방지를 위한 Preload 활성화
    __HAL_TIM_ENABLE_OCxPRELOAD(&htim3, TIM_CHANNEL_1);

    // TIM3 Channel 1 (PA6) PWM 시작
    HAL_TIM_PWM_Start(&htim3, TIM_CHANNEL_1);

    // 초기 각도 0도로 이동
    servo_set_angle(0);
    s_target_angle = 0;
    current_angle = 0;
    s_servo_state = SERVO_STATE_IDLE_REAR;

    s_servo_initialized = true;

#if SERVO_DIRECT_MODE
    printf("[SERVO] Initialized: 0 deg (DIRECT INSTANT 180 MODE)\r\n");
#else
    printf("[SERVO] Initialized: 0 deg (STEP MODE %lums)\r\n", (unsigned long)s_step_delay_ms);
#endif
}

/**
 * @brief 서버로부터 [STM]MOTOR@FRONT 수신 시 180도 회전 시퀀스 시작
 * 이미 180도에 도달해 있다면 즉시 [PI]MOTOR@FRONT@OK를 송신하고 LED RED 유지
 */
void servo_trigger_front(void)
{
    if (!s_servo_initialized)
    {
        return;
    }

    // 1. 이미 180도에 도달해 있는 경우 -> 즉시 [PI]MOTOR@FRONT@OK 응답 송신
    if (s_servo_state == SERVO_STATE_HOLD_AT_FRONT || current_angle >= 180)
    {
        esp_send_data("[PI]MOTOR@FRONT@OK\n");
        rgb_led_set_color(RGB_COLOR_RED);
        s_servo_state = SERVO_STATE_HOLD_AT_FRONT;
        s_target_angle = 180;

        printf("[SERVO] Already at 180 deg -> Immediate [PI]MOTOR@FRONT@OK, LED: RED\r\n");
    }
    // 2. 0도 대기 상태 또는 복귀 중일 때 -> 180도 회전 시작 및 LED YELLOW 점등
    else
    {
        s_target_angle = 180;
        s_servo_state = SERVO_STATE_MOVING_TO_FRONT;

        // 회전 중 LED를 YELLOW로 점등
        rgb_led_set_color(RGB_COLOR_YELLOW);

#if SERVO_DIRECT_MODE
        // [테스트 모드] 한 번에 즉시 180도로 PWM 펄스 출력
        servo_set_angle(180);
        s_move_start_tick = HAL_GetTick();
        printf("[SERVO] DIRECT MODE: Instant 180 deg PWM output applied! (Waiting %dms)\r\n", SERVO_DIRECT_MOVE_MS);
#else
        printf("[SERVO] STEP MODE: Command [STM]MOTOR@FRONT -> Moving to 180 deg, LED: YELLOW\r\n");
#endif
    }
}

/**
 * @brief 서버로부터 [STM]MOTOR@REAR 수신 시 0도 복귀 회전 시퀀스 시작
 * 이미 0도에 도달해 있다면 즉시 [PI]MOTOR@REAR@OK를 송신하고 LED GREEN 유지
 */
void servo_trigger_rear(void)
{
    if (!s_servo_initialized)
    {
        return;
    }

    // 1. 이미 0도에 도달해 있는 경우 -> 즉시 [PI]MOTOR@REAR@OK 응답 송신
    if (s_servo_state == SERVO_STATE_IDLE_REAR || current_angle <= 0)
    {
        esp_send_data("[PI]MOTOR@REAR@OK\n");
        rgb_led_set_color(RGB_COLOR_GREEN);
        s_servo_state = SERVO_STATE_IDLE_REAR;
        s_target_angle = 0;

        printf("[SERVO] Already at 0 deg -> Immediate [PI]MOTOR@REAR@OK, LED: GREEN\r\n");
    }
    // 2. 180도 유지 상태 또는 전진 중일 때 -> 0도 복귀 회전 시작 및 LED YELLOW 점등
    else
    {
        s_target_angle = 0;
        s_servo_state = SERVO_STATE_MOVING_TO_REAR;

        // 회전 중 LED를 YELLOW로 점등
        rgb_led_set_color(RGB_COLOR_YELLOW);

#if SERVO_DIRECT_MODE
        // [테스트 모드] 한 번에 즉시 0도로 PWM 펄스 출력
        servo_set_angle(0);
        s_move_start_tick = HAL_GetTick();
        printf("[SERVO] DIRECT MODE: Instant 0 deg PWM output applied! (Waiting %dms)\r\n", SERVO_DIRECT_MOVE_MS);
#else
        printf("[SERVO] STEP MODE: Command [STM]MOTOR@REAR -> Returning to 0 deg, LED: YELLOW\r\n");
#endif
    }
}

/**
 * @brief 서보모터를 지정한 각도(0~180도)로 PWM 펄스 즉시 반영
 */
void servo_set_angle(uint8_t angle)
{
    if (angle > SERVO_MAX_ANGLE)
    {
        angle = SERVO_MAX_ANGLE;
    }

    current_angle = angle;

    // 0도 -> SERVO_MIN_PULSE_US (500us), 180도 -> SERVO_MAX_PULSE_US (2500us)
    uint32_t pulse = SERVO_MIN_PULSE_US + 
                     ((uint32_t)angle * (SERVO_MAX_PULSE_US - SERVO_MIN_PULSE_US)) / SERVO_MAX_ANGLE;

    TIM3->CCR1 = pulse;
}

uint8_t servo_get_angle(void)
{
    return current_angle;
}

servo_state_t servo_get_state(void)
{
    return s_servo_state;
}

void servo_set_speed_delay(uint32_t delay_ms)
{
    s_step_delay_ms = delay_ms;
}

/**
 * @brief 서보모터 각도 0도 리셋 및 초기 상태 복귀
 */
void servo_reset(void)
{
    s_target_angle = 0;
    current_angle = 0;
    servo_set_angle(0);
    s_servo_state = SERVO_STATE_IDLE_REAR;
    s_step_cnt = 0;

    printf("[SERVO] Reset to 0 deg, State: IDLE_REAR\r\n");
}

/**
 * @brief 하드웨어 타이머(SysTick 1ms 인터럽트)에서 호출: 1도씩 부드럽게 각도 이동 (스텝 모드 시)
 */
void servo_tick_1ms(void)
{
    if (!s_servo_initialized)
    {
        return;
    }

#if !SERVO_DIRECT_MODE
    s_step_cnt++;
    if (s_step_cnt >= s_step_delay_ms)
    {
        s_step_cnt = 0;

        if (current_angle < s_target_angle)
        {
            current_angle++;
            uint32_t pulse = SERVO_MIN_PULSE_US + 
                             ((uint32_t)current_angle * (SERVO_MAX_PULSE_US - SERVO_MIN_PULSE_US)) / SERVO_MAX_ANGLE;
            TIM3->CCR1 = pulse;
        }
        else if (current_angle > s_target_angle)
        {
            current_angle--;
            uint32_t pulse = SERVO_MIN_PULSE_US + 
                             ((uint32_t)current_angle * (SERVO_MAX_PULSE_US - SERVO_MIN_PULSE_US)) / SERVO_MAX_ANGLE;
            TIM3->CCR1 = pulse;
        }
    }
#endif
}

/**
 * @brief 메인 루프에서 실행되는 서보 FSM 상태 전이 및 Wi-Fi 패킷 송신 처리
 */
void servo_loop(void)
{
    if (!s_servo_initialized)
    {
        return;
    }

    switch (s_servo_state)
    {
        case SERVO_STATE_MOVING_TO_FRONT:
#if SERVO_DIRECT_MODE
            // 한 번에 이동 시 물리적 회전 시간(SERVO_DIRECT_MOVE_MS) 대기 후 완료 처리
            if (HAL_GetTick() - s_move_start_tick >= SERVO_DIRECT_MOVE_MS)
            {
                esp_send_data("[PI]MOTOR@FRONT@OK\n");
                rgb_led_set_color(RGB_COLOR_RED);
                s_servo_state = SERVO_STATE_HOLD_AT_FRONT;

                printf("[SERVO] 180 deg Reached (DIRECT) -> Sent [PI]MOTOR@FRONT@OK, LED: RED\r\n");
            }
#else
            // 180도 회전 완료 감지 (스텝 모드)
            if (current_angle >= 180)
            {
                esp_send_data("[PI]MOTOR@FRONT@OK\n");
                rgb_led_set_color(RGB_COLOR_RED);
                s_servo_state = SERVO_STATE_HOLD_AT_FRONT;

                printf("[SERVO] 180 deg Reached -> Sent [PI]MOTOR@FRONT@OK, LED: RED (Waiting for MOTOR@REAR)\r\n");
            }
#endif
            break;

        case SERVO_STATE_HOLD_AT_FRONT:
            // 서버의 [STM]MOTOR@REAR 명령이 올 때까지 180도 및 RED 유지
            break;

        case SERVO_STATE_MOVING_TO_REAR:
#if SERVO_DIRECT_MODE
            // 한 번에 복귀 시 물리적 복귀 시간(SERVO_DIRECT_MOVE_MS) 대기 후 완료 처리
            if (HAL_GetTick() - s_move_start_tick >= SERVO_DIRECT_MOVE_MS)
            {
                esp_send_data("[PI]MOTOR@REAR@OK\n");
                rgb_led_set_color(RGB_COLOR_GREEN);
                s_servo_state = SERVO_STATE_IDLE_REAR;

                printf("[SERVO] 0 deg Reached (DIRECT) -> Sent [PI]MOTOR@REAR@OK, LED: GREEN\r\n");
            }
#else
            // 0도 복귀 회전 완료 감지 (스텝 모드)
            if (current_angle <= 0)
            {
                esp_send_data("[PI]MOTOR@REAR@OK\n");
                rgb_led_set_color(RGB_COLOR_GREEN);
                s_servo_state = SERVO_STATE_IDLE_REAR;

                printf("[SERVO] 0 deg Reached -> Sent [PI]MOTOR@REAR@OK, LED: GREEN (Standby)\r\n");
            }
#endif
            break;

        case SERVO_STATE_IDLE_REAR:
        default:
            // 대기 중
            break;
    }
}
