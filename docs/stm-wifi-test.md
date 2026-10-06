# STM32 Wi-Fi와 Arduino COUNT 수신 시험

| 항목 | 값 |
|---|---|
| Pi TCP 서버 | `10.10.16.90:5000` |
| STM32 로그인 | `[STM:PASSWD]` (LF 없음) |
| Arduino 대표 TCP ID | `ARD` (Pi Bluetooth 중계 프로그램이 로그인) |
| Jetson 로그인 ID | `JETSON` |

STM32는 ESP-01을 같은 LAN에 연결하고 TCP 연결 뒤 로그인합니다.
SSID와 Wi-Fi 비밀번호는 현장 설정을 사용합니다.
`[STM] New connected! ...\n`은 로그인 알림이며 명령으로 처리하지 않습니다.

## 현재 전송 경로

```text
Jetson → Pi 서버: [PI]COUNT@4@2@1\n
Pi 제어 수신: [JETSON]COUNT@4@2@1\n
Pi 제어 → Pi 서버: [STM]COUNT@4@2@1\n
Pi 제어 → Pi 서버: [ARD]COUNT@4@2@1\n
Pi 서버 → STM32: [PI]COUNT@4@2@1\n
Pi 서버 → Arduino 중계: [PI]COUNT@4@2@1\n
STM32/Arduino → Pi 서버: [PI]APPLIED@COUNT@4@2@1\n
Pi 제어 수신: [STM]APPLIED@COUNT@4@2@1\n (Arduino는 [ARD])
Pi 제어 → Pi 서버: [JETSON]APPLIED@COUNT@4@2@1\n
Pi 서버 → Jetson: [PI]APPLIED@COUNT@4@2@1\n
```

Jetson은 Python으로 PI에만 보냅니다. Pi 제어 클라이언트가 ARD와 STM 명령을 생성합니다.
MCU는 `[PI]` 명령을 처리하고 응답 목적지도 PI로 통일합니다.
서버는 목적지로 중계만 하며 Pi 제어 클라이언트를 함께 실행해야 합니다.
실제 경기 제어는 별도로 구현해야 합니다.

3초 간격으로 다음 가상값을 반복합니다. 각 줄 끝에는 실제 LF(`0x0A`)가 있습니다.

```text
[PI]COUNT@1@0@0
[PI]COUNT@2@1@0
[PI]COUNT@3@1@1
[PI]COUNT@4@2@1
[PI]COUNT@3@1@1
[PI]COUNT@2@1@0
```

총인원·성공·실패 순서이며 감소값은 LCD 갱신 시험용입니다. 카메라 결과가 아닙니다.
로그인 후 다음 전송부터 최대 약 3초 안에 수신합니다. 과거 값은 재전송하지 않습니다.
RUN/STOP/RESET이나 서보·LED 동작 명령은 보내지 않습니다.
UART에서 문자열을 확인하고 LCD 구현 후 적용 응답을 보내세요.
ESP-01 `+IPD`·AT 응답을 분리하고 LF 단위로 명령을 파싱해야 합니다.

## 실행과 로그

```bash
# Jetson (기존 프로세스 실행 중이면 중복 실행 금지)
cd /home/jetson/projects/mugunghwa/repo
python3 jetson/count_test_client.py
# Pi 제어 클라이언트 (이미 실행 중이면 중복 실행 금지)
cd /home/pi/Projects/mugunghwa/repo
python3 pi/controller/count_relay.py
# Pi 서버 로그
tail -f /home/pi/Projects/mugunghwa/repo/.runtime/stm-server.log
# Jetson 송신·응답 로그
tail -f /home/jetson/projects/mugunghwa/repo/.runtime/stm-client.log
# Pi 제어 로그
tail -f /home/pi/Projects/mugunghwa/repo/.runtime/pi-count-relay.log
# Arduino Bluetooth 중계 로그
tail -f /home/pi/Projects/mugunghwa/repo/.runtime/arduino-bridge.log
```

서버의 `msg : [PI->STM]` 또는 ARD 로그는 전달 시도입니다.
실제 수신은 MCU UART 출력 또는 Pi 제어의 `RX [STM]APPLIED...` 등으로 확인합니다.
PID는 `.runtime/stm-server.pid`, `pi-count-relay.pid`, `stm-client.pid`, `arduino-bridge.pid`에 기록합니다.
재부팅 후 자동 실행하지 않습니다. STM32·ESP-01·LCD 수신은 연결 후 검증합니다.
