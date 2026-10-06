# 통신과 게임 책임 분리

2026-10-06 합의한 구조이며 통신 테스트부터 같은 구성을 사용합니다.

| 프로그램 | 실행 장치·ID | 책임 |
|---|---|---|
| `pi/server/iot_server` | Pi, TCP 서버 | 로그인·연결·LF 프레임·목적지 중계 |
| `jetson/count_test_client.py` | Jetson, JETSON | 가상 COUNT를 PI로만 송신 |
| `pi/controller/iot_client` (C) | Pi, PI | 값 검사·ARD/STM 명령 생성·응답 확인 |
| Bluetooth 중계 | Pi, ARD | Arduino UART/Bluetooth와 TCP 연결 |
| 팀원 STM32 펌웨어 | STM32+ESP-01, STM | PI 명령 실행·PI로 응답 |

모든 TCP 클라이언트는 같은 Pi 서버 `10.10.16.90:5000`에 접속합니다.
Jetson이 Pi 제어 클라이언트에 별도의 TCP 연결을 여는 방식은 아닙니다.

```text
Jetson Python → Pi TCP 서버 → Pi 제어 클라이언트
                                  ↓ 값 검사·명령 생성
                              Pi TCP 서버
                               ├→ STM32
                               └→ Bluetooth 중계 → Arduino
```

서버는 COUNT의 의미를 판단하지 않고 실제 로그인 ID를 발신자 헤더로 붙입니다.
PI 제어 프로그램이 PI로 로그인해 명령을 보내므로 MCU는 `[PI]`를 받습니다.
Jetson에 MCU 대상 설정은 없습니다. Pi 제어 프로그램은 기본적으로 ARD·STM 모두에 보내며,
필요하면 `--target STM` 또는 `--target ARD`로 선택할 수 있습니다.

Pi 제어 소스는 `pi/controller/iot_client.c`입니다. 기존 Python 제어 프로그램은 제거했습니다.
수업의 C 서버·C 클라이언트 구성을 유지하며 Jetson 영상·송신 프로그램은 Python입니다.
Pi 제어는 수신을 계속 기다리는 방식이며 Ctrl+C로 종료합니다.

## 게임 개발로 확장

Jetson Python에는 검출·참가자 추적·움직임/도착 후보 생성을 추가합니다.
Pi 제어 프로그램에는 경기 상태·최종 판정·음성·시간표·DB 기능을 추가합니다.
서버는 중계 역할을 유지하고 MCU는 장치 동작과 응답을 담당합니다.
현재 가상 COUNT는 실제 영상 후보가 아니며 경기 상태 판단은 구현하지 않았습니다.
실물 통신 확인 후 같은 경로에 게임 메시지를 추가합니다.

## 검증 상태

- 별도 15000번 서버에서 Python 송신기·C PI 제어·STM/ARD 시뮬레이터 왕복 통과.
- C 제어 소스는 `-Wall -Wextra -Werror` 빌드 통과.
- 두 MCU의 발신자 헤더 PI, 응답 목적지 PI 확인.
- 잘못된 COUNT 차단, TCP 분할·여러 줄 수신 통과.
- 실제 Arduino Bluetooth는 최근 시도에서 `Host is down`; 실물 수신 미확인.
- STM32 ESP-01·LCD는 팀원 연결 완료 후 검증 필요.
- 웹캠/GPU 추론은 별도 검사 완료, 통신 테스트에 영상값은 아직 연결하지 않음.

Pi에서 통합 검사를 다시 실행하려면:

```bash
cd /home/pi/Projects/mugunghwa/repo
make -C pi/server
make -C pi/controller
python3 tests/count_integration.py
```

현재 테스트의 APPLIED 응답은 장치 ID와 최근 COUNT값으로 확인합니다.
게임에서는 game_id·phase_id·seq·command_id를 추가해 오래된/중복 사건을 구분해야 합니다.
서버의 로그인 프레임 분할 처리·부분 송신·연결 복구는 후속 개선 대상입니다.
