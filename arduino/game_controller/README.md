# Arduino 팀원 완성본

팀원이 완성한 Arduino 스케치와 함께 필요한 소스·헤더를 이 폴더에 복사하세요.
Arduino IDE의 폴더 이름 규칙에 맞춰 **메인 스케치 파일 이름은 `game_controller.ino`**로 둡니다.
여러 `.ino` 탭을 사용하는 경우 메인 파일 외의 탭도 함께 넣으세요.

```text
game_controller/
  game_controller.ino
  기타 소스·헤더 파일
  README.md
```

Arduino IDE에서 `game_controller.ino`를 열고 필요한 라이브러리를 설치한 뒤
보드·포트를 선택하여 업로드합니다. 파일 복사만으로 보드에 업로드되지는 않습니다.
사용한 보드, 라이브러리 버전, LCD 주소, Bluetooth UART 핀·속도도 이 문서에 기록하세요.
이 안내는 현재 완성본 코드가 들어 있다는 의미가 아닙니다.

기존 `../game_lcd_client/`는 이전 LCD 연결 시험 코드로 보존합니다.
팀원 최종 코드는 이 폴더를 기준으로 관리합니다.
현재 게임 통신 규약은 [경기 실행 문서](../../docs/game-runtime.md)를 참고하세요.
