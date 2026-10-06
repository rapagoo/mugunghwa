# Jetson TCP 테스트 클라이언트

소스는 `tools/tcp_client/iot_client.c`이며 Jetson에서 빌드합니다.

```bash
cd /home/jetson/projects/mugunghwa/repo
make -C jetson/tcp_client
./jetson/tcp_client/iot_client 10.10.16.90 5000 JETSON --lcd-demo
```

목적지는 PI로 고정했습니다. `--target`은 제거했습니다.
수동 입력도 일반 문자열 또는 `[PI]...`만 허용하고 다른 목적지는 거부합니다.
`--cycles N`을 추가하면 N개 메시지를 보내고 마지막 응답을 최대 3초 기다린 뒤 종료합니다.
생략하면 인증 성공 직후 처음 보내고 3초 간격으로 가상 COUNT를 반복합니다.

Pi 서버가 JETSON의 유효한 PI 목적지 COUNT를 받아 ARD와 STM 모두에
`[PI]COUNT`로 전달합니다. MCU의 응답 목적지도 PI입니다.
APPLIED 응답은 Pi 서버 로그에 기록하고 Jetson에 `[PI]APPLIED...`로 전달합니다.
어떤 MCU가 응답했는지는 서버 로그에서 확인합니다.
이 기능은 통신 테스트이며 실제 경기 상태 판단은 아직 구현 전입니다.
별도 `count_relay.py`는 제거했습니다. 동일 ID를 중복 실행하지 마세요.
[MCU 연결 절차](../../docs/stm-wifi-test.md)를 참고하세요.
