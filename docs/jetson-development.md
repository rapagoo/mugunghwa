# Jetson 영상 개발 — 1단계

STM32 펌웨어와 Wi-Fi 연결을 기다리는 동안 카메라 관측 경로부터 개발합니다.
Jetson Python → Pi TCP 서버 → Pi C 제어 클라이언트 구조를 그대로 사용합니다.
Pi는 관측을 기록하고 수신 확인을 반환합니다. 서버는 주소 중계만 담당합니다.

## 실행

Pi 저장소 루트에서 서버가 실행 중인 상태로 새 제어 클라이언트를 실행합니다.
기존 PI 클라이언트가 있으면 먼저 Ctrl+C로 종료합니다. 서버·Bluetooth는 계속 사용할 수 있습니다.

```bash
make -C pi/controller
./pi/controller/iot_client 127.0.0.1 5000 PI
```

Jetson 저장소 루트에서 실행합니다. JETSON ID를 사용하는 COUNT 테스트는 먼저 종료합니다.

```bash
/home/jetson/yolo_v8/bin/python jetson/vision_client.py --frames 100
# 계속 실행: --frames 생략, 종료: Ctrl+C
# Jetson 화면에 박스·추적 ID 표시: --display 추가 (SSH만으로는 화면을 열 수 없음)
```

YOLOv8n, 입력 크기 320, 사람 클래스만 검출하고 ByteTrack으로 임시 ID를 붙입니다.
기본 관측 송신은 초당 최대 2회이며 추론은 프레임마다 실행합니다.
초기 GPU 준비를 마친 뒤 TCP에 로그인합니다. 영상·사진은 저장하지 않습니다.
실행 중 자동 의존성 설치는 껐습니다. 기존 YOLO 가상환경에 `lapx==0.5.12`만 추가했습니다.
새 장비에는 기존 호환 YOLO 환경과 모델 파일을 별도로 준비해야 합니다.
추가 의존성은 `jetson/requirements-tracking.txt`에 기록했습니다.
사용 API는 [Ultralytics 추적 문서](https://docs.ultralytics.com/modes/track/)의
`model.track(..., persist=True, tracker="bytetrack.yaml")`입니다.

## 2026-10-06 검증

- Pi C 클라이언트는 `-Wall -Wextra -Werror` 빌드를 통과했습니다.
- 격리된 15000번 서버에서 영상 ACK·범위 초과/형식 오류 차단·MCU 미전달을 확인했습니다.
- 기존 COUNT 양쪽 MCU 전달·APPLIED 응답·분할/여러 줄 수신 검사도 통과했습니다.
- 실제 Jetson 웹캠 30프레임에서 사람 1명, 임시 ID 1이 유지됐습니다.
- 별도 Pi 15001번 서버로 전송한 28회 관측 모두 ACK를 받았고 발 위치도 Pi 로그에 표시됐습니다.
- 첫 두 영상 추론은 약 1221ms/503ms, 이후 약 49~65ms였습니다. 장기 FPS·다인원 정확도 검증은 아닙니다.
- 테스트 영상은 저장하지 않았으며 임시 서버·제어 클라이언트·영상 프로그램은 검사 후 종료했습니다.
- 기존 5000번 서버와 사용자가 실행한 프로그램은 유지했습니다. 실행 중인 기존 PI 프로그램은
  업데이트 전 바이너리이므로 영상 수신 시험 전 PI 클라이언트만 재실행해야 합니다.

## 실험용 관측 메시지

각 줄은 LF로 끝납니다. 기존 최대 100바이트 메시지 범위에 맞춥니다.

```text
[PI]POSITION@boot@seq@track_id@center_x@foot_y
[PI]VISION@boot@seq@people@tracked
```

`boot`는 실행마다 바뀌는 8자리 소문자 16진 문자열, `seq`는 처리 프레임 번호입니다.
발 위치는 검출 박스 아래쪽 중앙이며 좌표는 화면 너비·높이에 대해 0..1000으로 정규화합니다.
`people`은 해당 추론 결과 박스 수, `tracked`는 임시 ID가 부여된 박스 수입니다.
ByteTrack 특성상 검출 직후 미확정 박스가 출력에서 제외될 수 있어 실제 사람 수의 정답이 아닙니다.
POSITION 줄들을 먼저 보내고 VISION 요약을 마지막에 보냅니다.
Pi의 응답 `[PI]VISION_ACK@boot@seq`는 요약 수신만 확인하며 게임 판정·MCU 반영을 뜻하지 않습니다.
Pi는 현재 위치들을 게임 상태에 누적하거나 프레임 완전성·순서를 검증하지 않습니다.
seq/track_id는 1..2147483647, 인원 수는 0..999, tracked ≤ people이어야 합니다.

## 다음 개발 순서

1. 웹캠 구도를 고정하고 참가 등록 영역·결승선을 정합니다.
2. 가림·재진입 시험 후 임시 track_id와 참가 participant_id를 분리합니다.
3. Jetson은 이동·결승선 통과 후보를 보내고 Pi가 게임 단계와 생존 상태를 확인해 판정합니다.
4. Pi가 확정한 COUNT·장치 명령을 MCU로 보냅니다. STM 연결 시험은 독립적으로 계속합니다.

아직 참가 등록, 움직임 탈락 판정, 결승선 통과, 게임 상태 전환은 구현하지 않았습니다.
통신 끊김·ACK 지연·카메라 읽기 실패 시 프로그램은 종료합니다. 재접속과 지연 계측은 후속 작업입니다.
임시 ID는 가림·재실행으로 바뀔 수 있으며 자동 탈락 판정에 바로 사용하면 안 됩니다.
