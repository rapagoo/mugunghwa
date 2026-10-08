#ifndef __BUTTON_H
#define __BUTTON_H

#include "main.h"
#include <stdbool.h>

/*
 * 버튼 1 (START): PB4 (Nucleo CN10 pin 27, Arduino D5) - 하드웨어 풀다운 회로 (누르면 1)
 * 버튼 2 (STOP) : PB5 (Nucleo CN10 pin 29, Arduino D4) - 하드웨어 풀다운 회로 (누르면 1)
 */

#ifndef BTN1_PIN
#define BTN1_PIN            GPIO_PIN_4
#define BTN1_GPIO_PORT      GPIOB
#endif

#ifndef BTN2_PIN
#define BTN2_PIN            GPIO_PIN_5
#define BTN2_GPIO_PORT      GPIOB
#endif

/**
 * @brief 2개 버튼 GPIO 핀 초기화
 */
void button_init(void);

/**
 * @brief 주기적 루프에서 채터링 방지 및 상태변화 순간(상승 에지) 감지 후 서버 전송
 */
void button_loop(void);

/**
 * @brief 1번 버튼 클릭 여부 확인 (RESET)
 */
bool button1_is_clicked(void);

/**
 * @brief 2번 버튼 클릭 여부 확인 (STOP)
 */
bool button2_is_clicked(void);

#endif /* __BUTTON_H */
