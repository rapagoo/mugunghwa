#include "lcd1602.h"
#include <string.h>

// PCF8574 제어 비트 정의
#define LCD_RS_BIT         0x01
#define LCD_RW_BIT         0x02
#define LCD_EN_BIT         0x04
#define LCD_BACKLIGHT_BIT  0x08

static uint8_t s_i2c_addr = (LCD_I2C_DEFAULT_ADDR << 1);
static uint8_t s_backlight_val = LCD_BACKLIGHT_BIT;

// 마이크로초 단위 소프트웨어 딜레이 (84MHz F411RE 기준)
static void delay_us(uint32_t us)
{
    // 84MHz 기준 1us = 약 14~18 NOP 루프
    uint32_t count = us * 14;
    while (count--)
    {
        __NOP();
    }
}

// -----------------------------------------------------------------------------
// 소프트웨어 I2C 기본 제어 (Open-Drain Bit-Banging)
// -----------------------------------------------------------------------------
static void i2c_gpio_init(void)
{
    __HAL_RCC_GPIOB_CLK_ENABLE();

    GPIO_InitTypeDef GPIO_InitStruct = {0};
    GPIO_InitStruct.Pin = LCD_I2C_SCL_PIN | LCD_I2C_SDA_PIN;
    GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_OD;
    GPIO_InitStruct.Pull = GPIO_PULLUP;
    GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_HIGH;
    HAL_GPIO_Init(LCD_I2C_GPIO_PORT, &GPIO_InitStruct);

    HAL_GPIO_WritePin(LCD_I2C_GPIO_PORT, LCD_I2C_SCL_PIN, GPIO_PIN_SET);
    HAL_GPIO_WritePin(LCD_I2C_GPIO_PORT, LCD_I2C_SDA_PIN, GPIO_PIN_SET);
}

static inline void scl_high(void) { HAL_GPIO_WritePin(LCD_I2C_GPIO_PORT, LCD_I2C_SCL_PIN, GPIO_PIN_SET); }
static inline void scl_low(void)  { HAL_GPIO_WritePin(LCD_I2C_GPIO_PORT, LCD_I2C_SCL_PIN, GPIO_PIN_RESET); }
static inline void sda_high(void) { HAL_GPIO_WritePin(LCD_I2C_GPIO_PORT, LCD_I2C_SDA_PIN, GPIO_PIN_SET); }
static inline void sda_low(void)  { HAL_GPIO_WritePin(LCD_I2C_GPIO_PORT, LCD_I2C_SDA_PIN, GPIO_PIN_RESET); }
static inline uint8_t sda_read(void) { return HAL_GPIO_ReadPin(LCD_I2C_GPIO_PORT, LCD_I2C_SDA_PIN); }

static void i2c_start(void)
{
    sda_high();
    scl_high();
    delay_us(4);
    sda_low();
    delay_us(4);
    scl_low();
}

static void i2c_stop(void)
{
    sda_low();
    scl_high();
    delay_us(4);
    sda_high();
    delay_us(4);
}

static bool i2c_write_byte(uint8_t data)
{
    for (int i = 0; i < 8; i++)
    {
        if (data & 0x80)
            sda_high();
        else
            sda_low();
        data <<= 1;
        delay_us(2);
        scl_high();
        delay_us(4);
        scl_low();
        delay_us(2);
    }

    // ACK 읽기
    sda_high();
    delay_us(2);
    scl_high();
    delay_us(4);
    bool ack = (sda_read() == GPIO_PIN_RESET);
    scl_low();
    delay_us(2);

    return ack;
}

static bool pcf8574_write(uint8_t data)
{
    i2c_start();
    if (!i2c_write_byte(s_i2c_addr))
    {
        i2c_stop();
        return false;
    }
    i2c_write_byte(data | s_backlight_val);
    i2c_stop();
    return true;
}

// -----------------------------------------------------------------------------
// LCD 저수준 전송 함수 (4비트 모드)
// -----------------------------------------------------------------------------
static void lcd_pulse_enable(uint8_t data)
{
    pcf8574_write(data | LCD_EN_BIT);
    delay_us(5);
    pcf8574_write(data & ~LCD_EN_BIT);
    delay_us(50);
}

static void lcd_write_4bits(uint8_t value)
{
    pcf8574_write(value);
    lcd_pulse_enable(value);
}

static void lcd_send(uint8_t value, uint8_t mode)
{
    uint8_t highnib = (value & 0xF0) | mode;
    uint8_t lownib  = ((value << 4) & 0xF0) | mode;

    lcd_write_4bits(highnib);
    lcd_write_4bits(lownib);
}

static void lcd_command(uint8_t cmd)
{
    lcd_send(cmd, 0);
}

static void lcd_data(uint8_t data)
{
    lcd_send(data, LCD_RS_BIT);
}

// -----------------------------------------------------------------------------
// 공개 API 함수
// -----------------------------------------------------------------------------
bool lcd_init(void)
{
    i2c_gpio_init();
    HAL_Delay(50);

    // 0x27 주소 먼저 확인, 응답 없으면 0x3F로 전환
    s_i2c_addr = (LCD_I2C_DEFAULT_ADDR << 1);
    i2c_start();
    if (!i2c_write_byte(s_i2c_addr))
    {
        i2c_stop();
        s_i2c_addr = (LCD_I2C_ALT_ADDR << 1);
        i2c_start();
        if (!i2c_write_byte(s_i2c_addr))
        {
            i2c_stop();
            // 두 주소 모두 실패하더라도 기본값으로 진행 시도
            s_i2c_addr = (LCD_I2C_DEFAULT_ADDR << 1);
        }
        else
        {
            i2c_stop();
        }
    }
    else
    {
        i2c_stop();
    }

    // HD44780 4비트 초기화 시퀀스
    HAL_Delay(50);
    lcd_write_4bits(0x30);
    HAL_Delay(5);
    lcd_write_4bits(0x30);
    HAL_Delay(1);
    lcd_write_4bits(0x30);
    HAL_Delay(1);
    lcd_write_4bits(0x20); // 4비트 모드 진입
    HAL_Delay(1);

    // 기능 설정 (2줄, 5x8 도트)
    lcd_command(0x28);
    HAL_Delay(1);

    // 디스플레이 ON, 커서 OFF, 블링크 OFF
    lcd_command(0x0C);
    HAL_Delay(1);

    // 화면 지우기
    lcd_clear();
    HAL_Delay(2);

    // 엔트리 모드 설정 (커서 우측 이동)
    lcd_command(0x06);
    HAL_Delay(1);

    return true;
}

void lcd_clear(void)
{
    lcd_command(0x01);
    HAL_Delay(2);
}

void lcd_set_cursor(uint8_t col, uint8_t row)
{
    static const uint8_t row_offsets[] = {0x00, 0x40, 0x14, 0x54};
    if (row > 1) row = 1;
    if (col > 15) col = 15;
    lcd_command(0x80 | (col + row_offsets[row]));
}

void lcd_print(const char *str)
{
    while (*str)
    {
        lcd_data((uint8_t)(*str++));
    }
}

void lcd_backlight(bool on)
{
    s_backlight_val = on ? LCD_BACKLIGHT_BIT : 0;
    pcf8574_write(0);
}
