import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

const glossary = readFileSync("docs/glossary.md", "utf8");
const claimLedger = readFileSync("docs/claim-ledger.md", "utf8");
const qualityBar = readFileSync("docs/quality-bar.md", "utf8");

const requiredGlossaryTerms = [
  "Target output",
  "Prompt coordinate",
  "Shortest found",
  "Explicit reconstruction",
  "AlephRun",
  "Candidate point",
  "Leakage score",
  "Pareto frontier",
  "Observation mode",
  "Non-leaking mode",
  "Token loss",
  "Model-relative description length"
];

const errors = [];
for (const term of requiredGlossaryTerms) {
  if (!glossary.includes(`**${term}**:`)) errors.push(`docs/glossary.md missing term: ${term}`);
}

const requiredAvoidPhrases = [
  "globally shortest prompt",
  "true Kolmogorov complexity",
  "context window as semantic endpoint",
  "white-box language without logits",
  "fixture values as evidence"
];
for (const phrase of requiredAvoidPhrases) {
  if (!qualityBar.includes(phrase)) errors.push(`docs/quality-bar.md missing avoid phrase: ${phrase}`);
}

const requiredLedgerPhrases = [
  "Current claims",
  "Evidence",
  "Drift owner",
  "Account A",
  "Account B",
  "Account C",
  "Account D",
  "Account E",
  "Account G",
  "Fixture observations are not model evidence",
  "White-box product observations require logits or model internals"
];
for (const phrase of requiredLedgerPhrases) {
  if (!claimLedger.includes(phrase)) errors.push(`docs/claim-ledger.md missing phrase: ${phrase}`);
}

function walk(dir) {
  const out = [];
  for (const entry of readdirSync(dir)) {
    const path = join(dir, entry);
    if (["node_modules", ".git", "docs/archive"].includes(path)) continue;
    if (statSync(path).isDirectory()) out.push(...walk(path));
    else if (path.endsWith(".md")) out.push(path);
  }
  return out;
}

const activeDocs = ["README.md", "THESIS.md", ...walk("docs")];
const overclaimPatterns = [
  {
    pattern: /\bprove(?:s|n)? (?:a |the )?globally shortest prompt\b/i,
    allowedNearby: /\bdoes not\b|\bnot\b|\bavoid\b|\bdeferred\b|\bout of scope\b/i
  },
  {
    pattern: /\bstrict Kolmogorov complexity\b/i,
    allowedNearby: /\bdoes not\b|\bnot\b|\bavoid\b|\bdeferred\b|\bout of scope\b|\bnot strict\b/i
  },
  {
    pattern: /\bwhite-box observations?\b/i,
    allowedNearby: /\blogits\b|\bmodel internals\b|\bwithout\b|\bfuture\b|\bstub\b|\bnot\b|\brequires?\b/i
  },
  {
    pattern: /\bfixture values as evidence\b/i,
    allowedNearby: /\bavoid\b|\bnot\b|\bdo not\b|\bwithout\b/i
  }
];

for (const file of activeDocs) {
  const text = readFileSync(file, "utf8");
  for (const { pattern, allowedNearby } of overclaimPatterns) {
    for (const match of text.matchAll(new RegExp(pattern, "gi"))) {
      const start = Math.max(0, match.index - 180);
      const end = Math.min(text.length, match.index + match[0].length + 180);
      const nearby = text.slice(start, end);
      if (!allowedNearby.test(nearby)) errors.push(`${file}: unguarded overclaim phrase "${match[0]}"`);
    }
  }
}

if (errors.length) {
  console.error("Language check failed:");
  for (const error of errors) console.error(`- ${error}`);
  process.exit(1);
}
console.log("check-language: ok");
