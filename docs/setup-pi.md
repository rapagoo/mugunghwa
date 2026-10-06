# Pi 작업 환경

작업 폴더: `/home/pi/Projects/mugunghwa/repo`

기존 `/home/pi/Projects/mugunghwa/game`과 `lecturecode`는 보존했습니다.
새 작업은 `repo`에서 진행합니다. STM Wi-Fi 시험 준비 시 새 서버로 전환했습니다.

```bash
cd /home/pi/Projects/mugunghwa/repo
git status
git pull --ff-only
make -C pi/server
make -C pi/controller
make -C pi/bluetooth
```

2026-10-06 세 프로그램의 빌드를 확인했습니다.
기존 서버 로그인 설정을 새 폴더의 `pi/server/idpasswd.txt`에 복사했습니다.
실제 설정과 빌드 산출물은 Git에서 제외됩니다.
새 작업 폴더의 설정에는 `STM` 테스트 ID를 추가하고 사용하지 않는 `HSR_` ID를 제거했습니다.
변경 전 로그인 설정은 `idpasswd.txt.before-stm`으로 보존하며 Git에서 제외합니다.
STM Wi-Fi 시험 준비 시 기존 `game` 서버·PI 데모·Bluetooth 중계를 종료했습니다.
현재는 새 저장소의 서버가 5000번에서 실행됩니다. [현재 시험 절차](stm-wifi-test.md)를 참고하세요.
두 서버가 동시에 같은 5000번 포트를 사용할 수 없습니다.
서버를 실행할 때는 `pi/server` 폴더로 이동해야 로그인 파일을 찾습니다.
실물 Bluetooth/LCD 통신은 별도 검증이 필요합니다.
