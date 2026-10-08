#ifndef AP_H_
#define AP_H_

#include "main.h"

/**
 * @brief 애플리케이션 초기화 함수 (main.c의 MX 초기화 직후 호출)
 */
void ap_init(void);

/**
 * @brief 메인 루프 함수 (main.c의 while(1) 내부에서 주기적으로 호출)
 */
void ap_loop(void);

#endif /* AP_H_ */
