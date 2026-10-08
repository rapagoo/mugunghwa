#ifndef LCD1602_H_
#define LCD1602_H_

#include "main.h"
#include <stdint.h>
#include <stdbool.h>

// I2C GPIO 핀 정의 (Nucleo-F411RE의 Arduino D15=PB8(SCL), D14=PB9(SDA))
#define LCD_I2C_GPIO_PORT       GPIOB
#define LCD_I2C_SCL_PIN         GPIO_PIN_8
#define LCD_I2C_SDA_PIN         GPIO_PIN_9

// I2C 1602 기본 주소 (0x27 또는 0x3F) - 7비트 주소
#define LCD_I2C_DEFAULT_ADDR    0x27
#define LCD_I2C_ALT_ADDR        0x3F

/**
 * @brief I2C 1602 LCD 초기화
 * @return true: 성공 (LCD 감지됨), false: 실패
 */
bool lcd_init(void);

/**
 * @brief 화면 전체 지우기
 */
void lcd_clear(void);

/**
 * @brief 커서 위치 이동
 * @param col 열 (0 ~ 15)
 * @param row 행 (0 ~ 1)
 */
void lcd_set_cursor(uint8_t col, uint8_t row);

/**
 * @brief 문자열 출력
 * @param str 출력할 문자열
 */
void lcd_print(const char *str);

/**
 * @brief 백라이트 ON / OFF
 * @param on true: 켜기, false: 끄기
 */
void lcd_backlight(bool on);

#endif /* LCD1602_H_ */
