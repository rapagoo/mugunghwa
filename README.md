# 무궁화 꽃이 피었습니다

카메라로 참가자의 움직임을 관측하고, 인형의 회전과 게임 진행을 연결하는 IoT 프로젝트입니다. Raspberry Pi가 경기 시간과 최종 결과를 관리하며, 현장·별도 위치의 LCD와 웹에서 같은 경기의 현황을 확인합니다.

| 담당 | 장치 |
|---|---|
| 홍성록 | Raspberry Pi · Jetson |
| 박정환 | STM32 · Arduino |

## 주요 기능

- 웹에서 경기 구역·결승선·통과 방향 설정
- 시작 시 구역 안 참가자 등록, 기본 180초 경기 진행
- 인형 회전 처리·판정 시작 응답을 확인하는 단계 제어
- 고정 기준 자세와 관절 위치를 비교하는 움직임 후보 생성
- Pi에서 경기·단계·참가자를 검증한 후 통과·탈락 확정
- 두 LCD의 시간·인원 표시, 웹 현황 조회와 MariaDB 기록
- 구호·탈락 효과음, 중지·복귀·재시작 처리

## 구성

```text
Jetson: 카메라 · 관절 관측 · 웹
                  ↕ TCP
Pi: 메시지 중계 · 경기 제어 · 시간 · 최종 판정 · DB 저장
       ↕ Wi-Fi                     ↕ Bluetooth 중계
STM32: 버튼 · 모터 · LED · LCD     Arduino: 별도 위치 LCD
```

Jetson의 영상 관측은 후보이며 최종 결과는 Pi가 결정합니다. 회전 완료는 STM32 펌웨어 처리 완료 응답 기준입니다.

| 위치 | 내용 |
|---|---|
| `pi/server` | TCP 로그인·메시지 중계 |
| `pi/controller` | C 경기 제어기·타이머·단계·결과·LCD 명령 |
| `pi/bluetooth` | TCP ↔ Arduino Bluetooth 중계 |
| `pi/game_db_writer.py` | 로컬 저널의 MariaDB 반영·재시도 |
| `jetson/game` | 영상 입력·구역 설정·관절 후보·게임 연결 |
| `jetson/web_server.py`, `jetson/web` | 웹 미리보기·현황·설정·진단 |
| `stm32/game_controller` | STM32CubeIDE 펌웨어 프로젝트 |
| `arduino/game_controller` | Arduino 현황 표시 펌웨어 |
| `tests` | 단위·모의 통신·통합 검증 |

기존 수업 예제와 COUNT 진단 코드는 별도로 보존합니다. COUNT 진단은 실제 경기 모드와 구분합니다.

## 실행

장치별 환경과 모델·DB·서비스 준비는 [Pi 설정](docs/setup-pi.md), [Jetson 설정](docs/setup-jetson.md), [현재 게임 실행 문서](docs/game-runtime.md)를 따릅니다. 아래는 준비된 Pi에서 실행하는 명령입니다.

```bash
make -C pi/server
make -C pi/controller
make -C pi/bluetooth  # libbluetooth-dev 필요
```

Pi 서버와 Bluetooth 중계를 실행하고 Jetson 웹·연결기 서비스가 준비된 상태에서:

```bash
./pi/controller/iot_client 180
```

시간을 생략하면 180초입니다. 백그라운드 실행은 `python3 tools/start_pi_game.py`, 단축 시험은 `python3 tools/start_pi_game.py 20`을 사용합니다. 같은 PI 클라이언트를 중복 실행하지 않습니다.

1. 인형 복귀와 Jetson 대기가 완료된 HOME 상태를 확인합니다.
2. 웹에서 구역·결승선·방향을 설정하고 참가자가 들어섭니다.
3. STM32 시작 버튼으로 경기를 시작합니다.
4. 전원 결과 확정 또는 시간 만료 시 종료합니다. 중지 버튼은 경기 중단입니다.

## 문서

| 목적 | 문서 |
|---|---|
| 실행·게임 규칙·DB·장애 처리 | [게임 실행](docs/game-runtime.md) |
| 환경·저장소 관리 | [Pi](docs/setup-pi.md) · [Jetson](docs/setup-jetson.md) · [Git 운영](docs/repository.md) |
| 화면·영역 설정 | [웹 모니터](docs/web-monitor.md) · [카메라 설정](docs/game-camera-setup.md) |
| 모델·성능·검증 | [엔진 비교](docs/jetson-engine-optimization.md) · [관절 비교](docs/pose-comparison.md) · [현장 검증](docs/vision-validation.md) |
| 코드 이해·개발 기록 | [코드 해설](docs/code-evolution-guide.md) · [트러블슈팅](docs/troubleshooting.md) |
| DB·통신 | [DB 구성](docs/database.md) · [프로토콜](docs/protocol.md) |
| 발표 준비 | [최신 구성과 담당](docs/presentation-readiness.md) · [11장 대본](docs/presentation-script.md) · [대본 검토](docs/presentation-script-review-20261012.md) · [예상 질문 30개](docs/presentation-qa-20261012.md) |
| 이번 main 반영 검증 | [2026-10-12 통합 기록](docs/main-release-20261012.md) |

## 검증 범위와 한계

- 코드상 참가자 상한은32명이며, 실용 최대 인원을 검증한 수치는 아닙니다. 교차·가림 뒤 ID 유지와 먼 거리·조명별 오탐/누락은 추가 검증 대상입니다.
- 발표의12.76→18.53FPS는 동일598프레임 영상·YOLOv8n·입력384×640에서의 PyTorch FP32/TensorRT FP16 비교입니다. 화면·저장·Pi통신을 제외했으며 현재 관절 게임 전체 성능이 아닙니다. 지연·출력 일치도·정확도 한계는 [측정 기록](docs/jetson-engine-optimization.md)에 정리했습니다.
- 사진·시연 영상 추가, 최종 촬영 조건의 전체 경기·재시작·무선 단절 리허설은 별도 확인이 필요합니다. 놀이공원 활용은 향후 방향입니다.

## 자료 관리

비밀값·실제 로그인 설정·모델 가중치·엔진·DB·로그·사용자 영상과 음원은 커밋하지 않습니다. 예제 설정을 복사해 장치별로 준비합니다. 웹 발표 원본과 단일 HTML은 별도 발표작업 폴더에서 관리하며, 저장소에는 개발·검토 문서를 둡니다.
