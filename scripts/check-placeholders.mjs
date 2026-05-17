import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

const SKIP_DIRS = new Set(["node_modules", ".git", ".venv", "__pycache__", "dist"]);

function walk(dir) {
  const out = [];
  for (const entry of readdirSync(dir)) {
    if (SKIP_DIRS.has(entry)) continue;
    const path = join(dir, entry);
    if (path === "docs/archive/images") continue;
    if (statSync(path).isDirectory()) out.push(...walk(path));
    else if (/\.(md|ts|tsx|json|mjs|yml|yaml|html|css|py|toml)$/.test(path)) out.push(path);
  }
  return out;
}

const banned = ["TODO" + " TEMPLATE", "PROJECT" + "_NAME", "INSERT" + "_", "TBD" + "_OWNER"];
const hits = [];
for (const file of walk(".")) {
  const text = readFileSync(file, "utf8");
  for (const term of banned) if (text.includes(term)) hits.push(`${file}: ${term}`);
}
if (hits.length) {
  console.error("Template placeholders remain:");
  for (const hit of hits) console.error(`- ${hit}`);
  process.exit(1);
}
console.log("check-placeholders: ok");
