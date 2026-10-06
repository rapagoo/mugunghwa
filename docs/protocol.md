# LCD 통신 테스트 규격

## 주소

- Pi 제어 클라이언트 ID: `PI`
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
STM32와 Jetson의 기존 등록 ID는 이번 변경에서 유지했습니다. 해당 장치의 이름과 메시지는 통합 단계에서 확정합니다.
