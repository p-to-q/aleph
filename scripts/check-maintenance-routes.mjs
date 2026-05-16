import { existsSync, readFileSync } from "node:fs";

if (!existsSync("docs/maintenance-routes.md")) {
  console.error("docs/maintenance-routes.md missing");
  process.exit(1);
}
const routes = readFileSync("docs/maintenance-routes.md", "utf8");
for (const required of ["Active routes", "Parked routes", "artifact-first"]) {
  if (!routes.includes(required)) {
    console.error(`Maintenance routes missing phrase: ${required}`);
    process.exit(1);
  }
}
console.log("check-maintenance-routes: ok");
