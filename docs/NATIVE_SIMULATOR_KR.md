# Native Feature Simulator · 시작 및 모델 설명

**목표 입력·판정·새 진단 그래프:** [목표 단면과 공정 평가 사용법](NATIVE_TARGET_REVIEW_KR.md).

이 작업 공간은 **Python에서 ViennaPS 4.6.2 / ViennaLS 5.8.5를 실행하는 2D 형상 해석기**다.
기존 브라우저 학습 도구의 0D/1D 결과를 단면처럼 늘려 그린 것이 아니다.
입자 수송과 표면 반응으로 국소 이동 속도를 계산하고 level-set 형상을 갱신한다.
현재 실제 장비에 대한 보정·정량 검증은 수행하지 않았다.

## 1. 바로 실행

Windows / Python 3.12에서 저장소 루트 기준:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r native_lab/requirements.txt
cd sim_app/frontend
pnpm install --frozen-lockfile
pnpm build
cd ../..
.\START_NATIVE_LAB.ps1
```

브라우저에서 <http://127.0.0.1:8765>를 연다. 다른 PC에 노출하지 않도록 loopback에만 바인딩한다.
스크립트 실행이 제한된 PC에서는 정책을 바꾸지 않고 다음 명령으로 시작할 수 있다.

```powershell
.\.venv\Scripts\python.exe -m native_lab.server
```

**공개 GitHub Pages는 저장된 네이티브 계산 예제 뷰어다.** 새 조건 계산은 위 로컬 Python 서버가 필요하다.
공개 사이트에서 localhost로 몰래 연결하지 않는다. 로컬 서버와 웹 UI는 같은 origin을 사용한다.
한 번에 하나의 네이티브 작업만 실행하며, 작업마다 별도 Python 프로세스를 사용한다.

## 2. ripple / scallop과 보고서

**초기 표면 형상**에서 평면 ripple 또는 측벽 scallop을 선택한다. 진폭·반복 수를 지정하고 Etch/ALD를 실행한다. 예제 버튼으로 실제 계산된 네 가지 경우를 먼저 볼 수 있다.
이는 초기 요철을 공정으로 변화시키는 계산이다. 요철의 자발적 발생이나 Bosch scallop 생성은 풀지 않는다. 새 형상에는 마스크가 없다.
평면 Rq/Ra/PV, 평균 제거·성장량, 선형 추세를 뺀 좌우 측벽 Rq를 기록한다. 작은 차이는 격자·시드·입자 수 검사가 필요하다.
측정 정의, 실험 계획, **현재 단면 SVG / 보고서에 담기** 사용법은 [개인 프로젝트 안내](PROJECT_REPORT_KR.md)를 따른다.

## 2a. 첫 실험 — Etch

1. `Si / SF₆–O₂ Etch`에서 현재 **저장된 계산 예제**를 재생한다.
2. `비교 기준으로 고정`을 누른다. 이후 결과 위에 기준의 최종 단면을 겹쳐 볼 수 있다.
3. 입사 이온 **방향성 지수만** 500에서 20으로 줄여 `Run simulation`을 실행한다.
4. 중앙 깊이뿐 아니라 절반 깊이의 폭, 옆벽 형상을 비교한다.
5. 동일 조건에서 격자와 입자 수를 바꿔 차이가 물리 모델의 응답인지 수치 오차인지 확인한다.

저장된 Etch 변형 예제는 방향성 지수와 O 공급을 함께 바꾼 **복합 비교 사례**다.
둘 중 어느 변화가 원인인지 분리하려면 한 변수씩 별도로 실행해야 한다.

## 3. 첫 실험 — ALD

1. `Al₂O₃ / 제한 반응 ALD`의 기본 조건을 불러온다.
2. 노출 시간을 0.05 s에서 0.002 s로 줄여 계산한다.
3. 상단과 바닥의 두께, 바닥/상단 비율을 함께 읽는다. 공급이 충분하면 균일한 막도 정상적인 결과다.
4. 다음에는 사이클 수 또는 초기 개구 폭 중 하나만 바꿔 통로 축소와 피복의 관계를 본다.

현재 ALD 시간축은 **사이클 수**다. 재생 시간을 실제 챔버 처리 시간으로 해석하면 안 된다.
제한 반응물의 한 pulse를 계산하고 반대 반응 및 퍼지는 완료된 것으로 가정한다.
화학 계수의 온도 의존성은 보정하지 않았으므로 온도 변경은 입사 열 플럭스만 바꾼다.

## 4. 엔진이 계산하는 것

### Etch

- 원래 구현: ViennaPS `SF6O2Etching`, Si 기판과 유효 마스크.
- 이온·F·O 입자 추적으로 위치별 수송·재반사/그림자 효과를 계산한다.
- 이온 에너지·입사각, 표면 피복, 화학 반응·스퍼터링·이온 보조 반응으로 속도를 계산한다.
- `∂φ/∂t + Vn |∇φ| = 0`을 통해 형상을 이동한다. 음의 속도는 제거다.
- 입구 플럭스 단위는 `10^15 cm^-2 s^-1`, 에너지는 eV다.

RF 회로/전자기장/플라즈마 발생 자체는 풀지 않는다. 따라서 전력 W나 유량 sccm을 임의로 이온 플럭스에 연결하지 않았다.
이는 feature-scale 경계조건이며, reactor-scale 모델과 연결하는 별도 보정 단계가 필요하다.

**마스크 한계:** upstream 기본 마스크의 유효 밀도는 `500 × 10^22 atoms/cm³`다.
이는 실제 재료의 밀도로 해석할 수 없는 견고한 수치 마스크 설정이다.
현재 마스크 소모 수치는 이 모델 안의 응답이며 실제 SiO₂/PR 선택비로 제시하면 안 된다.

### ALD

- 원래 구현: ViennaPS `SingleParticleALD`와 ViennaLS의 이동 경계.
- TMA의 질량 72.09 u와 입력 분압·온도로 열 입사 플럭스를 계산한다.
- 위치별 피복률 θ에 따라 sticking이 `β(1−θ)`로 감소하고 입자는 확산 재반사된다.
- `dθ/dt = [Γ β (1−θ) − Γev θ] / Nsites`.
- 한 묶음의 성장량은 `GPC × θ × 묶음 사이클 수`다.
- 형상이 바뀌면 새 표면에서 수송을 다시 계산한다. 첫 사이클을 단순 N배 투영하지 않는다.

논문과 API의 기호를 주의해야 한다. Aguinsky 논문의 `s0`는 **자리 면적(m²)**이나,
이 버전의 `SingleParticleALDParams.s0`는 코드상 분모에 놓인 **자리 밀도(m⁻²)**다.
이 프로젝트는 사용자 입력 nm⁻²를 m⁻²로 변환해 전달한다.

기본 부착 계수 0.0075와 탈착 플럭스 `3e19 m⁻² s⁻¹`는 Aguinsky Table 2의 출발값이다.
자리 밀도 5 nm⁻²와 현재 구조·분압은 프로젝트 가정이며 해당 논문의 실험 피팅 재현은 아니다.
상단 막이 아직 없는 초기 프레임에서는 바닥/상단 비율을 정의할 수 없어 화면에 `—`를 표시한다.
JSON의 해당 초기 비율 값 0은 미성장 프레임의 저장용 값이며, 0% 피복률 측정값으로 해석하지 않는다.
반대 반응 포화, 완전 퍼지, Knudsen 수송을 가정하며 불순물·핵생성·완전 반응망은 제외한다.

## 5. 좌표·경계·수치 설정

| 항목 | 설정 |
|---|---|
| 공간 | 2D x–y 단면, x 수평 / y 위쪽 + |
| 길이 | 엔진 µm, 화면·JSON 단면 nm |
| 화면 | x/y 같은 축척. 확대 시 두 축을 같은 배율로 변경 |
| 경계 | 좌우 reflective, 세로 infinite |
| 형상 | level-set 연속 경계, 내보낸 선분을 그대로 표시 |
| 공간차분 | Engquist–Osher 1차, 기본 시간차분 Forward Euler |
| CFL | time step ratio 0.4999 |
| 난수 | 단일 스레드, 고정 seed + 구간/묶음 번호 |
| ray 제한 | 최대 재반사 10000, 경계 충돌 1000 |
| Etch | 출력 구간마다 native Process 계산, 내부 CFL substep |
| ALD | 묶음당 포화 성장량 ≤ 0.4격자, 피복률 dt 자동 상한 |

입자 수에 따른 통계적 울퉁불퉁함과 격자 오차는 실제 표면 거칠기가 아니다.
기본 설정은 탐색용이며 보고서용 결과는 격자·입자 수·seed·시간 간격을 바꿔 확인해야 한다.
ALD에서 샘플 위치의 통로가 2격자보다 좁아지면 해상도 한계로 중단한다.
이는 실제 장비에서의 완전 pinch-off 시점을 보증하는 판정이 아니다.

## 6. 결과와 재현

모든 로컬 실행은 `outputs/native_lab/<run-id>/`에 저장한다.

- `request.json`: 검증·정규화한 실제 입력
- `status.json`: 진행률, 완료/실패/중단, 최종 파일 SHA-256
- `worker.log`: native 경고 및 오류
- `result.json`: 모든 프레임·지표·수치 설정·버전·가정
- `final_surface*`, `final_levelset*`: native 형상 출력

웹의 `전체 결과`는 마지막 완료 실행의 JSON을 저장한다. 실행 기록에서 다시 열 수 있다.
입력을 바꿔도 마지막 결과를 새 조건의 계산처럼 표시하지 않는다.

```powershell
.\.venv\Scripts\python.exe -m native_lab.cli --model etch --output outputs/native_lab/manual-etch
.\.venv\Scripts\python.exe -m native_lab.cli --model ald --params my_ald_params.json --output outputs/native_lab/manual-ald
```

`--params` 파일은 파라미터 객체만 담는다. 기존 실행 폴더는 덮어쓰지 않는다.
웹의 실행 기록은 웹 서버가 만든 UUID 작업만 나열한다. CLI의 별도 이름 폴더는 직접 확인한다.

## 7. 검증과 아직 남은 연구

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s native_lab/tests -v
.\.venv\Scripts\python.exe -m native_lab.validate_numerics
.\.venv\Scripts\python.exe -m native_lab.build_examples
```

첫 명령은 입력 경계, topology export, 무공급, 결정적 재실행, ALD 평면 해석해와 시간 간격을 검사한다.
두 번째는 오차 수치를 웹 검증 패널의 `validation.json`으로 저장한다.
세 번째는 공개 뷰어의 4개 예제를 실제 엔진으로 다시 계산한다.
소프트웨어 테스트 통과를 실제 공정 정확도로 해석하지 않는다.

연구를 확장할 순서는 **실측 자료와 맞는 재료·구조 선택 → 보정용/검증용 조건 분리 → 계수 추정 →
독립 조건 오차 평가 → reactor/feature 연결 → 계측 불확실성이 있는 진단 과제**다.
현재는 원인이 숨겨진 고장 진단 모드나 센서 모델을 구현하지 않았다.

## 8. 원저작자와 참고 문헌

이 저장소의 기여는 Python 작업 관리, 조건 검증, 형상·지표 추출, 웹 UI, 수치 검증 및 재현 가능한 실험 구성이다.
ViennaPS/ViennaLS 해석기를 직접 창작했다고 주장하지 않는다. 패키지는 외부 의존성으로 설치하며 vendoring하지 않는다.

- [ViennaPS v4.6.2 source](https://github.com/ViennaTools/ViennaPS/tree/v4.6.2), [ViennaLS](https://github.com/ViennaTools/ViennaLS)
- [ViennaPS 라이선스](https://github.com/ViennaTools/ViennaPS/blob/v4.6.2/LICENSE)
- [SF₆/O₂ 모델이 참조하는 논문, DOI 10.1116/1.1830495](https://doi.org/10.1116/1.1830495)
- [Aguinsky et al., Modeling Incomplete Conformality during ALD in HAR Structures (2022)](https://arxiv.org/abs/2210.00749)

이 문서는 실제 장비 운전 절차서나 특정 회사의 장비 복제품 설명서가 아니다.
