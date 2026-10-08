#ifndef __SERVO_H
#define __SERVO_H

#include "main.h"
#include <stdint.h>
#include <stdbool.h>

// 서보모터 PWM 펄스 폭 설정 (단위: us, 마이크로초)
// 일반적인 SG90 기준: 0도 = 500us (0.5ms), 180도 = 2500us (2.5ms)
#define SERVO_MIN_PULSE_US       500
#define SERVO_MAX_PULSE_US       2500
#define SERVO_MIN_ANGLE          0
#define SERVO_MAX_ANGLE          180

// 서보모터 제어 모드 설정
// 1: 목표 각도(180도/0도)로 한 번에 즉시 PWM 펄스 반영 (전압 강하/진동 테스트용 모드)
// 0: 1도씩 부드럽게 스텝 이동 (기존 7ms 스텝 모드)
#define SERVO_DIRECT_MODE        1

// 모터 회전 속도 설정: 1도당 이동 지연 시간 (ms) (스텝 모드 시 사용)
// 7ms 기준: 180도 회전에 약 1.26초 소요 (부드러운 회전)
#define SERVO_STEP_DELAY_MS      7

// 한 번에 즉시 회전 시 모터가 물리적으로 도달하기까지 대기할 시간 (ms)
#define SERVO_DIRECT_MOVE_MS     500

// 서보모터 FSM 동작 상태 정의
typedef enum {
    SERVO_STATE_IDLE_REAR = 0,    // 0도 정지 상태 (대기 중, LED: GREEN)
    SERVO_STATE_MOVING_TO_FRONT,  // 180도로 회전 중 (LED: YELLOW)
    SERVO_STATE_HOLD_AT_FRONT,    // 180도 도달 완료 (서버 [PI]MOTOR@FRONT@OK 전송, LED: RED, 서버의 REAR 명령 대기)
    SERVO_STATE_MOVING_TO_REAR    // 0도로 복귀 회전 중 (LED: YELLOW, 완료 시 서버 [PI]MOTOR@REAR@OK 전송, LED: GREEN)
} servo_state_t;

/**
 * @brief 서보모터 PWM 시작 및 초기화 (초기 각도 0도, 상태 IDLE_REAR)
 */
void servo_init(void);

/**
 * @brief 서버로부터 [STM]MOTOR@FRONT 수신 시 호출 -> 180도 회전 시작 및 LED YELLOW 점등
 */
void servo_trigger_front(void);

/**
 * @brief 서버로부터 [STM]MOTOR@REAR 수신 시 호출 -> 0도 복귀 회전 시작 및 LED YELLOW 점등
 */
void servo_trigger_rear(void);

/**
 * @brief 서보모터 각도 즉시 반영 (0 ~ 180도)
 */
void servo_set_angle(uint8_t angle);

/**
 * @brief 현재 각도 반환
 */
uint8_t servo_get_angle(void);

/**
 * @brief 현재 서보 상태 반환
 */
servo_state_t servo_get_state(void);

/**
 * @brief 서보모터 각도 0도 리셋 및 상태 초기화
 */
void servo_reset(void);

/**
 * @brief 메인 루프에서 실행되는 서보 FSM 상태 전이 및 패킷 송신 처리 함수
 */
void servo_loop(void);

/**
 * @brief 서보모터 1도당 이동 속도(지연 ms) 변경
 */
void servo_set_speed_delay(uint32_t delay_ms);

/**
 * @brief SysTick 1ms 인터럽트에서 호출되는 1도 단위 부드러운 스텝 이동 함수
 */
void servo_tick_1ms(void);

#endif /* __SERVO_H */
