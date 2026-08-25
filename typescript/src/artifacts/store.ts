import { mkdir, readFile, writeFile } from "node:fs/promises";
import { randomUUID } from "node:crypto";
import { resolve } from "node:path";
import { validateArtifactRef } from "../harness/validate.js";

export interface ArtifactRef {
  artifactId: string;
  kind: string;
  sizeBytes: number;
  createdBy: string;
  createdAt: string;
  summary: string;
  uri: string;
}

export interface WriteArtifactInput {
  kind: string;
  summary: string;
  content: unknown;
  createdBy: string;
}

/**
 * Local filesystem artifact store (default). Pluggable: implement the same two methods
 * against S3/GCS/etc. and swap in orchestrator wiring - callers only ever see an ArtifactRef,
 * never a storage-specific type (notes section 4-5).
 */
export class LocalArtifactStore {
  constructor(private readonly rootDir: string) {}

  async write(input: WriteArtifactInput): Promise<ArtifactRef> {
    await mkdir(this.rootDir, { recursive: true });
    const artifactId = randomUUID();
    const path = resolve(this.rootDir, `${artifactId}.json`);
    const serialized = JSON.stringify(input.content, null, 2);
    await writeFile(path, serialized, "utf-8");

    const ref: ArtifactRef = {
      artifactId,
      kind: input.kind,
      sizeBytes: Buffer.byteLength(serialized, "utf-8"),
      createdBy: input.createdBy,
      createdAt: new Date().toISOString(),
      summary: input.summary,
      uri: `file://${path}`,
    };
    validateArtifactRef(ref);
    return ref;
  }

  async read(artifactId: string): Promise<unknown> {
    const path = resolve(this.rootDir, `${artifactId}.json`);
    const raw = await readFile(path, "utf-8");
    return JSON.parse(raw) as unknown;
  }
}
