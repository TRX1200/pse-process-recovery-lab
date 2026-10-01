import { useState } from "react";
import { GUIDE_SECTIONS, GUIDE_SOURCES, PARAMETER_TIPS, guideMarkdown, parameterTier } from "../userGuide";
import { download } from "../storage";
import type { ModelKey, Schema } from "../types";

export function UserGuide({ schema, model, onStart }: { schema: Schema; model: ModelKey; onStart: () => void }) {
  const [query, setQuery] = useState("");
  const [tier, setTier] = useState("전체");
  const spec = schema.models[model];
  const normalized = query.trim().toLocaleLowerCase();
  const parameters = spec.params.filter(p =>
    (tier === "전체" || parameterTier(model, p) === tier) &&
    `${p.label} ${p.key} ${p.description} ${PARAMETER_TIPS[model][p.key]}`.toLocaleLowerCase().includes(normalized));
  return (
    <article className="user-guide" aria-label="시뮬레이터 사용 설명서">
      <div className="guide-start">
        <p>처음에는 핵심 조건 4개만 조절하세요. 나머지 값의 의미는 아래 사전에서 필요할 때 찾아볼 수 있습니다.</p>
        <div>
          <button className="button primary" onClick={onStart}>표면 관찰로 시작</button>
          <button className="button secondary" onClick={() => download("ALD_Etch_Lab_User_Guide_KR.md", guideMarkdown(schema), "text/markdown;charset=utf-8")}>전체 설명서 저장 · Markdown</button>
        </div>
      </div>
      <div className="guide-sections">
        {GUIDE_SECTIONS.map((section, index) => (
          <details key={section.title} open={index < 2}>
            <summary><span>{String(index + 1).padStart(2, "0")}</span>{section.title}</summary>
            {section.paragraphs.map(p => <p key={p}>{p}</p>)}
          </details>
        ))}
      </div>
      <section className="parameter-dictionary" aria-label="전체 파라미터 사전">
        <h2>{spec.label} 파라미터 사전 <small>{parameters.length} / {spec.params.length}</small></h2>
        <p>위 공정 선택 버튼으로 ALD / Etch 사전을 바꿉니다. 기본값·범위·단위는 현재 모델 정의에서 읽습니다.</p>
        <div className="dictionary-filters">
          <label>파라미터 검색<input type="search" value={query} onChange={e => setQuery(e.target.value)} placeholder="예: 바이어스, 퍼지, 반응 확률" /></label>
          <label>입력 분류<select value={tier} onChange={e => setTier(e.target.value)}>{["전체", "먼저 조절", "추가 레시피", "챔버·형상", "모델 계수", "이상 주입"].map(t => <option key={t}>{t}</option>)}</select></label>
        </div>
        <div className="dictionary-cards">
          {parameters.map(p => (
            <section key={p.key} className="dictionary-entry">
              <div><h3>{p.label}</h3><span>{parameterTier(model, p)}</span></div>
              <code>{p.key}</code>
              <dl><div><dt>단위</dt><dd>{p.unit || "무차원"}</dd></div><div><dt>기본값</dt><dd>{p.default}</dd></div><div><dt>입력 범위</dt><dd>{p.min}–{p.max}</dd></div></dl>
              <p>{p.description}</p>
              <p className="dictionary-tip">{PARAMETER_TIPS[model][p.key]}</p>
            </section>
          ))}
        </div>
        {!parameters.length && <p role="status">검색 결과가 없습니다. 검색어나 입력 분류를 바꿔 보세요.</p>}
      </section>
      <section className="guide-faults"><h2>{spec.label} 이상 모드</h2><dl>{spec.faults.map(f => <div key={f.id}><dt>{f.label}</dt><dd>{f.description}</dd></div>)}</dl></section>
      <section className="guide-sources"><h2>근거와 더 읽기</h2>{GUIDE_SOURCES.map(s => <p key={s.url}><a href={s.url} target="_blank" rel="noreferrer">{s.title} ↗</a><br />{s.note}</p>)}</section>
    </article>
  );
}
