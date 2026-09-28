# PSE Process Recovery Lab: Etch + Deposition

**Status: Etch + PVD starter available; DOE and independent recovery evaluation planned.**

[01단계: 문제 정의](learning/01_problem_definition_KR.md)부터 함께 시작합니다.
[실행 안내](START_HERE_KR.md)에서 준비된 데이터 생성기를 실행할 수 있습니다.
AMK PSE 지원을 위해 Etch와 Deposition/PVD 두 사례에서 공정에 대한 관심과 문제 해결 능력을 보여주는 중소 규모 프로젝트입니다.
완료 목표는 공정별 가설 비교·작은 DOE·독립 확인, 최종 그림 총 6장과 사례 보고서 2쪽입니다.
`study_lab`은 합성 학습 fixture이며 실제 장비 모델이나 검증된 공정 simulator가 아닙니다.

PSE 직무 준비를 위해 합성 데이터로 공정 이상을 분석하고,
가설을 구분하는 평가와 조치 후 검증 과정을 구현할 예정인 프로젝트입니다.

## 함께 진행하는 순서

매 단계에서 **공정 개념 → 작은 계산/코드 → 실행 결과 → 자신의 해석**을 남깁니다.
현재는 저장소 준비와 첫 학습 안내까지이며, 학습자의 해석과 사례 보고서는 아직 작성 전입니다.

| 위치 | 역할 | 현재 상태 |
| --- | --- | --- |
| `learning/` | 한 번에 한 단계씩 이해하고 답하는 학습 안내 | 01 문제 정의부터 시작 |
| `docs/` | 프로젝트 전체 범위와 완료 기준 | 계획 문서 제공 |
| `study_lab/` | 교육용 합성 데이터 생성 코드 | 실행 가능 |
| `study_lab/tests/` | 코드 재현성·계산 관계 확인 | 테스트 제공 |
| `outputs/` | 실행하면서 생성하는 CSV와 작성 양식 | Git 업로드 제외 |

Git은 내 PC에서 변경 이력을 남기는 도구이고, GitHub는 그 저장소를 공유하는 서비스입니다.
앞으로 이해하고 확인한 작업 단위마다 commit을 남겨 진행 과정을 보여줍니다.
코드 작성에는 AI 도구를 활용하며, 학습자가 직접 검토한 가정·판단·검증 범위는 각 단계의 기록으로 구분합니다.

## 문제와 접근

- **Etch:** rate·CD·균일도와 RF·압력 관측을 비교하고 공정 상태와 모니터 bias를 구분합니다.
- **PVD:** 두께·sheet resistance·reference 계측을 비교하여 두께 변화, 막 특성 변화, 계측 오차를 구분합니다.
- 각 사례에서 가설을 구분하는 평가, 고정/변경 조건, 반증 기준과 여러 KPI의 검증을 기록합니다.
- 두 사례는 독립 실습이며 하나의 실제 연속 제조 공정으로 검증된 모델이 아닙니다.

## 모델 범위

- Physics-inspired synthetic model; no proprietary Applied Materials recipes or customer data.
- 공정 변수, 단위, 가정과 관측 가능한 범위를 명시합니다.
- 합성 환경에서의 결과를 실제 장비의 성능 검증으로 표현하지 않습니다.

## 현재 실행 가능한 범위

`study_lab/run_amk_starter.py`가 Etch 80 wafer와 PVD 45 wafer × 9 site의 관측, 별도 정답, manifest, 작성 양식을 생성합니다.
PVD는 일반적인 단일 도전막의 `R_sheet = rho / t` 관계를 사용하는 교육용 fixture입니다.
특정 재료의 물성·PVD 수송·plasma chemistry를 검증한 모델이 아닙니다.

2026-09-28에 `python -m unittest discover -s study_lab/tests -v`를 실행하여 13개 테스트가 통과했습니다.
검증 범위는 재현성·정답 분리·case 방향·단위 관계·NU 계산·입력 검사입니다.

DOE용 조건 변경 모델, recipe 선택, 독립 회복 검증과 최종 보고서는 학습하며 구현할 단계입니다.

Day 1 실행 명령과 학습 순서는 [시작 안내](START_HERE_KR.md)에 있습니다.
현재 범위와 데이터·실험·검증 조건은 [AMK PSE 전용 프로젝트 명세](docs/AMK_PSE_PROJECT_SPEC_KR.md)에 정리했습니다.
기존 세 직무 통합 명세와 `run_day1.py`는 이전 학습 자료입니다. 현재 AMK 프로젝트의 실행 진입점은 `run_amk_starter.py`입니다.
전체 진단 시스템의 정량 결과는 해당 구현과 검증을 마친 뒤 추가합니다.
