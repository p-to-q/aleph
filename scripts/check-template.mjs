#!/usr/bin/env node
/**
 * Template checks.
 *
 * These checks keep the four profile promises honest. They are intentionally
 * dependency-free so the template can run before a project chooses a stack.
 */
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

const matrix = JSON.parse(readFileSync("checks/profile-matrix.json", "utf8"));
const failures = [];

for (const [profile, files] of Object.entries(matrix)) {
  for (const file of files) {
    if (!existsSync(file)) failures.push(`profile ${profile} expects ${file}`);
  }
}

function walk(dir) {
  const ignored = new Set([".git", "node_modules", "dist", "build", "coverage"]);
  const out = [];
  for (const entry of readdirSync(dir)) {
    if (ignored.has(entry)) continue;
    const path = join(dir, entry);
    const st = statSync(path);
    if (st.isDirectory()) out.push(...walk(path));
    else if (entry === "README.md") out.push(path);
  }
  return out;
}

for (const file of walk(".")) {
  const body = readFileSync(file, "utf8");
  if (!/^## .*Sample|^### .*Sample|^## Sample|^### Sample/m.test(body)) {
    failures.push(`${file} should contain a Sample section`);
  }
}

if (failures.length) {
  console.error("Template check failed:");
  for (const f of failures) console.error(`- ${f}`);
  process.exit(1);
}

console.log(`Template checks passed (${Object.keys(matrix).length} profiles, README samples verified).`);
