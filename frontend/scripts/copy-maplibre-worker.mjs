// maplibre-gl 6 locates its web worker next to its own module via a dynamic URL that
// bundlers cannot see, so Next.js never emits it. Copy the worker (and the shared chunk
// it imports) to public/ and point maplibre at it with setWorkerUrl().
import { copyFileSync, mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";

const require = createRequire(import.meta.url);
const dist = join(dirname(require.resolve("maplibre-gl/package.json")), "dist");
const target = join(import.meta.dirname, "..", "public", "maplibre");

mkdirSync(target, { recursive: true });
for (const file of ["maplibre-gl-worker.mjs", "maplibre-gl-shared.mjs"]) {
  copyFileSync(join(dist, file), join(target, file));
}
console.log(`maplibre worker copied to ${target}`);
