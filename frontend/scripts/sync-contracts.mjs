// Copies shared contracts into the frontend. Run after ANY change in /contracts: npm run sync-contracts
import { mkdirSync, readdirSync, copyFileSync, rmSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const fixturesSrc = join(root, "contracts", "fixtures");
const fixturesDst = join(root, "frontend", "src", "fixtures");

rmSync(fixturesDst, { recursive: true, force: true });
mkdirSync(fixturesDst, { recursive: true });
for (const f of readdirSync(fixturesSrc).filter((n) => n.endsWith(".json"))) {
  copyFileSync(join(fixturesSrc, f), join(fixturesDst, f));
}
copyFileSync(join(root, "contracts", "enums.ts"), join(root, "frontend", "src", "lib", "enums.ts"));
console.log("synced contracts -> src/fixtures, src/lib/enums.ts");
