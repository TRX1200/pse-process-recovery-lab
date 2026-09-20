# PSE Process Recovery Lab

**Status: planning scaffold. No simulator or validation results are included yet.**

PSE 직무 준비를 위해 합성 데이터로 공정 이상을 분석하고,
가설을 구분하는 평가와 조치 후 검증 과정을 구현할 예정인 프로젝트입니다.

## 문제와 접근

가상 plasma etch 공정에서 식각 속도, CD bias, 균일도 변화가 발생하는 상황을 다룹니다.
RF 전력 전달, 압력 제어, 가스 유량, 챔버 상태, 센서 오류를 원인 후보로 비교합니다.
센서 trace와 wafer metrology를 이용해 다음 평가를 선택한 이유를 기록합니다.
장비 점검이나 추가 측정이 필요한 상황도 조치 선택에 포함할 예정입니다.

## 모델 범위

- Physics-inspired synthetic model; no proprietary Applied Materials recipes or customer data.
- 공정 변수, 단위, 가정과 관측 가능한 범위를 명시합니다.
- 합성 환경에서의 결과를 실제 장비의 성능 검증으로 표현하지 않습니다.

## 첫 구현 목표

1. 정상 상태와 한 가지 이상 상황을 생성합니다.
2. 관측 데이터만으로 가설을 비교합니다.
3. 원인 후보를 구분하는 평가와 판단 기록을 만듭니다.
4. 여러 공정 지표 및 반복 조건으로 조치 결과를 검증합니다.

실행 명령, 의존성, 정량 결과는 실제 구현과 검증 후 추가합니다.
