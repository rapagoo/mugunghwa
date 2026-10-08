# STM32 팀원 완성본

팀원의 STM32CubeIDE 프로젝트 **폴더 안의 내용 전체**를 이 폴더에 복사하세요.
`.ioc`, `.project`, `.cproject`가 이 README와 같은 위치에 오도록 넣으면 됩니다.

포함할 파일:

- `.ioc`, `.project`, `.cproject`, `.mxproject`, `.settings/` 등 프로젝트 설정
- `Core/`, `Drivers/`, 사용자 소스·헤더, 사용 중인 미들웨어
- 시작 코드, 링커 스크립트, 빌드 설정과 필요한 라이브러리

`Debug/`, `Release/` 등 빌드 결과는 이 폴더의 `.gitignore`로 제외합니다.
CubeIDE의 workspace 전체나 `.metadata/`는 복사하지 마세요.
이 안내와 `.gitignore`는 유지하고, 완성본에 별도 설명서가 있다면 다른 이름으로 함께 넣으세요.

CubeIDE에서 이 폴더를 기존 프로젝트로 가져온 뒤 보드에 빌드·업로드합니다.
파일을 저장소에 복사하는 것만으로 보드에 업로드되지는 않습니다.
Wi-Fi SSID·비밀번호 등 실제 비밀값은 Git에 올리기 전에 분리하거나 예시 값으로 바꾸세요.

현재 게임 통신 규약은 [경기 실행 문서](../../docs/game-runtime.md)를 참고하세요.
완성본 수령 후 보드/IDE 버전·UART 설정·배선·업로드 방법을 이 문서에 추가하면 됩니다.
