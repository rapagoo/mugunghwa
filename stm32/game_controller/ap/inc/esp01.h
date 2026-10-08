//서울기술교육센터 AIOT & Embedded System
//2024-04-16 By KSH


#ifndef __ESP_H__
#define __ESP_H__

#include "stm32f4xx_hal.h"
#include <stdbool.h>

#define MAX_ESP_RX_BUFFER      1024
#define MAX_ESP_COMMAND_LEN    64
#define MAX_ESP_CLIENT_NUM     10

#define SSID "YOUR_WIFI_SSID"
#define PASS "YOUR_WIFI_PASSWORD"
#define LOGID "STM"
#define PASSWD "PASSWD"
#define DST_IP "192.168.0.100"
#define DST_PORT 5000

typedef struct _cb_data_t
{
    uint8_t buf[MAX_ESP_RX_BUFFER];
    uint16_t length;
}cb_data_t;

extern cb_data_t cb_data;
extern volatile unsigned char rx2Flag;

extern volatile char rx2Data[50];
extern uint8_t cdata;

int drv_esp_init(void);
int drv_esp_test_command(void);
void AiotClient_Init(void);
int esp_client_conn(void);
void esp_send_data(char *data);
int esp_get_status(void);

//==================uart3=========================
#define MAX_UART_RX_BUFFER      512
#define MAX_UART_COMMAND_LEN    64

int drv_uart_init(void);
int drv_uart_rx_buffer(uint8_t *buf, uint16_t size);
int drv_uart_tx_buffer(uint8_t *buf, uint16_t size);
//==================uart3=========================

// 프로젝트 상위 모듈(ap.c, server_parser.c) 연동 함수
bool esp01_init(UART_HandleTypeDef *huart);
bool esp01_send_string(const char *str);
bool esp01_get_packet(char *out_buf, uint16_t max_len);
void esp01_uart_rx_callback(UART_HandleTypeDef *huart);

#endif
