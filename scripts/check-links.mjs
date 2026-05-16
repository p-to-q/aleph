#!/usr/bin/env node
/**
 * Local Markdown link checker.
 *
 * It checks relative links only; external links are intentionally not fetched.
 * This keeps CI fast and avoids flaky network checks in small projects.
 */
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { dirname, join, normalize } from "node:path";

const ignored = new Set(["node_modules", ".git", "dist", "build", "coverage"]);

function walk(dir) {
  const out = [];
  for (const entry of readdirSync(dir)) {
    if (ignored.has(entry)) continue;
    const path = join(dir, entry);
    const st = statSync(path);
    if (st.isDirectory()) out.push(...walk(path));
    else if (path.endsWith(".md")) out.push(path);
  }
  return out;
}

const linkRe = /\[[^\]]+\]\(([^)]+)\)/g;
const failures = [];
for (const file of walk(".")) {
  const body = readFileSync(file, "utf8");
  let m;
  while ((m = linkRe.exec(body))) {
    const raw = m[1].trim();
    if (!raw || raw.startsWith("http") || raw.startsWith("mailto:") || raw.startsWith("#")) continue;
    if (raw.startsWith("./#") || raw.startsWith("../#")) continue;
    const [target] = raw.split("#");
    if (!target) continue;
    const resolved = normalize(join(dirname(file), target));
    if (!existsSync(resolved)) failures.push(`${file} -> ${raw}`);
  }
}

if (failures.length) {
  console.error("Broken local Markdown links:");
  for (const f of failures) console.error(`- ${f}`);
  process.exit(1);
}
console.log("Local Markdown links passed.");
