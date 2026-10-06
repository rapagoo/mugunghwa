# LCD 통신 테스트 규격

## 주소

- Pi 제어 클라이언트 ID: `PI`
- Jetson 영상 클라이언트 ID: `JETSON`
- STM32 ESP-01 TCP 클라이언트 ID: `STM`
- Arduino Bluetooth 중계 클라이언트 ID: `ARD`
- ID는 대소문자를 구분합니다.
- 송신: `[수신자ID]명령@데이터\n`
- TCP 서버 중계 후 수신: `[발신자ID]명령@데이터\n`
- Bluetooth 중계는 문자열을 그대로 전달합니다. Arduino 수신 헤더는 `[PI]`입니다.
- `\n`은 실제 LF 문자이며, 필드 내부에는 `@`, `[`, `]`, `:`, CR, LF를 넣지 않습니다.

예:

```text
Pi 전송:       [ARD]COUNT@4@2@1
Arduino 수신:  [PI]COUNT@4@2@1
Arduino 응답:  [PI]APPLIED@COUNT@4@2@1
Pi 수신:       [ARD]APPLIED@COUNT@4@2@1
```

위 예시의 각 메시지 끝에 LF를 붙입니다. Arduino는 서버 로그인 절차를 수행하지 않고 Pi의 중계 프로그램이 `ARD`로 로그인합니다.

## LCD 명령 합의안 — 구현 예정

| Arduino 수신 | 동작 | Arduino 응답 |
|---|---|---|
| `[PI]RESET` | 시간·인원수 0, 타이머 정지 | `[PI]READY` |
| `[PI]COUNT@4@2@1` | 총인원·성공·실패 순으로 표시, 타이머 유지 | `[PI]APPLIED@COUNT@4@2@1` |
| `[PI]RUN` | 시간 0부터 계산 시작, 실행 중 중복은 무시 | `[PI]APPLIED@RUN` |
| `[PI]STOP` | 경과 시간 정지 | `[PI]APPLIED@STOP` |

각 메시지는 LF로 끝납니다. `COUNT`는 증감값이 아니라 현재 누적값입니다.
음수, 성공+실패가 총인원을 초과하는 값, 잘못된 필드 개수는 적용하지 않습니다.
LCD 첫 줄은 `T:012s ALL:04`, 둘째 줄은 `OK:02 OUT:01`처럼 MCU에서 구성합니다.
시간은 `millis()` 또는 시스템 tick의 현재값과 시작값 차이로 계산하며, 긴 대기로 통신을 막지 않습니다.

## 현재 구현

Arduino 스케치는 `[PI]DIAG@PING`을 5회 보내고 수신 바이트를 시리얼 모니터에 출력합니다.
LCD 명령 처리와 자동 응답은 아직 구현하지 않았습니다.
Jetson은 `JETSON`, STM32는 `STM`으로 로그인합니다. `HSR_` 수업 ID는 새 개발 설정에서 사용하지 않습니다.

## STM32 연결 시험

STM32 UART ↔ ESP-01 ↔ Wi-Fi/TCP ↔ Pi 서버로 연결합니다.
ESP-01 연결 후 STM32가 `[STM:PASSWD]`를 송신하고 로그인 성공을 기다립니다.
`PASSWD`는 현재 수업 클라이언트와 호환되는 테스트 값입니다.
로그인 문자열에는 LF를 붙이지 않고, 이후 명령과 응답은 LF로 끝냅니다.

Pi 제어 클라이언트가 처리하는 현재 COUNT 테스트 경로:

```text
Jetson → Pi 서버: [PI]COUNT@4@2@1\n
Pi 제어 수신: [JETSON]COUNT@4@2@1\n
Pi 제어 → Pi 서버: [STM]COUNT@4@2@1\n (Arduino 대상은 [ARD])
STM32 수신: [PI]COUNT@4@2@1\n
Arduino 중계 수신: [PI]COUNT@4@2@1\n
STM32 → Pi 서버: [PI]APPLIED@COUNT@4@2@1\n
Pi 제어 수신: [STM]APPLIED@COUNT@4@2@1\n
Pi 제어 → Pi 서버: [JETSON]APPLIED@COUNT@4@2@1\n
Jetson 수신: [PI]APPLIED@COUNT@4@2@1\n
```

STM32와 Arduino는 `[PI]` 명령을 받고 응답도 `[PI]`로 보냅니다.
LCD를 실제 적용한 뒤 APPLIED를 응답하며 로그인 알림은 명령에서 제외합니다.
TCP/UART 분할 수신을 누적하고 LF 단위로 처리해야 합니다.
ESP-01의 `+IPD` 및 AT 응답과 게임 명령 파서는 분리합니다.

현재 Pi 제어 `iot_client`가 유효한 COUNT를 검사해 ARD·STM 명령을 생성합니다.
서버는 목적지 중계만 수행하고 발신자 ID를 임의로 바꾸지 않습니다.
게임 상태 판단은 아직 구현 전입니다. 최종 흐름은
Jetson → Pi(영상 후보), Pi(검증·경기 상태 확정) → STM(현장 명령)입니다.
Jetson의 프레임별 사람 검출 수를 누적 참가자·도착·탈락 수로 취급하지 않습니다.

2026-10-06 별도 15000번 테스트 서버에서 STM 소프트웨어 시뮬레이터로
`[PI]COUNT` 수신, PI 목적지 응답, Jetson으로 응답 전달을 확인했습니다.
성공+실패가 총인원을 초과하는 COUNT는 Pi 제어가 차단합니다.
인증 후 게임 메시지의 TCP 분할 수신·여러 줄 수신을 처리하고 초과 길이는 다음 LF까지 버립니다.
ARD·STM 동시 전달과 응답, 분할·묶음 메시지를 시뮬레이터로 검증했습니다.
로그인 프레임의 분할 수신과 부분 송신 처리는 후속 개선 대상입니다.
실제 STM32·ESP-01·LCD 적용은 아직 검증하지 않았습니다.
