import { renderToString } from "katex";
import "katex/dist/katex.min.css";

/** Static, reviewed LaTeX only. MathML is preserved for assistive technology. */
export function MathBlock({
  expressions,
  label,
}: {
  expressions: readonly string[];
  label: string;
}) {
  return (
    <div className="math-block" role="group" aria-label={label}>
      {expressions.map((expression) => (
        <div
          className="math-row"
          key={expression}
          tabIndex={0}
          dangerouslySetInnerHTML={{
            __html: renderToString(expression, {
              displayMode: true,
              output: "htmlAndMathml",
              throwOnError: true,
              strict: "error",
              trust: false,
            }),
          }}
        />
      ))}
    </div>
  );
}
