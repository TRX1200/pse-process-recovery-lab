import { useEffect, useRef, useState } from "react";
import {
  Activity,
  ArrowDownToLine,
  ArrowUpFromLine,
  Beaker,
  BookOpen,
  ChartNoAxesCombined,
  Check,
  ChevronDown,
  CircleHelp,
  FileJson,
  FlaskConical,
  FolderOpen,
  Info,
  Layers3,
  LoaderCircle,
  Play,
  Save,
  Trash2,
  TriangleAlert,
} from "lucide-react";
import { getSchema, simulate } from "./api";
import {
  defaults,
  exportJson,
  exportRunCsv,
  loadRecipes,
  loadRuns,
  saveRecipes,
  saveRuns,
  validateRecipe,
} from "./storage";
import type {
  ModelKey,
  Params,
  Recipe,
  Schema,
  Series,
  Simulation,
} from "./types";
import { Chart } from "./components/Chart";
import { Controls } from "./components/Controls";
import { Metrics } from "./components/Metrics";
import { Modal } from "./components/Modal";
import { Reactor } from "./components/Reactor";
import { SweepPanel } from "./components/SweepPanel";
import { Playback } from "./components/Playback";
import { durationOf, isTimeSeries } from "./playback";
import { usePlayback } from "./usePlayback";
import "./styles.css";

type View = "simulate" | "sweep" | "recipes";
type PlotTab = "process" | "physics" | "troubleshooting";

export default function App() {
  const [schema, setSchema] = useState<Schema | null>(null);
  const [model, setModel] = useState<ModelKey>("etch");
  const [params, setParams] = useState<Params>({});
  const [fault, setFault] = useState("none");
  const [run, setRun] = useState<Simulation | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const [view, setView] = useState<View>("simulate");
  const [tab, setTab] = useState<PlotTab>("process");
  const [showBaseline, setShowBaseline] = useState(true);
  const [baselineId, setBaselineId] = useState("auto");
  const [recipes, setRecipes] = useState<Recipe[]>(loadRecipes);
  const [history, setHistory] = useState<Simulation[]>(loadRuns);
  const [modal, setModal] = useState<"save" | "notes" | null>(null);
  const [recipeName, setRecipeName] = useState("");
  const [notes, setNotes] = useState("");
  const importRef = useRef<HTMLInputElement>(null);
  const requestId = useRef(0);
  const playbackDuration = durationOf(run?.result);
  const playback = usePlayback(
    playbackDuration,
    view === "simulate" && !busy && modal === null,
  );

  function record(response: Simulation) {
    setRun(response);
    setHistory((current) => {
      const next = [
        response,
        ...current.filter((item) => item.run_id !== response.run_id),
      ].slice(0, 10);
      try {
        saveRuns(next);
      } catch {
        setToast(
          "계산은 완료됐지만 브라우저 저장 공간이 부족합니다. JSON으로 내보내 주세요.",
        );
      }
      return next;
    });
  }

  useEffect(() => {
    let active = true;
    async function initialize() {
      setBusy(true);
      try {
        const data = await getSchema();
        if (!active) return;
        setSchema(data);
        const initial = defaults(data.models.etch);
        setParams(initial);
        const response = await simulate("etch", initial, "none");
        if (active) record(response);
      } catch (error) {
        if (active)
          setError(
            error instanceof Error
              ? error.message
              : "서버에 연결할 수 없습니다.",
          );
      } finally {
        if (active) setBusy(false);
      }
    }
    void initialize();
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(""), 6000);
    return () => clearTimeout(timer);
  }, [toast]);

  useEffect(() => {
    try {
      setNotes(
        run
          ? (localStorage.getItem(`process-studio.notes.v1.${run.run_id}`) ??
              "")
          : "",
      );
    } catch {
      setNotes("");
    }
  }, [run?.run_id]);

  if (!schema)
    return (
      <div className="boot-screen">
        <div className="brand-symbol">
          <Layers3 size={28} />
        </div>
        <h1>PROCESS STUDIO</h1>
        <p>ALD / Etch Simulator</p>
        {error ? (
          <>
            <div className="error-banner" role="alert">
              {error}
            </div>
            <button
              className="button primary"
              onClick={() => window.location.reload()}
            >
              다시 연결
            </button>
          </>
        ) : (
          <>
            <LoaderCircle className="spin" size={22} />
            <small>Python 모델에 연결 중…</small>
          </>
        )}
      </div>
    );

  const modelSchema = schema.models[model];
  const modelRecipes = recipes.filter((recipe) => recipe.model === model);
  const compatibleHistory = history.filter(
    (item) =>
      item.model === model &&
      item.result.model_version === modelSchema.model_version &&
      item.run_id !== run?.run_id,
  );
  const selectedBaseline =
    baselineId === "auto"
      ? run?.baseline
      : compatibleHistory.find((item) => item.run_id === baselineId)?.result;
  const baseline =
    showBaseline && selectedBaseline?.effective.status !== "outside_rate_fit"
      ? selectedBaseline
      : null;
  const pending =
    !!run &&
    (run.model !== model ||
      run.fault !== fault ||
      Object.keys(params).some((key) => params[key] !== run.params[key]));
  const result = run?.model === model ? run.result : undefined;
  const invalid = result?.effective.status === "outside_rate_fit";
  const currentFault = modelSchema.faults.find((item) => item.id === fault);
  const displayedParams = run?.model === model ? run.params : params;
  const spatialSeries: Series | null = result
    ? {
        key: "spatial",
        title:
          model === "etch"
            ? "가정한 웨이퍼 반경별 식각량"
            : "채널 깊이별 투영 두께",
        x_label: model === "etch" ? "웨이퍼 위치 (mm)" : "채널 깊이 (µm)",
        y_label: result.spatial.unit,
        x: result.spatial.x,
        lines: [
          {
            name: model === "etch" ? "식각 깊이" : "막 두께",
            values: result.spatial.values,
          },
        ],
      }
    : null;
  const spatialBaseline: Series | undefined = baseline
    ? {
        ...spatialSeries!,
        x: baseline.spatial.x,
        lines: [
          {
            name: model === "etch" ? "식각 깊이" : "막 두께",
            values: baseline.spatial.values,
          },
        ],
      }
    : undefined;
  const displayedSeries =
    result?.series.filter((series) =>
      model === "etch"
        ? tab === "process"
          ? ["depth", "coverage"].includes(series.key)
          : ["particle_balance", "yield"].includes(series.key)
        : tab === "process"
          ? ["pressure", "growth"].includes(series.key)
          : ["coverage", "profile"].includes(series.key),
    ) ?? [];

  function selectModel(next: ModelKey) {
    if (next === model || !schema) return;
    requestId.current += 1;
    playback.reset();
    playback.setSpeed(next === "ald" ? 0.5 : 5);
    setModel(next);
    setParams(defaults(schema.models[next]));
    setFault("none");
    setRun(null);
    setError("");
    setTab("process");
    setBaselineId("auto");
  }

  async function execute() {
    const token = ++requestId.current;
    setBusy(true);
    playback.pause();
    setError("");
    try {
      const response = await simulate(model, params, fault);
      if (token === requestId.current) {
        record(response);
        setView("simulate");
        setTab("process");
        if (durationOf(response.result) > 0) playback.start();
        else playback.reset();
      }
    } catch (error) {
      if (token === requestId.current)
        setError(
          error instanceof Error ? error.message : "계산에 실패했습니다.",
        );
    } finally {
      if (token === requestId.current) setBusy(false);
    }
  }

  function reset() {
    setParams(defaults(modelSchema));
    setFault("none");
    setError("");
    setToast("기본 레시피로 복원했습니다. Run simulation으로 다시 계산하세요.");
  }

  function loadRecipe(recipe: Recipe) {
    if (busy) return;
    try {
      const validated = validateRecipe(recipe, schema!);
      playback.reset();
      if (validated.model !== model)
        playback.setSpeed(validated.model === "ald" ? 0.5 : 5);
      requestId.current += 1;
      setBusy(false);
      setModel(validated.model);
      setParams(validated.params);
      setFault(validated.fault);
      setRun(null);
      setError("");
      setView("simulate");
      setTab("process");
      setBaselineId("auto");
      setToast(`“${validated.name}” 레시피를 불러왔습니다.`);
    } catch (error) {
      setError(
        error instanceof Error ? error.message : "레시피를 읽을 수 없습니다.",
      );
    }
  }

  function currentRecipe(name = `${model.toUpperCase()} recipe`): Recipe {
    return { format: "process-studio-recipe-v1", name, model, params, fault };
  }

  function storeRecipe() {
    try {
      const name =
        recipeName.trim() ||
        `${model.toUpperCase()} recipe ${recipes.length + 1}`;
      const recipe = validateRecipe(currentRecipe(name), schema!);
      const next = [
        recipe,
        ...recipes.filter((item) => item.name !== name || item.model !== model),
      ].slice(0, 20);
      saveRecipes(next);
      setRecipes(next);
      setModal(null);
      setToast("이 브라우저에 레시피를 저장했습니다.");
    } catch (error) {
      setError(error instanceof Error ? error.message : "레시피 저장 실패");
    }
  }

  async function importRecipe(file: File) {
    if (busy) return;
    try {
      if (file.size > 128 * 1024)
        throw new Error("레시피 파일은 128 KB 이하여야 합니다.");
      const recipe = validateRecipe(JSON.parse(await file.text()), schema!);
      loadRecipe(recipe);
    } catch (error) {
      setError(
        error instanceof Error
          ? error.message
          : "올바른 JSON 레시피를 선택해 주세요.",
      );
    }
  }

  const navItems = [
    { key: "simulate" as const, label: "Simulate", icon: FlaskConical },
    { key: "sweep" as const, label: "Sweep", icon: ChartNoAxesCombined },
    { key: "recipes" as const, label: "Recipes", icon: FolderOpen },
  ];

  return (
    <div className="app-shell">
      <nav className="nav-rail" aria-label="주 메뉴">
        <div className="rail-brand" title="Process Studio">
          <Layers3 size={27} />
        </div>
        <div className="rail-main">
          {navItems.map((item) => (
            <button
              key={item.key}
              className={`rail-item ${view === item.key ? "active" : ""}`}
              aria-current={view === item.key ? "page" : undefined}
              disabled={busy}
              onClick={() => setView(item.key)}
            >
              <item.icon size={22} strokeWidth={1.7} />
              <span>{item.label}</span>
            </button>
          ))}
        </div>
        <button
          className="rail-item rail-help"
          onClick={() => setModal("notes")}
        >
          <CircleHelp size={22} />
          <span>Model notes</span>
        </button>
      </nav>
      <header className="topbar">
        <div className="brand">
          <strong>PROCESS STUDIO</strong>
          <span>ALD / Etch Simulator</span>
        </div>
        <div className="model-switch" aria-label="공정 모델">
          <button
            className={model === "ald" ? "selected" : ""}
            onClick={() => selectModel("ald")}
            disabled={busy}
          >
            ALD
          </button>
          <button
            className={model === "etch" ? "selected" : ""}
            onClick={() => selectModel("etch")}
            disabled={busy}
          >
            Plasma Etch
          </button>
        </div>
        <div className="header-actions">
          <button
            aria-label="Save recipe"
            className="button secondary"
            onClick={() => {
              setRecipeName("");
              setModal("save");
            }}
            disabled={busy}
          >
            <Save size={16} />
            <span>Save recipe</span>
          </button>
          <details className="export-menu">
            <summary
              aria-label="Export recipe or run"
              className="button secondary"
            >
              <ArrowUpFromLine size={16} />
              <span>Export</span>
              <ChevronDown size={13} />
            </summary>
            <div>
              <button
                onClick={() =>
                  exportJson(`${model}-recipe.json`, currentRecipe())
                }
              >
                <FileJson size={16} />
                Recipe JSON
              </button>
              <button
                disabled={!run}
                onClick={() =>
                  run &&
                  exportJson(`${run.run_id}.json`, {
                    ...run,
                    user_notes: notes,
                  })
                }
              >
                <ArrowDownToLine size={16} />
                Run JSON + notes
              </button>
              <button disabled={!run} onClick={() => run && exportRunCsv(run)}>
                <ArrowDownToLine size={16} />
                Run data CSV
              </button>
            </div>
          </details>
        </div>
      </header>
      <Controls
        schema={modelSchema}
        params={params}
        onChange={(key, value) =>
          setParams((current) => ({ ...current, [key]: value }))
        }
        busy={busy}
        onRun={() => void execute()}
        onReset={reset}
        recipes={modelRecipes}
        onLoadRecipe={loadRecipe}
      />
      <main className="workspace">
        <div className="workspace-heading">
          <div>
            <h1>
              {view === "recipes"
                ? "Recipe library"
                : view === "sweep"
                  ? "Explore the process window"
                  : modelSchema.label}
            </h1>
            <p>
              {view === "recipes"
                ? "레시피와 실행 기록을 저장하고, 다음 실험으로 이어갑니다."
                : view === "sweep"
                  ? "조건을 바꾸고, 공정 응답의 방향과 민감도를 확인하세요."
                  : "레시피에서 물리 모델로, 물리 모델에서 공정 응답으로."}
            </p>
          </div>
          <div className="model-caption">
            {model === "etch"
              ? "Ar 기반 입자·전력 수지 / 유효 반응종"
              : "열 ALD / 반응·확산 모델"}
            <button
              onClick={() => setModal("notes")}
              title="모델 가정과 한계 보기"
              aria-label="모델 가정과 한계 보기"
            >
              <Info size={16} />
            </button>
          </div>
        </div>
        {error && (
          <div className="error-banner" role="alert">
            <TriangleAlert size={18} />
            {error}
            <button onClick={() => setError("")} aria-label="오류 메시지 닫기">
              ×
            </button>
          </div>
        )}
        {toast && (
          <div className="toast" role="status">
            <Check size={16} />
            {toast}
          </div>
        )}
        {view === "simulate" ? (
          <>
            {pending && (
              <div className="pending-banner">
                <Info size={16} />
                레시피가 변경되었습니다. 아래 결과와 개념도는 마지막 실행 조건을
                보여줍니다.
              </div>
            )}
            {model === "ald" && (
              <div className="model-limitation">
                <Info size={14} />총 두께: 첫 사이클 × N 투영 · 채널 형상은 고정
                · 반복 사이클 전체의 진화 해석 아님
              </div>
            )}
            {invalid && (
              <div className="error-banner" role="alert">
                <TriangleAlert size={18} />
                모델 적용 범위 밖입니다. 0 값은 물리 예측으로 표시하지 않습니다.
                진단과 레시피를 확인하세요.
              </div>
            )}
            {result && !invalid && (
              <Playback
                model={model}
                result={result}
                params={displayedParams}
                duration={playbackDuration}
                controller={playback}
              />
            )}
            <div
              className={`simulation-overview ${result && !invalid ? "playback-overview" : ""}`}
            >
              <Reactor
                model={model}
                result={invalid ? undefined : result}
                params={displayedParams}
                time={playback.time}
                motion={playback.motion}
                playing={playback.playing && !playback.reduceMotion}
              />
              <Metrics model={model} result={result} baseline={baseline} />
            </div>
            <div className="fault-strip">
              <label htmlFor="fault-selection">
                <Beaker size={17} />
                <strong>Fault injection</strong>
              </label>
              <select
                id="fault-selection"
                value={fault}
                onChange={(event) => {
                  setFault(event.target.value);
                  setBaselineId("auto");
                  setShowBaseline(true);
                }}
                disabled={busy}
              >
                {modelSchema.faults.map((item) => (
                  <option value={item.id} key={item.id}>
                    {item.label}
                  </option>
                ))}
              </select>
              <div className="fault-severity">
                <label htmlFor="severity">강도</label>
                <input
                  id="severity"
                  aria-label="이상 강도 슬라이더"
                  type="range"
                  min={0}
                  max={1}
                  step={0.05}
                  value={params.fault_severity ?? 0.35}
                  disabled={busy || fault === "none"}
                  onChange={(event) =>
                    setParams((current) => ({
                      ...current,
                      fault_severity: Number(event.target.value),
                    }))
                  }
                />
                <output htmlFor="severity">
                  {Math.round((params.fault_severity ?? 0.35) * 100)}%
                </output>
              </div>
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={showBaseline}
                  onChange={(event) => setShowBaseline(event.target.checked)}
                />
                Compare baseline
              </label>
            </div>
            <div className="fault-explanation">
              <span>
                {currentFault?.description}
                {pending ? " · 실행하면 적용됩니다." : ""}
              </span>
              {showBaseline && (
                <label>
                  비교 기준
                  <select
                    aria-label="비교 기준"
                    value={baselineId}
                    onChange={(event) => setBaselineId(event.target.value)}
                  >
                    <option value="auto">
                      동일 레시피 · 고장 없음
                      {!run?.baseline ? " (고장 실행 시 계산)" : ""}
                    </option>
                    {compatibleHistory.map((item) => (
                      <option key={item.run_id} value={item.run_id}>
                        {item.run_id.slice(0, 6)} ·{" "}
                        {item.fault === "none" ? "정상" : item.fault}
                      </option>
                    ))}
                  </select>
                </label>
              )}
            </div>
            <div className="result-tabs" role="tablist" aria-label="결과 보기">
              <button
                role="tab"
                aria-selected={tab === "process"}
                className={tab === "process" ? "active" : ""}
                onClick={() => setTab("process")}
              >
                Process response
              </button>
              <button
                role="tab"
                aria-selected={tab === "physics"}
                className={tab === "physics" ? "active" : ""}
                onClick={() => setTab("physics")}
              >
                {model === "etch" ? "Plasma balance" : "Channel & surface"}
              </button>
              <button
                role="tab"
                aria-selected={tab === "troubleshooting"}
                className={tab === "troubleshooting" ? "active" : ""}
                onClick={() => setTab("troubleshooting")}
              >
                Troubleshooting
                {result?.diagnostics.some(
                  (item) => item.level === "warning",
                ) && <span className="warning-dot" />}
              </button>
              <span className="run-caption">
                {busy ? (
                  <>
                    <LoaderCircle className="spin" size={12} />
                    Calculating
                  </>
                ) : run ? (
                  <>Run {run.run_id.slice(0, 8)}</>
                ) : (
                  "Ready to simulate"
                )}
              </span>
            </div>
            {tab === "troubleshooting" ? (
              <section className="troubleshooting">
                <div className="diagnostics">
                  <h2>관측 → 가설 → 검증</h2>
                  <p>
                    고장을 주입한 뒤 정상 기준과 비교하고, 바꾼 조건과 해석을
                    기록하세요.
                  </p>
                  {result?.diagnostics.map((item, index) => (
                    <div className={`diagnostic ${item.level}`} key={index}>
                      {item.level === "warning" ? (
                        <TriangleAlert size={16} />
                      ) : (
                        <Info size={16} />
                      )}
                      <span>{item.message}</span>
                    </div>
                  ))}
                  {!result && (
                    <p className="muted">실행 후 모델 진단이 표시됩니다.</p>
                  )}
                  <p className="subtle-note">
                    Baseline은 같은 모델의 정상 조건 계산입니다. 실제 장비
                    측정값 또는 독립 검증값이 아닙니다.
                  </p>
                </div>
                <div className="experiment-notes">
                  <h2>실험 메모</h2>
                  <label htmlFor="experiment-notes">
                    관측한 변화 / 원인 가설 / 다음 구분 실험 / 회복 여부
                  </label>
                  <textarea
                    id="experiment-notes"
                    placeholder="예: 전구체 주입 시간을 늘렸을 때, 입구 두께와 바닥 두께가 같은 비율로 증가하는지 비교한다."
                    value={notes}
                    disabled={!run}
                    onChange={(event) => {
                      setNotes(event.target.value);
                      if (run) {
                        try {
                          localStorage.setItem(
                            `process-studio.notes.v1.${run.run_id}`,
                            event.target.value,
                          );
                        } catch {
                          setToast(
                            "메모를 브라우저에 저장하지 못했습니다. Run JSON으로 내보내세요.",
                          );
                        }
                      }
                    }}
                  />
                  <small>
                    {run
                      ? "이 실행 ID에 자동 저장 · Run JSON에 포함"
                      : "시뮬레이션을 먼저 실행하세요."}
                  </small>
                </div>
              </section>
            ) : result && !invalid ? (
              <div className="plots-grid">
                {displayedSeries.map((series) => (
                  <Chart
                    key={series.key}
                    series={series}
                    baseline={baseline?.series.find(
                      (other) => other.key === series.key,
                    )}
                    time={isTimeSeries(series) ? playback.time : undefined}
                    staticLabel={!isTimeSeries(series)}
                  />
                ))}
                {tab === "physics" && model === "etch" && spatialSeries && (
                  <Chart
                    series={spatialSeries}
                    baseline={spatialBaseline}
                    staticLabel
                  />
                )}
              </div>
            ) : (
              <div className="workflow-empty">
                <Activity size={29} />
                <h3>
                  {invalid
                    ? "이 조건의 공정 응답은 표시하지 않습니다."
                    : "첫 공정 응답을 확인하세요."}
                </h3>
                <p>
                  {invalid
                    ? "Troubleshooting 탭에서 모델 진단을 확인한 뒤 조건을 조정해 주세요."
                    : "왼쪽에서 레시피를 설정하고 Run simulation을 누르면 계산 결과가 나타납니다."}
                </p>
                {!invalid && (
                  <button
                    className="button primary"
                    type="submit"
                    form="recipe-form"
                    disabled={busy}
                  >
                    <Play size={15} />
                    Run simulation
                  </button>
                )}
              </div>
            )}
          </>
        ) : view === "sweep" ? (
          <SweepPanel
            key={model}
            model={model}
            schema={modelSchema}
            params={params}
            fault={fault}
          />
        ) : (
          <section className="library">
            <div className="library-actions">
              <button
                className="button primary"
                onClick={() => {
                  setRecipeName("");
                  setModal("save");
                }}
              >
                <Save size={16} />
                현재 레시피 저장
              </button>
              <button
                className="button secondary"
                disabled={busy}
                onClick={() => importRef.current?.click()}
              >
                <ArrowDownToLine size={16} />
                JSON 불러오기
              </button>
              <button
                className="button secondary"
                onClick={() =>
                  exportJson(`${model}-recipe.json`, currentRecipe())
                }
              >
                <ArrowUpFromLine size={16} />
                현재 레시피 내보내기
              </button>
            </div>
            <input
              className="visually-hidden"
              ref={importRef}
              aria-label="레시피 JSON 파일"
              type="file"
              accept="application/json,.json"
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) void importRecipe(file);
                event.target.value = "";
              }}
            />
            <div className="library-section">
              <h2>
                저장한 레시피 <span>{recipes.length}</span>
              </h2>
              {recipes.length ? (
                recipes.map((recipe, index) => (
                  <div
                    className="library-row"
                    key={`${recipe.model}-${recipe.name}-${index}`}
                  >
                    <div className={`recipe-icon ${recipe.model}`}>
                      <Layers3 size={22} />
                    </div>
                    <div>
                      <h3>{recipe.name}</h3>
                      <p>
                        {recipe.model.toUpperCase()} ·{" "}
                        {recipe.fault === "none" ? "정상 조건" : recipe.fault}
                      </p>
                    </div>
                    <button
                      className="button secondary small"
                      disabled={busy}
                      onClick={() => loadRecipe(recipe)}
                    >
                      불러오기
                    </button>
                    <button
                      className="icon-button"
                      aria-label={`${recipe.name} 내보내기`}
                      onClick={() =>
                        exportJson(`${recipe.model}-recipe.json`, recipe)
                      }
                    >
                      <ArrowUpFromLine size={17} />
                    </button>
                    <button
                      className="icon-button"
                      aria-label={`${recipe.name} 삭제`}
                      onClick={() => {
                        const next = recipes.filter((_, i) => i !== index);
                        try {
                          saveRecipes(next);
                          setRecipes(next);
                        } catch {
                          setError("저장 공간을 변경할 수 없습니다.");
                        }
                      }}
                    >
                      <Trash2 size={17} />
                    </button>
                  </div>
                ))
              ) : (
                <p className="library-empty">
                  아직 저장한 레시피가 없습니다. 현재 조건을 이름과 함께
                  저장하세요.
                </p>
              )}
            </div>
            <div className="library-section">
              <h2>
                최근 실행 <span>{history.length} / 10</span>
              </h2>
              {history.map((item) => (
                <div className="library-row" key={item.run_id}>
                  <div className="history-icon">
                    <Activity size={20} />
                  </div>
                  <div>
                    <h3>
                      {item.model.toUpperCase()}{" "}
                      <code>{item.run_id.slice(0, 8)}</code>
                    </h3>
                    <p>
                      {new Date(item.created_at).toLocaleString("ko-KR")} ·{" "}
                      {item.fault === "none" ? "정상" : item.fault}
                    </p>
                  </div>
                  <button
                    className="button secondary small"
                    disabled={busy}
                    onClick={() => {
                      requestId.current += 1;
                      setModel(item.model);
                      setParams(item.params);
                      setFault(item.fault);
                      setRun(item);
                      playback.reset();
                      if (item.model !== model)
                        playback.setSpeed(item.model === "ald" ? 0.5 : 5);
                      setView("simulate");
                      setBaselineId("auto");
                      setTab("process");
                    }}
                  >
                    결과 열기
                  </button>
                  <button
                    className="icon-button"
                    aria-label={`실행 ${item.run_id} 내보내기`}
                    onClick={() => exportJson(`${item.run_id}.json`, item)}
                  >
                    <ArrowUpFromLine size={17} />
                  </button>
                </div>
              ))}
            </div>
            <p className="subtle-note">
              레시피·실행 기록·메모는 현재 브라우저에 저장됩니다. 중요한 실험은
              JSON과 CSV로 내보내 주세요.
            </p>
          </section>
        )}
        <footer className="workspace-footer">
          <button onClick={() => setModal("notes")}>
            <Info size={13} />
            Reduced physical model · 실험 데이터 검증 전의 학습용 모델
          </button>
          <span>PROCESS STUDIO v0.2.0</span>
        </footer>
      </main>
      {modal === "save" && (
        <Modal title="Save recipe" onClose={() => setModal(null)}>
          <form
            onSubmit={(event) => {
              event.preventDefault();
              storeRecipe();
            }}
            className="save-form"
          >
            <p>현재 입력 조건과 고장 설정을 저장합니다.</p>
            <label htmlFor="recipe-name">레시피 이름</label>
            <input
              id="recipe-name"
              autoFocus
              maxLength={100}
              value={recipeName}
              placeholder={`${model.toUpperCase()} · 첫 번째 실험`}
              onChange={(event) => setRecipeName(event.target.value)}
            />
            <p className="subtle-note">
              같은 모델의 같은 이름은 현재 조건으로 업데이트됩니다.
            </p>
            <div className="modal-actions">
              <button
                className="button secondary"
                type="button"
                onClick={() => setModal(null)}
              >
                취소
              </button>
              <button className="button primary" type="submit">
                <Save size={16} />
                저장
              </button>
            </div>
          </form>
        </Modal>
      )}
      {modal === "notes" && (
        <Modal
          title="Model notes · 계산의 의미와 범위"
          onClose={() => setModal(null)}
          wide
        >
          <div className="model-notes">
            <div className="note-intro">
              <BookOpen size={24} />
              <div>
                <h3>{modelSchema.label}</h3>
                <code>{modelSchema.model_version}</code>
              </div>
            </div>
            <p>
              공정 입력 → 물리 상태 → 공정 결과의 관계를 탐색하는 자체 구현
              학습용 시뮬레이터입니다. 실제 장비의 레시피나 상용 TCAD와 동등한
              예측 정확도를 주장하지 않습니다.
            </p>
            {model === "ald" ? (
              <div className="equation-note">
                <b>공급 응답 + 1D 반응·확산 + 표면 반응</b>
                <p>
                  기체 수송과 표면 피복 변화를 한 사이클 동안 적분합니다. 총 막
                  두께는 첫 사이클 성장량 × 반복 횟수의 선형 투영입니다.
                </p>
              </div>
            ) : (
              <div className="equation-note">
                <b>입자 수지 + 전력 수지 + 유효 식각 수율</b>
                <p>
                  전자 온도와 전자 밀도는 입력 전력·압력·챔버 조건에서
                  계산합니다. Ar 기반 근사이며, 실제 혼합가스 반응망·RF
                  전자기장·2D/3D 식각 형상을 해석하지 않습니다.
                </p>
              </div>
            )}
            <h3>현재 모델의 가정</h3>
            {result?.assumptions.length ? (
              <ul>
                {result.assumptions.map((assumption) => (
                  <li key={assumption}>{assumption}</li>
                ))}
              </ul>
            ) : (
              <p>시뮬레이션 실행 후 모델별 상세 가정이 표시됩니다.</p>
            )}
            <h3>결과를 읽는 기준</h3>
            <ul>
              <li>Baseline은 같은 입력에서 주입한 고장만 제거한 계산입니다.</li>
              <li>
                개념도는 장치 구조와 계산 상태를 설명합니다. 입자 궤적·실제 장비
                도면이 아닙니다.
              </li>
              <li>
                모델 테스트 통과와 실제 공정의 물리 검증은 구분해야 합니다.
              </li>
              <li>
                계수 보정, 실험 비교, 재료별 반응 데이터 확보는 후속 검증
                과제입니다.
              </li>
            </ul>
            {result && (
              <details className="effective-details">
                <summary>유효 계산 상태 · Effective parameters</summary>
                <pre>{JSON.stringify(result.effective, null, 2)}</pre>
              </details>
            )}
          </div>
        </Modal>
      )}
    </div>
  );
}
