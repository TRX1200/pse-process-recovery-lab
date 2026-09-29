// One worker owns Python state; model calculations never block the UI thread.
type Operation = "schema" | "simulate" | "sweep";
type Pending = {
  resolve: (value: unknown) => void;
  reject: (error: Error) => void;
  timer: ReturnType<typeof setTimeout>;
};

let worker: Worker | undefined;
let nextId = 0;
const pending = new Map<number, Pending>();

function reset(message: string) {
  worker?.terminate();
  worker = undefined;
  for (const item of pending.values()) {
    clearTimeout(item.timer);
    item.reject(new Error(message));
  }
  pending.clear();
}

export function browserRequest<T>(
  operation: Operation,
  payload?: unknown,
): Promise<T> {
  if (!worker) {
    worker = new Worker(new URL("./browser.worker.ts", import.meta.url), {
      type: "module",
    });
    worker.onmessage = (
      event: MessageEvent<{ id: number; result?: unknown; error?: string }>,
    ) => {
      const item = pending.get(event.data.id);
      if (!item) return;
      clearTimeout(item.timer);
      pending.delete(event.data.id);
      if (event.data.error) item.reject(new Error(event.data.error));
      else item.resolve(event.data.result);
    };
    worker.onerror = () =>
      reset(
        "브라우저 계산 엔진을 실행할 수 없습니다. 인터넷 연결을 확인하고 다시 시도해 주세요.",
      );
    worker.onmessageerror = () =>
      reset("계산 결과를 읽을 수 없습니다. 다시 실행해 주세요.");
  }
  const activeWorker = worker;
  const id = ++nextId;
  return new Promise<T>((resolve, reject) => {
    const timer = setTimeout(
      () =>
        reset(
          "계산 엔진 응답 시간이 초과됐습니다. 인터넷 연결을 확인하거나 계산 범위를 줄여 다시 시도해 주세요.",
        ),
      300_000,
    );
    pending.set(id, { resolve: (value) => resolve(value as T), reject, timer });
    activeWorker.postMessage({ id, operation, payload });
  });
}
