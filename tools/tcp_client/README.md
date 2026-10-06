# 공용 TCP 테스트 클라이언트

Pi에서 수정한 수동 클라이언트와 3초 간격 LCD COUNT 테스트를 공용 소스로 이동했습니다.
`pi/controller`와 `jetson/tcp_client`의 Makefile이 같은 소스를 각 장비에서 빌드합니다.
Pi의 기존 실행 경로와 기본 `--lcd-demo` 대상 `ARD`는 유지합니다.

Jetson에서:

```bash
cd /home/jetson/projects/mugunghwa/repo
make -C jetson/tcp_client
./jetson/tcp_client/iot_client 10.10.16.90 5000 JETSON --lcd-demo --target STM --cycles 3
```

Pi 제어 클라이언트에서 STM으로:

```bash
./pi/controller/iot_client 127.0.0.1 5000 PI --lcd-demo --target STM --cycles 3
```

`--cycles N`은 N개 메시지를 보내고 마지막 응답을 최대 3초 기다린 뒤 종료합니다.
생략하면 계속 전송합니다. 인증 성공 후 처음 한 개를 즉시 전송합니다.
COUNT는 기존 여섯 개의 가상 총인원·성공·실패 패턴이며 실제 카메라 판정과 연결되지 않았습니다.
반드시 대상 장치가 로그인한 뒤 실행하세요. 같은 ID로 중복 로그인하지 마세요.
STM32 파서는 시험 시 `[JETSON]`, 최종 Pi 제어 시 `[PI]` 헤더를 처리해야 합니다.
현재 등록 설정은 시작할 때 읽으므로 기존 서버 프로세스에는 새 STM ID가 자동 반영되지 않습니다.
기존 Bluetooth 시험을 종료하고 새 저장소의 서버로 전환한 뒤 5000번에서 실물 시험합니다.
현재 클라이언트는 진단 도구이며 완성된 경기 제어/영상 클라이언트가 아닙니다.
