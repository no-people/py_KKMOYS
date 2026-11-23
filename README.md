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

## 예산·회비 사용 예

아래 예는 예제 설정의 월 예산이 1,500,000원이고, 자료 파일에 `이서연`이 명부에 있으며,
회비와 지출 기록은 없는 상태에서 순서대로 실행한 결과입니다.
실제 자료에서는 기록과 설정에 따라 금액이 달라집니다. 연습할 때는 별도 자료 파일을 사용하세요.

### 월 예산과 남은 금액

월 예산은 설정 파일의 `budget.monthly`에서 읽습니다. 지출은 그달 1일부터 말일까지 세고,
삭제 표시한 지출은 제외합니다. 예산과 사용액이 같으면 초과가 아닙니다.

```powershell
python -m moim --config config.json budget status --month 2026-11
```

```text
2026-11 월 예산: 1,500,000원
사용액: 0원
남은 금액: 1,500,000원
예산 이내
```

특정 날짜까지의 사용액만 보려면 `--today 2026-11-15`를 덧붙입니다.

### 회비 입금 기록

`--member`에는 명부에 있는 이름을 씁니다. 금액의 쉼표와 `원` 표시는 허용되며,
소수점은 사사오입해 원 단위로 저장합니다. 0원 이하 입금은 받지 않습니다.

```powershell
python -m moim --config config.json budget pay --date 2026-11-02 --member "이서연" --amount "20,000" --memo "11월 회비"
```

```text
회비 입금 기록: 2026-11-02 이서연 20,000원
```

`pay`는 자료 파일에 새 입금 한 건을 저장합니다. 같은 명령을 다시 실행하면 별도 입금이 추가되므로,
이미 기록한 입금을 다시 입력하지 않도록 확인하세요. 조회 명령은 자료 파일을 변경하지 않습니다.

### 통장 잔고

잔고는 기록한 회비 입금 합계에서 삭제되지 않은 지출 합계를 뺀 금액입니다.
위 입금 후 지출이 없다면 다음과 같이 나옵니다.

```powershell
python -m moim --config config.json budget balance
```

```text
통장 잔고: 20,000원
```

특정 날짜까지 보려면 `--until YYYY-MM-DD`를 덧붙입니다. 지정한 날짜 당일도 포함합니다.
예를 들어 위 자료에서 `--until 2026-11-01`을 지정하면 입금 전이므로 `통장 잔고: 0원`입니다.

## 분류 규칙 사용 예

`cat`은 지출 메모의 키워드 등으로 분류를 정합니다. 규칙을 추가한 뒤 미리 보고 적용합니다.
설정 파일의 `rules` 항목에 규칙 파일 경로가 필요합니다(예제: `"rules": "rules.json"`).
`add`와 `remove`는 규칙 파일만 저장하고, `apply`는 바뀐 지출이 있을 때 자료 파일을 저장합니다.

아래는 **규칙이 없는 연습 자료**에서 순서대로 실행한 예입니다.
지출 두 건은 모두 미분류이며 날짜는 `2026-11-12`, 낸 사람은 `김민수`입니다.

| 번호 | 금액 | 메모 |
|---|---:|---|
| 1 | 9,000원 | 회의 후 저녁 |
| 2 | 36,000원 | 현수막 |

### 규칙 추가와 목록

메모에 `저녁` 또는 `점심`이 있으면 식비로 분류하는 규칙을 만듭니다.
규칙 추가만으로 기존 지출의 분류가 바뀌지는 않습니다.

```powershell
python -m moim --config config.json cat add 식비 --keywords 저녁 점심
```

```text
규칙 추가: 0. 식비  키워드: 저녁, 점심  우선순위: 0
```

```powershell
python -m moim --config config.json cat list
```

```text
0. 식비  키워드: 저녁, 점심  우선순위: 0
```

`add`의 선택 인자는 `--priority 숫자`(큰 값 우선, 같으면 먼저 등록한 규칙),
`--payer 이름`(낸 사람), `--min 원`·`--max 원`(금액 범위, 양 끝 포함)입니다.
키워드·낸 사람·금액 범위 중 조건을 하나 이상 지정해야 합니다.

### 적용 미리 보기와 실제 적용

먼저 바뀔 지출을 확인합니다. `--preview`는 자료 파일을 변경하지 않습니다.

```powershell
python -m moim --config config.json cat apply --preview
```

```text
1번: 미분류 → 식비
(미리 보기) 1건이 바뀝니다. 자료는 바꾸지 않았습니다
```

실제로 분류를 바꾸려면 `--preview` 없이 실행합니다.
분류가 고정된 지출·삭제된 지출·확정 기간의 지출은 건너뜁니다.

```powershell
python -m moim --config config.json cat apply
```

```text
1번: 미분류 → 식비
1건을 다시 분류했습니다
```

### 미분류 지출과 규칙 삭제

위 규칙과 맞지 않는 2번 지출은 미분류로 남습니다.

```powershell
python -m moim --config config.json cat uncat
```

```text
2번  2026-11-12  36,000원  김민수  현수막
미분류 1건
```

삭제할 규칙의 현재 번호는 `cat list`에서 확인합니다. 지출 번호와는 다릅니다.
규칙 삭제는 이미 분류된 지출의 분류를 되돌리지 않습니다.

```powershell
python -m moim --config config.json cat remove 0
```

```text
규칙 삭제: 0. 식비
```

다른 기능의 사용 예와 출력 예는 각 기능의 실제 실행 결과를 확인해 이어서 추가합니다.

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
