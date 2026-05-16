#!/usr/bin/env node
/**
 * GitHub ledger sync seed.
 *
 * This script deliberately prints commands instead of mutating docs. The intent
 * is to make the historical audit reproducible without assuming every template
 * consumer has GitHub CLI auth or the same issue taxonomy.
 */
const repo = process.argv[2] || "OWNER/REPO";
console.log(`# GitHub ledger sync plan for ${repo}`);
console.log("");
console.log("Run these commands when GitHub CLI is authenticated:");
console.log("");
console.log(`gh issue list --repo ${repo} --state all --limit 200 --json number,title,state,labels,createdAt,updatedAt,url`);
console.log(`gh pr list --repo ${repo} --state all --limit 200 --json number,title,state,labels,createdAt,updatedAt,mergedAt,url`);
console.log("");
console.log("Then summarize into optional/history/issue-pr-ledger.md by pattern, not by dumping raw JSON.");
