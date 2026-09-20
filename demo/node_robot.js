"use strict";

const fs = require("node:fs");

const runId = process.env.RCC_RUN_ID;
const resultPath = process.env.RCC_RESULT_PATH;
const temporaryPath = `${resultPath}.tmp`;
const result = {
  version: 1,
  run_id: runId,
  status: "success",
  summary: "Processo Node.js concluido com contrato de resultado",
};

console.log("Robo Node.js executado pelo Zanella Orchestrator");
fs.writeFileSync(temporaryPath, JSON.stringify(result), "utf8");
fs.renameSync(temporaryPath, resultPath);
