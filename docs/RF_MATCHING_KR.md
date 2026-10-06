# RF 매칭과 플라즈마 — 실험 안내

이 프로젝트의 질문은 **“발생기에서 나간 전력이 얼마나 반사되고, 어디에서 소모되며, 부하가 달라지면 매칭을 어떻게 바꿔야 하는가?”**입니다.
RF 전공의 임피던스·전송선 지식을 플라즈마 장비의 전력 전달과 데이터 해석으로 연결합니다.
Python 회로 계산과 공개된 등가회로 원리를 사용하고, 실행 결과를 실제 Apache Superset에서 분석합니다.

## 오늘 처음 할 일 — 약 45분

이미 설치한 PC에서는 저장소 루트의 `START_RF_LAB.ps1`과 `START_SUPERSET.ps1`을 각각 실행합니다.
서비스가 이미 열려 있다면 다시 실행할 필요가 없습니다.

1. [로컬 RF 실험실](http://127.0.0.1:8768/#rf)을 엽니다. 회로의 연결 순서와 전력 표시를 읽습니다.
2. 기본 조건에서 **회로 계산 · 기록**을 누릅니다. 이 실행의 ID가 분석 DB와 JSON에 저장됩니다.
3. 수동 설정과 **자동 정합점 보기**를 비교합니다. 후자는 같은 입력에 대해 계산한 최적 C를 보는 기능이며 입력 칸을 바꾸지 않습니다.
4. **자동 정합값 적용 · 계산**을 누르면 입력 C까지 바꾸고 새 실행으로 기록합니다.
5. **코일 손실 증가 Q = 15** 예제를 선택합니다. 예제 선택만으로는 DB에 기록하지 않으므로 다시 계산합니다.
6. **Superset 분석 → 대시보드 열기**를 누릅니다. Superset의 Refresh dashboard를 눌러 최신 실행을 읽습니다.
7. “반사율만 보고 정상이라고 판단하면 무엇을 놓치는가?”에 수치와 함께 답합니다.

처음부터 모든 파라미터를 바꿀 필요는 없습니다. 첫날에는 Cₚ, Cₛ, 코일 Q만 바꿉니다.
**플라즈마 학습** 탭에는 아래 원리의 수식과 현재 계산값이 함께 표시됩니다.

## 정확히 무엇을 계산하는가

```text
50 Ω 발생기 ─ 무손실 50 Ω 급전선 ─┬─ 코일 L + ESR ─ Cₛ + ESR ─ 플라즈마 부하 ─ 접지
                                  └─ Cₚ + ESR ─ 접지
플라즈마 부하: Rᵦ, Lᵦ, Csh의 직렬 연결
```

단일 주파수의 선형 정상상태 회로입니다. 페이저는 `exp(+jωt)`, 전압과 전류는 **RMS**, 내부 계산은 SI 단위입니다.
RMS 페이저의 전력에는 1/2를 곱하지 않습니다. 순간 파형을 만들 때는 √2를 곱합니다.
진행파 전력은 발생기 기준면에서 정의하며, 반사계수도 기본적으로 그 기준면의 값입니다.

\[
\Gamma=\frac{Z_{in}-50}{Z_{in}+50},\qquad
P_{ref}=|\Gamma|^2 P_{fwd},\qquad S_{11,dB}=20\log_{10}|\Gamma|
\]

매칭 커패시터와 코일은 유한 Q에 따른 직렬 손실 저항을 가집니다.

\[
R_L=\frac{\omega L}{Q_L},\qquad R_C=\frac{1}{\omega C Q_C}
\]

플라즈마 벌크는 전자 운동량 방정식의 균일 전류 근사에서 다음과 같이 표현합니다.
두 쉬스는 같은 유효 면적의 고정 평행판 커패시터를 직렬 합성합니다.

\[
L_b=\frac{m_e\ell_b}{n_e e^2 A},\quad R_b=\nu L_b,\quad
C_{sh}=\frac{\varepsilon_0 A}{s_1+s_2},\quad
Z_p=R_b+j\omega L_b+\frac{1}{j\omega C_{sh}}
\]

`nₑ`는 전자밀도, `ν`는 유효 충돌 빈도, `ℓᵦ`는 벌크 길이, `A`는 유효 전극 면적입니다.
**회로 · 매칭** 모드에서는 이 값을 사용자가 지정합니다. 새 **매칭 ↔ 플라즈마** 모드는 Ar 입자·전력 수지와 회로를 연결해 Te와 ne를 계산합니다. [결합식·가정·첫 보고서 실험](PROJECT_REPORT_KR.md)을 참고하세요.
밀도를 절반으로 하면 다른 조건이 같을 때 Rᵦ와 Lᵦ는 두 배가 됩니다.

계산 결과는 항상 다음 전력 수지를 함께 제공합니다.

\[
P_{fwd}=P_{ref}+P_{bulk}+P_L+P_C,\qquad
P_{bulk}=|I_{bulk,rms}|^2 R_b
\]

`P_fwd − P_ref`는 매칭 회로와 플라즈마가 합쳐서 받아들인 전력입니다.
그 전부를 플라즈마 흡수 전력이라고 부르면 코일·커패시터 손실을 놓칩니다.
지금의 `P_bulk`도 플라즈마 벌크 저항의 소산만 의미합니다. 실제 전체 방전의 에너지 분배를 모두 계산한 값은 아닙니다.

## 입력을 읽는 법

| 묶음 | 입력 / 단위 | 공부할 관계 |
|---|---|---|
| 발생기 | 주파수 MHz, 진행파 W | 주파수는 리액턴스를, 전력은 전압·전류 크기를 바꾼다 |
| 매칭 | Cₚ·Cₛ pF, L µH | 병렬/직렬 소자가 입력 임피던스를 이동시키는 방향 |
| 손실 | 코일·커패시터 Q | 낮은 반사와 높은 부하 전달 효율은 별개 |
| 벌크 | 밀도 10¹⁵ m⁻³, 충돌 10⁸ s⁻¹, 길이 mm | 전자 관성과 충돌 손실 |
| 기하 | 면적 cm², 두 쉬스 두께 합 mm | 부하 저항·인덕턴스·커패시턴스의 변화 |
| 급전선 | 길이 m, 속도 계수 | 기준면 변화와 Smith chart 회전 |
| 부하 변화 | 밀도 배수 | 기준 정합 → 같은 C로 달라진 부하 → 재정합 |
| 비교 한계 | Cₛ V RMS, 코일 A RMS | 사용자 지정 학습 기준. 실제 부품 정격 인증 아님 |

전체 범위와 개별 설명은 화면의 접힌 입력 그룹과 `rf_lab/model.py`의 `FIELDS`가 기준입니다.
밀도·충돌 빈도·쉬스 두께는 실제 장비에서 각각 독립적으로 설정하는 레시피 노브가 아닙니다.
압력·가스 조성에서 이 상태로 연결하려면 추가 물리 모델과 실측 보정이 필요합니다.

## 그래프와 자동 정합

- **Smith chart:** 수동/자동 정합의 주파수 궤적. 점은 설정 주파수입니다. 기준 임피던스는 50 Ω입니다.
- **매칭 영역:** Cₚ/Cₛ 각각 10–3000 pF의 로그 격자 41×41점. 밝을수록 반사 전력이 작습니다. 맵을 누르면 입력만 바뀌며 재계산해야 합니다.
- **주파수 응답:** 설정 주파수의 0.6–1.4배, 181점. 각 곡선의 C는 고정입니다. 주파수마다 다시 튜닝한 곡선이 아닙니다.
- S₁₁ 그래프 표시만 −60 dB에서 제한합니다. JSON에는 수치 바닥값 −240 dB까지 원래 계산값을 보존합니다.
- **전압·전류 두 주기:** 정상상태 복소 페이저를 시간 파형으로 재구성합니다. 점화 과도응답을 적분한 결과가 아닙니다.
- **자동 정합:** 양수 C를 로그 변수로 두고 10개 결정론적 초기점에서 제한된 최소제곱 탐색을 합니다. 목적함수는 복소 Γ의 실수·허수 성분입니다. 전역 최적해 보장, 부품 정격 제약 최적화, 실제 모터 제어 알고리즘은 아닙니다.

무손실 급전선에서는 `Γ_gen = Γ_match exp(−j2βℓ)`입니다. 길이만 바꾸면 |Γ|와 벌크 흡수 전력은 변하지 않아야 합니다.
반사가 너무 작은 지점의 dB 값은 수치 바닥값을 적용합니다. 극도로 작은 수치를 장비의 실제 계측 분해능으로 해석하지 마세요.

## 5회 실습 — 회당 30–60분

| 회차 | 조작 | 기록할 증거 | 답할 질문 |
|---|---|---|---|
| 1 | Cₚ만, 다음에는 Cₛ만 변경 | 입력 Z, Γ, Smith 이동 | 어느 소자가 어느 위치에 연결되어 있는가? |
| 2 | 수동/자동 정합 비교 | 반사 W, 벌크 W, 코일 W, C 전압 | 정합만 잘하면 충분한가? |
| 3 | 밀도 배수 0.5 또는 2 | 고정 C와 재정합의 세 조건 표 | 부하 변화와 매칭 변화의 효과를 분리할 수 있는가? |
| 4 | Q=100/15, 이어서 급전선 길이 변경 | 손실·전압과 기준면 위상 | 손실 문제와 기준면 문제는 어떤 관측으로 구분하는가? |
| 5 | Superset 조회, ALD/Etch 결과 동기화 | 실행 ID, 입력, 결과, SQL | 내 가설을 어떤 추가 측정으로 반증할 수 있는가? |

실험 메모에는 **가설 → 한 변수 변경 → 관측 → 다른 가능한 원인 → 다음 확인**을 적습니다.
밀도를 바꿔 얻은 결과는 ‘밀도 변화라는 가정하에’의 계산입니다. 실제 반사 증가에서 밀도 변화를 유일한 원인으로 확정할 수는 없습니다.
Q, 케이블 손실, 오염, 접촉, 기생 성분, 센서 기준면 등은 별도 가설이 될 수 있습니다. 이 중 현재 구현하지 않은 항목은 시뮬레이션했다고 쓰지 않습니다.

## 기본 예제의 계산값

13.56 MHz, 300 W, 코일 2 µH/Q100, C의 Q1000, nₑ=10¹⁵ m⁻³,
ν=2×10⁸ s⁻¹, 벌크 30 mm, 면적 200 cm², 두 쉬스 합 1 mm,
급전선 0.5 m/속도 계수 0.7. 다른 값은 기본 입력입니다.

| 조건 | Cₚ / Cₛ (pF) | 반사 (%) | 벌크 (W) | 코일 손실 (W) |
|---|---:|---:|---:|---:|
| 수동 | 500 / 120 | 15.462 | 216.702 | 34.685 |
| 기준 자동 정합 | 407.717 / 134.884 | 수치적으로 약 0 | 256.352 | 41.031 |
| 밀도 0.5배, C 고정 | 407.717 / 134.884 | 10.410 | 247.463 | 19.804 |
| 밀도 0.5배, 재정합 | 253.455 / 133.015 | 수치적으로 약 0 | 276.410 | 22.121 |

밀도 감소 후 재정합에서 벌크 소산이 늘어나는 것은 이 처방된 회로에서 벌크 저항과 손실 분배가 달라지기 때문입니다.
이 결과만으로 실제 방전 밀도나 식각률의 증감을 예측할 수 없습니다.

## Superset: 무엇이 연결되어 있는가

**Superset은 물리 해석기가 아니라 SQL 기반 분석·시각화 도구**입니다.
이 프로젝트의 흐름은 `Python 계산 → SQLite 분석 DB → Superset 차트`입니다.

| 테이블/뷰 | 내용 |
|---|---|
| `rf_runs` | 실행 ID, UTC 시각, 모델 버전, 소스 SHA-256, 입력 해시, 전체 입력 JSON |
| `rf_cases` | 실행마다 수동/기준 정합/밀도 변화/재정합 네 조건 |
| `rf_case_history` | 각 조건에 실행 시각·버전·코일 Q·커패시터 Q를 연결한 뷰 |
| `rf_frequency` | 실행마다 수동/자동의 주파수 응답 각 181점 |
| `rf_latest_cases`, `rf_latest_frequency` | 가장 최근 실행만 선택하는 뷰 |
| `process_results` | 완료된 ALD/Etch 결과. 로컬 실행과 저장된 공개 예제의 출처 구분 |

모든 데이터는 **simulation**입니다. ALD와 Etch에 해당하지 않는 지표는 NULL입니다. 이를 0으로 바꿔 비교하지 않습니다.
RF 결과와 ALD/Etch 결과는 독립 모델이므로 서로 다른 실행을 같은 공정의 인과 연결이라고 해석하지 않습니다.

대시보드는 기존 다섯 차트에 **Ar 결합 수지·밀도**와 **초기 요철의 공정 전후 변화**를 더한 일곱 차트를 제공합니다. 새 테이블은 `rf_coupled_cases`, `surface_results`입니다.
새 계산 뒤에는 **Refresh dashboard**를 누릅니다. ALD/Etch 새 결과는 RF 화면의 **결과 동기화** 버튼으로 가져옵니다.

SQL Lab을 써 보려면 로컬 `local/superset/credentials.json`의 username/password로 로그인합니다.
이 파일에는 비공개 secret_key도 있으므로 공유·커밋하지 않습니다. 대시보드 조회에는 로그인이 필요 없습니다.
SQL Lab에서 `Process Lab (simulation, read only)` 데이터베이스를 선택하고 실행합니다.

```sql
SELECT case_name, reflected_pct, bulk_w, coil_loss_w, series_cap_rms_v
FROM rf_latest_cases
ORDER BY case_name;
```

```sql
SELECT r.created_at, r.run_id, r.version, c.case_name,
       c.reflected_pct, c.bulk_w, c.coil_loss_w
FROM rf_runs AS r JOIN rf_cases AS c ON r.run_id = c.run_id
WHERE c.case_name = '01 기준 정합'
ORDER BY r.created_at DESC;
```

코일 Q별 정합 결과는 `SELECT created_at, coil_q, reflected_pct, bulk_w, coil_loss_w FROM rf_case_history WHERE case_name = '01 기준 정합' ORDER BY created_at DESC;`로 비교합니다.

## 새 PC에 설치

Python 3.12, Node/pnpm을 사용한 Windows 로컬 환경입니다. 두 Python 환경을 분리합니다.
Superset의 pandas/NumPy 의존성을 native solver 환경과 혼합하지 않습니다.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r native_lab/requirements.txt
cd sim_app/frontend
pnpm install --frozen-lockfile
pnpm build
cd ../..
# Native 엔진과 RF를 함께 실행
.\START_RF_LAB.ps1
```

다른 터미널에서 아래 명령을 실행합니다. 최초 데이터가 있어야 대시보드에 차트가 나옵니다.

```powershell
.\.venv\Scripts\python.exe -c "from rf_lab.service import run_request,run_coupled,import_process_results; run_request({'params':{}}); run_coupled({'rf_params':{}}); import_process_results()"
python -m venv local/superset-venv
.\local\superset-venv\Scripts\python.exe -m pip install -r analytics_tools/requirements.txt
.\local\superset-venv\Scripts\python.exe -m analytics_tools.bootstrap_superset
.\local\superset-venv\Scripts\python.exe -m analytics_tools.provision_dashboard
.\START_SUPERSET.ps1
```

`bootstrap`는 임의 관리자 자격증명·암호화 키를 로컬에 생성하고 메타데이터 DB를 초기화합니다.
`provision_dashboard`는 이 프로젝트 이름의 DB·데이터셋·차트만 생성/갱신하며 재실행 가능합니다.
이 설정은 Waitress/127.0.0.1의 **로컬 학습 환경**입니다. 외부 서비스 배포용 설정이 아닙니다.
분석 DB는 SQLite `mode=ro`로 연결하며, 쓰기는 RF 서비스가 담당합니다.
설치 버전은 Superset 6.1.0, NumPy 1.26.4, Flask-Caching 2.3.1입니다. 캐시 API 호환 문제를 피하기 위해 별도 고정했습니다.
검증한 Windows 로컬 실행과 Superset의 일반적인 운영 배포 권장 환경은 구분해야 합니다.

## 검증과 한계

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s rf_lab/tests -v
cd sim_app/frontend
pnpm test
pnpm build:pages
```

RF 테스트는 별도의 노달 어드미턴스 행렬과 회로 계산 대조, seed=42의 120개 조건에서 수동성·전력 보존,
급전선 위상/전력 불변성, 전력-전압 스케일링, 플라즈마 소자 스케일링, 정합·부하 변화,
부품 Q에 따른 손실, 입력 검증, 분석 DB 저장을 확인합니다. 프런트엔드 테스트는 RF 수식 조판도 확인합니다.
이것은 **구현·회로 수치 검증**입니다. 실제 장비나 측정 데이터에 대한 검증이 아닙니다.

RF 회로·Ar 결합·API 테스트는 18개입니다. 결합 모델의 입자/전력 수지, 무전력, 밀도 탐색 간격도 확인합니다. 실행 저장/JSON 일치, 잘못된 입력과 외부 Origin 거부도 확인합니다.
Superset이 켜져 있을 때 `.venv/Scripts/python.exe -m analytics_tools.verify_dashboard`를 실행하면
실제 HTTP 차트 응답 7개를 원본 SQLite와 대조합니다. 대시보드 생성 재실행도 확인했습니다.

현재 제외: 비선형 쉬스, DC self-bias, 점화, 고조파, 펄스 과도응답, 공간 분포 및 비선형 쉬스와 결합된 전자온도·밀도 해,
ICP 변압기 결합, 3D 전자기장, 분포정수 매칭 부품, 온도 의존 손실, 장비 기생 성분, 공정 반응과의 직접 결합.
RF 흡수 전력을 ViennaPS 식각 플럭스에 임의 환산하지 않았습니다.

포트폴리오에는 “RF·플라즈마 등가회로와 매칭 손실을 구현하고, 조건 변화/재정합 실험을 기록하여 Superset으로 분석했다”라고 설명할 수 있습니다.
논문 전체 모델 재현, 실제 장비 디지털 트윈, 측정 검증된 공정 예측이라고 표현할 근거는 아직 없습니다.
사용한 AI 개발 지원, 직접 공부한 가정과 실험 해석, 외부 라이브러리의 역할을 각각 명시하세요.

## 출처와 코드

- [Schmidt, Mussenbrock, Trieschmann (2018)](https://arxiv.org/abs/1804.05638): 벌크 등가회로와 외부 매칭 회로의 연결을 공부할 자료. 이 논문은 비선형 쉬스·방전과 결합하며, 본 구현은 그 전체 해석기를 재현하지 않습니다.
- [Apache Superset 공식 문서](https://superset.apache.org/docs/): SQL Lab·데이터셋·대시보드 사용.
- [Superset 설치 안내](https://superset.apache.org/docs/installation/docker-compose/): 운영체제·배포 환경 검토 자료.
- `rf_lab/model.py`: 계산·단위·입력·튜닝. `rf_lab/service.py`: 결과와 분석 DB.
- `analytics_tools/`: 외부 Superset 패키지의 로컬 설치·설정·대시보드 생성 스크립트.
- `sim_app/frontend/src/components/RFWorkbench.tsx`: 학습과 조작 화면.
