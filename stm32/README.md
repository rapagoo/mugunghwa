# STM32 현장 장치

`game_controller/`는 시작·중지 버튼, ESP-01 Wi-Fi, 인형 서보, 회전 상태 LED와 LCD를 제어하는 STM32CubeIDE 프로젝트입니다. Pi 명령을 수행하고 회전 처리·표시 완료를 응답합니다.

회전 완료는 펌웨어 처리 기준이며 별도 각도 센서의 실측으로 설명하지 않습니다. 상세 구성은 [펌웨어 문서](game_controller/README.md), 연동 순서는 [게임 실행](../docs/game-runtime.md)을 참고하세요. 실기 빌드·다운로드는 STM32CubeIDE와 해당 보드 환경이 필요합니다.
