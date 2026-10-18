import { spawnSync } from "node:child_process"
import { existsSync, readFileSync } from "node:fs"
import { createRequire } from "node:module"
import { join, resolve } from "node:path"
import { fileURLToPath, pathToFileURL } from "node:url"

const root = fileURLToPath(new URL("../../", import.meta.url))
const source = JSON.parse(readFileSync(join(root, "integrations/retouch-source.json"), "utf8"))
const checkout = resolve(root, source.checkout), frontend = join(checkout, "frontend")
function command(file, args, cwd = root) {
  const result = spawnSync(file, args, { cwd, stdio: "inherit", shell: false })
  if (result.error || result.status !== 0) throw new Error(`${file} failed: ${result.error?.message ?? result.status}`)
}
if (!existsSync(join(checkout, ".git"))) {
  command("git", ["clone", "--no-checkout", source.repository, checkout])
  command("git", ["checkout", source.commit], checkout)
  command("git", ["apply", resolve(root, source.patch)], checkout)
}
const head = spawnSync("git", ["rev-parse", "HEAD"], { cwd: checkout, encoding: "utf8" })
if (head.stdout.trim() !== source.commit) throw new Error("Retouch checkout does not match the pinned revision")
const patched = spawnSync("git", ["apply", "--reverse", "--check", resolve(root, source.patch)], { cwd: checkout, encoding: "utf8" })
if (patched.status !== 0) throw new Error("The PhotoAI retouch patch must be applied before building the demo")
if (!existsSync(join(frontend, "node_modules/vite"))) {
  if (!process.env.npm_execpath) throw new Error("Run this build using npm run build:demo")
  command(process.execPath, [process.env.npm_execpath, "ci", "--no-audit", "--no-fund"], frontend)
}
const require = createRequire(join(frontend, "package.json"))
command(process.execPath, [require.resolve("typescript/bin/tsc"), "--project", join(root, "integrations/demo-retouch/tsconfig.json")])
const { build } = await import(pathToFileURL(require.resolve("vite")).href)
const runtime = join(root, "integrations/demo-retouch/runtime.ts").replaceAll("\\", "/")
await build({
  root: frontend, configFile: join(frontend, "vite.config.ts"), base: "/demo-editor/",
  plugins: [{ name: "photoai-static-demo", enforce: "pre", transform(code, id) {
    const path = id.replaceAll("\\", "/")
    if (path.endsWith("/src/main.tsx")) return `import ${JSON.stringify(runtime)};\n${code}`
    if (path.endsWith("/src/App.tsx")) return code.replace("<BrowserRouter>", '<BrowserRouter basename="/demo-editor">')
    if (path.endsWith("/src/pages/PhotoAIImportPage.tsx")) return code.replace(/const PHOTOAI_ORIGIN = .*/, "const PHOTOAI_ORIGIN = window.location.origin")
  } }],
  build: { outDir: join(root, "frontend/out-demo/demo-editor"), emptyOutDir: true, sourcemap: false },
})
