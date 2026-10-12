# Jetson 영상·웹·게임 연결

카메라 입력과 YOLO 관절 관측, 경기 구역 설정, Pi 후보 송신과 웹 현황 조회를 담당합니다. 최종 통과·탈락은 Pi에서 확정합니다.

- `game/`: 영상 입력·검출/추적·기하 설정·관절 움직임 후보·게임 연결기
- `web_server.py`, `web/`: 영상 미리보기·경기 현황·설정·진단
- `build_engine.py`, `benchmark_engine.py`: TensorRT 엔진 준비와 별도 성능 비교
- `vision_client.py`, `count_test_client.py`: 관측/가상 COUNT 진단
- `examples/`: 기존 수업 예제 보존

모델·엔진은 Git에 포함하지 않습니다. 설치와 서비스 구성은 [Jetson 설정](../docs/setup-jetson.md), 실제 게임은 [게임 실행](../docs/game-runtime.md), 모델 입력과 측정 범위는 [엔진 비교](../docs/jetson-engine-optimization.md)·[관절 비교](../docs/pose-comparison.md)를 참고하세요.
