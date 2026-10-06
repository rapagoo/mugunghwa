# Jetson

웹캠과 게임 영상 판정 코드를 개발할 위치입니다.

`examples/`에는 기존 `/home/jetson/python_tcp` 코드를 보존했습니다.

- `iot_client.py`: 수업 TCP 서버용 수동 클라이언트. 기본 주소는 localhost입니다.
- `iot_server.py`: 독립적인 단일 연결 TCP 서버 예제.
- `person_count.py`: OpenCV와 Ultralytics YOLO를 사용하는 웹캠 인원 검출 예제.

게임별 참가자 추적·움직임·결승선 판정과 Pi 통합은 아직 구현되지 않았습니다.
기존 클라이언트의 예외 경로에는 `sys` import 누락이 있으며 후속 개선 대상입니다.
영상 예제는 `cv2`, `ultralytics` 및 `yolov8n.pt`가 필요합니다.
현재 Jetson 환경의 패키지 버전·모델 호환성·실행 성능은 별도로 검증해야 합니다.
모델 가중치는 Git에 포함하지 않습니다.
