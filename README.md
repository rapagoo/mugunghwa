# 무궁화게임 개발 코드

Raspberry Pi와 Jetson의 개인 담당 개발을 관리하는 저장소입니다.
Pi의 기존 `game` 코드와 Jetson의 TCP·영상 예제를 기준으로 시작했습니다.
수업 참고 코드 `lecturecode`는 저장소에 포함하지 않습니다.
담당 범위와 Git 사용 흐름은 [저장소 관리](docs/repository.md)를 참고하세요.
장비별 작업 폴더와 실행 환경: [Pi](docs/setup-pi.md), [Jetson](docs/setup-jetson.md).

## 구성

- `pi/server`: TCP 메시지 중계 서버와 로그인 ID 설정.
- `pi/bluetooth`: Arduino Bluetooth ↔ TCP 중계 프로그램.
- `pi/controller`: 수동 메시지 테스트용 C 클라이언트. 자동 게임 제어는 아직 미구현.
- `arduino/bluetooth_uart_test`: Bluetooth 진단용 스케치. LCD·타이머·자동 응답은 아직 미구현.
- `stm32`: STM32 펌웨어 추가 위치.
- `jetson/examples`: 기존 TCP·YOLO 인원 검출 예제. 게임 통합은 아직 미구현.
- `docs/protocol.md`: 주소 규칙과 LCD 테스트 메시지 합의안.

## Pi에서 빌드

저장소 루트에서 아래 명령을 실행합니다. Bluetooth 프로그램은 시스템에 BlueZ 개발 헤더와 라이브러리(`libbluetooth-dev`)가 필요합니다.

```bash
make -C pi/server
make -C pi/controller
make -C pi/bluetooth
```

## 수동 통신 테스트

1. `pi/server/idpasswd.example.txt`를 같은 폴더의 `idpasswd.txt`로 복사하고 테스트 ID를 확인합니다. 실제 설정 파일은 Git에서 제외합니다. `pi/server` 폴더에서 `./iot_server 5000` 실행. 서버는 현재 작업 폴더의 `idpasswd.txt`를 읽습니다.
2. 별도 터미널의 `pi/controller` 폴더에서 `./iot_client 127.0.0.1 5000 PI` 실행.
3. `pi/bluetooth/bluetooth_client.c`의 `dest`를 실제 Arduino Bluetooth 모듈 MAC 주소로 맞춘 뒤 다시 빌드.
4. Arduino에 진단 스케치를 업로드.
5. 별도 터미널의 `pi/bluetooth` 폴더에서 `./bluetooth_client 127.0.0.1 5000 ARD` 실행.

Pi 제어 클라이언트는 `PI`, Arduino를 대표하는 Bluetooth 중계 클라이언트는 `ARD`로 로그인합니다.
현재 C 클라이언트와 예제 설정의 로그인 비밀번호는 수업 코드의 테스트 값 `PASSWD`를 사용합니다. 기존 장비의 실제 등록 파일은 저장소에 포함하지 않았습니다.
서버를 다른 장치에서 실행한다면 `127.0.0.1` 대신 해당 서버의 LAN IP를 사용합니다.

Pi 클라이언트에서 `[ARD]COUNT@4@2@1`을 입력하고 Enter를 누르면 Arduino 시리얼 모니터에 `[PI]COUNT@4@2@1`이 나타나야 합니다.
진단 스케치는 기동 후 약 2초 간격으로 `[PI]DIAG@PING`을 총 5회 전송합니다. Bluetooth 연결 전에 전송 횟수가 소진되면 연결 후 Arduino를 리셋하세요.

현재 스케치는 수신 문자열 출력까지만 수행합니다. `COUNT`의 LCD 적용 및 응답은 다음 개발 단계입니다.

## 3초 간격 LCD 카운트 전송

서버와 Bluetooth 중계(`ARD`)를 실행한 뒤, 수동 `PI` 클라이언트를 종료하고 같은 클라이언트의 자동 전송 옵션을 사용합니다.

```bash
cd pi/controller
./iot_client 127.0.0.1 5000 PI --lcd-demo
```

인증 완료 후 즉시 첫 메시지를 보내고 이후 3초 간격으로 다음 누적값을 반복합니다.

```text
[ARD]COUNT@1@0@0
[ARD]COUNT@2@1@0
[ARD]COUNT@3@1@1
[ARD]COUNT@4@2@1
[ARD]COUNT@3@1@1
[ARD]COUNT@2@1@0
```

숫자는 총인원·성공·실패 순서입니다. 감소는 표시 갱신 확인용 가상 데이터입니다.
Arduino는 헤더가 `[PI]`로 바뀐 메시지를 받으며, `[PI]APPLIED@COUNT@...`로 응답하면 Pi 터미널에 출력됩니다.
`RESET`, `RUN`, `STOP`은 자동으로 보내지 않습니다. 종료는 Ctrl+C를 사용합니다.
Bluetooth 연결·LCD 적용은 실제 장치에서 확인해야 합니다.

## 현재 제한

수업 소스의 메시지 파서와 연결 처리는 그대로 복사했습니다. 부분 수신·여러 줄 수신·길이 초과·부분 송신 처리는 추가 개선이 필요합니다.
서버가 `:`를 구분자로 사용하므로 숫자 데이터를 보내고 LCD 문구는 MCU에서 구성합니다.
서버 로그인 알림도 Bluetooth로 전달되므로 MCU의 명령 파서는 로그인 알림을 명령으로 실행하지 않아야 합니다.
