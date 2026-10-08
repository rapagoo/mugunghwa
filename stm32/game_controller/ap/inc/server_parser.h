#ifndef SERVER_PARSER_H_
#define SERVER_PARSER_H_

#include "main.h"
#include <stdbool.h>

/**
 * @brief LCD 및 서버 파서 초기화 (전원 인가 시 게임 대기 화면 표시)
 */
void server_parser_init(void);

/**
 * @brief 서버 수신 버퍼(+IPD) 확인, 문자 파싱, esp_event 및 LCD/타이머 처리
 */
void server_parser_loop(void);

/**
 * @brief 수신된 명령 문자열 직접 파싱 및 처리 (esp_event)
 */
void server_parser_esp_event(char *recvBuf);

/**
 * @brief "게임 대기중" 화면 표시 및 대기 상태로 리셋
 */
void server_parser_show_waiting_screen(void);

/**
 * @brief 5분 카운트다운 게임 시작 및 화면 표시 (START 시 호출)
 */
void server_parser_start_game(void);

/**
 * @brief 화면 및 게임 데이터 전체 리셋
 */
void server_parser_reset_game(void);

/**
 * @brief 게임 타이머 일시정지 (STOP)
 */
void server_parser_stop_game(void);

#endif /* SERVER_PARSER_H_ */
