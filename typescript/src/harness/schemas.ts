import { existsSync, readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

/**
 * Walks up from this module's actual location until it finds `specs/schemas` - deliberately
 * not a fixed parent-count, since that breaks the moment this file is bundled (tsup flattens
 * src/harness/schemas.ts into dist/, changing its depth relative to the repo root). A
 * deployment must keep `specs/` as a sibling of `typescript/` on disk either way - see
 * deploy/Dockerfile.typescript - this just stops assuming a specific directory depth to find it.
 */
function findRepoRoot(startDir: string): string {
  let dir = startDir;
  for (;;) {
    if (existsSync(resolve(dir, "specs", "schemas"))) return dir;
    const parent = dirname(dir);
    if (parent === dir) {
      throw new Error(`could not locate repo root (no ancestor of ${startDir} contains specs/schemas)`);
    }
    dir = parent;
  }
}

const repoRoot = findRepoRoot(dirname(fileURLToPath(import.meta.url)));
const schemasDir = resolve(repoRoot, "specs", "schemas");

export function loadSchema(fileName: string): Record<string, unknown> {
  const path = resolve(schemasDir, fileName);
  return JSON.parse(readFileSync(path, "utf-8")) as Record<string, unknown>;
}

export function loadAgentRole(roleName: string): Record<string, unknown> {
  const path = resolve(repoRoot, "specs", "agents", `${roleName}.json`);
  return JSON.parse(readFileSync(path, "utf-8")) as Record<string, unknown>;
}

export function loadPrompt(promptRelativePath: string): string {
  const path = resolve(repoRoot, promptRelativePath);
  return readFileSync(path, "utf-8");
}

export const repoRootPath = repoRoot;
