# 무궁화게임 개발 코드

Raspberry Pi와 Jetson의 개인 담당 개발을 관리하는 저장소입니다.
Pi의 기존 `game` 코드와 Jetson의 TCP·영상 예제를 기준으로 시작했습니다.
수업 참고 코드 `lecturecode`는 저장소에 포함하지 않습니다.
담당 범위와 Git 사용 흐름은 [저장소 관리](docs/repository.md)를 참고하세요.
장비별 작업 폴더와 실행 환경: [Pi](docs/setup-pi.md), [Jetson](docs/setup-jetson.md).
[STM32 Wi-Fi 연결 직후 수신 확인](docs/stm-wifi-test.md).
[통신·게임 책임 분리와 검증 상태](docs/architecture.md).
[Jetson 웹캠 검출·추적 개발](docs/jetson-development.md).
[게임 영상 입력·영역·결승선 설정](docs/game-camera-setup.md).
[프로젝트 트러블슈팅 기록·추론 최적화 계획](docs/troubleshooting.md).
[Jetson TensorRT 엔진 생성·비교](docs/jetson-engine-optimization.md).
[Jetson 웹 영상 모니터·게임 DB 조회](docs/web-monitor.md).
[웹캠 구역·결승선·두 사람 추적 검증](docs/vision-validation.md).
[Pi MariaDB 기본 구성·웹 조회 검증](docs/database.md).
[관절 검출 비교 전 백업·복원 절차](docs/backup-before-pose.md).
[별도 관절 모델·속도 비교·웹 미리보기](docs/pose-comparison.md).
[웹 시험 시작·중지와 원본 프레임·좌표 기록](docs/pose-recording.md).
[참가자·180초 경기·DB·LCD 실행](docs/game-runtime.md).

## 구성

- `pi/server`: TCP 메시지 중계 서버와 로그인 ID 설정.
- `pi/bluetooth`: Arduino Bluetooth ↔ TCP 중계 프로그램.
- `pi/controller`: Pi C 게임 제어기. --game에서 참가자 고정·180초·결과·DB 저널·LCD 전송.
- `tools/tcp_client`: Pi·Jetson 공용 TCP 진단 소스. [STM 연결 시험](tools/tcp_client/README.md).
- `jetson/tcp_client`: 공용 소스를 Jetson에서 빌드하는 위치.
- `arduino/bluetooth_uart_test`: Bluetooth 진단용 스케치. LCD·타이머·자동 응답은 아직 미구현.
- `stm32`: STM32 펌웨어 추가 위치.
- `jetson/examples`: 기존 TCP·YOLO 인원 검출 예제. 게임 통합은 아직 미구현.
- `jetson/vision_client.py`: YOLO·ByteTrack 웹캠 관측을 PI로 전송하는 Python 클라이언트.
- `jetson/game`: 공통 웹캠·영상 입력, 영역 설정 브라우저 화면, 설정 검증 모듈.
- `docs/protocol.md`: 주소 규칙과 LCD 테스트 메시지 합의안.

## Pi에서 빌드

저장소 루트에서 아래 명령을 실행합니다. Bluetooth 프로그램은 시스템에 BlueZ 개발 헤더와 라이브러리(`libbluetooth-dev`)가 필요합니다.

```bash
make -C pi/server
make -C pi/controller
make -C pi/bluetooth
```

## 실제 경기 실행 (2026-10-08)

Pi 서버와 Bluetooth 중계는 기존처럼 켜고, PI 클라이언트는 다음 하나만 실행합니다.

```bash
./pi/controller/iot_client 127.0.0.1 5000 PI --game --duration 180 --audio
```

백그라운드 실행은 `python3 tools/start_pi_game.py`입니다.
20초 단축 경기 시험은 `python3 tools/start_pi_game.py --duration 20`으로 실행합니다.
실행 중인 PI 클라이언트를 먼저 종료해야 하며, 옵션을 생략하면 기본 180초입니다.
Jetson 웹과 연결기는 등록된 서비스로 자동 실행합니다.
복귀 완료 HOME → 사람이 구역 안에 들어오기 → STM START 순서입니다.
0명일 때는 시작하지 않습니다. 시간 만료 시 남은 참가자는 모두 탈락합니다.
기존 `--cycle-test`는 한 회차 진단용입니다. 같은 PI ID로 둘을 동시에 실행하면
기존 연결이 교체되므로 새 게임 테스트에는 --game을 사용하세요.
자세한 검증·DB·LCD 팀원 전달은 [현재 게임 실행](docs/game-runtime.md)을 따릅니다.

## COUNT 통신 테스트 (게임과 별도 진단)

Pi에서 `pi/server` 폴더의 `./iot_server 5000`을 실행합니다.
로그인 설정은 `idpasswd.example.txt`를 참고하여 실제 `idpasswd.txt`로 준비합니다.
Jetson에서는 다음 명령을 사용합니다. 이미 실행 중이면 중복 실행하지 마세요.

```bash
python3 jetson/count_test_client.py
```

Jetson Python 목적지는 PI로 고정됩니다. Pi에서는 서버와 함께
`./pi/controller/iot_client 127.0.0.1 5000 PI`를 실행합니다.
PI 제어 클라이언트가 가상 COUNT를 검사해 ARD·STM 명령을 만들고 서버가 중계합니다.
MCU 수신 헤더와 응답 목적지는 PI입니다. 서버는 게임 로직을 처리하지 않습니다.
Arduino는 Pi의 Bluetooth 중계가 ARD로 로그인해야 합니다.
STM32는 ESP-01 TCP 연결 뒤 STM으로 로그인합니다.
가상 데이터는 3초 간격의 기존 여섯 패턴이며 카메라 결과가 아닙니다.
RUN/STOP/RESET은 보내지 않습니다.
[연결·수신·로그 확인](docs/stm-wifi-test.md)을 참고하세요.

## 현재 제한

기본 COUNT 중계 모드는 통신 진단용이고 --game이 실제 참가자/게임 상태를 관리합니다.
Jetson USB 사운드 연동을 구현했습니다. MCU TIME 양 보드 표시 시험은 통과했고,
사운드와 실제 경기 전체 흐름·180초 현장 시험은 남아 있습니다.
서버는 인증 후 LF 단위로 메시지를 누적하고 여러 줄·초과 길이를 처리합니다.
서버 로그인 분할 수신·부분 송신·동일 ID 재접속 처리는 보완했습니다. 무선 단절의 현장 검증은 별도입니다.
MCU는 로그인 알림과 명령을 구분해야 합니다.
