#!/usr/bin/env node
/**
 * Print gh commands to apply .github/labels.yml.
 *
 * This avoids choosing a label-sync action for every template consumer while
 * preserving the Wittgenstein pattern that labels are an explicit contract.
 */
import { readFileSync } from "node:fs";

const repo = process.argv[2] || "OWNER/REPO";
const text = readFileSync(".github/labels.yml", "utf8");
const blocks = text.split(/\n(?=- name: )/g).filter((b) => b.includes("name:"));
console.log(`# Apply labels to ${repo}`);
for (const block of blocks) {
  const name = block.match(/name:\s*(.+)/)?.[1]?.trim();
  const color = block.match(/color:\s*(.+)/)?.[1]?.trim();
  const description = block.match(/description:\s*(.+)/)?.[1]?.trim().replaceAll('"', '\\"');
  if (!name) continue;
  console.log(
    `gh label create "${name}" --repo "${repo}" --color "${color || "ededed"}" --description "${description || ""}" --force`,
  );
}
