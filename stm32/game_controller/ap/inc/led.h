#ifndef LED_H_
#define LED_H_

#include "main.h"
#include <stdint.h>
#include <stdbool.h>

/* ==========================================================================
 * RGB LED 설정 (Common Cathode vs Common Anode)
 * --------------------------------------------------------------------------
 * 0: Common Cathode (GND 공통 핀 사용 모듈 - 신호 HIGH일 때 켜짐) [기본값]
 * 1: Common Anode   (VCC 3.3V 공통 핀 사용 모듈 - 신호 LOW일 때 켜짐)
 * ========================================================================== */
#define RGB_LED_COMMON_ANODE      0

// PWM 주기 최대값 (TIM1 Period = 999 기준, 분해능 0 ~ 1000)
#define RGB_PWM_MAX_VALUE         1000

/* ==========================================================================
 * 순수 옐로우 (개나리색) 색상 비율 설정
 * - R: 1000 (255)
 * - G: 220 ~ 300 (55 ~ 75) -> 기본값 260 (약 3.8:1 개나리색 비율)
 * - B: 0
 * ========================================================================== */
#define RGB_YELLOW_R_DUTY         1000
#define RGB_YELLOW_G_DUTY         260   // 220 ~ 300 범위로 미세 조절 가능
#define RGB_YELLOW_B_DUTY         0

// 색상 정의 열거형
typedef enum {
    RGB_COLOR_OFF = 0,
    RGB_COLOR_RED,
    RGB_COLOR_YELLOW,
    RGB_COLOR_GREEN,
    RGB_COLOR_BLUE,
    RGB_COLOR_CYAN,
    RGB_COLOR_MAGENTA,
    RGB_COLOR_WHITE
} rgb_color_t;

/* 기존 온보드 LD2(PA5) 관련 함수 */
void led_init(void);
void led_toggle(void);

/* RGB LED PWM 제어 함수 */
void rgb_led_init(void);
void rgb_led_set_pwm(uint16_t r, uint16_t g, uint16_t b);
void rgb_led_set_color(rgb_color_t color);
rgb_color_t rgb_led_get_color(void);

/* 1초 주기 순환 제어 함수 (적색 -> 황색 -> 녹색) */
void rgb_led_loop(void);

#endif /* LED_H_ */
