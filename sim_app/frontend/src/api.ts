import type { ModelKey, Params, Schema, Simulation, Sweep } from "./types";

async function request<T>(url: string, body?: unknown): Promise<T> {
  const response = await fetch(
    url,
    body === undefined
      ? undefined
      : {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
  );
  let data: unknown;
  try {
    data = await response.json();
  } catch {
    throw new Error(
      "서버 응답을 읽을 수 없습니다. Python 서버 실행 상태를 확인해 주세요.",
    );
  }
  if (!response.ok) {
    const message =
      typeof data === "object" && data !== null
        ? ((data as Record<string, unknown>).error ??
          (data as Record<string, unknown>).detail)
        : null;
    throw new Error(
      typeof message === "string"
        ? message
        : `Request failed (${response.status})`,
    );
  }
  return data as T;
}

export const getSchema = () => request<Schema>("/api/schema");
export const simulate = (model: ModelKey, params: Params, fault: string) =>
  request<Simulation>("/api/simulate", { model, params, fault });
export const runSweep = (
  model: ModelKey,
  params: Params,
  fault: string,
  parameter: string,
  values: number[],
) => request<Sweep>("/api/sweep", { model, params, fault, parameter, values });
