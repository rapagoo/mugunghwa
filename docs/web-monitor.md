# Jetson 웹 모니터 (2026-10-06)

같은 네트워크의 브라우저에서 `http://10.10.16.120:8080/`에 접속합니다.
현재 촬영한 960×540 영상을 FP16 엔진으로 반복 재생합니다. VNC 화면 없이 작동합니다.

## 실행

Jetson 저장소 `/home/jetson/projects/mugunghwa/repo`에서:

```bash
/home/jetson/yolo_v8/bin/python jetson/web_server.py \
  --video data/video-tests/20261006-141148/20261006_141148-960x540.mp4 \
  --config data/video-tests/20261006-141148/calibration.json \
  --model .runtime/trt-models/yolov8n-384x640-fp16.engine --loop
```

웹캠은 영상 서버를 종료한 뒤 아래 명령으로 실행합니다. 카메라 입력은 640×480이며,
16:9 영상용 calibration을 그대로 쓰면 화면 비율 검증에서 거부됩니다.
카메라에 맞는 calibration이 준비되면 `--config`를 추가합니다.

```bash
/home/jetson/yolo_v8/bin/python jetson/web_server.py \
  --camera 0 --model .runtime/trt-models/yolov8n-480x640-fp16.engine
```

동일 카메라/GPU에 다른 검출 프로그램을 중복 실행하지 않습니다.
터미널 실행은 Ctrl+C로 종료합니다. 백그라운드 실행 로그는 `.runtime/web/server.log`입니다.
프로세스는 `pgrep -af jetson/web_server.py`로 확인 후 해당 PID에 `kill -TERM PID`로 종료합니다.
자동 시작 서비스 등록은 아직 하지 않았습니다.

## 화면과 API

- `/`: 반응형 한국어 모니터. 검출 인원, 임시 추적 ID, 결승선 통과 후보, 처리 시간.
- `/stream.mjpg`: 검출한 프레임과 같은 프레임에 박스를 그린 MJPEG. JPEG를 기본 최대 5 Hz로 한 번만 생성하고 모든 접속자에게 공유.
- `/frame.jpg`: 마지막 JPEG. 준비 중이면 503.
- `/api/vision`: 현재 입력·추론 상태. 브라우저에서 1초 간격 조회.
- `/api/game`: SQLite의 최신 게임, 참가자 결과, 최근 이벤트 30개 조회.

추론은 최신 프레임만 처리합니다. 입력 스레드는 영상의 미디어 시간에 맞춰 재생하고,
웹 요청은 추론을 실행하지 않습니다. 영상 반복 시 추적·통과 후보를 초기화합니다.
JPEG 최대 폭은 960, 품질은 75, `--preview-hz` 범위는 0 초과~15입니다.
처리 시간은 추론·추적·기하 판정, 검출 간격은 완료 시각 간격입니다.
결과 경과 시간은 API 조회 시 마지막 검출 완료 후 지난 시간이며 카메라부터 브라우저까지의 지연은 아닙니다.
2초 이상 결과가 갱신되지 않으면 이전 화면이라는 안내를 표시합니다.
HTTP 접속 실패·카메라 오류·추론 준비·영상 종료를 구분합니다.

## DB와 이후 연결

MariaDB 연결은 [Pi DB 설정 문서](database.md)를 따른다.
`--db-config .runtime/db/web.json` 지정 시 Pi MariaDB에서 읽고, 지정하지 않으면 아래 SQLite 경로를 사용한다.
두 DB 사이의 자동 복제/대체는 없다. MariaDB의 빈 게임 상태는 'DB 연결됨 · 게임 대기'로 표시한다.
아래 SQLite 설명은 최초 웹 모니터의 기본 경로 기록이다.

기본 DB는 **Jetson**의 `.runtime/web/game.db` (Git 제외)입니다. 실행 시 빈 테이블을 생성하고
웹 서버는 게임 데이터를 조회합니다. 게임 시작 버튼·판정 쓰기 API는 없습니다.

| 테이블 | 역할 |
|---|---|
| games | 게임 ID, phase, started_at, remaining_seconds, updated_at, authority=PI |
| participants | 게임별 참가자 ID·이름·playing/passed/failed·갱신 시각 |
| events | 이벤트 ID, 중복 방지 event_key, 종류, 참가자 ID, 발생 시각 |

DB 수신 연결은 **후속 개발**입니다. 예정 흐름은 Pi C 제어 클라이언트가 확정한 상태/이벤트를
인증된 수신 경로로 전달하고, 하나의 저장 담당 모듈이 트랜잭션으로 이 테이블들을 갱신하는 것입니다.
TCP 중계 서버의 책임은 그대로 유지합니다. 수신 규약·재접속 복구·event_key 중복 방지·시각 동기화는 연결 단계에서 구현합니다.
타임스탬프는 UTC ISO 8601로 통일하고, 남은 시간은 Pi가 계산하도록 합니다.
DB 위치를 Pi로 바꾸거나 다른 DB를 쓰더라도 브라우저의 `/api/game` 응답 구조를 유지할 수 있습니다.

현재 빈 DB에는 게임 수·남은 시간·통과/탈락 수가 없습니다. 대기 표시가 정상입니다.
관측 후보로 DB에 통과를 기록하지 않습니다. ByteTrack ID는 임시 값이며 참가자 ID 연결이 별도로 필요합니다.
화면은 DB의 저장된 남은 시간과 마지막 갱신 시각을 그대로 표시합니다. 아직 자동 카운트다운하지 않습니다.
이 웹 입력은 모니터링 전용으로, 기존 `vision_client.py`의 Pi 관측 송신은 통합 전입니다.

## 범위와 검증

Python 표준 라이브러리 HTTP/SQLite를 사용하여 Jetson의 torch·NumPy 환경과 추가 패키지를 변경하지 않았습니다.
현재 내부 네트워크 개발용 서버로 인증/TLS가 없으며 인터넷 공개용 배포는 구성하지 않았습니다.
자동 테스트는 빈 DB, Pi 상태 저장 후 재조회, 관측 후보의 판정 비기록, HTTP JSON/JPEG/MJPEG 응답을 확인합니다.
Jetson에서 전체 테스트 13개 통과, 실제 영상 검출과 브라우저 상태 갱신을 확인했습니다.
웹캠 모드의 실장 테스트와 전체 카메라→브라우저 지연 측정은 후속 검증입니다.
