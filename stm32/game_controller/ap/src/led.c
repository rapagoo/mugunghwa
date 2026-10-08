#include "led.h"
#include <stdio.h>

extern TIM_HandleTypeDef htim1;

static rgb_color_t s_current_color = RGB_COLOR_OFF;

/* --------------------------------------------------------------------------
 * 온보드 LD2 (PA5) 제어 함수 (기존 코드 유지)
 * -------------------------------------------------------------------------- */
void led_init(void)
{
    HAL_GPIO_WritePin(LD2_GPIO_Port, LD2_Pin, GPIO_PIN_RESET);
}

void led_toggle(void)
{
    HAL_GPIO_TogglePin(LD2_GPIO_Port, LD2_Pin);
}

/* --------------------------------------------------------------------------
 * RGB LED PWM 제어 함수 (TIM1 CH1: PA8[R], CH2: PA9[G], CH3: PA10[B])
 * -------------------------------------------------------------------------- */
void rgb_led_init(void)
{
    // TIM1 및 GPIOA 클럭 확실하게 활성화
    __HAL_RCC_TIM1_CLK_ENABLE();
    __HAL_RCC_GPIOA_CLK_ENABLE();

    // TIM1 각 채널 PWM 출력 시작
    HAL_StatusTypeDef s1 = HAL_TIM_PWM_Start(&htim1, TIM_CHANNEL_1); // PA8  (D7) - RED
    HAL_StatusTypeDef s2 = HAL_TIM_PWM_Start(&htim1, TIM_CHANNEL_2); // PA9  (D8) - GREEN
    HAL_StatusTypeDef s3 = HAL_TIM_PWM_Start(&htim1, TIM_CHANNEL_3); // PA10 (D2) - BLUE

    // 고급 타이머(TIM1) Main Output Enable 및 카운터 동작 인에이블
    __HAL_TIM_MOE_ENABLE(&htim1);
    __HAL_TIM_ENABLE(&htim1);

    // 초기 상태: 전원 켜졌을 때 초기 LED 색상은 황색(YELLOW - 게임 대기/준비 상태)으로 설정
    rgb_led_set_color(RGB_COLOR_YELLOW);
    s_current_color = RGB_COLOR_YELLOW;

    printf("[RGB LED] Initialized on PA8(D7), PA9(D8), PA10(D2) (PWM Start status: %d,%d,%d)\r\n", s1, s2, s3);
    printf("[RGB LED] TIM1 CR1=0x%04lX, BDTR=0x%08lX, CCER=0x%04lX\r\n",
           (unsigned long)TIM1->CR1, (unsigned long)TIM1->BDTR, (unsigned long)TIM1->CCER);
    printf("[RGB LED] Init Color -> YELLOW (게임 대기/준비 상태)\r\n");
}

/**
 * @brief R, G, B 각 색상의 PWM 듀티비를 직접 설정 (0 ~ 1000)
 * @param r Red 채널 듀티비 (0 ~ 1000)
 * @param g Green 채널 듀티비 (0 ~ 1000)
 * @param b Blue 채널 듀티비 (0 ~ 1000)
 */
void rgb_led_set_pwm(uint16_t r, uint16_t g, uint16_t b)
{
    if (r > RGB_PWM_MAX_VALUE) r = RGB_PWM_MAX_VALUE;
    if (g > RGB_PWM_MAX_VALUE) g = RGB_PWM_MAX_VALUE;
    if (b > RGB_PWM_MAX_VALUE) b = RGB_PWM_MAX_VALUE;

#if (RGB_LED_COMMON_ANODE == 1)
    // Common Anode는 LOW 신호에서 켜지므로 듀티 반전
    r = RGB_PWM_MAX_VALUE - r;
    g = RGB_PWM_MAX_VALUE - g;
    b = RGB_PWM_MAX_VALUE - b;
#endif

    TIM1->CCR1 = r; // PA8  (TIM1_CH1 - RED)
    TIM1->CCR2 = g; // PA9  (TIM1_CH2 - GREEN)
    TIM1->CCR3 = b; // PA10 (TIM1_CH3 - BLUE)
}

/**
 * @brief 사전 정의된 색상으로 설정
 */
void rgb_led_set_color(rgb_color_t color)
{
    s_current_color = color;

    switch (color)
    {
        case RGB_COLOR_RED:
            // 적색: R 100%, G 0%, B 0%
            rgb_led_set_pwm(1000, 0, 0);
            break;

        case RGB_COLOR_YELLOW:
            // 순수 옐로우 (개나리색): R: 1000, G: 220 ~ 300, B: 0 (약 4:1 ~ 3.5:1)
            rgb_led_set_pwm(RGB_YELLOW_R_DUTY, RGB_YELLOW_G_DUTY, RGB_YELLOW_B_DUTY);
            break;

        case RGB_COLOR_GREEN:
            // 녹색: R 0%, G 100%, B 0%
            rgb_led_set_pwm(0, 1000, 0);
            break;

        case RGB_COLOR_BLUE:
            rgb_led_set_pwm(0, 0, 1000);
            break;

        case RGB_COLOR_CYAN:
            rgb_led_set_pwm(0, 800, 1000);
            break;

        case RGB_COLOR_MAGENTA:
            rgb_led_set_pwm(1000, 0, 800);
            break;

        case RGB_COLOR_WHITE:
            rgb_led_set_pwm(1000, 800, 800);
            break;

        case RGB_COLOR_OFF:
        default:
            rgb_led_set_pwm(0, 0, 0);
            break;
    }
}

rgb_color_t rgb_led_get_color(void)
{
    return s_current_color;
}

/**
 * @brief LED 주기 루프 함수 (현재 모터 및 서버 이벤트 FSM 연동으로 동작)
 */
void rgb_led_loop(void)
{
    // 이벤트 기반 제어로 동작 (서보모터 상태 및 서버 수신 이벤트에 따라 변경)
}
