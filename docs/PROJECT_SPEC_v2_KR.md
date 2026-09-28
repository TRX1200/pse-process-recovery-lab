# Semiconductor Diagnosis Lab v2 프로젝트 명세

> 이전 세 직무 통합 학습 명세입니다. 현재 AMK PSE의 Etch + Deposition 프로젝트는 [AMK PSE 전용 명세](AMK_PSE_PROJECT_SPEC_KR.md)를 사용합니다.

이 문서는 구현 계획과 학습 명세입니다. 실제 구현·실행·검증 상태는 README와 실행 기록을 확인하세요.

## W01 하나의 기반과 세 개의 직무별 사례

프로젝트 이름은 Semiconductor Diagnosis Lab이다. 기존 PSE 식각 프로젝트를 중심으로 시간순 데이터·가설 기록·독립 검증을 공통 기반으로 만들고, 노광 장비 진단과 검사 응용을 선택 트랙으로 추가한다. 세 회사의 실제 장비를 재현하는 모델이 아니다.

| 트랙 | 문제 | 최종 증거 |
| --- | --- | --- |
| A AMK PSE | 식각 KPI drift의 원인과 회복 | 센서·DOE·조치·다중 KPI 검증 |
| B ASML TSE | focus/overlay 잔차와 장비 사건 | 공간 map·시간순 로그·지원 요청서 |
| C KLA FAE | DOI 검출과 nuisance 부담 | 독립 wafer의 recall·review 비용 |

14일 경로에서는 A를 주력으로 끝내고 B·C는 교재 사례를 설명한다. 21일 경로에서는 B·C의 작은 평가 실습까지 완성한다. Dashboard·딥러닝·Bayesian optimization은 완료 조건이 아니다.

**현재 제공 범위**
이 워크북과 함께 Day 1 데이터 생성기·기초 검증 테스트·작성 양식을 제공한다. 전체 simulator, 진단기, DOE planner와 세 트랙 완제품을 이미 구현했다고 주장하지 않는다. 아래 페이지는 이후 직접 구현할 명세와 완료 기준이다.

**이 프로젝트가 증명하는 것**
명시한 합성 환경에서 데이터를 검사하고 가설·평가·보류·검증을 연결한 능력이다. 양산 성능·실제 recipe 최적화·장비 운용 경력을 증명하지 않는다.

## W02 첫 실행과 첫 번째 판단 기록

기존 로컬 저장소 pse-process-recovery-lab에서 아래 명령을 실행한다. Python 표준 라이브러리만 쓰는 입문 실습이라 추가 package 설치는 필요 없다. 구체적인 로컬 경로와 실행 환경은 저장소 START_HERE_KR.md에 적었다.

**실행 명령**
python study_lab/run_day1.py --seed 20260921 --out outputs/day1
python -m unittest discover -s study_lab/tests -v

| 생성 파일 | 오늘 할 일 |
| --- | --- |
| etch_wafer_observations.csv | 정상 기준과 case별 rate·RF·압력 비교 |
| overlay_sites.csv | dx/dy와 x/y 관계를 산점도로 확인 |
| inspection_candidates.csv | score threshold별 검출 건수 비교 |
| DAY1_WORKSHEET.md | 관측·가설·추가 평가를 직접 작성 |
| instructor_only/ | 오늘 판단을 기록한 뒤 정답 확인 |

먼저 CASE_A와 CASE_B를 같은 원인으로 설명할 수 있는지 생각한다. 표시 압력이 바뀌었을 때 실제 공정 결과도 변했는지, RF 비율의 변화가 공정 결과와 함께 나타나는지 비교한다. 첫날에는 원인 확정을 목표로 삼지 않는다.

**종료 조건**
두 case마다 관측 사실 2개, 가능한 원인 2개, 다음 평가 1개, 가설을 약화시키는 결과 1개를 적는다. Label을 보기 전에 문서를 저장한다. 수치를 복사하는 대신 왜 그 평가인지 한 문장으로 설명한다.

## W03 데이터 생성과 판단을 분리하는 구조

Simulator가 정답을 보유해도 분석기는 그 정답을 읽지 않도록 인터페이스를 나눈다. Ground truth, latent state, fault onset 정답은 평가기에만 전달한다. 같은 사람이 모델을 작성했으므로 이것을 독립적인 현장 blind test라고 부르지 않는다.

| 단계 | 입력 | 출력 |
| --- | --- | --- |
| 생성기 | 설정·seed·숨은 fault | 관측 데이터와 별도 truth |
| 분석기 | 그 시점까지 이용 가능한 관측 | feature·alarm·가설 순위 |
| 평가 계획 | 가설·가능한 intervention·예산 | 선택 이유와 반증 기준 |
| 최종 평가 | 고정된 판단·숨겨 둔 truth | 성능·실패·불확실성 |

권장 확장 구조는 src/semilab 아래 simulator, features, spc, diagnosis, evaluation, recovery, reporting 모듈이다. 이 모듈명은 구현 계획이며 현재 존재하는 API로 가정하지 않는다. Day 1 코드는 study_lab에 분리되어 있다.

## W04 단위와 시간과 키를 먼저 고정한다

| 테이블 | 필수 키와 열 | 정의 |
| --- | --- | --- |
| wafer | wafer_id, lot_id, tool_id, chamber_id, recipe_id | 실험 단위와 상태 식별 |
| trace | wafer_id, step_id, t_s, sensor, value, unit | step 시작 기준의 상대 시간 |
| metrology | wafer_id, site_id, x_mm, y_mm, measured_at, available_at | 측정 시각과 이용 가능 시각 분리 |
| event | event_id, occurred_at, event_type, changed_items | 정비·교정·recipe 변경 이력 |
| decision | decision_id, available_until, evidence_ids, action | 사용한 정보의 시점 고정 |

RF는 W와 reflected/forward 비율, 압력은 mTorr, 유량은 sccm, 온도는 degree C, 시간은 s, CD는 nm로 저장한다. Wafer 좌표는 중심 원점의 mm, overlay vector는 nm로 둔다. 회전 방향과 notch 기준도 설정에 적는다.

**입력 검증**
중복 key, 비단조 시간, unit 불일치, NaN/inf, 빈 step, forward power<=0은 명시적으로 오류 또는 unavailable로 처리한다. Measurement 누락을 정상값이나 0으로 채우지 않는다.

대부분의 최종 metrology는 공정 후에 얻는다. 그러므로 프로젝트의 기본 결정 시점은 다음 wafer의 공정 전이다. 공정 중 제어를 주장하려면 그 시점에 실제 이용 가능한 센서만 쓰는 별도 평가가 필요하다.

## W05 분할과 누수 방지와 고정 평가

| 구간 | 용도 | 허용되는 선택 |
| --- | --- | --- |
| Train | 정상 기준·feature scaling·모델 적합 | baseline과 초기 구조 |
| Validation | threshold·가설 score·비용 기준 | 설정 선택 및 실패 분석 |
| Test | 고정한 설계의 최종 평가 | 성능 보고만 |
| 새 평가 | Test를 보고 설계를 바꾼 경우 | 새 seed·새 조건의 추가 시험 |

예시 seed 영역은 train 1000~1099, validation 2000~2099, test 3000~3099다. 번호는 구분을 위한 교육 설계이며 숫자 자체가 독립성을 보장하지 않는다. Generator family와 noise 분포도 고정하고 저장한다.

Wafer 안의 site를 무작위 행 분할하지 않는다. 같은 wafer의 공간 패턴과 공통 noise가 train과 test에 함께 들어가면 일반화를 과대평가한다. 시간 drift는 과거 train과 이후 test, chamber transfer는 별도 chamber 조건으로 시험한다.

**Blind의 정확한 표현**
Fault label을 분석 입력에서 숨기고 평가 이후 공개했다고 쓴다. 모델 작성자가 fault 정의를 아는 상황을 미지의 실제 fab 원인에 대한 독립 blind 검증이라고 표현하지 않는다.

**새 seed만 바꾸면 충분한가?**
기본 재현성 평가에는 유용하지만 모델 형태에 대한 의존성은 남는다. Noise·센서 가용성·fault 크기·외삽 조건을 바꾼 stress test도 별도로 보고한다.

## W06 가상 공정의 상태와 관측을 정의한다

실제 가스 chemistry를 정밀하게 흉내 내지 않고, 반응·전달·wall·측정 상태를 표현하는 dimensionless surrogate를 사용한다. Recipe 입력은 기준값으로 정규화해 a=source/source0-1, b=bias/bias0-1, p=pressure/pressure0-1, g=gas_ratio/gas_ratio0-1로 둔다.

`q = (1+a) (1-r_loss) ; R = 100 q (1+0.20 b) exp(-0.40 p²) (1+0.15 g) (1-0.20 w)`

R [nm/min], r_loss와 w는 무차원 latent loss와 wall state. 계수는 교육용 가정이다. 실제 반사계측값을 plasma 흡수 손실에 바로 대입하는 모델이 아니다.

`CD_bias = 3 b + 1.5 g + 2 w ; S = 10 - 4 b - 1.5 |g|`

CD_bias [nm], S는 선택비. 이 식은 trade-off를 만드는 학습용 설계이며 실제 공정의 보편적 방향성이나 계수가 아니다.

관측은 실제 상태에 sensor bias와 noise를 더해 만든다. Process variation은 wafer별 latent 상태에, measurement noise는 관측에 추가한다. 같은 seed와 설정이면 결과가 같아야 하며, 정상 상태에서 충분한 variation이 있는지 확인한다.

**중요한 제한**
이 식들을 진단기에 그대로 역대입해 정답을 맞추는 것은 제한적인 자기일관성 검사다. 공개된 관측과 구분 평가만 사용하는 진단 baseline, 다른 계수·noise 조건에서의 평가를 함께 둔다.

## W07 다섯 Fault와 식별 불가능한 경우

| Fault | 주입 위치 | 예상 관측과 반증 |
| --- | --- | --- |
| RF 전달 저하 | 잠재 전달 효율 | RF 비율·KPI 변화. Pressure/gas 동시 변화면 단독 원인 약화 |
| APC 지연 | 압력 동역학 tau | settling 증가. 평균만 보면 누락 가능 |
| MFC delivery bias | 실제 유량 | 내부 readback 정상일 수도 있음. 독립 확인 필요 |
| Wall drift | wafer history의 잠재 상태 | 여러 신호·KPI gradual drift. 다른 교정 동시 변경 주의 |
| Monitor sensor bias | 표시값만 | 해당 sensor 이동·독립 KPI 정상. Feedback 센서와 구분 |

Stage 1은 fault를 하나씩 주입한다. Stage 2는 크기·onset·noise를 바꾼다. Stage 3에서 복합 fault와 학습하지 않은 fault를 넣고 보류가 가능한지 확인한다. 다섯 label 중 하나를 반드시 출력하게 하지 않는다.

**관측의 동등성**
MFC 표시값이 정상이고 독립 유량 데이터가 없으면 MFC bias와 일부 wall drift가 같은 관측을 만들 수 있다. 이 경우의 올바른 출력은 확정 원인 대신 경쟁 가설과 추가 평가다.

**Sensor fault 모델에서 꼭 나눌 것**
모니터 전용 bias와 feedback sensor bias를 나눈다. 후자는 controller의 actuator 동작을 바꾸므로 실제 공정이 변할 수 있다. Day 1 CASE_B는 모니터 전용 예시다.

## W08 Feature의 정의와 추출 기준

| Feature | 계산 정의 | 주의 |
| --- | --- | --- |
| Steady mean/std | 고정된 step 후반 구간의 통계 | 이상마다 구간을 유리하게 바꾸지 않음 |
| Overshoot | 목표 대비 최대 초과량 | 상승·하강 step과 단위 구분 |
| Settling time | 허용 band 안에서 유지되는 첫 시각 | 진입만 하고 다시 나가면 미정착 |
| RF ratio | 동일 기준면의 reflected/forward | forward<=0이면 unavailable |
| Slope | 정해진 시간/wafer 구간 선형 변화 | sampling과 outlier 영향 |
| Map feature | center-edge·방향성·공간 산포 | site 좌표와 edge exclusion |

Settling band 예시는 max(목표의 2%, baseline sensor noise의 3배)다. 유지 시간과 평가 종료를 명시하고, 주어진 trace 안에서 정착하지 않으면 missing_with_reason으로 보고한다. 이 숫자는 초기 교육 설정이며 장비 spec이 아니다.

**완료 조건**
Feature마다 입력 열·단위·계산 구간·결측 정책·가설 연결을 한 줄씩 문서화한다. Flat trace, spike, drift, 빈 trace, 0 power를 이용한 작은 시험을 수행한다.

## W09 SPC 기준과 탐지 성능을 고정한다

단순 z-score 또는 Shewhart 기준을 먼저 만들고 EWMA를 추가한다. CUSUM은 선택 심화다. Normal train에서 평균·산포를 적합한 뒤 validation에서 정상 alarm 부담과 drift 탐지를 비교한다. Test를 열기 전에 threshold와 reset 정책을 저장한다.

| 평가 묶음 | 초기 실습 크기 | 보고 |
| --- | --- | --- |
| 정상 run | 30 runs × 100 wafers | run별 alarm과 평균 false-alarm rate |
| 단일 fault | 5종 × 10 runs × 100 wafers | onset 이후 delay와 miss |
| Stress | noise·누락·fault 크기 변화 | 성능 저하와 적용 한계 |

표의 크기는 계산 시간을 제한하기 위한 교육 설계다. 충분한 통계력을 보장하는 양산 표본 수가 아니다. Run별 결과를 보존하고 confidence interval이나 bootstrap을 붙이되 독립 단위를 run 또는 wafer로 유지한다.

**비교 기준**
같은 데이터에서 단순 threshold와 EWMA를 비교한다. Alert 횟수가 줄었다는 사실만 성공으로 보지 않는다. 비슷한 false-alarm 수준에서 delay와 miss를 비교한다.

**SPC 통과가 root cause 정확도인가?**
아니다. 탐지, 원인 순위, 조치 선택, 최종 회복은 따로 평가한다. 한 단계의 성공을 전체 시스템의 성공으로 합치지 않는다.

## W10 RCA는 점수보다 증거 표를 먼저 만든다

| 가설 | 지지 증거 | 반대 또는 부족한 증거 |
| --- | --- | --- |
| RF 전달 | ratio 상승·rate 감소 | 압력 과도도 변화하면 단독 설명 부족 |
| Pressure control | settling 증가·step 의존 | 독립 gauge가 정상이면 sensor 후보 |
| Gas delivery | 독립 flow·chemistry 변화 | 내부 readback만으로 배제 불가 |
| Wall state | count/clean 이력과 공정 drift | 동시 정비 항목을 분리해야 함 |
| Measurement | 독립 KPI와 모순 | feedback 경로면 실제 공정 영향 가능 |

첫 구현은 명시적 규칙과 weighted score로 충분하다. 각 점수의 이유를 저장하고 score를 확률이라고 부르지 않는다. Bayesian update를 쓸 때에는 prior, likelihood, 센서 간 의존성 가정을 기록하고 calibration을 별도로 평가한다.

**필수 출력**
Top 후보 2개 / 사용한 evidence ID / counter-evidence / 관측 누락 / 다음 평가 / 가설 폐기 기준 / HOLD 여부. 후보 간 점수가 비슷하다는 이유만이 아니라 식별 가능한 관측이 있는지를 판단한다.

**Feature importance가 높으면 원인인가?**
예측에 도움이 된 상관 feature일 수 있다. 개입·시간 순서·독립 관측으로 원인 설명을 추가 검증해야 한다.

## W11 다음 평가를 정보와 비용으로 고른다

각 평가에 두 가설이 예측하는 결과를 미리 적는다. 둘 다 같은 결과를 예측하면 그 평가는 구분력이 작다. 가능한 평가의 시간·wafer 수·비용과 위험을 함께 기록한다. 실제 현장에 적용 가능한 절차인지는 별도 문제다.

| 경쟁 가설 | 후보 평가 | 해석 |
| --- | --- | --- |
| RF vs wall | 고정 가스·압력의 RF 진단 proxy | 전달 정상화 후 KPI 회복 여부 |
| APC vs gauge | 독립 압력 채널·step 응답 | 실제 동역학과 관측 오류 분리 |
| MFC vs wall | 독립 flow proxy | gas delivery 변화 여부 |
| 공정 vs metrology | 같은 wafer의 reference 재측정 | 측정 편향·repeatability |

MVP에서는 “구분 가능한 결과 수/평가 비용” 같은 단순 순위 규칙을 쓴다. Entropy 감소를 쓰려면 보정된 가설 확률과 평가 결과의 likelihood가 필요하다. 계산식이 화려해도 입력 가정이 불명확하면 더 나은 선택이 아니다.

**실험 예산**
초기 원인 진단은 최대 6회 평가로 제한한다는 교육 조건을 둔다. 예산이 끝났는데 식별되지 않으면 HOLD와 필요한 추가 증거를 보고한다. 억지로 정답을 출력하지 않는다.

## W12 DOE와 상호작용을 확인하는 실험

원인 진단을 마친 뒤 합리적인 보정 범위에서 bias와 pressure를 예시 factor로 선택한다. 정규화 범위 [-0.1,+0.1]은 교육용 수치이며 실제 장비 안전 범위를 뜻하지 않는다. 물리적인 hardware fault가 남아 있으면 recipe 탐색에 들어가지 않는다.

| 실험 | 개수 | 목적 |
| --- | --- | --- |
| 2×2 corners × 2회 독립 반복 | 8 | 주효과·interaction·noise |
| Center point 반복 | 4 | 중심 반복성과 곡률 단서 |
| 별도 확인 조건 | 탐색 뒤 선택 | 새 조건의 예측 검증 |

12회 순서는 무작위화하고 lot나 chamber state가 달라지면 block을 둔다. 반복은 같은 숫자를 복제하는 것이 아니라 새 measurement/process realization이다. Rate, CD, selectivity, uniformity 각각에 효과와 불확실성을 보고한다.

`y = b0 + bA A + bB B + bAB A B + error`

A,B는 coded -1/+1. Residual의 시간 순서·분산·비선형성을 확인한다. 4점만 맞춘 포화 모델의 p-value를 만들어 내지 않는다.

**ANOVA가 유의하면 바로 조건을 바꾸나?**
효과의 실제 크기·단위·다른 KPI·재현성과 제약을 확인한다. 통계적 유의성과 공정상 유용성은 다르다.

## W13 조치는 원인에 맞추고 목적함수는 정규화한다

허용 action을 remeasure, sensor_check, hardware_restore, chamber_restore, recipe_adjust, hold로 구분한다. 앞의 복구 action은 합성 상태를 바꾸는 교육용 intervention이다. 실제 장비 정비·교정 방법을 재현하는 API가 아니다.

`Loss = sum_j w_j × |y_j-target_j| / scale_j + change_cost`

KPI 단위가 다르므로 scale_j는 사전 정의한 허용 편차 등으로 정규화한다. Weight와 scale을 test 결과가 좋아지도록 바꾸지 않는다.

| 교육용 제약 | 초기 값 | 의미 |
| --- | --- | --- |
| Etch rate | 95~105 nm/min | 평균 제거 속도 범위 |
| CD bias | -2~+2 nm | 이 문서의 부호 정의 |
| Selectivity | 8 이상 | 목표막/기준막 rate 비 |
| NU_range | 3% 이하 | 정의·sampling 고정 |

위 범위는 프로젝트 평가를 위한 가상 spec이다. 최종 선택은 모든 hard constraint를 만족해야 한다. 성공할 때까지 임의로 spec을 넓히지 않는다. 가능한 조건이 없으면 INFEASIBLE로 보고하고 원인 또는 모델 가정을 재검토한다.

**실패 사례를 만드는 방법**
단일 KPI 최적화 baseline과 multi-KPI 조건을 실제로 비교한다. Baseline이 실패하면 그대로 기록하고 성공하면 성공으로 기록한다. 발표를 위해 실패 결과를 미리 강제하지 않는다.

## W14 회복 검증과 완료 판단

선택한 action과 설정을 고정한 뒤 새로운 seed의 wafer에서 평가한다. 같은 noisy sample로 조건을 고르고 그 sample의 개선을 최종 성능으로 보고하지 않는다. 평균뿐 아니라 각 KPI의 분포·spec 이탈 수·시간 drift를 저장한다.

| 게이트 | 통과 조건 또는 출력 |
| --- | --- |
| 데이터 | schema·단위·시간·누수 검증 통과 |
| 원인 | 증거·반증·대안 가설을 기록 |
| 조치 | 허용 action과 가상 범위 준수 |
| 확인 | 독립 20 wafer, 2개 가상 lot의 결과 보고 |
| 안정성 | KPI별 이탈과 추가 drift를 보고 |
| 한계 | 복합 fault·미지 조건에서의 실패/보류 표시 |

20 wafer는 프로젝트 시간 안의 최소 확인 설계이며 실제 양산 qualification의 충분한 표본 수가 아니다. 전부 spec 안이어도 미래의 실패 확률이 0이라고 주장할 수 없다. 어떤 환경과 크기의 이상까지 확인했는지 적는다.

**완료 상태**
PASS: 정의한 합성 평가 기준 충족 / FAIL: 기준 미충족 / HOLD: 증거 또는 측정 부족 / INFEASIBLE: 허용 조치로 제약을 만족할 수 없음. 모든 case가 PASS일 필요는 없다.

## W15 Focus와 Overlay의 합성 모델

트랙 B는 scanner의 내부 servo나 광학계를 재현하지 않는다. Spatial error와 시간순 subsystem proxy가 주어졌을 때 장비·공정·계측 가설을 구분하는 진단 연습이다. 교재의 affine model을 기본으로 사용한다.

`dx = a0 + a1 x + a2 y + r_x ; dy = b0 + b1 x + b2 y + r_y`

x,y [mm], dx,dy [nm]. r은 국소·wafer 공통·측정 성분을 분리해 생성한다. Site별 독립 noise만 쓰면 실제 상관성을 과소평가할 수 있다.

`CD = CD0 + cD dose_offset + cF focus_offset² + cDF dose_offset × focus_offset`

교육용 response. 계수는 material·resist 보편 법칙이 아니며, 비유일성과 상호작용을 연습하기 위한 것이다.

| 상황 | 주입할 변화 | 분리할 가설 |
| --- | --- | --- |
| Global shift | a0,b0 변화 | alignment·좌표·계측 offset |
| Spatial drift | slope·rotation 변화 | stage·thermal·wafer 영향 |
| Local height issue | 국소 focus pattern | wafer·chuck·leveling |
| Measurement bias | 관측 좌표·값만 변화 | 실제 노광과 계측 구분 |

**모델 residual을 줄이는 것이 목표인가?**
진단 가능한 패턴을 찾고 독립 wafer에서 개선과 한계를 검증하는 것이 목표다. 고차 적합만으로 원인을 설명하지 않는다.

## W16 진단 실습과 에스컬레이션 산출물

Day 1 overlay_sites.csv로 먼저 x/y 단위와 wafer별 map을 확인한다. 21일 확장에서는 별도의 정상 wafer와 이상 wafer를 만들고 reference recipe, maintenance event, sensor availability를 추가한다.

| 작업 | 완료 조건 |
| --- | --- |
| 1. Baseline | translation-only와 affine model 비교 |
| 2. Residual map | 보정 전후 vector·RMS·상위 분위수 |
| 3. Holdout | fit에 쓰지 않은 wafer·site에서 평가 |
| 4. 가설 분리 | tool·wafer/mark·metrology의 예측 차이 |
| 5. 조치 계획 | reference test·추가 로그·복귀 조건 |
| 6. 지원 요청 | 시간 창·재현 조건·증거·남은 요청 |

TSE 보고서는 root cause를 무조건 확정할 필요가 없다. 중앙 조직이 다음 단계로 바로 분석할 수 있도록 범위를 줄이고 재현 정보를 제공하면 유의미한 산출물이다. 조치가 없어도 무엇이 아직 부족한지 명확히 할 수 있다.

**최종 한 장의 구성**
Symptom / Last known good / Change timeline / Before-after residual map / Hypotheses / Tests already performed / Workaround limits / Requested support. 합성 데이터임을 제목 아래 표시한다.

## W17 검사 Recipe의 목적을 다시 정의한다

트랙 C는 합성 defect candidate의 score와 wafer context를 이용해 review 정책을 비교한다. 실제 KLA optical pipeline이나 AI model을 복제하지 않는다. DOI, nuisance, 가용 reference label을 명시하고 label이 없는 것을 정상으로 간주하지 않는다.

| 입력 | 설명 |
| --- | --- |
| candidate_id / wafer_id | 후보와 독립 평가 단위 |
| x_mm / y_mm | 좌표와 spatial pattern |
| signal_score | 검출·분류에 쓸 관측 score |
| size_proxy / background_proxy | 교육용 보조 관측 |
| review_label | 독립 review가 있는 경우에만 사용 |
| recipe_id / available_at | 설정과 사용 가능 시점 |

첫 모델은 score threshold 하나다. 두 번째는 background에 따라 threshold를 다르게 하는 단순한 규칙 또는 해석 가능한 분류기다. 같은 validation wafer에서 선택하고 test wafer에는 설정을 고정한다.

**성능 목표의 형태**
Recall을 최대화하되 nuisance/wafer 또는 review budget 제약을 둔다. 예시 threshold나 목표 수치는 학습용이며 고객 spec이 아니다. 성능을 못 맞추면 그 trade-off 자체가 결과다.

## W18 표본 선택과 독립 검증

확인된 DOI만 모아 만든 데이터로는 실제 prevalence를 모른다. 높은 score만 review하면 precision조차 전체 후보를 대표하지 않을 수 있다. Score 구간·wafer 위치·결함 종류에 따라 stratified review를 계획하고 선택 확률을 저장한다.

`Estimated count = sum_reviewed (indicator / sampling_probability)`

확률 표본에서 쓰는 역확률 가중 추정의 기본 형태. 선택 확률이 알려져야 하며 작은 확률의 큰 가중치는 분산을 키운다.

| 보고 지표 | 해석 |
| --- | --- |
| DOI recall와 FN | 중요 결함을 놓치는 정도 |
| Precision | 검출된 후보의 유용성 |
| Nuisance/wafer | 불필요한 review 부담 |
| 종류·크기별 성능 | 전체 평균에 숨은 취약점 |
| Review time 또는 budget | 운영 비용의 proxy |
| Label coverage와 불확실성 | 평가가 대표하는 범위 |

Day 1은 완전 label이 따로 있는 교육 데이터지만, 이후 일부 label만 제공하는 조건을 추가한다. Label을 열어 threshold를 고친 경우 그 wafer는 더 이상 최종 test가 아니다.

**작은 DOI가 test에 하나도 없으면?**
그 종류의 recall을 100%라고 쓰지 않는다. 평가 불가와 표본 부족을 보고하고 필요한 추가 표본을 명시한다.

## W19 보류를 실패가 아닌 명시적 결정으로 만든다

| HOLD 조건 | 필요한 다음 행동 |
| --- | --- |
| 단위·키·시간 불일치 | 데이터 정합성 확인 |
| 독립 관측이 없어 가설이 겹침 | 식별 가능한 새 measurement |
| 예측 구간이 spec 경계와 겹침 | 추가 반복 또는 reference 측정 |
| Training 범위를 벗어남 | 적용 제한과 새 검증 |
| 점수의 확률 해석이 검증 안 됨 | 순위로 보고하고 calibration 평가 |
| 조치 예산 소진 | 남은 원인·추가 요청 보고 |

Abstention을 많이 하면 accuracy가 높아 보일 수 있다. 답을 낸 case 비율인 coverage와 그 subset의 오류율, 전체 중요한 miss를 함께 보고한다. Uncertainty를 이용해 불리한 case를 숨기지 않는다.

**설명 가능한 출력**
Decision=HOLD / Reason=independent pressure reference missing / Competing hypotheses=APC lag, gauge bias / Next evaluation=reference gauge step comparison / Cost=1 diagnostic unit.

Bootstrap에서는 site를 독립으로 재표집하기보다 wafer 또는 run 묶음을 재표집한다. 모델 uncertainty, measurement uncertainty, simulator mismatch를 각각 구분하고 포함하지 못한 항목을 적는다.

## W20 작성할 테스트와 실제 수행 상태

| 시험 | 검증하려는 행동 |
| --- | --- |
| 재현성 | 같은 seed·설정의 데이터가 같음 |
| 입력 계약 | 빈 입력·중복 key·NaN·잘못된 단위 거부 |
| 정상·경계 사례 | 상수 trace와 0 forward의 명시 처리 |
| 누수 방지 | truth·미래 metrology가 분석 입력에 없음 |
| 평가 단위 | 동일 wafer가 train/test에 겹치지 않음 |
| 제약 | 범위 밖 action 거부, feasible 없으면 명시 |
| 보류 | 비식별/누락 조건에서 이유를 출력 |
| 지표 | 분모 0과 miss/censoring 정책 준수 |

Day 1에 제공하는 테스트는 생성기의 재현성·schema·label 분리·case 방향·오류 입력에 대한 기초 검증이다. 이 테스트의 성공을 전체 진단 프로젝트의 성능이나 물리 검증으로 확대하지 않는다.

**구현 상태를 적는 방식**
Implemented / Executed / Passed in synthetic evaluation / Not evaluated를 분리한다. README의 결과 숫자는 실행 파일에서 생성하고 사용한 seed·설정·코드 버전에 연결한다.

## W21 작업을 작은 결과물로 나눈다

| 순서 | 시간 가이드 | 완료 기준 |
| --- | --- | --- |
| Day 1 시작 | 40분 | CSV 확인·case 가설 기록 |
| 데이터 계약·정상 기준 | 2시간 | schema 검사·seed·baseline |
| Fault와 feature | 3시간 | 5종·결측·계산 정의 |
| 탐지와 RCA | 3시간 | baseline 비교·counter-evidence |
| 평가와 recovery | 3시간 | 이유 있는 평가·제약·독립 확인 |
| 보고·재현 | 2시간 | 한 장 요약·재실행·한계 |
| TSE 선택 확장 | 4시간 | residual map·escalation 문서 |
| FAE 선택 확장 | 4시간 | threshold 평가·sampling 한계 |

시간은 과제 배치용 추정이며 실제 코딩 숙련도에 따라 달라진다. 총량을 줄여야 하면 선택 트랙·고급 알고리즘부터 미룬다. 데이터 정의와 검증·판단 기록을 생략해서 분량을 맞추지 않는다.

**매일 저장**
무엇을 만들었는지보다 어떤 판단이 가능해졌는지 기록한다. 구현한 기능, 실행한 검증, 실패한 기준, 내일의 가장 작은 다음 평가를 분리한다.

## W22 의사결정 기록을 직접 채운다

| 항목 | 작성할 내용 |
| --- | --- |
| Decision ID / 시점 | 사용 가능한 데이터의 마감 시각 |
| Observed | 값·단위·기간·wafer/site·baseline |
| Hypotheses | 상위 두 원인과 예상 메커니즘 |
| Evidence | 각 가설을 지지하는 데이터 ID |
| Counter-evidence | 맞지 않는 관측·빠진 관측 |
| Next evaluation | 고정 조건·바꿀 조건·예산 |
| Falsification | 어떤 결과가 가설을 약화시키는가 |
| Action / HOLD | 선택한 조치와 선택 이유 |
| Verification | 확인할 KPI·독립 평가 단위·종료 기준 |
| Unknown | 현재 구분 못 하는 원인·미검증 범위 |

예시: “압력 평균 정상”은 관측으로 쓰되 실제 압력 정상이라고 바꾸지 않는다. “RF가 원인”은 가설 또는 추론이며 독립 평가가 부족하면 확정으로 쓰지 않는다. 가정의 변경은 이전 기록을 지우지 않고 새 decision으로 남긴다.

**오늘의 작성 과제**
CASE_A 또는 CASE_B 하나를 골라 표를 채운다. 다음 실험의 결과를 보기 전에 반증 기준과 종료 기준을 적고 저장한다.

## W23 직무별 한 장 요약과 GitHub 구성

| 공통 한 장 | 포함할 내용 |
| --- | --- |
| 문제와 역할 | 가상 customer issue·본인이 수행한 일 |
| 핵심 증거 | 단위·기간·범례가 있는 figure |
| 가설과 평가 | 후보·반증·선택 이유 |
| 조치와 검증 | 변경·비교군·독립 평가 결과 |
| 실패와 한계 | 미해결 case·모델 가정·보류 |
| 재현 링크 | 코드·설정·data manifest·실행법 |

PSE용은 multi-KPI 회복과 trade-off, TSE용은 원인 격리·복구 계획과 escalation, FAE용은 application별 성능·sampling·고객 acceptance 근거를 앞에 둔다. 하나의 그림에 세 직무의 모든 내용을 넣지 않는다.

GitHub에는 README, 명세, 재현 코드, 작은 합성 예제, 테스트, decision log, 결과 요약을 둔다. 대용량 결과와 환경·비밀 값은 분리한다. 원본 논문·공동 연구 데이터는 공개 가능한 범위를 확인한 자료만 사용한다.

**성과 문장 규칙**
아직 계산하지 않은 accuracy·회복률·시간 절감을 적지 않는다. 완료 전에는 “설계·구현 중”, 완료 후에는 평가 환경과 범위를 포함해 쓴다. 실제 회사 장비에 적용했다고 표현하지 않는다.

## W24 제출 전 스스로 답할 질문

| 질문 | 자료에서 보여줄 증거 |
| --- | --- |
| 모델이 틀리면 결과는 무엇을 의미하나 | 가정·민감도·적용 한계 |
| Fault 정답을 코드가 미리 알았나 | 입력 schema와 truth 분리 |
| 왜 그 평가를 먼저 했나 | 경쟁 가설의 다른 예측·비용 |
| 확률은 어떻게 보정했나 | 보정 결과 또는 score라는 명시 |
| 실패를 억지로 만들었나 | 사전 고정 baseline과 실제 결과 |
| 회복이 재현되는가 | 새 seed·wafer·lot 결과 |
| 모든 KPI가 좋아졌는가 | 다중 KPI와 부작용·miss |
| 고객에게 무엇을 요청할 것인가 | 추가 데이터·조치·업데이트 계획 |

완료 기준은 “모든 결과가 좋음”이 아니다. 정의·구현·검증·한계가 일치하고, 원인을 모를 때도 다음에 무엇을 확인해야 하는지 설명할 수 있으면 포트폴리오 사례로 정리할 수 있다. 채용 합격이나 실제 공정 운용 가능성을 보장하는 평가표는 아니다.

**마지막 실습**
자료를 닫고 3분 설명을 녹음한다. 질문 2개를 무작위로 골라 추가로 답한다. 설명하지 못한 코드·식·지표는 다시 확인한 뒤 자신의 기여 범위에 반영한다.
