# AMK PSE: Etch + Deposition 첫 실습

Etch의 rate·CD·RF·압력 관측과 PVD의 두께·막 저항·계측 차이를 비교합니다.
현재 제공된 코드는 교육용 관측 데이터 생성기이며, 조건 변경 DOE와 공정 회복 검증은 다음 구현 단계입니다.
전체 프로젝트는 [AMK PSE 명세](docs/AMK_PSE_PROJECT_SPEC_KR.md)를 따릅니다.

## 함께 시작할 때

먼저 [01단계: 문제 정의](learning/01_problem_definition_KR.md)를 읽고 마지막 질문에 자신의 말로 답합니다.
아래 실행 명령과 60분 실습은 이어서 사용할 안내입니다. 한 번에 모두 완료할 필요는 없습니다.

## 기본 실행

저장소 폴더에서 Python 3.10 이상으로 실행합니다. 외부 package는 필요 없습니다.

```powershell
python study_lab/run_amk_starter.py --seed 20260928 --out outputs/amk_day1
python -m unittest discover -s study_lab/tests -v
```

생성되는 `outputs/amk_day1/AMK_PSE_WORKSHEET.md`를 작성합니다.
CSV는 UTF-8 BOM으로 저장하여 Excel에서도 열 수 있게 했습니다.
`instructor_only`의 정답은 자신의 가설과 반증 기준을 기록한 다음 확인합니다.
다시 실행하면 생성 CSV는 재생성되지만 작성한 워크시트는 덮어쓰지 않습니다.

## 첫 60분 실습

1. Etch의 정상 40 wafer와 CASE_A/B 각 20 wafer에서 rate, CD, NU, RF ratio, 표시/reference 압력을 비교합니다.
2. PVD의 정상과 CASE_A/B 각 15 wafer에서 두께와 sheet resistance를 비교합니다.
3. 같은 PVD site에서 `rho_apparent = R_sheet * thickness_reference_nm * 1e-9`를 계산합니다. 단위는 ohm·m입니다.
4. 각 공정별로 관측 2개, 경쟁 가설 2개, 다음 평가 1개, 반증 기준 1개를 적습니다.
5. 두께를 늘려 막 저항만 맞췄을 때 다른 spec이 어떻게 되는지 설명합니다.

PVD의 405개 site 관측은 45개 wafer에 속합니다. 405개의 독립 wafer로 간주하지 않습니다.
Etch와 PVD의 CASE_A/B는 별개의 실습 이름이며 동일 원인을 뜻하지 않습니다.
첫날 데이터에는 실제 timestamp, DOE 입력 조건, 실제 장비/customer 데이터가 없습니다.

교재와 워크북의 수치·모델은 모두 교육용입니다. 실제 공정 recipe나 고객 spec으로 사용하지 않습니다.
