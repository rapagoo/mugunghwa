# Pi 작업 환경

작업 폴더: `/home/pi/Projects/mugunghwa/repo`

기존 `/home/pi/Projects/mugunghwa/game`과 `lecturecode`는 보존했습니다.
새 작업은 `repo`에서 진행합니다. 기존 실행 중인 프로세스를 전환하지는 않았습니다.

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
서버를 실행할 때는 `pi/server` 폴더로 이동해야 로그인 파일을 찾습니다.
실물 Bluetooth/LCD 통신은 별도 검증이 필요합니다.
