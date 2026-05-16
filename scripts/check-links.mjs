import { readdirSync, readFileSync, statSync, existsSync } from "node:fs";
import { dirname, join, normalize } from "node:path";

function walk(dir) {
  const out = [];
  for (const entry of readdirSync(dir)) {
    const path = join(dir, entry);
    if (entry === "node_modules" || entry === ".git") continue;
    if (statSync(path).isDirectory()) out.push(...walk(path));
    else if (path.endsWith(".md")) out.push(path);
  }
  return out;
}

const broken = [];
for (const file of walk(".")) {
  const text = readFileSync(file, "utf8");
  for (const match of text.matchAll(/\[[^\]]+\]\(([^)]+)\)/g)) {
    const href = match[1];
    if (/^(https?:|mailto:|#)/.test(href)) continue;
    const target = normalize(join(dirname(file), href.split("#")[0]));
    if (!existsSync(target)) broken.push(`${file} -> ${href}`);
  }
}
if (broken.length) {
  console.error("Broken local markdown links:");
  for (const item of broken) console.error(`- ${item}`);
  process.exit(1);
}
console.log("check-links: ok");
