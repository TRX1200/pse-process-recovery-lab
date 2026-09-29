# 공개 웹 실행과 재현성

공개 주소: https://trx1200.github.io/pse-process-recovery-lab/

GitHub Pages는 정적 파일을 제공합니다. 웹 버전은 Web Worker 안에서 Pyodide의 Python을 실행하며, 로컬 API와 같은 `sim_app/service.py` 및 `sim_app/models/*.py`를 빌드 시 포함합니다. 물리 모델을 JavaScript 근사식으로 다시 작성하지 않습니다.

## 두 실행 환경

| 구분 | 로컬 | 공개 웹 |
| --- | --- | --- |
| 계산 | PC의 Python + NumPy/SciPy | 브라우저의 Python + NumPy/SciPy |
| 실행 | `pnpm build`, `python sim_app/server.py` | `pnpm build:pages`, 정적 호스팅 |
| 배포 Python | 설치 환경에 따름 | Pyodide 314.0.7 / Python 3.14.2 |
| 웹 수치 라이브러리 | 설치 환경에 따름 | NumPy 2.4.6 / SciPy 1.18.0 |
| 데이터 보관 | 현재 브라우저 localStorage, JSON/CSV export | 동일; 사이트 주소별로 별도 저장 |

첫 접속 시 공식 Pyodide 배포를 jsDelivr CDN에서 내려받습니다. 브라우저 캐시는 재접속을 도울 수 있지만 오프라인 실행을 보장하지 않습니다. 외부 CDN 연결이 막혔거나 엔진이 실패하면 오류를 표시합니다. 임의 예제 결과로 대체하지 않습니다. 복잡한 ALD 스윕은 PC 성능에 따라 시간이 걸립니다.

`Run JSON`과 웹 sweep export에는 `execution_environment`가 포함됩니다. `run_id`는 모델 버전, 입력값, 고장 조건의 해시이며 계산 환경이나 실험 검증을 인증하는 값은 아닙니다. 다른 Python/라이브러리 환경의 부동소수점 결과는 허용오차를 정해 비교해야 합니다.

## 배포

`.github/workflows/pages.yml`은 `main` push 시 Python 테스트, 화면 로직 테스트와 웹 빌드를 실행한 뒤 GitHub Pages에 배포합니다. 저장소 Pages의 소스는 GitHub Actions입니다. PDF는 `output/pdf/Process_Studio_Semiconductor_Study_KR.pdf`에서 빌드 산출물의 `study/`로 복사합니다. 이 파일이 없으면 빌드는 실패합니다.

```powershell
cd sim_app/frontend
pnpm install --frozen-lockfile
pnpm test
pnpm build:pages
pnpm preview
```

모델 수식, 수치 해법, 예제 규격은 웹 배포 때문에 변경하지 않았습니다. 시간 재생은 계산된 궤적의 재생이며 플라즈마 발광 애니메이션은 설명용입니다. 실제 장비 보정 및 실험 데이터에 대한 물리 검증은 완료되지 않았습니다.

## 확인한 계산 일치 범위 (2026-09-30)

웹 빌드를 Chrome에서 실행하고 UI의 JSON export로 결과를 저장한 뒤, Python 3.12.2 환경에서 같은 입력을 재계산했습니다. 지표만이 아니라 `result`와 정상 비교 기준 전체의 시간 배열·공간 분포·진단·모델 버전을 비교했습니다.

| 사례 | run_id / 조건 | 비교한 수치 개수 | 결과 |
| --- | --- | ---: | --- |
| Etch 기본 | `9f29c7512177` | 6,536 | 허용오차 내 일치 |
| Etch RF 매칭 이탈 | `2fcf769f6d96` | 13,072 | 허용오차 내 일치 |
| ALD 기본 | `cb8d81257c08` | 4,125 | 허용오차 내 일치 |
| ALD 배기 응답 지연 | `9f213d3b0556` | 8,250 | 허용오차 내 일치 |
| ALD 고장 중 A 주입 스윕 | 0.25 / 0.5 / 0.75 s, 나머지 기본값 | 138 | 허용오차 내 일치 |

수치 비교는 `rtol=1e-7`, `atol=1e-9`이며 총 32,121개를 비교했습니다. 문자열·배열 길이·키 집합은 정확히 비교합니다. 이는 이 사례들의 실행 환경 간 일치 확인이며, 모든 입력 조합의 동일성이나 물리적 정확성을 보증하지 않습니다.

```powershell
python sim_app/verify_browser_export.py path/to/exported-run.json
```

검증 명령은 실제 브라우저에서 내려받은 `Run JSON + notes` 또는 sweep JSON을 입력으로 받습니다. 웹 버전의 내보내기에는 실행 엔진 버전이 함께 기록됩니다.

## 공식 구현 자료

- [Pyodide: Web Worker 사용](https://pyodide.org/en/stable/usage/webworker.html)
- [Pyodide: 배포와 정적 호스팅](https://pyodide.org/en/stable/usage/downloading-and-deploying.html)
- [고정 배포의 패키지 버전 목록](https://cdn.jsdelivr.net/pyodide/v314.0.7/full/pyodide-lock.json)
- [GitHub Pages: Actions 워크플로](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)
