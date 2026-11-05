// Builds a throw-away fake Steam + Dota 2 folder for the GSI end-to-end test (test data only).
import { mkdirSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));

export const FAKE_STEAM = join(HERE, ".tmp", "Steam");

/** Called from playwright.config.ts, i.e. before the web server starts. */
export function createFakeDota() {
  rmSync(join(HERE, ".tmp"), { recursive: true, force: true });
  const apps = join(FAKE_STEAM, "steamapps");
  const dota = join(apps, "common", "dota 2 beta");
  mkdirSync(join(dota, "game", "dota", "cfg"), { recursive: true });
  mkdirSync(join(dota, "game", "bin", "win64"), { recursive: true });
  writeFileSync(join(dota, "game", "bin", "win64", "dota2.exe"), "MZ");
  writeFileSync(join(apps, "appmanifest_570.acf"),
    '"AppState" { "appid" "570" "name" "Dota 2" "StateFlags" "4" "installdir" "dota 2 beta" "buildid" "1" }');
}
