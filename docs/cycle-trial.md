# Pi・STM・Jetson 한 회차 자동 시험

2026-10-07. 실제 장비 제어를 사용하는 **시험 모드**다.
음원/랜덤 시간/참가자 확정/DB 결과/실제 탈락/후보의 Pi 보고는 이번 단계에 포함하지 않았다.
Jetson은 기존 관절 웹 프로세스를 그대로 사용하며 별도 모델을 추가 실행하지 않는다.

## 흐름

1. 시작 요청 → Pi가 Jetson에 이동 허용 통지 → 웹 추론 적용 확인.
2. Pi가 STM에 MOTOR@FRONT 송신 → FRONT@OK 수신.
3. Pi가 Jetson에 정지 통지 → 실제 추론 적용 확인.
4. Pi가 FRONT@OK 수신 시점부터 고정5초를 관리한다.
5. 5초 경과 및 Jetson 적용 확인 후 MOTOR@REAR 송신.
6. REAR@OK 수신까지 정지 판정 유지 → 이동 허용 통지·추론 적용 확인 → 회차 완료.

완료 후 자동 반복하지 않는다. 새 시작 요청으로 다음 한 회차를 수행한다.
Pi 타이머는 단조 증가 시계를 사용하고 수신을 막는 sleep으로 구현하지 않았다.

## 프로토콜

STM 명령/응답은 합의대로 유지한다. Pi에 송신하는 STM 완료 문자열:
`[PI]MOTOR@FRONT@OK\n`, `[PI]MOTOR@REAR@OK\n`.

Pi→Jetson은 시험용 확인 번호를 추가했다:

```text
Pi 송신:     [JETSON]PHASE@STOP@1234abcd
Jetson 수신: [PI]PHASE@STOP@1234abcd
Jetson 송신: [PI]PHASE@STOP@1234abcd@OK
Pi 수신:     [JETSON]PHASE@STOP@1234abcd@OK
```

MOVE/IDLE도 같은 형식. 번호는 Pi가 생성하는8자리16진수다. Pi는 현재 요청의
단계/번호/발신자JETSON과 일치하는 확인만 인정한다. Jetson은 로컬 HTTP 요청 접수뿐 아니라
신선한 관절 추론 결과에 해당 단계가 적용된 뒤 OK를 보낸다.
STM 응답에는 아직 회차 번호가 없어 이전 회차의 같은 방향 OK가 매우 늦게 도착하는 경우는
완전히 구별할 수 없다. 이번 회차 동안 잘못된 방향/중복/중단 후 완료는 무시한다.

Pi는 TRIAL@PING, Jetson은 신선한 웹 추론이 있으면 TRIAL@READY를1초마다 보낸다.
3초 이상 연결 신호가 없거나 추론이 준비/오류/수동 단계 변경 상태이면 시험을 중단한다.
회전/단계 확인 대기10초 초과도 중단하며 다음 회전 명령을 보내지 않는다.
시험 중단은 서보의 물리적 비상정지를 보장하지 않는다. 이미 시작된 회전은 STM 펌웨어 동작을 따른다.

## 실행

서버5000번은 유지한다. 기존 수동 클라이언트와 자동 클라이언트가 동시에PI로,
다른 Jetson 송신기와 연결 클라이언트가 동시에JETSON으로 로그인하면 안 된다.

Pi에서 직접 실행:

```bash
cd /home/pi/Projects/mugunghwa/repo
make -C pi/controller
./pi/controller/iot_client 127.0.0.1 5000 PI --cycle-test --hold-seconds 5 --ack-timeout 10
```

터미널에 `start` + Enter로 한 회차, `stop` + Enter로 시험 중단.
STM 버튼의 `[PI]START`/`[PI]STOP`도 같은 동작을 한다.
옵션 없이 실행하면 기존 COUNT 테스트 동작을 유지한다.

Jetson에서:

```bash
cd /home/jetson/projects/mugunghwa/repo
/home/jetson/yolo_v8/bin/python -u jetson/phase_test_client.py
```

브리지 시작/연결 상실/종료는 로컬 시험을 대기로 돌린다. MOVE 적용 때도 로컬 시험을
초기화해 이전 결승 통과 후보가 정지 감시 대상을 제외하지 않도록 한다.
구역 설정과 모델은 유지하지만 웹의 수동 시험 버튼을 자동 회차 중 조작하면 회차를 중단한다.

## 배포된 백그라운드 시험의 운영

Pi `tools/start_pi_cycle_trial.py`는 자동 시작하지 않고 대기하는 제어기를 실행한다.
입력 FIFO `.runtime/cycle-test/input`, 로그 `.runtime/cycle-test/controller.log`,
PID `.runtime/cycle-test/controller.pid`를 남긴다.

```bash
cd /home/pi/Projects/mugunghwa/repo
printf 'start\n' > .runtime/cycle-test/input
printf 'stop\n' > .runtime/cycle-test/input
tail -f .runtime/cycle-test/controller.log
```

FIFO는 제어기가 실행 중일 때 사용한다. 재부팅 자동 실행은 설정하지 않았다.
Jetson 백그라운드 브리지 로그/PID는 `.runtime/cycle-test/bridge.log`, `bridge.pid`다.
웹의 관절 시험 단계에서 stop/move를 확인하고 관절 점수/후보를 관찰한다.
화면 갱신은5Hz이며 전체 통신/물리 동작 지연은 별도 검증해야 한다.

## 자동 검증

Pi의 별도15001번 서버, STM 시뮬레이터, 실제 C 제어기/Python 단계 브리지,
HTTP 서버와 모의 신선한 추론을 사용했다. 정상회차/잘못된 방향/중복·분할 완료/
완료 타임아웃/중단 뒤 늦은 완료/Pi 연결 신호 상실에서의 Jetson 대기 복귀 통과.
C `-Wall -Wextra -Werror` 빌드 통과. 실물 모터/관절 정확도 검증과 구분한다.

```bash
make -C pi/server
make -C pi/controller CFLAGS='-O2 -Wall -Wextra -Werror'
python3 tests/cycle_integration.py
python3 tests/count_integration.py
```

[전체 게임 설계](game-communication-sequence.md), [관절 시험](pose-motion-trial.md).

## 2026-10-07 실제 장비 왕복 검증

Pi 기존 서버5000번을 유지하고 PI 자동 시험 제어기와 JETSON 단계 연결기를 실행했다.
별도의 새 추론 프로세스 없이 현재 관절 웹에 적용했다.
운영 입력으로 한 회차를 시작해 실제STM FRONT@OK/REAR@OK에 따른 상태 진행,
Jetson MOVE→STOP→MOVE 추론 적용 확인, Pi의 `CYCLE DONE`을 확인했다.
Jetson 로그 확인 번호는6ac5fc70/71/72였다. 고정 유지5초/완료 제한10초 조건이다.
STM 서보 각도·방향의 육안 확인과 사람이 정지 구간에서 움직인 통합 정확도 검증은 미실행이다.
명령→물리 완료/화면 표시 전체 지연 수치는 이번 시험에서 측정하지 않았다.

Pi 제어기와 Jetson 연결기를 실행 상태로 남겼다. 회차 완료 후 움직임 허용 상태이며,
자동 반복은 하지 않는다. STM START 또는 Pi FIFO start로 다음 회차를 시작할 수 있다.
실제 로그는 각 장비 `.runtime/cycle-test/`에 있고 Git에서 제외한다.
