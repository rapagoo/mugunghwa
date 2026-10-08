# STM32 팀원 완성본

팀원의 STM32CubeIDE 프로젝트 **폴더 안의 내용 전체**를 이 폴더에 복사하세요.
`.ioc`, `.project`, `.cproject`가 이 README와 같은 위치에 오도록 넣으면 됩니다.

포함할 파일:

- `.ioc`, `.project`, `.cproject`, `.mxproject`, `.settings/` 등 프로젝트 설정
- `Core/`, `Drivers/`, 사용자 소스·헤더, 사용 중인 미들웨어
- 시작 코드, 링커 스크립트, 빌드 설정과 필요한 라이브러리

`Debug/`, `Release/` 등 빌드 결과는 이 폴더의 `.gitignore`로 제외합니다.
CubeIDE의 workspace 전체나 `.metadata/`는 복사하지 마세요.
이 안내와 `.gitignore`는 유지하고, 완성본에 별도 설명서가 있다면 다른 이름으로 함께 넣으세요.

CubeIDE에서 이 폴더를 기존 프로젝트로 가져온 뒤 보드에 빌드·업로드합니다.
파일을 저장소에 복사하는 것만으로 보드에 업로드되지는 않습니다.
Wi-Fi SSID·비밀번호 등 실제 비밀값은 Git에 올리기 전에 분리하거나 예시 값으로 바꾸세요.

현재 게임 통신 규약은 [경기 실행 문서](../../docs/game-runtime.md)를 참고하세요.

---

## 1. 하드웨어 사양 및 부품 구성

* **MCU 보드:** STMicroelectronics NUCLEO-F411RE (STM32F411RET6, ARM Cortex-M4 @ 84MHz)
* **Wi-Fi 통신 모듈:** ESP8266 ESP-01 (UART6 통신, TCP Client 모드)
* **디스플레이:** 16x2 Character LCD (I2C 모듈 일체형, 기본 주소 `0x27` / 보조 `0x3F`)
* **서보모터:** SG90 (TIM3 CH1 PWM, 술래 인형 180도 회전 및 0도 복귀)
* **RGB LED:** Common Cathode 3색 LED (TIM1 CH1/CH2/CH3 PWM, 상태 표시: RED/YELLOW/GREEN)
* **조작 버튼:**
  * **버튼 1 (START):** 게임 시작 패킷 `[PI]START\n` 전송
  * **버튼 2 (STOP):** 게임 정지 패킷 `[PI]STOP\n` 전송

---

## 2. 핀 매핑 (Pin Configuration) & 통신 속도

### [1] Wi-Fi (ESP-01) 연결
* **ESP-01 TX** -> STM32 **PC7 (USART6 RX)**
* **ESP-01 RX** -> STM32 **PC6 (USART6 TX)**
* **VCC:** 3.3V, **GND:** GND
* **Baud Rate:** `38400 bps`

### [2] 디버그 시리얼 (PC ST-LINK Virtual COM Port)
* **STM32 TX:** PA2 (USART2 TX)
* **STM32 RX:** PA3 (USART2 RX)
* **Baud Rate:** `115200 bps` (시리얼 터미널 디버그 모니터링)

### [3] 16x2 I2C LCD 연결
* **SCL** -> STM32 **PB8** (Nucleo Arduino D15, Software I2C)
* **SDA** -> STM32 **PB9** (Nucleo Arduino D14, Software I2C)
* **VCC:** 5V, **GND:** GND
* **I2C Address:** `0x27` (또는 `0x3F`)

### [4] 서보모터 (SG90)
* **PWM Signal:** STM32 **PA6** (TIM3 CH1 PWM, 주파수 50Hz, 주기 20ms)
* **VCC:** 5V, **GND:** GND

### [5] RGB LED (Common Cathode)
* **R (Red):** STM32 **PA8** (TIM1 CH1 PWM)
* **G (Green):** STM32 **PA9** (TIM1 CH2 PWM)
* **B (Blue):** STM32 **PA10** (TIM1 CH3 PWM)
* **Common Pin:** GND

### [6] 버튼 2개
* **버튼 1 (START):** STM32 **PB4** (Active HIGH, 하드웨어 풀다운)
* **버튼 2 (STOP):** STM32 **PB5** (Active HIGH, 하드웨어 풀다운)

---

## 3. 네트워크 및 비밀값 설정

본 펌웨어는 Git 보안 규정에 따라 실제 Wi-Fi 비밀번호가 제외되어 있습니다.  
보드 빌드 전 `ap/inc/esp01.h` 파일에서 네트워크 환경에 맞게 접속 정보를 수정하세요:

```c
#define SSID     "YOUR_WIFI_SSID"      // 접속할 Wi-Fi SSID
#define PASS     "YOUR_WIFI_PASSWORD"  // Wi-Fi 비밀번호
#define LOGID    "STM"                 // 서버 접속 ID
#define PASSWD   "PASSWD"              // 서버 접속 비밀번호
#define DST_IP   "10.10.16.90"         // 라즈베리 파이 게임 서버 IP
#define DST_PORT 5000                  // 게임 서버 포트
```

---

## 4. 빌드 및 업로드 방법

### 방법 A: VS Code + CMake (권장)
1. **필수 도구 설치:**
   - ARM GNU Toolchain (`arm-none-eabi-gcc`)
   - CMake 3.22 이상
   - Ninja 빌드 도구
   - OpenOCD (보드 플래시용)
2. **빌드:**
   ```bash
   cmake -B build -G Ninja
   cmake --build build
   ```
3. **업로드 (ST-LINK 연결 상태):**
   ```powershell
   ./flash.ps1
   ```
   또는 VS Code의 `Build & Flash` 기본 태스크(Ctrl+Shift+B)를 실행합니다.

### 방법 B: STM32CubeIDE / STM32CubeMX
1. CubeIDE에서 **File > Import > Existing Projects into Workspace** 또는 **Open Projects from File System**을 선택합니다.
2. `stm32/game_controller/` 폴더를 지정하여 가져옵니다.
3. 또는 `stm32_project.ioc`를 열어 코드 생성을 실행한 후 빌드(`Ctrl+B`)하고, 보드 연결 후 **Run > Run**으로 다운로드합니다.

