# STM32 Wi-Fi 수신 확인

팀원 전달용 TCP 설정:

| 항목 | 값 |
|---|---|
| TCP 서버 | `10.10.16.90` |
| 포트 | `5000` |
| 로그인 ID | `STM` (대문자) |
| 테스트 비밀번호 | `PASSWD` |
| 로그인 데이터 | `[STM:PASSWD]` (LF 없음) |

ESP-01이 Pi와 통신 가능한 LAN에 연결된 뒤 TCP 연결을 열고 로그인 데이터를 송신합니다.
SSID와 Wi-Fi 비밀번호는 현장 네트워크 설정을 사용합니다.
로그인 성공 응답은 `[STM] New connected! ...\n`이며 게임 명령으로 처리하지 않습니다.

## 연결 직후 확인할 데이터

Jetson의 `JETSON` 클라이언트가 Pi 제어 클라이언트에 가상값을 3초 간격으로 보냅니다.
Pi 제어 클라이언트는 값을 검사하고 STM32에 새 명령을 보냅니다.
STM32에서 수신하는 실제 게임 문자열은 다음과 같습니다.

```text
[PI]COUNT@1@0@0
[PI]COUNT@2@1@0
[PI]COUNT@3@1@1
[PI]COUNT@4@2@1
[PI]COUNT@3@1@1
[PI]COUNT@2@1@0
```

각 줄 끝에는 실제 LF 바이트 `0x0A`가 있습니다. 숫자는 총인원·성공·실패 순서입니다.
감소하는 값은 LCD 갱신 시험용입니다. 이 값들은 카메라 결과가 아닙니다.
STM32 연결 전에 보내진 값은 보관하지 않지만, 로그인 후 다음 전송부터 최대 약 3초 안에 받습니다.
RUN/STOP/RESET이나 서보·LED 동작 명령은 보내지 않습니다.

먼저 UART 수신 출력으로 위 문자열을 확인하고 LCD 구현 후 표시 적용을 확인합니다.
LCD 적용 후 다음과 같이 응답하면 Jetson 로그에서 왕복 통신을 확인할 수 있습니다.

```text
[PI]APPLIED@COUNT@1@0@0
```

응답 끝에도 LF를 붙입니다. Pi는 `[STM]APPLIED@COUNT@1@0@0`을 받습니다.
Pi가 테스트 응답을 Jetson에 전달하면 Jetson은 `[PI]APPLIED@COUNT@1@0@0`을 받습니다.
아직 LCD를 구현하지 않았다면 수신 확인만 먼저 진행해도 됩니다.
ESP-01의 `+IPD` 헤더·AT 응답을 분리하고 TCP/UART 조각을 누적해 LF 단위로 파싱합니다.
STM32와 Arduino는 `[PI]` 발신자의 명령을 처리하고 응답 목적지도 `PI`로 통일합니다.

## 현재 실행과 로그

Pi 서버 작업 폴더: `/home/pi/Projects/mugunghwa/repo/pi/server`

Jetson 테스트 명령:

```bash
cd /home/jetson/projects/mugunghwa/repo
./jetson/tcp_client/iot_client 10.10.16.90 5000 JETSON --lcd-demo --target PI
```

Pi 제어 클라이언트 명령 (Pi 서버와 함께 실행):

```bash
cd /home/pi/Projects/mugunghwa/repo
python3 pi/controller/count_relay.py --target STM
```

Arduino로 바꿔 시험할 때는 Pi 제어 클라이언트의 `--target ARD`와 Bluetooth 중계가 필요합니다.
`count_relay.py`는 COUNT 검사·명령 전달·응답 확인용이며 경기 상태 판단은 아직 구현하지 않았습니다.

준비된 백그라운드 프로세스의 로그:

```bash
# Pi
tail -f /home/pi/Projects/mugunghwa/repo/.runtime/stm-server.log
# Pi 제어 클라이언트
tail -f /home/pi/Projects/mugunghwa/repo/.runtime/pi-count-relay.log
# Jetson
tail -f /home/jetson/projects/mugunghwa/repo/.runtime/stm-client.log
```

Pi에서 `New connected`의 ID가 STM인지 확인합니다.
Jetson의 `TX`는 송신만 의미하며 STM32 수신 성공은 UART 출력 또는 응답으로 확인해야 합니다.
각 PID는 같은 `.runtime` 폴더의 `stm-server.pid`, `pi-count-relay.pid`, `stm-client.pid`에 기록합니다.
백그라운드 실행은 재부팅 후 자동 시작하지 않습니다.
새 프로세스를 실행하기 전에 기존 PID가 실행 중인지 확인해 중복 로그인을 피합니다.
실제 STM32·ESP-01 수신은 팀원 연결 완료 후 확인합니다.
