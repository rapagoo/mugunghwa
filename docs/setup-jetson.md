# Jetson 작업 환경

작업 폴더: `/home/jetson/projects/mugunghwa/repo`

기존 `python_tcp`, `yolo_v8`, `lecturecode`는 보존했습니다.
새 개발은 `repo/jetson`에서 진행합니다.

```bash
cd /home/jetson/projects/mugunghwa/repo
git status
git pull --ff-only
source /home/jetson/yolo_v8/bin/activate
cd jetson/examples
python person_count.py
```

Python은 3.8.10이며 기존 `yolo_v8` 가상환경에 OpenCV와 Ultralytics가 있습니다.
시스템 Python에는 Ultralytics가 없어 영상 예제는 가상환경을 사용합니다.
`yolov8n.pt`는 기존 환경에서 새 `jetson/examples`로 복사하며 Git에서 제외합니다.
2026-10-06 Python 예제 세 개의 문법 검사를 통과했습니다.
웹캠 연결 후 `/dev/video0`에서 640×480 프레임 5개를 읽었습니다.
GPU에서 `imgsz=320` YOLO 추론 3회를 확인했습니다. 사람 검출 수는 모두 0명이었습니다.
최초 실행 약 31.4초, 후속 추론 약 44ms 두 회는 단기 확인값이며 장기 FPS/정확도 측정이 아닙니다.
GUI 없이 재확인하려면 저장소 루트에서 실행합니다.

```bash
/home/jetson/yolo_v8/bin/python jetson/camera_smoke_test.py --frames 3
make -C jetson/tcp_client
```

통신 시험은 [공용 클라이언트](../tools/tcp_client/README.md)를 참고하세요.
현재 통신 송신기는 C 실행 파일 대신 `python3 jetson/count_test_client.py`입니다.
표준 라이브러리만 사용하며 가상 COUNT를 PI로 보내고 응답을 출력합니다.
YOLO용 가상환경은 영상 검사 시 사용합니다. 현재 가상 COUNT와 영상 처리는 분리되어 있습니다.

실제 웹캠 관측 송신기는 `jetson/vision_client.py`입니다.
[실행 방법·관측 메시지·개발 단계](jetson-development.md)를 참고하세요.
기존 YOLO 환경에 ByteTrack용 `lapx==0.5.12`를 추가했습니다.

게임 개발은 기존 장비 `game` 폴더가 아닌 Git 저장소 `repo/jetson/game`에서 진행합니다.
[영상 입력과 클릭 설정](game-camera-setup.md)을 참고하세요.
