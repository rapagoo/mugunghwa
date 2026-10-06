# 게임 영상 입력과 영역 설정

개발 기준은 Git 저장소입니다. 장비의 기존 `game` 폴더는 원본 보관용입니다.
새 게임 영상 모듈은 `repo/jetson/game`, 실행 진입점은 `repo/jetson/vision_client.py`입니다.
Pi 제어는 계속 `repo/pi/controller`의 C 클라이언트를 확장합니다.
2026-10-06 사용자가 STM·Arduino 연결 확인 완료를 알려주어 게임 개발을 진행합니다.

## 영역·결승선 설정

PC에서 `jetson/game/calibrate.html`을 Chrome/Edge로 열면 됩니다. Python·YOLO 설치가 필요 없습니다.
이 파일은 사진·영상 선택과 설정 생성만 브라우저 안에서 처리합니다.

1. 사진이나 영상을 선택합니다. 영상은 원하는 장면에서 일시정지 후 **이 장면 사용**을 누릅니다.
2. **게임 영역**에서 구역 가장자리를 순서대로 클릭합니다. 최소 3점, 최대 32점입니다.
3. **결승선 두 점**에서 선의 양 끝을 클릭합니다.
4. **통과할 쪽**에서 선 너머 도착할 쪽의 한 점을 클릭합니다.
5. **설정 저장**으로 `calibration.json`을 저장합니다. 다운로드가 지원되지 않으면 아래 JSON을
   복사해 같은 이름의 파일로 저장합니다. **설정 불러오기**로 기존 JSON을 다시 열 수 있습니다.

되돌리기는 현재 선택한 단계의 마지막 점을 지웁니다. 전체 초기화는 모든 점을 지웁니다.
영상이 없으면 **연습 화면**으로 클릭·저장을 시험할 수 있습니다. 연습 설정은 실제 시연에 사용하지 마세요.
겹치거나 교차하는 영역, 길이 없는 결승선, 선 위의 방향점은 저장할 수 없습니다.

현재 웹캠에서 설정용 사진을 추출하려면 Jetson에서:

```bash
cd /home/jetson/projects/mugunghwa/repo
/home/jetson/yolo_v8/bin/python jetson/frame_snapshot.py --output .runtime/camera.jpg
```

PC PowerShell에서 사진을 가져오고 설정을 되돌려 보냅니다. 저장한 JSON은 현재 경로에 놓습니다.

```powershell
scp jetson:/home/jetson/projects/mugunghwa/repo/.runtime/camera.jpg .\camera.jpg
scp .\calibration.json jetson:/home/jetson/projects/mugunghwa/repo/.runtime/calibration.json
```

사진·영상·시연별 설정은 Git에서 제외되는 `.runtime` 또는 `data`에 보관합니다.
좌표는 0..1로 정규화됩니다. 비율이 같은 해상도 변경은 허용하지만 화면 비율이 1% 이상 달라지면
실행을 중단합니다. 같은 비율이어도 카메라 위치·자르기·회전·구도가 바뀌면 다시 설정해야 합니다.
폰 영상은 표시 방향이 브라우저와 OpenCV에서 같은지 미리 확인하세요.

## 웹캠·영상 공통 실행

Jetson 저장소 루트에서 실행합니다. 먼저 Pi·MCU 연결 없이 확인할 수 있습니다.

```bash
# 웹캠: GUI 없이 유한 프레임 검사
/home/jetson/yolo_v8/bin/python jetson/vision_client.py --offline --frames 30 --config .runtime/calibration.json

# 영상: 데스크톱에서 표시·반복
/home/jetson/yolo_v8/bin/python jetson/vision_client.py --video data/test.mp4 --offline --display --loop --config .runtime/calibration.json

# SSH만 있는 경우: 마지막 표시 프레임을 파일로 확인
/home/jetson/yolo_v8/bin/python jetson/vision_client.py --video data/test.mp4 --offline --frames 30 --config .runtime/calibration.json --preview-output .runtime/preview.jpg

# 실제 웹캠 관측을 PI로 전송: 기존 PI C 클라이언트가 실행 중이어야 함
/home/jetson/yolo_v8/bin/python jetson/vision_client.py --config .runtime/calibration.json
```

`--display`는 Jetson 데스크톱 화면이 필요합니다. 기본 SSH에는 DISPLAY가 없습니다.
영상 화면에서 Space는 일시정지/재개, 일시정지 중 N은 한 프레임 진행, R은 처음부터,
Q는 종료입니다. `--loop`는 끝에서 자동 반복하며 추적기를 초기화합니다.
`--speed 0.5`로 느리게 재생할 수 있습니다. 추론이 느리면 실제 재생도 느려지며 프레임을 건너뛰지 않습니다.
로그의 `media_s`는 영상 시간이며 일시정지 때 증가하지 않습니다. 반복하면 시간은 0으로,
`epoch`는 다음 번호로 바뀝니다. OpenCV의 영상 타임스탬프를 우선 사용하고 지원되지 않으면 FPS로 추정합니다.
[OpenCV 영상 속성](https://docs.opencv.org/4.10.0/d4/d15/group__videoio__flags__base.html)

영역은 사람 박스 아래쪽 중앙이 안에 있는지를 기준으로 관측 대상을 필터링합니다.
화면에는 전체 검출 박스도 보일 수 있으나 로그·PI 관측 인원은 영역 안의 대상만 포함합니다.
결승선·방향은 표시·저장까지 구현됐고, 실제 통과·움직임·탈락 판정은 아직 없습니다.
녹화 영상은 현재 `--offline`으로만 실행합니다. 영상 시간과 Pi 게임 상태의 동기화는 다음 단계입니다.
실제 웹캠의 VISION/POSITION/ACK 통신은 기존 규약을 유지합니다.

## 검증 기록

- Jetson에서 설정 유효성·영역 안/밖·영상 디코딩 종료·재시작·반복 시간 검사 3개 통과.
- 브라우저에서 이미지 불러오기, 영역·선·방향 클릭, JSON 생성 확인.
- 브라우저에서 실제 생성한 JSON을 Jetson Python에서 읽고 검증 완료.
- 합성 영상 15프레임을 실제 YOLO/ByteTrack 경로로 재생, 두 번 반복 시 추적 초기화 확인.
- 저장한 표시 프레임에서 게임 영역·결승선·방향·영상 시간 표시 확인.
- 설정을 적용한 실제 웹캠 3프레임 검사에서 관측 1회가 Pi C 클라이언트까지 왕복 ACK 통과.
- 실제 Jetson 데스크톱의 키보드 일시정지 조작과 폰 영상 정확도는 사용자 영상 준비 후 확인 필요.
