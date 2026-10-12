# Git 관리와 담당 범위

2026-10-12 기준 Pi·Jetson·STM32·Arduino 소스와 개발·발표 검토 문서를 관리합니다.
홍성록은 Pi·Jetson, 박정환은 STM32·Arduino를 담당합니다. 현재 게임 흐름은 [게임 실행](game-runtime.md)을 우선합니다.

`main`은 통합 기준 브랜치입니다. 기능 개발은 별도 브랜치에서 진행하고 검증 후 통합합니다.
실제 장비에서는 변경 사항을 확인한 뒤 승인된 커밋을 받아 다시 빌드·검증합니다. 이 문서 갱신만으로 실행 중인 장비를 배포하거나 재시작하지 않습니다.

## 개발 흐름

Pi와 Jetson에서 같은 저장소를 사용하고 각 장치 담당 폴더를 수정합니다.
작업 시작 전 변경 사항을 확인한 뒤 `git pull --ff-only`를 실행합니다.
변경 후 필요한 파일만 `git add`하고 `git commit`, `git push`로 공유합니다.
다른 장치의 커밋을 받은 뒤 해당 장치에서 빌드/실행합니다.
동시에 서로 다른 작업을 할 때는 기능별 브랜치를 사용합니다.
통합 시험에는 두 장치의 `git rev-parse HEAD` 결과를 기록합니다.

## 연결된 작업 폴더와 인증

- Windows: `C:\Users\kccistc\Documents\Mugunghwa`
- Pi: `/home/pi/Projects/mugunghwa/repo` ([환경](setup-pi.md))
- Jetson: `/home/jetson/projects/mugunghwa/repo` ([환경](setup-jetson.md))

Pi와 Jetson에는 각각 이 저장소에만 적용되는 읽기·쓰기 deploy key를 등록했습니다.
개인키는 각 장비의 `~/.ssh/id_ed25519_mugunghwa_git`에만 보관합니다.
GitHub 공식 API에서 확인한 호스트 키는 `~/.ssh/mugunghwa_github_known_hosts`에 둡니다.
각 clone의 `core.sshCommand`가 해당 키를 사용하며 전역 SSH 설정은 변경하지 않습니다.
키 이름은 `mugunghwa-pi`, `mugunghwa-jetson`입니다.
장비를 더 이상 사용하지 않을 때 저장소 Settings → Deploy keys에서 해당 키를 삭제합니다.
Git 작성자와 fast-forward pull 설정은 각 저장소에만 적용했습니다.

## 관리 대상

소스, Makefile, 실행 스크립트, 통신 규약, 환경 설정 예제를 관리합니다.
실행 파일, 오브젝트, 실제 로그인 설정, 가상환경, 로그, DB 데이터,
모델 가중치와 녹화 자료는 제외합니다. 모델 준비 방법과 버전은 문서에 기록합니다.
소스의 `PASSWD`는 기존 수업용 테스트 값이며 실제 비밀값으로 대체하여 커밋하지 않습니다.
Bluetooth MAC 주소는 현재 진단 코드에 고정되어 있으며 설정 분리는 후속 작업입니다.

## 초기 코드 출처

- `pi/`, `arduino/`, `docs/protocol.md`: Pi의 기존 `game` 폴더.
- `jetson/examples/`: Jetson의 기존 `python_tcp` 폴더.
- Jetson 예제는 게임 서버와 통합하거나 실행 검증한 상태가 아닙니다.
- 장치에 있던 원본 폴더는 보존합니다.

초기 기획서는 아래 Drive 자료를 참고합니다. 최신 웹 발표자료는 별도 로컬 발표작업 폴더에서 관리하고, 발표 대본 검토·예상 질문은 이 저장소 docs에 정리합니다.
[무궁화게임 기획서](https://drive.google.com/file/d/1uo1cv8Olc6oX-2BzcBcs0l_VGradksoT/view)
