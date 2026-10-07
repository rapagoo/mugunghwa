# MariaDB 기본 구성

설치 대상 Pi: `10.10.16.90`. 웹 조회 클라이언트 Jetson: `10.10.16.120`.
Pi 제어 프로그램이 확정한 상태를 저장하고, 웹은 조회하는 구조를 준비한다.
현재 실제 보드 데이터 저장과 게임 판정 연결은 범위 밖이다.

## Pi 설치 (관리자 실행 필요)

```bash
cd /home/pi/Projects/mugunghwa/repo
sudo bash tools/database/setup_pi.sh
```

공식 OS 패키지의 MariaDB와 python3-pymysql을 설치한다.
기존 서비스/DB를 삭제하거나 root 인증 방식을 변경하지 않는다.
InnoDB/utf8mb4 테이블: games, participants, events, device_status.
시간은 UTC ISO 8601 문자열, 게임/참가자 ID는 영구 ID, 검출 추적 ID와 분리한다.
`games.is_test`는 가상 시험 데이터를 화면에 명시하기 위한 값이다.
신규 스키마이며 기존 SQLite 데이터는 자동 이관하지 않는다.

계정은 프로젝트 DB에 한정된다:

- `mugunghwa_writer@localhost`: SELECT/INSERT/UPDATE/DELETE. Pi Unix socket 연결.
- `mugunghwa_web@10.10.16.120`: SELECT만. Jetson에서만 인증 가능.

랜덤 비밀번호를 생성하고 `.runtime/db/writer.json`, `.runtime/db/web.json`에 권한 600으로 저장한다.
파일과 상위 폴더는 Pi 사용자 소유이며 Git 제외. 비밀번호를 터미널 출력/문서에 쓰지 않는다.
MariaDB는 Pi의 LAN IP에 바인딩한다. root의 원격 접속이나 `%` 호스트 계정을 만들지 않는다.
3306 방화벽 정책이 있는 환경에서는 Jetson→Pi 연결을 별도로 허용해야 한다.
IP가 바뀌면 계정 호스트·설정 파일·bind-address를 함께 갱신한다.

설치 스크립트는 계정/설정 재생성을 거부한다. 실패 후에는 로그와 현재 상태를 확인해
남은 단계만 처리한다. 기존 비밀번호를 초기화하거나 프로젝트 DB를 삭제하며 재시도하지 않는다.

## Jetson 조회 준비

Pi의 `web.json`만 Jetson `.runtime/db/web.json`으로 전달한다. writer.json은 Pi에 둔다.
Jetson 폴더 권한 700, 파일 권한 600을 유지한다.
Python 3.8 지원 드라이버 PyMySQL 1.1.1을 격리된 경로에 설치한다:

```bash
cd /home/jetson/projects/mugunghwa/repo
/home/jetson/yolo_v8/bin/python -m pip install --no-deps \
  --target .runtime/web/vendor -r jetson/requirements-web.txt
PYTHONPATH="$PWD/.runtime/web/vendor" /home/jetson/yolo_v8/bin/python \
  tools/database/verify_web.py
```

웹 실행은 기존 영상/모델 옵션에 `--db-config .runtime/db/web.json`을 추가하고
위 PYTHONPATH로 실행한다. MariaDB 선택 시 SQLite로 자동 대체하지 않는다.
DB 연결 실패는 `/api/game` 503으로 표시하고 영상 API는 계속 서비스한다.
서버는 요청마다 최대 2초의 연결/읽기 제한으로 조회하고, 동일 트랜잭션에서
게임·참가자·이벤트·장치 상태를 읽는다. 스키마 변경 권한은 없다.

## 실제 연결 검증

Pi 저장 계정 시험(기본은 rollback):

```bash
python3 tools/database/smoke_test.py
python3 tools/database/smoke_test.py --keep
```

`--keep`이 출력한 TEST ID를 기록한다. 웹에서 '시험 데이터' 표시, 남은 42초,
시험 참가자 2명(통과 1·탈락 1)을 확인한 뒤 아래로 해당 fixture만 정리한다:

```bash
python3 tools/database/smoke_test.py --cleanup TEST-출력된ID
```

실제 게임은 삭제하지 않도록 is_test를 검사한다. 시험 데이터는 MCU 명령을 보내지 않는다.
Jetson verify_web.py는 SELECT 성공과 UPDATE 거부(1142)를 확인한다.
보드 상태는 실제 저장 연결 전까지 빈 목록이다. 연결된 것처럼 가상 상태를 넣지 않는다.

## 2026-10-06 검증 결과

- Pi의 OS 패키지 MariaDB 11.8.6 설치·서비스 실행 확인. 설치의 sudo 인증은 사용자가 Pi 터미널에서 수행.
- 저장 계정 트랜잭션 삽입·조회·rollback 확인.
- Jetson에서 원격 SELECT 성공, UPDATE는 오류 1142로 거부됨.
- 시험 게임을 commit하고 웹에서 '시험 데이터 · 진행 중', 42초, 참가자 2명,
  통과 1명·탈락 1명과 두 이벤트를 확인. 이후 해당 시험 게임과 자식 행만 삭제.
- 현재 웹 실행에 `--db-config .runtime/db/web.json` 적용. API는 backend=mariadb,
  connected=true, game=null, 참가자/이벤트/장치 상태 빈 목록을 반환.
- Pi/Jetson의 설정 파일은 600, 상위 DB 설정 폴더 700. 비밀값은 Git에 포함하지 않음.
- DB 장애 응답은 503이고 영상 JPEG는 유지되는 자동 테스트 통과.

DB 자체는 재부팅 시 자동 실행된다. 2026-10-07 Jetson 웹 서버도 `mugunghwa-web.service`로 등록했다.
현재 웹캠 입력과 MariaDB 조회를 사용한다. 실제 보드 데이터 저장·게임 상태 계산은 미연결이다.

## 후속 개발

Pi C 클라이언트의 저장 모듈/큐, 이벤트 중복 방지 키, 명령 송신과 처리 ACK 구분,
재접속 복구, 게임 단계/마감 시각/일시정지 규약을 구현한다.
웹의 남은 시간은 현재 DB에 저장된 값 그대로이며, 마감 시각 기반 보간은 연결 단계에서 추가한다.
장치 상태의 last_seen_at을 기준으로 만료된 연결을 표시하는 규칙도 후속이다.

참고: [MariaDB 원격 연결](https://mariadb.com/docs/server/mariadb-quickstart-guides/mariadb-remote-connection-guide),
[계정 권한](https://mariadb.com/docs/server/reference/sql-statements/account-management-sql-statements/grant),
[트랜잭션](https://mariadb.com/docs/server/reference/sql-statements/transactions/start-transaction).
