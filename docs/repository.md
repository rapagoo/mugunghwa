# Git 관리와 담당 범위

현재 이 저장소는 개인 담당인 Raspberry Pi와 Jetson 개발을 관리합니다.
STM32는 팀원 코드 합류를 위한 자리이며 현재 구현은 없습니다.
Arduino 스케치와 Pi Bluetooth 중계는 기존 통신 진단용 코드입니다.
Drive 기획서의 목표 구성은 STM32–ESP-01–Pi 통신이며 Arduino는 제외합니다.
기획과 현재 구현은 구분하고, 기존 진단 코드는 전환 전까지 보존합니다.

## 개발 흐름

Pi와 Jetson에서 같은 저장소를 사용하고 각 장치 담당 폴더를 수정합니다.
작업 시작 전 변경 사항을 확인한 뒤 `git pull --ff-only`를 실행합니다.
변경 후 필요한 파일만 `git add`하고 `git commit`, `git push`로 공유합니다.
다른 장치의 커밋을 받은 뒤 해당 장치에서 빌드/실행합니다.
동시에 서로 다른 작업을 할 때는 기능별 브랜치를 사용합니다.
통합 시험에는 두 장치의 `git rev-parse HEAD` 결과를 기록합니다.

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

기획서와 발표 자료는 Google Drive에서 관리합니다.
[무궁화게임 기획서](https://drive.google.com/file/d/1uo1cv8Olc6oX-2BzcBcs0l_VGradksoT/view)
