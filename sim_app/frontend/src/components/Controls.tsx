import {
  ChevronDown,
  RotateCcw,
  Play,
  LoaderCircle,
  SlidersHorizontal,
  Box,
} from "lucide-react";
import type { ModelKey, ModelSchema, Parameter, Params, Recipe } from "../types";
import { QUICK_KEYS } from "../userGuide";

function ParameterControl({
  parameter,
  value,
  onChange,
}: {
  parameter: Parameter;
  value: number;
  onChange: (value: number) => void;
}) {
  const { key, label, min, max, step, unit, description } = parameter;
  return (
    <div className="parameter-control">
      <div className="parameter-top">
        <label htmlFor={`number-${key}`} title={description}>
          {label}
        </label>
        <div className="parameter-number">
          <input
            id={`number-${key}`}
            aria-describedby={`help-${key}`}
            type="number"
            value={value}
            min={min}
            max={max}
            step={key === "cycles" ? 1 : "any"}
            required
            onChange={(event) => {
              if (event.target.value !== "")
                onChange(Number(event.target.value));
            }}
          />
          <span>{unit}</span>
        </div>
      </div>
      <input
        className="range"
        aria-label={`${label} 슬라이더`}
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        style={
          {
            "--range-progress": `${Math.max(0, Math.min(100, ((value - min) / (max - min)) * 100))}%`,
          } as React.CSSProperties
        }
        onChange={(event) => onChange(Number(event.target.value))}
      />
      <div className="range-labels">
        <span>{min}</span>
        <span>{max}</span>
      </div>
      <p className="parameter-help" id={`help-${key}`}>
        {description}
      </p>
    </div>
  );
}

export function Controls({
  model,
  schema,
  params,
  onChange,
  busy,
  onRun,
  onReset,
  recipes,
  onLoadRecipe,
}: {
  model: ModelKey;
  schema: ModelSchema;
  params: Params;
  onChange: (key: string, value: number) => void;
  busy: boolean;
  onRun: () => void;
  onReset: () => void;
  recipes: Recipe[];
  onLoadRecipe: (recipe: Recipe) => void;
}) {
  const groups = [
    "Quick",
    ...new Set(
      schema.params
        .filter((parameter) => parameter.key !== "fault_severity")
        .map((parameter) => parameter.group),
    ),
  ];
  const groupLabels: Record<string, string> = {
    Quick: "먼저 조절할 조건 4개",
    Recipe: "추가 레시피 조건",
    Chamber: "챔버 · 수송 조건",
    Advanced: "물리 모델 파라미터",
  };
  return (
    <aside className="control-panel">
      <div className="control-title">
        <h2>레시피 입력</h2>
        <SlidersHorizontal size={17} />
      </div>
      <form
        id="recipe-form"
        onSubmit={(event) => {
          event.preventDefault();
          onRun();
        }}
        className="control-form"
      >
        <fieldset disabled={busy} className="parameter-fieldset">
          <div className="reference-recipe">
            <label htmlFor="recipe-selection">레시피 불러오기</label>
            <div className="select-wrap">
              <select
                id="recipe-selection"
                value=""
                onChange={(event) => {
                  if (event.target.value === "default") onReset();
                  else onLoadRecipe(recipes[Number(event.target.value)]);
                }}
              >
                <option value="">{schema.label} · Custom recipe</option>
                <option value="default">기본 레시피</option>
                {recipes.map((recipe, index) => (
                  <option key={`${recipe.name}-${index}`} value={index}>
                    {recipe.name}
                  </option>
                ))}
              </select>
              <ChevronDown size={15} />
            </div>
          </div>
          {groups.map((group, index) => (
            <details
              className={`parameter-group ${index === 0 ? "primary-group" : ""}`}
              key={group}
              open={index === 0}
            >
              <summary>
                {index === 0 ? null : <Box size={17} />}
                <span>{groupLabels[group] ?? group}</span>
                <ChevronDown size={15} />
              </summary>
              <div className="group-parameters">
                {schema.params
                  .filter(
                    (parameter) =>
                      (group === "Quick" ? QUICK_KEYS[model].includes(parameter.key) : parameter.group === group && !QUICK_KEYS[model].includes(parameter.key)) &&
                      parameter.key !== "fault_severity",
                  )
                  .map((parameter) => (
                    <ParameterControl
                      key={parameter.key}
                      parameter={parameter}
                      value={params[parameter.key] ?? parameter.default}
                      onChange={(value) => onChange(parameter.key, value)}
                    />
                  ))}
              </div>
            </details>
          ))}
        </fieldset>
        <div className="control-actions">
          <button
            className="button primary run-button"
            type="submit"
            disabled={busy}
          >
            {busy ? (
              <LoaderCircle className="spin" size={17} />
            ) : (
              <Play size={17} fill="currentColor" />
            )}{" "}
            {busy ? "계산 중…" : "레시피 계산 · 재생"}
          </button>
          <button
            className="button secondary"
            type="button"
            onClick={onReset}
            disabled={busy}
          >
            <RotateCcw size={16} /> 기본값으로 초기화
          </button>
        </div>
      </form>
    </aside>
  );
}
