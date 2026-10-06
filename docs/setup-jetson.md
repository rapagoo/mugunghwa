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
확인 당시 `/dev/video*` 장치는 발견되지 않았습니다.
영상 실시간 실행은 웹캠 연결과 GUI 표시 환경을 준비한 뒤 검증해야 합니다.
문법 검사와 패키지 위치 확인은 실제 영상 처리 동작을 보장하지 않습니다.
