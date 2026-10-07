# Jetson 웹 모니터 (2026-10-07 갱신)

같은 네트워크의 브라우저에서 `http://10.10.16.120:8080/`에 접속합니다.
현재 640×480 웹캠을 FP16 엔진으로 실시간 검출합니다. VNC 화면 없이 작동합니다.

## 웹에서 계속 테스트

1. 메인 화면의 **구역 설정**을 누릅니다.
2. 현재 웹캠 사진에서 게임 구역 가장자리를 순서대로 3~32점 클릭합니다.
3. **2. 결승선**을 누르고 양 끝 두 점을 클릭합니다.
4. **3. 통과 방향**을 누르고 선을 넘은 뒤 도착할 쪽을 클릭합니다.
5. **저장하고 테스트 화면으로**를 누릅니다. 재시작 없이 다음 검출부터 적용됩니다.

구역 안 인원은 박스 하단 중앙(발 위치 추정)이 구역에 있는지로 계산합니다.
결승선 통과 후보는 기존 방향·유한 선분·여유 폭·추적 시간 간격 검사로 계산합니다.
ROI 밖 사람도 전체 검출 인원에는 포함되며 화면에서 별도 구역 안 인원을 표시합니다.
이 화면은 검출/통과 후보 시험이며 정지 중 움직임·최종 통과/탈락·Pi 관측 전송은 아직 연결 전입니다.

설정 페이지는 `/camera.jpg`의 박스/기존 선이 없는 웹캠 사진을 사용합니다.
**현재 화면 다시 가져오기**로 배경만 갱신합니다. **점 모두 지우기**는 편집 중 점만 비우고,
**저장된 설정 해제**는 서버 설정과 파일을 해제합니다. 편집 중 검출은 계속됩니다.
저장 시 검출 추적/기존 통과 후보를 초기화하므로 진행 중 게임에 설정을 바꾸는 기능은 추후 제한해야 합니다.
다른 브라우저가 먼저 저장하면 409로 덮어쓰기를 거부합니다. 페이지를 새로 열어 최신 설정을 불러옵니다.
잘못된 다각형·선·방향·화면 비율은 서버에서 검사하고 마지막 유효 설정을 유지합니다.

카메라 설정은 Jetson `.runtime/web/calibration-camera.json`에 원자적으로 저장하며 Git 제외입니다.
재시작 후 불러옵니다. 영상 재생 시에는 `--calibration-store .runtime/web/calibration-video.json`을 지정해
웹캠 설정과 분리합니다. 카메라 위치/렌즈/화면 비율을 바꾼 경우 다시 설정합니다.

## 재부팅 자동 실행

Jetson의 시스템 서비스 `mugunghwa-web.service`를 설치하고 enabled/active를 확인했습니다.
Jetson 사용자로 웹캠·카메라용 480×640 FP16 엔진·Pi MariaDB 조회 설정을 사용합니다.

```bash
systemctl status mugunghwa-web.service
sudo systemctl restart mugunghwa-web.service
journalctl -u mugunghwa-web.service -n 50 --no-pager
```

서비스 파일은 `deploy/mugunghwa-web.service`입니다. 재등록은 `sudo install -m 644
deploy/mugunghwa-web.service /etc/systemd/system/` 후 daemon-reload와 enable --now를 사용합니다.
프로세스 오류는 systemd가 재시작하고, 카메라 입력/추론 오류는 웹 페이지를 유지한 채 3초 간격 재시도합니다.
카메라가 늦게 연결돼도 복구하도록 구현했으며 실제 USB 분리/재연결 반복 검증은 남아 있습니다.
모델 준비 중에는 준비 메시지와 첫 웹캠 사진이 보이고 준비 후 스트림이 계속 갱신됩니다.
이번 검증은 서비스 재시작/저장 유지까지이며 실제 장비 재부팅 시험은 별도로 남겼습니다.

## 실행

Jetson 저장소 `/home/jetson/projects/mugunghwa/repo`에서:

```bash
/home/jetson/yolo_v8/bin/python jetson/web_server.py \
  --video data/video-tests/20261006-141148/20261006_141148-960x540.mp4 \
  --config data/video-tests/20261006-141148/calibration.json \
  --calibration-store .runtime/web/calibration-video.json \
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
현재 웹캠은 위 시스템 서비스로 관리하므로 수동 시험 전에 `sudo systemctl stop mugunghwa-web.service`로
중복 실행을 막고, 끝나면 `sudo systemctl start mugunghwa-web.service`로 복구합니다.

## 화면과 API

- `/`: 반응형 한국어 모니터. 검출 인원, 임시 추적 ID, 결승선 통과 후보, 처리 시간.
- `/stream.mjpg`: 검출한 프레임과 같은 프레임에 박스를 그린 MJPEG. JPEG를 기본 최대 5 Hz로 한 번만 생성하고 모든 접속자에게 공유.
- `/frame.jpg`: 마지막 JPEG. 준비 중이면 503.
- `/camera.jpg`: 박스/선이 없는 마지막 카메라 JPEG. 설정 배경용.
- `/calibrate`: 현재 카메라 구역/결승선 클릭 설정 화면.
- `/api/calibration`: GET으로 현재 설정·버전 조회, POST로 설정 저장/해제. LAN 개발용이며 공개 인증 기능은 아직 없음.
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
2026-10-07 웹캠 640×480, 카메라용 FP16 엔진에서 실제 브라우저 표시와 클릭 설정 저장,
검출 적용 버전·ROI 인원 출력·서비스 재시작 후 설정 유지·설정 해제를 확인했습니다.
자동 테스트 16개 통과. 전체 카메라→브라우저 지연·게임 환경 다인 판정 검증은 후속입니다.
