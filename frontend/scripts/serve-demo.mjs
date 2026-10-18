// Minimal static-only preview server: intentionally no API or SPA fallback.
import { createServer } from "node:http"
import { readFile, stat } from "node:fs/promises"
import { resolve, extname, sep } from "node:path"
import { fileURLToPath } from "node:url"

const root = fileURLToPath(new URL("../out-demo/", import.meta.url))
const mime = { ".html": "text/html; charset=utf-8", ".js": "application/javascript", ".css": "text/css", ".png": "image/png", ".svg": "image/svg+xml", ".ico": "image/x-icon", ".woff2": "font/woff2", ".txt": "text/plain; charset=utf-8" }
const server = createServer(async (request, response) => {
  try {
    const pathname = decodeURIComponent(new URL(request.url, "http://localhost").pathname)
    let target = resolve(root, "." + pathname)
    if (target !== resolve(root) && !target.startsWith(resolve(root) + sep)) throw new Error("Forbidden")
    if ((await stat(target)).isDirectory()) target = resolve(target, "index.html")
    const body = await readFile(target)
    response.writeHead(200, { "Content-Type": mime[extname(target)] ?? "application/octet-stream" })
    response.end(request.method === "HEAD" ? undefined : body)
  } catch {
    response.writeHead(404, { "Content-Type": "text/html; charset=utf-8" })
    response.end(await readFile(resolve(root, "404.html")).catch(() => "Not found"))
  }
})
server.listen(Number(process.env.DEMO_PORT ?? 4175), "127.0.0.1", () => console.log("Static demo: http://127.0.0.1:4175"))
