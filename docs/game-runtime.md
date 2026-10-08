# 참가자·180초 경기·DB·LCD 연결

갱신: 2026-10-08. Pi C `--game` 모드 구현. 실제 새 경기/LCD 표시는 사용자 현장 검증 필요.
기존 `--cycle-test`는 한 회차 시험용으로 보존했다. 음원은 아직 연결하지 않았다.

## 실행과 현장 시험

Pi 서버는 기존처럼 `pi/server/iot_server 5000`을 실행한다. PI 클라이언트는 하나만 실행한다.
기존 `--cycle-test` 클라이언트를 종료한 뒤 저장소 루트에서 다음을 실행한다.

```bash
python3 tools/start_pi_game.py
tail -f .runtime/game/controller.log
```

직접 터미널에서 실행하려면:

```bash
cd pi/controller
./iot_client 127.0.0.1 5000 PI --game --duration 180
```

서버·Bluetooth ARD 중계는 별도로 유지한다. Jetson 웹/연결기는 등록된 두 서비스로 자동 실행한다.
Pi 저장기는 `--game` 실행 시 자동 시작하며 DB 장애 시 로컬 기록을 재전송한다.
게임 시작 자체는 자동이 아니다. STM의 START 또는 직접 실행 터미널의 `start`로 시작한다.
시작 전에는 STM 뒤보기 완료와 Jetson IDLE 완료를 모두 확인한 `HOME`이 필요하다.

1. 웹의 구역·결승선을 대기 중 설정하고 전신/발이 보이도록 1~2명이 들어선다.
2. STM 시작 버튼을 누른다. DB 참가자 목록과 총원이 고정되고 3분이 표시되는지 확인한다.
3. 이후 다른 사람이 들어와도 참가자 수가 늘지 않아야 한다. 기존 참가자 ID가 유지되는지 본다.
4. 이동 허용 때 지정 방향으로 결승선을 넘으면 해당 참가자 통과가 1회만 확정된다.
5. 앞보기 완료 이후 정지 신호에서 움직이면 탈락한다. 이미 통과한 사람은 다시 탈락하지 않는다.
6. 전원이 통과/탈락하면 즉시 종료·뒤보기 복귀. 남은 사람이 있으면 180초에 모두 탈락·시간 0.
7. STOP은 경기 중단·뒤보기 복귀. 미완료 사람을 임의로 탈락시키지 않는다. 다시 START는 새 경기다.
8. STM/ARD COUNT 숫자를 웹 DB 결과와 비교한다. TIME을 지원하는 펌웨어에서 03:00→00:00도 확인한다.

백그라운드 실행 시 운영자 중단:

```bash
printf 'stop\n' > .runtime/game/input
```

Pi 클라이언트의 SIGINT/SIGTERM은 경기 중단 기록과 뒤보기 요청을 수행한다.
강제 전원 종료/SIGKILL은 기록을 남길 수 없으므로 웹의 오래된 기록 경고를 확인하고 새 경기로 시작한다.

## 책임과 시각

Pi C 클라이언트가 참가자, 결과, 단조 시계 기반 180초, 랜덤 정지 유지 시간을 결정한다.
참가자 확정 직후부터 제한 시간을 계산하며 모터/통신 대기 시간도 포함한다.
현재 음원 대신 이동 허용 5초 뒤 FRONT를 요청한다. FRONT OK → Jetson STOP 적용 OK → 정지 판정.
앞보기 완료 후 Pi가 2~5초 랜덤 유지 후 REAR를 요청한다. REAR OK → MOVE 적용 OK → 다음 회차.
`--move-seconds`, `--duration`으로 시험 조건을 바꿀 수 있고 `--hold-seconds`는 랜덤 대신 고정 대기다.
정지 판정 중 결승선 통과는 통과가 아닌 탈락이다. 앞보기 회전 중에는 STOP 적용 전까지 이동 허용이다.

Jetson은 기존 웹 추론 결과를 최대 5Hz로 읽는다. 별도 모델/엔진 프로세스를 만들지 않는다.
최종 결과는 Pi에서만 확정한다. 웹 미리보기 5FPS, 추론 속도, 후보 전송 5Hz, DB 조회 2초는 서로 다르다.
후보 전송에 최대 약 0.2초 대기가 더해지며 HTTP/TCP/추론 지연은 별도다. 이번 검증은 성능 측정이 아니다.
관절 시험 기준(3% 민감도 및 신뢰도/유예/지속 조건)은 그대로 유지했다.

## 참가자·메시지 검증

시작 시 구역 안에서 추적되는 고유 ID만 등록한다(최대 32명). 0명/미설정 구역/오래된 관측은 시작 거부.
이후 들어온 ID는 무시한다. ID가 사라져도 즉시 탈락시키지 않고, ID 변경을 다른 참가자에 자동 연결하지 않는다.
이 한계 때문에 실제 교차·가림 후 ID 유지 시험은 계속 필요하다. 시간 만료 시 미완료 ID도 탈락한다.
카메라 epoch/구역 설정 버전이 바뀌면 경기를 중단하고 인형을 복귀시킨다.
연결기 재로그인은 기존 경기 문맥을 복구한 것으로 취급하지 않고 경기를 중단·복귀한다.

모든 아래 메시지는 LF로 끝나며 서버의 100바이트 제한 이내를 사용한다.

| Pi 송신 | Jetson 응답 |
|---|---|
| `[JETSON]JOIN@token8` | `[PI]JOIN_BEGIN@token8@n@epoch@calrev` |
| | 참가자별 `[PI]JOIN_PERSON@token8@trackid` |
| | `[PI]JOIN_END@token8` |
| `[JETSON]GAME@gamehex32@epoch@calrev` | 후보 `[PI]OBS@gamehex32@phase_token8@trackid@PASS또는FAIL@epoch@calrev` |
| `[JETSON]GAME@END` | 경기 보고 중단 |

Pi는 경기 ID·단계 확인 토큰·카메라 epoch·설정 버전·등록 ID·허용 판정 단계를 검사한다.
종료한 참가자의 상태는 불변이다. 중복 OBS는 집계와 이벤트를 늘리지 않는다.
결승선 후보에도 생성 당시 단계 버전을 붙여 이전 MOVE의 통과 후보가 STOP 탈락으로 재사용되지 않게 한다.
단계 경계에서 늦게 도착한 이전 토큰은 버린다. 판정 지연/경계 공정성은 실제 영상으로 추가 검증해야 한다.
`--game`에서는 기존 Jetson COUNT 테스트로 게임 집계를 덮어쓸 수 없다.

## DB 저장

C가 `.runtime/game/events.jsonl`에 fsync한 상태를 독립 Python 저장기가 MariaDB에 반영한다.
게임, 고정 참가자, 결과, 단계/종료 이벤트를 하나의 트랜잭션으로 저장한다.
남은 시간은 매초 저장하지만 tick 이벤트는 목록에 쌓지 않는다.
경기별 증가 버전과 고유 이벤트 키로 중복 재전송/오래된 스냅샷 역전을 막는다.
저장 완료 오프셋을 따로 기록해 장애 복구 시 이어서 처리한다. 원본/오프셋을 임의로 지우지 않는다.
DB 장애는 `writer.log`에 비밀값 없이 오류 코드만 기록하고 재시도한다. 웹은 마지막 DB 기록임을 표시한다.
로컬 디스크 쓰기 실패는 경기를 계속 저장한 것처럼 취급하지 않고 클라이언트를 중단한다.
디스크 fsync와 TCP 송신은 동기 호출이므로 극단적인 디스크/네트워크 장애의 지연은 별도 실장 검증 대상이다.

웹은 읽기 전용 계정으로 조회한다. 장치 상태는 마지막 유효 수신 시각/ACK이며 10초 이상 수신이 없으면
연결 상태를 unknown으로 표시한다. 독립 heartbeat가 없는 MCU의 무응답은 단선 확정이 아니다.
경기 중 마지막 DB 갱신이 5초 이상 오래되면 상태 지연 경고를 표시한다.

## LCD 팀원 전달

STM과 ARD는 모두 `[PI]COUNT@전체@통과@탈락`, `[PI]TIME@남은초`를 받는다.
기존 COUNT 자체 시작형 경과 시간 타이머는 제거하고 Pi의 TIME을 표시한다.
COUNT와 TIME은 별도 패킷이므로 짧은 순간 표시가 순차 갱신될 수 있다.
예: `T:03:00 ALL:02`, `PASS:01 FAIL:00` (16×2 이내).
경기 종료 시 숫자와 시간을 유지하며 자동 RESET하지 않는다. 새 경기는 새 COUNT/TIME으로 덮어쓴다.

보드 독립 참고 구현: [파서 헤더](../firmware/common/lcd_game_protocol.h), [파서 코드](../firmware/common/lcd_game_protocol.c).
STM `server_parser.c`의 패킷 처리에서 `game_lcd_packet`을 호출하고, 렌더 콜백을 LCD 두 행 쓰기에,
송신 콜백을 `esp01_send_string`을 감싸는 void 함수에 연결한다. 기존 MOTOR/START/STOP 파서는 보존한다.
Arduino도 같은 형식으로 구현할 수 있다. 두 LCD 행은 남는 칸을 공백으로 채워 출력한다.
적용 완료 후 `[PI]APPLIED@COUNT@...`, `[PI]APPLIED@TIME@...`을 응답한다.
COUNT는 수 변경과 5초 주기 재전송, TIME은 매초 전송한다. TIME 반복 수신으로 자체 경기를 재시작하면 안 된다. 실제 보드 소스/배선은 이 저장소에 없으므로
참고 파서의 호스트 시험 통과와 실제 펌웨어 반영/표시 성공은 구분한다.

## 검증 범위

- `tests/game_integration.py`: 실제 C 서버/C 제어/Python 연결기/합성 HTTP 추론/양 보드 시뮬레이터.
  참가자 고정·외부 ID 제외·결과 불변·COUNT/TIME·5초 시험 만료·STOP·0명 거부·epoch 변경 중단·빠른 연결기 재시작 중단.
- `tests/game_database.py`: 실제 MariaDB 트랜잭션, 중복/이전 버전 재생, 전체 rollback.
- `tests/game_writer_recovery.py`: 별도 저장기 인증 실패 후 저널 유지·복구·체크포인트·중복 방지, TEST fixture 정리.
- `tests/test_game_bridge.py`: 구역 등록, 단계 경계의 이전 통과 후보 제외, STOP 통과 탈락.
- `tests/lcd_protocol.c`: Pi 형식 COUNT/TIME·LCD 16칸·ACK·잘못된 입력 검사. 실제 LCD 하드웨어 시험 아님.
- 기존 COUNT·회차·웹 API 회귀 시험 유지. 180초 실제 현장 만료와 실물 LCD는 사용자 시험 필요.

## 실물 LCD 전용 터미널 시험

`python3 tools/lcd_terminal_test.py`는 PI ID 전용 진단으로 실행 중 PI 제어기 연결을 교체한다.
실제 플레이 중 사용하지 말고 먼저 시험을 중단한다. 서버와 Bluetooth 중계는 유지한다.
Jetson STOP·STM REAR 복귀 확인 후 고정 COUNT/TIME 값과 양 보드 APPLIED를 검사하며
START/FRONT나 실제 경기 DB는 생성하지 않는다. 종료 후 `python3 tools/start_pi_game.py`로
게임 제어기를 다시 켠다. 2026-10-08 STM 7개 ACK·사용자 화면 변경 확인, ARD 7개 ACK 누락·
화면 미변경으로 미통과. [TS-LCD-001](troubleshooting.md#ts-lcd-001)에 근거와 남은 조사를 기록했다.
