import { spawnSync } from "node:child_process"
import { createRequire } from "node:module"
import { fileURLToPath } from "node:url"

const require = createRequire(import.meta.url)
const result = spawnSync(process.execPath, [require.resolve("next/dist/bin/next"), "build"], {
  cwd: fileURLToPath(new URL("../", import.meta.url)),
  env: { ...process.env, NEXT_PUBLIC_DEMO_MODE: "1", NEXT_PUBLIC_API_MODE: "mock" },
  stdio: "inherit",
})
if (result.error) console.error(result.error.message)
if (result.status !== 0) process.exit(result.status ?? 1)
await import("./build-retouch-demo.mjs")
