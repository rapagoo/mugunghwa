# Jetson Nano 추론 엔진 최적화

Python과 기존 관측 프로토콜을 유지하고 YOLOv8n 추론 엔진만 비교한다.
장비는 TensorRT 8.0.1.6 / CUDA 10.2 / L4T R32.6.1이다.
환경 전체를 업그레이드하지 않았고 ONNX 1.14.1 / protobuf 3.20.3은
`.runtime/trt-setup/vendor`에 준비해 변환/빌드 프로세스에만 적용한다.

## 입력과 파일

960×540 영상의 기존 PyTorch 실제 입력은 `1×3×384×640`이다.
640×480 웹캠의 기존 입력은 `1×3×480×640`이다.
정적 엔진은 이 크기를 고정하므로 입력별 엔진을 만든다.
`game/detector.py`가 엔진 메타데이터의 크기로 전처리를 설정한다.
`.pt` 모델의 기존 `--imgsz`와 기본 동작은 유지한다.

`build_engine.py`는 TensorRT 8 전용으로, 명시 배치 1 / opset 12 / workspace 512MiB를 사용한다.
ONNX 단순화나 추가 자동 패키지 설치를 실행하지 않는다.
빌드는 Nano 자체에서 하고, 변환 프로세스와 빌드 프로세스를 분리해 메모리 중복을 줄인다.
엔진에는 Ultralytics가 읽는 JSON 메타데이터 헤더를 포함한다.
엔진 빌더는 기존 엔진 출력 경로를 덮어쓰지 않는다.

```bash
cd /home/jetson/projects/mugunghwa/repo
# 원본 모델 복사본으로 실행; .runtime/trt-models/yolov8n.pt는 사전 준비
PYTHONPATH=.runtime/trt-setup/vendor /home/jetson/yolo_v8/bin/python \
  jetson/build_engine.py export --model .runtime/trt-models/yolov8n.pt --shape 384 640
PYTHONPATH=.runtime/trt-setup/vendor /home/jetson/yolo_v8/bin/python \
  jetson/build_engine.py build --model .runtime/trt-models/yolov8n.onnx \
  --output .runtime/trt-models/yolov8n-384x640-fp32.engine --shape 384 640
# 다른 새 출력 경로에 --fp16을 추가해 FP16 엔진 생성
```

웹캠용 ONNX는 별도 모델 복사본에서 `--shape 480 640`으로 생성한다.
같은 ONNX 경로의 크기를 바꾸면 영상용 ONNX 재현 파일이 사라지므로 입력별 복사본을 유지한다.
엔진은 장비/버전/입력 크기에 의존하는 산출물이며 Git 제외 `.runtime`에 보관한다.

## 비교 방법

`benchmark_engine.py`는 화면이나 Pi 통신 없이 같은 소스/전처리/추적 조건에서 검출 증거와 타이밍을 기록한다.
5프레임 준비 후 추적을 초기화하며 영상은 처음부터 전체 프레임을 검사한다.
프레임 읽기·검출/추적·기하 계산의 평균/전체 p95, 순수 추론 평균/p95,
검출/추적 프레임 수·임시 ID·통과 후보를 기록한다. 결과 파일 저장 시간은 측정에서 제외한다.
엔진과 PyTorch 비교는 GPU를 동시에 사용하는 프로세스를 두지 않고 순서대로 실행한다.
사람 박스 출력 여부는 정답 주석 기반 정확도 지표가 아니다.

```bash
/home/jetson/yolo_v8/bin/python jetson/benchmark_engine.py \
  --model .runtime/trt-models/yolov8n-384x640-fp16.engine \
  --video data/video-tests/20261006-141148/20261006_141148-960x540.mp4 \
  --config data/video-tests/20261006-141148/calibration.json \
  --report .runtime/trt-benchmark/video-fp16.json
# 웹캠: --video/--config 생략, 해당 웹캠 엔진 --model, --camera 0 --frames 120
```

실시간/VNC는 `realtime_video.py --model ...engine`, 웹캠 클라이언트는
`vision_client.py --model ...engine`로 선택한다. 기본 `.pt` 경로는 유지한다.
TensorRT 8.0의 `np.bool` 참조는 엔진을 선택한 프로세스에서만 호환 처리한다.
PyTorch 경로에서는 TensorRT를 import하지 않는다.
영상 엔진을 웹캠에 적용해 입력을 줄이는 방식은 동일 조건 성능 비교에 사용하지 않는다.
`realtime_video.py --loop --cycles 3`은 세 번 반복 후 종료해 화면을 포함한 비교에 사용할 수 있다.
일반 확인에는 `--cycles`를 생략해 계속 반복한다.

## 웹 화면 연결

웹캠/영상의 검출 결과는 Jetson에서 처리한 최신 화면을 HTTP 영상 스트림으로 보내 웹에서 볼 수 있다.
첫 구현은 최신 결과 JPEG를 제한된 빈도로 보내는 MJPEG 방식과 상태 조회를 분리하는 구조가 적합하다.
게임 상태/인원/연결 상태는 별도 JSON으로 제공하고, 이후 저지연 필요에 따라 WebRTC를 검토한다.
검출/후보/검출 지연은 Jetson에서, 확정된 경기 단계·통과/탈락·최종 인원은 Pi 제어 클라이언트에서 가져온다.
웹을 추가해도 최종 게임 판정 책임을 Jetson이나 중계 서버로 옮기지 않는다.
추론·게임 판정 주기와 화면 전송 주기를 분리하고, 보는 사람이 늘어도 추론을 중복 실행하지 않는다.
웹 미리보기 인코딩/전송도 비용이 있으므로 켜짐/꺼짐 조건의 지연을 비교해야 한다.
현재 웹 스트리밍 서버는 구현 전이며, 이번 변경은 추론 엔진 선택과 비교 도구다.

구현 시 참고: [Flask 스트리밍 응답](https://flask.palletsprojects.com/en/stable/patterns/streaming/),
[브라우저 WebRTC API](https://developer.mozilla.org/en-US/docs/Web/API/WebRTC_API).

## 2026-10-06 영상 전체 비교 결과

960×540 H.264 영상 598프레임, 실제 입력 `1×3×384×640`, 같은 YOLOv8n / 신뢰도 0.35 / ByteTrack.
준비 5프레임 후 순차 실행했으며 화면·저장·Pi 통신 비용은 제외했다.

| 항목 | PyTorch FP32 | TensorRT FP32 | TensorRT FP16 |
| --- | ---: | ---: | ---: |
| 처리 FPS | 12.76 | 15.49 | 18.53 |
| 전체 평균(ms) | 78.37 | 64.56 | 53.97 |
| 전체 p95(ms) | 85.67 | 68.53 | 56.44 |
| 순수 추론 평균(ms) | 57.63 | 42.94 | 32.01 |
| 순수 추론 p95(ms) | 58.27 | 43.19 | 32.21 |
| 사람 검출 프레임 | 594 | 594 | 594 |
| ID 1 추적 프레임 | 572 | 572 | 572 |
| ROI 검출 프레임 | 512 | 512 | 512 |
| 결승선 후보 수 | 1 | 1 | 1 |
| 후보 교차 시간(초) | 8.195696 | 8.195696 | 8.195438 |
| 후보 확인 시간(초) | 8.220339 | 8.220339 | 8.220339 |

FP16 전체 처리량은 기준선 대비 약 1.45배, 순수 추론 평균 시간은 약 44% 감소했다.
FP16이 모든 박스 좌표까지 비트 단위로 같다는 의미는 아니다.
같은 594개 단일 박스 프레임의 PyTorch 대비 박스 IoU는 FP32 평균 0.9999996/최소 0.999996,
FP16 평균 0.993876/최소 0.934298이었다. 이는 기존 출력과의 일치도이며 정답 박스 정확도가 아니다.
위 검출/추적/후보 관측은 이 한 명 영상에서 유지됐으며 다인·가림·움직임 판정 정확도는 별도 검증한다.
FP32는 기준선과 같은 관측 수와 통과 시점을 확인하는 대조 엔진으로 보관한다.
산출물은 로컬/Jetson `.runtime/trt-benchmark/video-{pytorch,fp32,fp16}.json` 및 Jetson의 대응 `.frames.jsonl`이다.

## 2026-10-06 실제 웹캠 비교

640×480 웹캠 / 모델 입력 `1×3×480×640` / 모델 입력 설정 640,
각 120프레임 순차 측정, 준비 5프레임 제외, 화면·파일 저장·Pi 통신 제외.

| 항목 | PyTorch FP32 | TensorRT FP16 |
| --- | ---: | ---: |
| 전체 처리 FPS | 9.86 | 13.52 |
| 전체 평균(ms) | 101.38 | 73.97 |
| 전체 p95(ms) | 89.97 | 69.85 |
| 순수 추론 평균(ms) | 68.83 | 40.57 |
| 순수 추론 p95(ms) | 68.75 | 40.79 |
| 사람 검출이 있는 프레임 | 120 | 120 |
| 추적 ID가 있는 프레임 | 118 | 118 |

영상 처리와 달리 두 측정은 서로 다른 시점의 실제 카메라 입력이다.
대상 위치/인원/ID를 같은 프레임 기준으로 비교한 정확도 검증은 아니다.
짧은 측정이며 일부 큰 지연 표본 때문에 평균이 p95보다 클 수 있다. 장시간/대표 장면 재측정이 필요하다.
전체 처리량은 이 조건에서 약 1.37배 증가했고 순수 추론 평균 시간은 약 41% 줄었다.
앞선 20프레임 측정의 11.55fps나 기본 모델 입력 320의 15.38fps와 같은 조건의 수치로 섞지 않는다.

기존 `vision_client.py`에서도 웹캠 FP16 엔진 + `--offline --frames 30` 실행을 확인했다.
1~2명 관측과 추적 출력이 생성됐으며 Pi/MCU로 시험 데이터를 보내지는 않았다.
웹캠에서 실제 관측을 Pi로 보내려면 준비된 서버/PI C 클라이언트 상태를 확인하고 다음처럼 실행한다:

```bash
/home/jetson/yolo_v8/bin/python jetson/vision_client.py \
  --model .runtime/trt-models/yolov8n-480x640-fp16.engine
# --offline 추가: Pi에 접속하지 않는 카메라 확인
```

기존 `.pt` 기본 경로와 모델 입력 320은 바꾸지 않았다.
기존 PyTorch 모델 입력 640 비교가 필요하면 `--imgsz 640`을 명시한다.
엔진을 선택하면 모델 입력은 엔진 메타데이터의 480×640으로 고정된다.
보고서는 `.runtime/trt-benchmark/camera-{pytorch,fp16}.json`에 보관했다.

## VNC 실시간 영상 비교

같은 960×540 영상·1배속·VNC 화면, 각 엔진 세 번 반복 재생했다.
초기 반복을 제외한 다음 두 반복의 검출 완료 표본을 합쳐 비교했다.
표본 수는 PyTorch 190개, FP16 317개다. 프레임 큐를 쌓지 않고 최신 프레임만 검사한다.

| 지표 | PyTorch | FP16 |
| --- | ---: | ---: |
| 검출 갱신 간격 평균(ms) | 106.34 | 63.79 |
| 검출 갱신 간격 p95(ms) | 157.39 | 81.55 |
| 프레임 전달→결과 완료 평균(ms) | 118.60 | 74.67 |
| 프레임 전달→결과 완료 p95(ms) | 178.69 | 98.28 |
| 두 반복 실제 재생 시간(초) | 10.094 / 10.095 | 10.096 / 10.088 |
| 두 반복 앱 표시 수(598장 중) | 405 / 473 | 494 / 523 |

세 번 모두 각 반복당 통과 후보 1회를 관측했다.
화면 제출·VNC 단말 표시·카메라 센서·Pi/MCU 전달 지연을 위 결과 지연에 포함한 값은 아니다.
VNC 단말의 수신 FPS 자체는 측정하지 않았다. 실제 다인/장시간 실행은 별도 검증한다.

첫 반복에는 두 엔진 모두 약 1.3~1.4초의 큰 앱 표시 지연 표본이 있었다.
첫 프레임에 인물이 없으면 준비 실행이 후처리/추적 경로를 충분히 다루지 않을 수 있어,
최종 `realtime_video.py`는 약 2초 위치의 프레임을 준비 입력으로 사용한 뒤 소스를 다시 열고
처음부터 재생한다. 해당 프레임을 못 읽으면 첫 프레임을 사용한다.
이 보완 전의 첫 반복 성능을 안정 구간 성능과 섞지 않는다.
보완 후에도 첫 반복 최대 표시 지연 약 1.94초가 관측돼 초기 지연은 해결되지 않았다.
다음 반복 평균 갱신 간격은 약 65/66ms였다. 시작 직후 성능을 안정 구간의 64ms로 보장하지 않는다.
타이밍 로그는 `.runtime/trt-benchmark/realtime-{pytorch,fp16}.jsonl`,
PC 요약은 `.runtime/trt-benchmark/realtime-summary.json`이다.

현재 VNC 확인 명령:

```bash
DISPLAY=:0 XAUTHORITY=/run/user/1000/gdm/Xauthority \
/home/jetson/yolo_v8/bin/python jetson/realtime_video.py \
  --video data/video-tests/20261006-141148/20261006_141148-960x540.mp4 \
  --config data/video-tests/20261006-141148/calibration.json \
  --model .runtime/trt-models/yolov8n-384x640-fp16.engine --loop \
  --metrics .runtime/trt-benchmark/realtime-fp16-final.jsonl
```
