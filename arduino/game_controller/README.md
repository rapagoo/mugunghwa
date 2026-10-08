# Arduino Game Status Display Firmware

라즈베리 파이(서버)로부터 블루투스(HC-06) 통신을 통해 게임 진행 현황(남은 시간, 참가자 수, 통과/탈락 카운트)을 수신하여 16x2 I2C LCD에 실시간 표시하고 ACK 응답을 전송하는 펌웨어입니다.

---

## 1. 하드웨어 사양 및 부품 구성

* **MCU 보드:** Arduino Uno / Nano (ATmega328P)
* **디스플레이:** 16x2 Character LCD (I2C 모듈 일체형, 기본 주소 `0x27`)
* **블루투스 모듈:** HC-06 (Slave, UART 통신)
* **보안 안내:** 본 기기는 Wi-Fi 모듈을 사용하지 않으며, 블루투스 SPP를 사용하므로 별도의 Wi-Fi 비밀번호 설정이 없습니다.

---

## 2. 핀 매핑 (Pin Configuration) & 통신 속도

### [1] Bluetooth (HC-06) 연결
* **HC-06 TX** -> Arduino **D2 (SoftwareSerial RX)**
* **HC-06 RX** -> Arduino **D3 (SoftwareSerial TX)**
* **Baud Rate:** `9600 bps`

### [2] I2C 16x2 LCD 연결
* **SDA** -> Arduino **A4**
* **SCL** -> Arduino **A5**
* **VCC** -> **5V**, **GND** -> **GND**
* **I2C Address:** `0x27`

### [3] 디버깅 시리얼 (PC 연결)
* **Baud Rate:** `9600 bps` (아두이노 시리얼 모니터 확인용)

---

## 3. 필수 라이브러리

Arduino IDE의 **툴 > 라이브러리 관리자**에서 아래 라이브러리를 검색하여 설치합니다.

* **LiquidCrystal_I2C** (by Frank de Brabander 또는 Marco Schwartz)
* `Wire` (아두이노 기본 내장)
* `SoftwareSerial` (아두이노 기본 내장)

---

## 4. 통신 프로토콜 요약

### 수신 명령 (라즈베리 파이 -> 아두이노)
* `[PI]COUNT@전체@통과@탈락\n` : 인원수 갱신 후 화면 출력
* `[PI]TIME@남은초\n` : 남은 시간 갱신 후 화면 출력 (`MM:SS`)
* `[PI]RESET\n` : 대기 화면 (`GAME WAITING / READY!`)으로 초기화
* `[PI]STOP\n` : 현재 화면 유지

### 송신 응답 (아두이노 -> 라즈베리 파이)
* `[PI]APPLIED@COUNT@전체@통과@탈락\n` (카운트 적용 확인 ACK)
* `[PI]APPLIED@TIME@남은초\n` (시간 적용 확인 ACK)

---

## 5. 빌드 및 업로드 방법

1. Arduino IDE를 실행하고 `arduino/game_controller/game_controller.ino` 파일을 엽니다.
2. **툴 > 보드**에서 `Arduino Uno` (또는 사용하는 보드)를 선택합니다.
3. **툴 > 포트**에서 연결된 COM 포트를 선택합니다.
4. **업로드(Ctrl + U)** 버튼을 눌러 컴파일 및 펌웨어 다운로드를 진행합니다.
5. 업로드 완료 후 시리얼 모니터(`9600 bps`)를 열어 `[SYSTEM] LCD client ready` 로그가 출력되는지 확인합니다.
