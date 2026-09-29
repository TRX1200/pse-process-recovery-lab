import { copyFile, mkdir } from "node:fs/promises";

const source = new URL(
  "../../../output/pdf/Process_Studio_Semiconductor_Study_KR.pdf",
  import.meta.url,
);
const destination = new URL("../dist/study/", import.meta.url);
await mkdir(destination, { recursive: true });
await copyFile(
  source,
  new URL("Process_Studio_Semiconductor_Study_KR.pdf", destination),
);
