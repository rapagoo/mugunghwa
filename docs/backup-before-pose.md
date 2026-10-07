# 관절 검출 비교 전 백업

2026-10-07. 정상 동작 중인 1~5단계 웹 검증 코드 기준: `f81dd5a`.
코드는 GitHub에 저장돼 있다. 장비 내부에 Git 제외 파일의 별도 사본을 만들었다.
원본 파일과 서비스는 변경하지 않았다. Git 작업 트리는 두 장비 모두 깨끗했다.

| 장비 | 백업 폴더 | 포함 |
|---|---|---|
| Jetson | `/home/jetson/projects/mugunghwa/backups/20261007-before-pose` | 웹캠 FP16 엔진, DB 읽기 접속 설정, systemd 웹 서비스 파일, 코드 커밋/상태 |
| Pi | `/home/pi/Projects/mugunghwa/backups/20261007-before-pose` | DB 쓰기·읽기 접속 설정, 코드 커밋/상태 |

폴더는 700, 파일은 600 권한이며 장비 사용자만 읽을 수 있다. 엔진은 약 18MB다.
사본과 원본의 cmp 일치 및 SHA256SUMS 검증 성공을 확인했다.
백업과 비밀번호는 Git에 추가하지 않는다. 웹 구역/결승선은 사용자 요청대로 재설정 가능해 제외했다.
실제 MariaDB 테이블 데이터, DB 계정/권한 정의, 운영체제와 Python 환경 전체를 백업한 것은 아니다.
현재 MariaDB의 변경된 Jetson 호스트 허용 문제(TS-WEB-005)를 해결한 백업으로 해석하지 않는다.
같은 SD 카드 안의 사본이므로 향후 파일 수정 복구에는 쓸 수 있지만 SD 카드 고장에 대비한 사본은 아니다.

## 확인

각 장비에서 백업 폴더로 이동한 뒤 `sha256sum -c SHA256SUMS`를 실행한다.
코드 복구 기준은 백업의 code-commit.txt를 확인한다.

## 복원 절차 (필요할 때 실행, 지금은 실행하지 않음)

먼저 현재 개발 변경을 커밋하거나 안전하게 별도 보존한다. 작업 트리가 깨끗한 상태에서
새 복원 브랜치에 코드를 여는 방법은 `git switch -c codex/restore-before-pose f81dd5a`다.
이는 이후 커밋을 삭제하지 않는다. 기존 브랜치가 있다면 새 이름을 선택한다.

Jetson 웹 서비스를 중지한 뒤 엔진·설정 사본을 원래 repo/.runtime 경로로 복사하고
DB 설정 권한 600을 유지한다. 엔진은 같은 Nano의 현행 환경을 위한 것으로 다른 GPU/환경의
호환성을 보장하지 않는다. 서비스 파일까지 변경했다면 저장된 파일을 관리자 권한으로
/etc/systemd/system/mugunghwa-web.service에 복원하고 systemctl daemon-reload를 실행한다.
그 뒤 서비스를 시작하고 웹 영상·설정·API를 확인한다. 구역/결승선은 웹에서 다시 설정한다.
Pi 설정 복원이 필요하면 db/writer.json과 db/web.json을 repo/.runtime/db/에 복사한다.
DB 계정·권한/테이블 데이터는 이 파일 복사만으로 복원되지 않는다.

관절 모델과 엔진은 별도 파일명으로 생성하며 현재 yolov8n-480x640-fp16.engine을 덮어쓰지 않는다.
