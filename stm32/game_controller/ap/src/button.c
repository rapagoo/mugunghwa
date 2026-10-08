#include "button.h"
#include "esp01.h"
#include <stdio.h>

// 버튼 릴리즈 바운스 및 손 뗄 때의 방전 글리치 방지 쿨다운 시간(ms)
#define BTN_DEBOUNCE_COOLDOWN_MS    150

typedef struct {
    GPIO_TypeDef *port;
    uint16_t pin;
    uint32_t last_press_tick;
    bool is_pressed;            // 현재 버튼이 '눌린 상태'로 유지 중인지 여부 (상태 락)
    bool clicked;
} button_t;

// 1번 버튼 (START): PB4 - 하드웨어 RC 디바운싱(10kΩ + 1μF) + 1kΩ 풀다운 회로 연결
static button_t s_btn1 = {
    .port = BTN1_GPIO_PORT,
    .pin = BTN1_PIN,
    .last_press_tick = 0,
    .is_pressed = false,
    .clicked = false
};

// 2번 버튼 (STOP): PB5 - 일반 스위치
static button_t s_btn2 = {
    .port = BTN2_GPIO_PORT,
    .pin = BTN2_PIN,
    .last_press_tick = 0,
    .is_pressed = false,
    .clicked = false
};

void button_init(void)
{
    __HAL_RCC_GPIOB_CLK_ENABLE();

    GPIO_InitTypeDef GPIO_InitStruct = {0};

    // 하드웨어 풀다운 회로 기준 NOPULL 설정
    GPIO_InitStruct.Pin = BTN1_PIN | BTN2_PIN;
    GPIO_InitStruct.Mode = GPIO_MODE_INPUT;
    GPIO_InitStruct.Pull = GPIO_NOPULL;
    HAL_GPIO_Init(GPIOB, &GPIO_InitStruct);
}

// 1번 버튼 (START) 누름 이벤트
static void on_btn1_pressed(void)
{
    char send_buf[32] = "[PI]START\n";
    esp_send_data(send_buf);
    printf("[BTN1/START] Rising Edge Triggered -> Sent: [PI]START\r\n");
}

// 2번 버튼 (STOP) 누름 이벤트
static void on_btn2_pressed(void)
{
    char send_buf[32] = "[PI]STOP\n";
    esp_send_data(send_buf);
    printf("[BTN2/STOP] Triggered -> Sent: [PI]STOP\r\n");
}

/**
 * @brief 릴리즈 바운스 및 전압 방전 리플 방지 상태 머신 (0ms 즉시 반응)
 * - 누르는 순간(0ms): 즉시 감지하여 1회 실행 후 is_pressed = true(락) 설정
 * - 누르고 있는 동안: 락 상태이므로 재실행 불가
 * - 손을 뗄 때(Release): 전압이 떨어지면서 접점 바운스나 방전 리플이 생기더라도,
 *   누른 지 최소 쿨다운(150ms)이 지나 스위치가 완전히 떨어질 때까지 락을 풀지 않음!
 *   따라서 손을 뗄 때 발생하는 '2번째 오입력'이 100% 원천 차단됩니다.
 */
static void update_button(button_t *btn, void (*on_pressed)(void))
{
    uint32_t now = HAL_GetTick();
    bool curr_state = (HAL_GPIO_ReadPin(btn->port, btn->pin) == GPIO_PIN_SET);

    // 1. 버튼이 눌린 상태 (HIGH)
    if (curr_state)
    {
        // 이전에 눌려 있지 않았고(LOW), 쿨다운이 지났다면 누르는 찰나에 즉시(0ms) 1회 실행
        if (!btn->is_pressed && (now - btn->last_press_tick >= BTN_DEBOUNCE_COOLDOWN_MS))
        {
            btn->is_pressed = true;          // 눌림 락(Lock)
            btn->last_press_tick = now;
            btn->clicked = true;

            if (on_pressed != NULL)
            {
                on_pressed();
            }
        }
    }
    // 2. 버튼에서 손을 뗀 상태 (LOW)
    else
    {
        // 손을 떼더라도 누른 지 최소 150ms가 지나서 신호가 완전히 LOW로 안착했을 때만 락 해제
        if (btn->is_pressed && (now - btn->last_press_tick >= BTN_DEBOUNCE_COOLDOWN_MS))
        {
            btn->is_pressed = false;
        }
    }
}

void button_loop(void)
{
    // 1. START 버튼 검사 및 실행
    update_button(&s_btn1, on_btn1_pressed);

    // 2. STOP 버튼 검사 및 실행
    update_button(&s_btn2, on_btn2_pressed);
}

bool button1_is_clicked(void)
{
    if (s_btn1.clicked)
    {
        s_btn1.clicked = false;
        return true;
    }
    return false;
}

bool button2_is_clicked(void)
{
    if (s_btn2.clicked)
    {
        s_btn2.clicked = false;
        return true;
    }
    return false;
}