import { existsSync } from "node:fs";
import { spawnSync } from "node:child_process";

const apiPython = existsSync("apps/api/.venv/bin/python") ? "apps/api/.venv/bin/python" : "python3";
const searchPython = process.env.ALEPH_PY ?? (existsSync("search/.venv/bin/python") ? "search/.venv/bin/python" : "python3");
const searchHealthUrl = process.env.ALEPH_MLX_SEARCH_HEALTH_URL ?? "http://127.0.0.1:8000/health";

const requiredChecks = [
  ["npm", ["test"]],
  ["npm", ["run", "lint"]],
  ["npm", ["run", "build"]],
  ["npm", ["run", "api:smoke"]],
  [apiPython, ["-m", "compileall", "apps/api/aleph_api"], { PYTHONPATH: "apps/api" }],
  [apiPython, ["-m", "pytest", "apps/api/tests"], { PYTHONPATH: "apps/api" }],
];

const optionalChecks = [
  [searchPython, ["search/preflight.py"]],
];

function run(label, command, args, extraEnv = {}) {
  console.log(`\n==> ${label}`);
  const result = spawnSync(command, args, {
    cwd: process.cwd(),
    env: { ...process.env, ...extraEnv },
    encoding: "utf8",
    stdio: "inherit",
  });
  return result.status ?? 1;
}

for (const [command, args, env] of requiredChecks) {
  const status = run([command, ...args].join(" "), command, args, env);
  if (status !== 0) {
    console.error(`\ndemo-check: failed required check: ${command} ${args.join(" ")}`);
    process.exit(status);
  }
}

const blockedOptional = [];
let searchPreflightOk = false;
for (const [command, args, env] of optionalChecks) {
  const status = run(`[optional] ${command} ${args.join(" ")}`, command, args, env);
  if (status === 0 && args.join(" ") === "search/preflight.py") searchPreflightOk = true;
  if (status !== 0) blockedOptional.push(`${command} ${args.join(" ")}`);
}

if (searchServerHealthy()) {
  const status = run("[optional] npm run api:live-smoke", "npm", ["run", "api:live-smoke"]);
  if (status !== 0) blockedOptional.push("npm run api:live-smoke");
} else {
  blockedOptional.push(`npm run api:live-smoke (search health unavailable at ${searchHealthUrl})`);
}

if (blockedOptional.length) {
  console.log("\ndemo-check: required path ok; optional checks blocked:");
  for (const check of blockedOptional) console.log(`- ${check}`);
  if (searchPreflightOk) {
    console.log("Local MLX dependencies are present; start search/server.py before relying on live local MLX mode.");
  } else {
    console.log("Set up search/.venv with search/requirements.txt before relying on local MLX mode.");
  }
} else {
  console.log("\ndemo-check: required and optional checks ok");
}

function searchServerHealthy() {
  const result = spawnSync("curl", ["-fsS", "-m", "2", searchHealthUrl], {
    cwd: process.cwd(),
    encoding: "utf8",
    stdio: "ignore",
  });
  return result.status === 0;
}
