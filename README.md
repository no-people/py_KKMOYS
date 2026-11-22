# MOIM — 모임 재무 관리

모임의 지출·분류·보고서·정산·예산 및 회비·자료 가져오기와 내보내기를 관리하는 명령행 프로그램입니다.
현재 기능을 개발 중입니다. 명령 묶음의 도움말에서 사용할 수 있는 하위 명령을 확인하세요.

## 실행 환경과 설치

- Python 3.10 이상, Git, Windows PowerShell
- 파이썬 표준 라이브러리만 사용합니다. 별도 패키지를 설치할 필요가 없습니다.

PowerShell에서 저장소를 내려받고 해당 폴더로 이동합니다.

```powershell
git clone https://github.com/no-people/py_KKMOYS.git
cd py_KKMOYS
python --version
python -m moim --help
```

이미 내려받았다면 다시 clone 하지 말고 기존 작업 폴더에서 실행하세요.
`python`이나 `git`을 찾을 수 없으면 설치 여부를 확인하고 PowerShell을 새로 여세요.

가상 환경을 사용하려면 다음을 실행합니다. 활성화 없이 환경의 Python을 직접 사용합니다.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m moim --help
```

## 설정 파일

처음 한 번 예제 설정을 복사합니다. 기존 `config.json`이 있다면 복사하지 말고 내용을 확인하세요.

```powershell
Copy-Item config.example.json config.json
python -m moim --config config.json --help
```

설정은 UTF-8 JSON 파일입니다. 예제의 금액은 원 단위 정수입니다.

| 항목 | 의미 | 예 |
|---|---|---|
| `group` | 모임 이름 | `"AI 동아리"` |
| `data` | 명부·지출·회비 등을 저장할 자료 파일 | `"data.json"` |
| `members_file` | 참여자 명부 파일 | `"members.txt"` |
| `rules` | 분류 규칙 파일 | `"rules.json"` |
| `backup_dir` / `log_dir` | 백업 / 로그 폴더 | `"backup"` / `"logs"` |
| `treasurer` | 은행 출금을 지출로 기록할 때의 총무 이름 | `"김민수"` |
| `budget.monthly` | 월 전체 예산 | `1500000` |
| `budget.by_category` | 분류 이름별 월 예산 | `{"식비": 800000, "장소": 300000}` |
| `dues.monthly` | 1인당 월 회비 | `20000` |
| `warn_ratio` | 예산 사전 경보 기준 비율 | `0.8` |

`--config`는 명령 묶음보다 앞에 둡니다. 예: `python -m moim --config config.json budget --help`.
`data` 경로는 설정 파일이 있는 폴더를 기준으로 읽습니다.
나머지 경로 항목의 자동 변환과 백업·로그 연결은 각 담당 작업이 병합된 뒤 사용할 수 있습니다.
예산을 바꾸려면 `config.json`의 `budget` 안에 있는 `monthly` 값을 수정합니다.

## 명령 도움말

```powershell
python -m moim --help
python -m moim budget --help
```

| 묶음 | 기능 |
|---|---|
| `member` | 참여자 명부 |
| `exp` | 지출 입력·관리 |
| `cat` | 분류 규칙 |
| `report` | 보고서 |
| `settle` | 정산 |
| `budget` | 예산·회비 |
| `io` | 가져오기·내보내기 |

각 기능의 명령·출력 예는 구현이 병합되면 실제 실행 결과를 확인해 추가합니다.

## 연습 자료와 검사

실제 자료와 섞이지 않도록 연습 자료는 별도 폴더에 만드세요.
출력 위치와 옵션을 먼저 확인합니다.

```powershell
python tools/gen_data.py --help
python tools/gen_data.py practice --month 2026-11
python -m compileall -q moim tools
python tools/check_imports.py
python -m unittest discover -s tests
```

검사 결과의 `OK`는 실행한 테스트가 통과했다는 뜻입니다.
`skipped`는 아직 구현되지 않은 기능 등에 대한 건너뜀이며, 모든 기능의 완성을 뜻하지 않습니다.
실패하면 `FAIL`·`ERROR` 아래에 표시된 테스트 이름과 오류 내용을 확인하세요.
개인 설정·자료 파일과 `backup/`, `logs/`는 저장소에 올리지 않습니다.

## 프로젝트 문서

- [역할 분담과 작업 순서](docs/역할분담_작업순서.md)
- [작업 방식과 협업 규칙](docs/작업방식_협업규칙.md)
- [공통 모듈 함수 규격](docs/공통모듈_함수규격.md)
- [금액·날짜 등 공통 규약](docs/규약.md)
- [은행 거래내역 형식](docs/은행거래내역형식.md)
