import { metricValue } from "../assessment";
import { metricNumber } from "../storage";
import { modelEquations } from "../modelEquations";
import type { ModelKey, ModelResult, Params } from "../types";
import { MathBlock } from "./MathBlock";

export function Equations({
  model,
  result,
  params,
}: {
  model: ModelKey;
  result?: ModelResult;
  params: Params;
}) {
  const valid = !!result && result.effective.status !== "outside_rate_fit";
  const format = (value: unknown) =>
    valid && typeof value === "number" && Number.isFinite(value)
      ? metricNumber(value, 5)
      : "—";
  const metric = (key: string) => format(metricValue(result, key));
  const state = (key: string) => format(result?.effective[key]);
  const cards =
    model === "etch"
      ? [
          {
            title: "흡수 전력: RF 전달이 출발점",
            equations: modelEquations.etch.absorbedPower,
            variables:
              "Pfwd: 소스 순방향 전력 [W] · r: 실제 반사율 · η: 결합 효율 · D: 듀티. 바이어스 전원은 별도입니다.",
            reading: `${format(params.source_power_w)} × (1 − ${state("reflected_fraction")}) × ${format(params.coupling_efficiency)} × ${format(params.source_duty)} = ${metric("absorbed_power_w")} W`,
            meaning:
              "RF 매칭이 나빠지면 같은 설정 전력에서도 흡수 전력이 줄 수 있습니다. 설정값과 실제 전달량을 구분합니다.",
          },
          {
            title: "입자 수지 → 전자온도",
            equations: modelEquations.etch.particleBalance,
            variables:
              "nAr: Ar 밀도 [m⁻³] · kiz: 이온화 속도 계수 [m³/s] · uB: Bohm 속도 [m/s] · Aeff: 유효 손실 면적 [m²] · V: 체적 [m³] · Te: eV 단위.",
            reading: `Te = ${metric("electron_temperature_ev")} eV · 입자 수지 상대 잔차 = ${state("particle_balance_relative_residual")}`,
            meaning:
              "생성과 벽 손실이 같은 Te를 찾습니다. 이 축약 모델에서 압력·형상을 고정하면 소스 전력이 Te를 직접 올리지 않습니다.",
          },
          {
            title: "전력 수지 → 전자밀도",
            equations: modelEquations.etch.powerBalance,
            variables:
              "ne: 전자밀도 [m⁻³] · e: 기본 전하 [C] · Ec: 충돌 손실 [eV/pair] · 7.2Te: 벽의 전자·이온 손실 근사 · Pdiss: 가상 X₂ 해리 전력 [W].",
            reading: `ne = ${metric("electron_density_m3")} m⁻³ · Pdiss = ${state("dissociation_power_w")} W · 전력 수지 상대 잔차 = ${state("power_balance_relative_residual")}`,
            meaning:
              "흡수 전력을 입자 생성·손실에 필요한 전력과 맞춥니다. 수지 잔차가 작다는 것은 계산 일관성이며 실측 정확도의 증거는 아닙니다.",
          },
          {
            title: "바이어스와 충돌 → 이온 에너지",
            equations: modelEquations.etch.ionEnergy,
            variables:
              "Vs: 쉬스 전위 강하 [V] · sCL: DC Child–Langmuir 쉬스 길이 [m] · λi: 유효 평균자유행로 [m] · Te, Ei: eV 단위. 단일 전하 이온이며 V의 전위 강하를 eV로 환산한 식입니다.",
            reading: `|Vbias| = ${format(params.bias_voltage_v)} V · sCL = ${state("sheath_scale_mm")} mm · λi = ${state("mean_free_path_mm")} mm · Ei = ${metric("ion_energy_ev")} eV`,
            meaning:
              "바이어스와 압력이 입사 에너지를 바꾸어 타깃·마스크 수율에 영향을 줍니다. 충돌 감쇠는 휴리스틱 근사이며 RF 파형이나 에너지 분포를 직접 계산하지 않습니다.",
          },
          {
            title: "표면 반응 → 시간별 식각량",
            equations: modelEquations.etch.surfaceRemoval,
            variables:
              "θ: 피복률 · s: 부착 확률 · ΓX, Γi: 라디칼/이온 플럭스 [m⁻²s⁻¹] · Ns: 표면 자리 밀도 [m⁻²] · kdes, kchem: 속도 [s⁻¹] · Y: 수율 · Ntarget: 원자밀도 [m⁻³] · d: nm.",
            reading: `Γi = ${metric("ion_flux_m2_s")} m⁻²s⁻¹ · ΓX = ${metric("radical_flux_m2_s")} m⁻²s⁻¹ · 최종 면적 평균 깊이 = ${metric("etch_depth_nm")} nm`,
            meaning:
              "이온·반응종 공급과 표면 반응이 제거량으로 이어집니다. 각 위치에서 계산한 깊이를 면적 평균합니다. 가스·플라즈마는 정상상태이고 표면만 시간에 따라 변합니다.",
          },
          {
            title: "선택비: 타깃과 마스크를 함께 보기",
            equations: modelEquations.etch.selectivity,
            variables:
              "E, Eth: 이온 에너지와 반응 문턱 [eV] · Nmask: 마스크 원자밀도 [m⁻³] · R: 정상 제거율 [nm/min]. 수율 함수와 계수는 이 프로젝트의 가정입니다.",
            reading: `타깃 ${metric("etch_rate_nm_min")} / 마스크 ${state("mask_rate_nm_min")} nm/min → S = ${result?.effective.selectivity_defined === true ? metric("selectivity") : "정의되지 않음"}`,
            meaning:
              "바이어스나 시간을 올려 깊이를 확보하더라도 마스크 소모가 커질 수 있습니다. 선택비가 높아도 목표 깊이·균일도는 따로 평가합니다.",
          },
          {
            title: "공간 균일도: 평균만으로는 부족",
            equations: modelEquations.etch.uniformity,
            variables:
              "q: 면적에 균등한 좌표 · aradial: 입력한 비균일 분포 계수 · d̄area: 면적 평균 깊이. 평균 깊이가 0이면 NU는 정의되지 않습니다.",
            reading: `aradial = ${format(params.radial_nonuniformity)} · NU = ${(metricValue(result, "etch_depth_nm") ?? 0) > 0 ? metric("nonuniformity_pct") : "정의되지 않음"} %`,
            meaning:
              "중앙과 가장자리의 깊이 차이를 평가합니다. 이 공간 분포는 가정한 플럭스에 따른 것이며 전자기장이나 챔버 유동을 풀어 얻은 분포가 아닙니다.",
          },
        ]
      : [
          {
            title: "주입과 퍼지 → 챔버 분압",
            equations: modelEquations.ald.chamberPressure,
            variables:
              "i = A 또는 B · ui: 밸브가 요구하는 분압 [Pa] · Pi: 실제 챔버 분압 [Pa] · τi: 공급/배기 응답 시간 [s].",
            reading: `공급 τ = ${state("fill_tau_s")} s · 배기 τ = ${state("pump_tau_s")} s · 실제 A 목표 분압 = ${state("pressure_a_pa")} Pa`,
            meaning:
              "밸브를 닫아도 가스가 즉시 사라지지 않습니다. 배기가 느리면 다음 반응물과 겹칠 수 있습니다.",
          },
          {
            title: "Knudsen 수송 → 깊은 곳의 노출",
            equations: modelEquations.ald.transport,
            variables:
              "H: 슬릿 간격 [m] · q: 표면 자리 밀도 [m⁻²] · pi: 채널 분압 [Pa] · Di: 확산계수 [m²/s] · kBoltz: 볼츠만 상수. 입구 pi=Pi, 막힌 끝 ∂pi/∂x=0.",
            reading: `DA = ${state("diffusivity_a_m2_s")} m²/s · DB = ${state("diffusivity_b_m2_s")} m²/s · ${state("cells")} 셀`,
            meaning:
              "채널을 따라 확산하는 동안 벽 반응이 가스를 소비합니다. 입구가 충분히 반응해도 깊은 곳은 공급이 부족할 수 있습니다.",
          },
          {
            title: "표면 피복과 성장",
            equations: modelEquations.ald.surfaceGrowth,
            variables:
              "ki: 반응 계수 [Pa⁻¹s⁻¹] · θ: A 종결 비율 · z: B에 의한 누적 전환 횟수 · gsat: 완전 전환당 성장 환산량 [nm]. 여기서 kB는 B 반응 계수이며 볼츠만 상수 kBoltz와 다릅니다.",
            reading: `유효 sA = ${state("sticking_a")} · sB = ${state("sticking_b")} · 입구 쪽 h₁ = ${metric("gpc_nm")} nm`,
            meaning:
              "A가 빈 자리를 채우고 B가 A 종결 자리를 전환하며 막을 형성합니다. A/B가 겹치면 반복 전환이 생길 수 있지만 실제 CVD나 불순물 농도를 예측하지 않습니다.",
          },
          {
            title: "온도와 반응 확률",
            equations: modelEquations.ald.temperature,
            variables:
              "Tref=473.15 K · Ea는 입력 eV를 J로 환산 · T는 절대온도 [K].",
            reading: `실제 온도 = ${state("temperature_c")} °C`,
            meaning:
              "온도에 따른 반응 확률을 Arrhenius 형태로 보정합니다. 응축·탈착·열분해가 없으므로 실제 ALD 온도 창 전체를 계산하는 식은 아닙니다.",
          },
          {
            title: "총 두께와 깊이 방향 피복",
            equations: modelEquations.ald.thickness,
            variables:
              "N: 반복 횟수 · near/deep: 첫/마지막 셀 중심 · C: 두께비 [%]. near 성장이 거의 0이면 두께비는 정의되지 않습니다.",
            reading: `${metric("gpc_nm")} nm × ${format(params.cycles)}회 = ${metric("top_thickness_nm")} nm · C = ${(metricValue(result, "gpc_nm") ?? 0) >= 1e-12 ? metric("conformality_pct") : "정의되지 않음"} %`,
            meaning:
              "첫 사이클 결과를 반복 투영합니다. 사이클 수만 늘리면 입구와 깊은 곳이 같이 늘어나므로 부족한 두께비 자체는 해결되지 않습니다.",
          },
          {
            title: "퍼지 평가: 중첩과 잔류",
            equations: modelEquations.ald.purge,
            variables:
              "O: 분압 중첩 적분 [Pa·s] · t_end: 한 사이클 종료 시각 [s] · Presidual: 종료 잔류 분압 [Pa]. 종료 시각은 온도 T와 구분합니다.",
            reading: `O = ${metric("overlap_pa_s")} Pa·s · 잔류 = ${metric("residual_pressure_pa")} Pa · 사이클 = ${metric("cycle_time_s")} s`,
            meaning:
              "퍼지 연장으로 잔류를 줄일 수 있지만 사이클 시간이 늘어납니다. 기준치는 프로젝트 규격으로 설정하며 실제 오염·결함의 합격 기준으로 해석하지 않습니다.",
          },
        ];
  return (
    <section className="equations-panel" aria-label="모델 수식">
      <div className="equations-heading">
        <span className="eyebrow">MODEL EXPLAINER</span>
        <h2>입력에서 결과까지, 계산의 연결</h2>
        <p>
          아래 수식은 현재 Python 구현의 요약입니다. 표시값은 마지막 실행
          조건이며 시간 재생 중에도 종점·정상상태 값입니다.
        </p>
      </div>
      <div className="equations-grid">
        {cards.map((card, index) => (
          <article className="equation-card" key={card.title}>
            <div className="equation-title">
              <span>{String(index + 1).padStart(2, "0")}</span>
              <h3>{card.title}</h3>
            </div>
            <MathBlock expressions={card.equations} label={`${card.title} 수식`} />
            <p className="equation-variables">{card.variables}</p>
            <div className="equation-reading">
              <b>현재 계산</b>
              <p>{card.reading}</p>
            </div>
            <p className="equation-meaning">{card.meaning}</p>
          </article>
        ))}
      </div>
      <div className="equations-source">
        <b>구현·식의 출처</b>
        <p>
          <code>sim_app/models/{model}.py</code> ·{" "}
          {result?.model_version ?? "실행 전"} · 상세 가정과 단위는 저장소
          문서에서 확인합니다.
        </p>
        <a
          href={`https://github.com/TRX1200/pse-process-recovery-lab/blob/main/docs/${model.toUpperCase()}_MODEL.md`}
          target="_blank"
          rel="noreferrer"
        >
          {model.toUpperCase()} 모델 명세와 문헌 보기 ↗
        </a>
      </div>
    </section>
  );
}
