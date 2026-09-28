# Etch 모델 명세 — Ar global plasma + generic surface reaction

모델 버전: `etch-ar-global-0.1.0`

구현: `sim_app/models/etch.py`
증거 수준: **문헌식과 명시적 축약 가정의 구현 / 실제 장비 검증 전**

이 모델은 압력·전력·유량·바이어스를 바꾸어 벌크 플라즈마와 일반화한 표면 제거의 관계를 공부하는 도구다. 실제 Si/SF6, SiO2/CF4, 상용 ICP/RIE 장비의 완전한 반응망·전기장·형상 해석을 구현했다고 해석하면 안 된다. `Advanced`의 반응 계수는 최적화 레시피가 아니라 **모델 가정의 민감도를 확인하는 입력**이다.

## 계산 흐름과 단위

1. 레시피 설정에 고장을 적용해 실제 반사율·압력·가스 공급·벽 손실을 계산한다.
2. Ar 입자 수지의 근을 찾아 전자온도 `Te`를 계산한다.
3. Ar 손실과 가상 반응 가스의 해리 에너지를 합한 전력 수지에서 전자밀도 `ne`를 구한다.
4. 이온 플럭스·쉬스 에너지 근사와 라디칼 수지에서 표면에 도달하는 공급을 계산한다.
5. 표면 피복률의 선형 ODE를 적분하여 제거 깊이·마스크 손실을 얻는다.

내부 단위는 m, s, K, Pa, W이며 `Te`와 입자 에너지는 eV다. `bias_voltage_v`는 음의 바이어스의 **절댓값**이다. `source_power_w`는 소스의 순방향 전력이며 바이어스 전원의 전력과 다르다. `sccm`의 표준 상태는 **273.15 K, 101325 Pa**로 고정했다. 결과는 결정론적이며 측정 잡음·무작위 seed를 쓰지 않는다.

## 1. 흡수 전력과 챔버

입력 반사율 `r`, 결합 효율 `eta`, 듀티 `D`에 대해:

```text
Pabs = Pforward × (1-r) × eta × D
V = π R² L
A = 2π R(R+L)
ng = p/(kB Tg)
nAr = (1-x) ng
lambda_i = 1/(ng sigma_i)
```

`sigma_i`는 일정한 유효 충돌 단면적이라는 **가정**이다. 기본 `1e-18 m²`는 에너지별 충돌 단면적 데이터베이스를 대신하는 조정값이다. 가스 온도와 전력 결합 효율도 입력이며, 에너지 수지로 기체 온도까지 구하거나 회로 임피던스를 계산하지 않는다.

## 2. Ar 입자·에너지 수지

원통의 손실 면적 근사는 아래와 같다. `hL`, `hR`와 `Aeff`의 형태는 Berenguer–Katsonis의 식 (1)–(3)에 근거한다. 여기서는 하나의 벌크 밀도와 경계 손실 인자로 축약하고 공간 분포는 풀지 않는다. [원문](https://doi.org/10.1155/2012/740869)

```text
hL = 0.86 / sqrt(3 + L/(2 lambda_i))
hR = 0.80 / sqrt(4 + R/lambda_i)
Aeff = 2π(hL R² + hR R L)
uB = sqrt(e Te / mAr)
nAr kiz(Te) = uB Aeff / V
```

마지막 식은 생성과 Bohm 벽 손실의 균형이다. `Te`만 남으므로 고정 압력·형상에서 소스 전력을 올려도 `Te`가 직접 증가하지 않는 것이 이 축약 모델의 특징이다. 전자온도를 독립 입력으로 동시에 지정하지 않는다.

사용한 Ar Maxwellian 속도 계수는 다음과 같다. `kiz`, `kex`의 계수, 15.76/12.14 eV 유효 에너지와 **1–7 eV 적용 범위**는 Kim의 Table 6.2와 식 (6.13)–(6.15)를 확인했다. [Berkeley 원문, 본문 60쪽](https://www2.eecs.berkeley.edu/Pubs/TechRpts/2006/Archive/EECS-2006-56.pdf)

```text
kiz = 2.34e-14 Te^0.59 exp(-17.44/Te)     [m³/s]
kex = 2.48e-14 Te^0.33 exp(-12.78/Te)     [m³/s]
kel = (0.084 + 0.537 Te + 1.192 Te²)1e-14 [m³/s]
Ec = 15.76 + 12.14 kex/kiz + 3(me/mAr)Te kel/kiz [eV/pair]
Epair = Ec + 2 Te + 5.2 Te
Pabs = ne e uB Aeff Epair + P_dissociation(ne)
```

`kel`은 위 Kim 표와 동일식이 아니라 Yildiz–Celik 식 (10)의 대체 근사다. `2Te`, `5.2Te` 벽 손실은 같은 문헌의 식 (13)–(15)를 사용했다. 원문의 **추력기 결과를 식각 장비 검증에 전용하지 않았으며**, 사용한 것은 명시한 국소 계수와 수지 구성뿐이다. [IEPC-2015-266 원문, PDF 7쪽](https://electricrocket.org/IEPC/IEPC-2015-266_ISTS-2015-b-266.pdf)

이분법 80회로 두 수지를 푼다. 입자 근이 1–7 eV에 없으면 `status=outside_rate_fit`으로 표시한다. 이때 0 출력은 **모델 계산 범위 밖**이라는 표시이며 실제 방전이 꺼진다는 주장이 아니다. `Pabs=0`이면 `status=off`이고 이온·라디칼·제거량을 0으로 반환한다. 양의 전력에서 점화 문턱, E/H 모드 전환, 잔광, 펄스 주파수는 계산하지 않는다.

## 3. 희석된 가상 X2와 라디칼 X

다음은 **이 프로젝트에서 정의한 교육용 반응 모델**이다. 계수를 SF6·CF4·Cl2 등 특정 가스의 측정값으로 해석하지 않는다. 반응 가스 최대 분율은 0.2이며 0.05 초과에서는 Ar 우세/부착 무시 근사의 한계를 경고한다. 실제 반응 가스는 작은 첨가량도 전자 에너지·음이온에 큰 영향을 줄 수 있으므로 5%가 검증된 물리적 안전 범위라는 뜻은 아니다.

```text
tau = ng V / (Qtotal particles_per_sccm_s)
kd = A_d exp(-Ed/Te)
S2 = Qreactive particles_per_sccm_s / V
nX2 = S2 / (1/tau + kd ne)
G = 2 kd ne nX2                           [radicals/m³/s]
P_dissociation = e Ed kd ne nX2 V          [W]
vX = sqrt(8 kB Tg/(π mX))
GammaX = nX vX/4
G = nX [1/tau + gamma vX(A-Awafer)/(4V)] + wafer_consumption/V
```

웨이퍼 반경은 챔버 반경의 0.8배인 **유효 처리 면적 가정**이다. 웨이퍼의 정상 반응 소비량은 아래 표면 모델을 면적 적분해 수지에 포함한다. 벽 손실 확률은 웨이퍼를 제외한 벽에만 적용한다. 해리 생성은 공급된 X2당 X 2개를 넘지 않는다. 벽에서 생긴 생성물의 환류, X의 이온화·전자 부착, 압력에 대한 해리 입자수 피드백은 제외했다.

## 4. 쉬스와 이온 에너지

```text
Gamma_i = hL ne uB
Vfloat = 0.5 Te ln(mAr/(2πme))
Vs = |Vbias| + Vfloat
sCL = sqrt[(4/9) eps0 sqrt(2e/mAr) Vs^1.5 / (e Gamma_i)]
Ei = 0.5 Te + Vs/(1+sCL/lambda_i)          [eV]
```

`sCL`은 평판 DC Child–Langmuir 척도다. `1/(1+sCL/lambda_i)`는 **이 구현이 선택한 충돌 에너지 감쇠 근사**이며 해당 문헌에서 검증된 식각 쉬스 수율이라는 주장이 아니다. RF IEDF, 각도 분포, 부착·전하 교환 반응망, 이차전자, 바이어스의 벌크 전자 가열은 없다. 바이어스 전원 에너지는 소스 전력 수지에 포함되지 않는 독립 공급이다. 쉬스가 높이의 20%보다 크면 얇은 쉬스 근사가 약해졌다고 경고한다.

## 5. 표면 반응과 제거 깊이

표면 제거의 물리·화학·이온 보조 성분을 구별하지만 아래 **수율 함수와 기본 계수는 이 프로젝트의 가정**이다. 실제 재료 측정값으로 보정하지 않았다.

```text
Y(E) = Yscale max(sqrt(E/Ethreshold)-1, 0)
a = sticking GammaX / Ns
b = kdes + kchem + Gamma_i Yassist/Ns
dtheta/dt = a(1-theta) - b theta
theta(0) = 0
theta_ss = a/(a+b)
theta(t) = theta_ss[1-exp(-(a+b)t)]
Jtarget(t) = (Ns kchem + Gamma_i Yassist)theta(t) + Gamma_i Ysputter
depth(t) = integral(Jtarget(t), 0..t)/Ntarget
mask_depth(t) = Gamma_i Ymask t/Nmask
```

깊이 적분은 해석식이며 짧은 시간의 상쇄 오차를 피하는 급수형을 사용한다. 기체와 플라즈마는 정상 해를 고정하고 표면만 초기 피복률 0에서 시작한다. 따라서 **초기 과잉 흡착의 기체 피드백을 무시한 준정상 분리 근사**이고 완전한 시동 transient가 아니다. 타깃 기본 원자밀도 `5e28 m^-3`는 Si와 비슷한 규모를 택한 가정이며, 특정 Si/마스크 조합의 선택비를 보증하지 않는다.

정상 선택비는 `steady target rate / steady mask rate`다. 분모가 0이면 `selectivity_defined=false`로 반환하고 수치 0은 계산 불가 표시로만 쓴다. 마스크 두께 한계, 막 관통·엔드포인트, CD, ARDE, charging, 표면 거칠기, sidewall passivation은 구현하지 않았다.

## 6. 공간 표시의 의미

```text
q = r²/Rwafer²
Gamma_i(q) = mean_Gamma_i [1 + a_radial(0.5-q)]
```

`q`는 면적에 균등한 좌표다. 위 분포의 면적 평균은 정확히 1이다. 라디칼 플럭스와 에너지는 균일하다고 두고 위치별 표면 반응만 다시 계산한다. 화면의 방사형 지도는 **가정한 비균일 플럭스에서 발생한 깊이 분포**이며, 챔버 공간 plasma solver나 패턴 측벽 계산 결과가 아니다. KPI는 `q`의 101점 사다리꼴 면적 평균, 라디칼의 정상 웨이퍼 소비 수지는 41점 평균을 쓴다. 비균일도는 `(최대깊이-최소깊이)/(2×면적평균깊이)×100%`다. 시간 곡선은 면적 평균 이온 플럭스를 쓰는 균일 참고 사례이므로 비선형 반응이 있을 때 방사형 평균 KPI와 약간 다를 수 있다.

## 7. 고장과 복구

| 고장 | 직접 바뀌는 상류 항 | 결과 계산 |
| --- | --- | --- |
| RF 매칭 이탈 | `r_actual=r+(1-r)severity` | 흡수 전력부터 전 수지 재계산 |
| 압력 제어 편차 | `p_actual=p_set(1+severity)` | 중성 밀도·충돌·수지 재계산 |
| 반응 가스 공급 저하 | 반응 유량 `×(1-severity)` | Ar 유량과 압력 제어 유지; 총 유량·분율·체류시간 재계산 |
| 벽 상태 변화 | `gamma_actual=gamma+(1-gamma)severity` | 라디칼 벽 손실·표면 공급 재계산 |

고장별 식각 KPI를 미리 지정하지 않는다. 고장 강도 0 또는 정상 조건으로 되돌리면 원래 입력의 결정론적 해로 복귀한다. 이것은 **내부 일관성 확인**이며 실제 장비의 고장 진단 성공률이 아니다.

## 8. 검증 범위와 다음 검증

`python -m unittest discover -s sim_app/tests -p test_etch.py -v`:

- 입자·에너지·라디칼 수지 상대 잔차, 공급 상한, 피복률 범위
- 0 전력 / 0 결합 / 완전 반사 / 0 듀티 / 0 처리시간
- 순수 Ar에서 `ne∝Pabs` 및 고정 압력의 `Te` 불변
- 바이어스 변화와 이온 에너지, 고장 상류 조건 변화와 정상 복구
- 31개 노출 입력의 최소·최대 값 62개, 잘못된 값 거부, JSON 유한성
- 1–7 eV 적용 범위 밖 상태, 짧은 시간 적분, 균일 공간 분포

테스트 통과는 구현과 위 한계 내 수치 일관성의 증거다. 실험/상용 해석기와의 교차 검증은 아직 없다. 다음 단계는 순수 Ar 공개 실험의 압력·형상·전력·`Te/ne`를 독립 검증점으로 고정하고, 불일치를 보존한 채 유효계수의 식별 가능성과 오차를 보고하는 것이다. 그 후 한 재료·한 가스계의 반응망 및 독립 etch-rate/수율 데이터를 추가한다.
