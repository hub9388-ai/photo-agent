// Loaded only by the static demo build. The original editor and its API types stay intact.
import type { Asset } from '@/api/assets'
import type { SessionDetail, HistoryEntry } from '@/api/sessions'
import type { Run } from '@/api/runs'
import type { Turn } from '@/api/agent'
import { makeAdjustFilter, toAdjustPreview } from '@/lib/adjustPreview'
import { useEditorUi } from '@/stores/editorUi'
import { readAdviceDraft } from '@/lib/postAdvice'

const nativeFetch = window.fetch.bind(window)
const KEY = 'photoai.demo.editor.meta.v2'
const SESSION = 'demo-editor-cat'
type Model = { assets: Asset[]; sequence: string[]; cursor: number; revision: number; title: string; history: HistoryEntry[]; turns: Turn[] }
const original: Asset = { id: 'original', kind: 'original', source: 'upload', image_format: 'PNG', width: 768, height: 1024,
  size_bytes: 1372477, has_alpha: false, created_at: new Date().toISOString(), url: '/demo/cat-original.png' }
let model: Model = { assets: [original], sequence: ['original'], cursor: 0, revision: 1, title: 'PhotoAI · 街角三花猫', history: [], turns: [] }
const blobs = new Map<string, Blob>()
const database = new Promise<IDBDatabase>((resolve, reject) => {
  const request = indexedDB.open('photoai.demo.editor.v2', 1)
  request.onupgradeneeded = () => request.result.createObjectStore('images')
  request.onsuccess = () => { request.result.onversionchange = () => request.result.close(); resolve(request.result) }
  request.onerror = () => reject(new Error('无法打开浏览器图片存储'))
})
void database.catch(() => {}) // An unavailable store is reported when a save is attempted.
async function readBlob(id: string) {
  const db = await database
  return new Promise<Blob | undefined>((resolve, reject) => {
    const request = db.transaction('images').objectStore('images').get(id)
    request.onsuccess = () => resolve(request.result); request.onerror = () => reject(request.error)
  })
}
async function storeBlob(id: string, blob: Blob) {
  const db = await database
  await new Promise<void>((resolve, reject) => {
    const transaction = db.transaction('images', 'readwrite')
    transaction.objectStore('images').put(blob, id)
    transaction.oncomplete = () => resolve(); transaction.onerror = () => reject(transaction.error)
  })
  blobs.set(id, blob)
}
const ready = (async () => {
  try {
    const saved = localStorage.getItem(KEY)
    if (!saved) return
    const candidate = JSON.parse(saved) as Model
    if (!Array.isArray(candidate.assets) || !candidate.sequence?.length) return
    for (const asset of candidate.assets) {
      if (asset.id === 'original') asset.url = original.url
      else if (asset.id.startsWith('rounded-')) asset.url = '/demo/cat-rounded.png'
      else { const blob = await readBlob(asset.id); if (!blob) throw new Error('版本图片缺失'); blobs.set(asset.id, blob); asset.url = URL.createObjectURL(blob) }
    }
    model = candidate
  } catch { localStorage.removeItem(KEY) }
})()
function persist() {
  localStorage.setItem(KEY, JSON.stringify({ ...model, assets: model.assets.map(asset => ({ ...asset, url: asset.id === 'original' ? original.url : '' })) }))
}
function current() { return model.assets.find(asset => asset.id === model.sequence[model.cursor])! }
function documentFor(asset: Asset) {
  return { width: asset.width, height: asset.height, layers: [{ id: 'base', name: '底图', kind: 'image' as const,
    width: asset.width, height: asset.height, asset_id: asset.id, opacity: 1, visible: true, locked: true,
    transform: { x: 0, y: 0, scale_x: 1, scale_y: 1, rotation: 0 } }] }
}
function detail(): SessionDetail {
  return { id: SESSION, title: model.title, revision: model.revision, history_seq: model.history.length,
    original_asset_id: 'original', current_asset_id: current().id, created_at: original.created_at, updated_at: new Date().toISOString(),
    document: documentFor(current()), previous_document: model.cursor ? documentFor(model.assets.find(a => a.id === model.sequence[model.cursor - 1])!) : null,
    assets: model.assets, can_undo: model.cursor > 0, can_redo: model.cursor < model.sequence.length - 1 }
}
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
const unsupported = () => json({ detail: '演示仅支持本地调色、裁剪、翻转和猫咪圆润预置效果。此操作需完整服务，原图未修改。' }, 422)
function run(tool: string, assets: Asset[] = []): Run {
  return { id: `demo-run-${Date.now()}`, tool, status: 'succeeded', progress: 1, stage: '浏览器演示操作完成', error: null, prompt: null, candidates: assets, result: {} }
}
async function commit(asset: Asset, tool: string, params: Record<string, unknown>) {
  model.assets.push(asset)
  model.sequence = [...model.sequence.slice(0, model.cursor + 1), asset.id]
  model.cursor++; model.revision++
  model.history.push({ seq: model.history.length + 1, action: tool, params, result: { asset_id: asset.id, demo: true }, created_at: new Date().toISOString() })
  persist()
  return { session: detail(), run: run(tool, [asset]) }
}
async function pixels(tool: string, params: Record<string, unknown>) {
  const asset = current()
  const image = new Image(); image.src = asset.url; await image.decode()
  const canvas = document.createElement('canvas'); canvas.width = image.naturalWidth; canvas.height = image.naturalHeight
  const context = canvas.getContext('2d')!
  if (tool === 'flip_layer') { context.translate(params.direction === 'horizontal' ? canvas.width : 0, params.direction === 'vertical' ? canvas.height : 0); context.scale(params.direction === 'horizontal' ? -1 : 1, params.direction === 'vertical' ? -1 : 1) }
  context.drawImage(image, 0, 0)
  if (tool === 'adjust_image') {
    const values = Object.fromEntries(Object.entries(params).filter(([, value]) => typeof value === 'number')) as Record<string, number>
    for (const key of ['brightness','contrast','saturation','highlights','shadows','temperature','tint','vibrance','vignette','sharpness','clarity']) {
      if (values[key] !== undefined && (!Number.isFinite(values[key]) || Math.abs(values[key]) > 1)) throw new Error('滑杆值超出范围')
    }
    const data = context.getImageData(0, 0, canvas.width, canvas.height)
    const preview = toAdjustPreview(values)
    if (preview) makeAdjustFilter(preview)(data)
    context.putImageData(data, 0, 0)
    // The existing UI says these appear on apply. Keep them local and explicit.
    for (const [key, radius] of [['sharpness', 1], ['clarity', 12]] as const) {
      const strength = values[key] ?? 0
      if (!strength) continue
      const blur = document.createElement('canvas'); blur.width = canvas.width; blur.height = canvas.height
      const ctx = blur.getContext('2d')!; if (!('filter' in ctx)) throw new Error('浏览器不支持该调色项')
      ctx.filter = `blur(${radius}px)`; ctx.drawImage(canvas, 0, 0)
      const low = ctx.getImageData(0, 0, canvas.width, canvas.height).data
      const high = context.getImageData(0, 0, canvas.width, canvas.height)
      for (let index = 0; index < high.data.length; index++) if (index % 4 !== 3) high.data[index] += (high.data[index] - low[index]) * strength
      context.putImageData(high, 0, 0)
    }
  }
  let output = canvas
  if (tool === 'crop_canvas') {
    const rect = params.rect as { x: number; y: number; width: number; height: number }
    if (!rect || Object.values(rect).some(v => !Number.isFinite(v) || v < 0 || v > 1) || !rect.width || !rect.height) throw new Error('裁剪区域无效')
    output = document.createElement('canvas'); output.width = Math.max(1, Math.round(rect.width * canvas.width)); output.height = Math.max(1, Math.round(rect.height * canvas.height))
    output.getContext('2d')!.drawImage(canvas, rect.x * canvas.width, rect.y * canvas.height, output.width, output.height, 0, 0, output.width, output.height)
  }
  const blob = await new Promise<Blob>((resolve, reject) => output.toBlob(b => b ? resolve(b) : reject(new Error('图片生成失败')), 'image/png'))
  const id = `local-${crypto.randomUUID()}`; await storeBlob(id, blob)
  return commit({ ...original, id, kind: 'generated', source: 'tool', width: output.width, height: output.height, size_bytes: blob.size, url: URL.createObjectURL(blob) }, tool, params)
}

window.fetch = async (input, init = {}) => {
  const url = new URL(typeof input === 'string' ? input : input instanceof URL ? input.href : input.url, location.origin)
  if (url.origin !== location.origin || !url.pathname.startsWith('/api/')) return nativeFetch(input, init)
  await ready
  const path = url.pathname.slice(4), method = init.method ?? 'GET'
  const body = typeof init.body === 'string' ? JSON.parse(init.body) : {}
  try {
    if (path.startsWith('/auth/')) return json({ id: 'demo', username: '体验用户' })
    if (path === '/assets/library') return json([{ session_id: SESSION, title: model.title, updated_at: new Date().toISOString(), cover: current(), assets: model.assets }])
    if (path === '/assets') {
      if (method === 'POST') {
        const file = init.body instanceof FormData ? init.body.get('file') : null
        if (!(file instanceof File)) return unsupported()
        const hash = [...new Uint8Array(await crypto.subtle.digest('SHA-256', await file.arrayBuffer()))].map(v => v.toString(16).padStart(2, '0')).join('')
        if (hash !== 'dab6670f65a71a69e08e02119141ee6fd89433acb22c8a781fab47ecb57e29be') return json({ detail: '本演示仅使用指定猫图，不能将预置结果套用到其他照片。' }, 422)
      }
      return json(method === 'POST' ? original : model.assets)
    }
    if (path === '/sessions') return json(method === 'POST' ? detail() : [detail()])
    const match = path.match(/^\/sessions\/([^/]+)(?:\/(.*))?$/)
    if (!match || match[1] !== SESSION) return unsupported()
    const action = match[2]
    if (!action) { if (method === 'PATCH') { if (body.title) model.title = String(body.title).slice(0, 100); if (body.current_asset_id) { const index = model.sequence.indexOf(body.current_asset_id); if (index >= 0) model.cursor = index }; persist() }; return json(detail()) }
    if (action === 'history') return json(model.history)
    if (action.startsWith('selection')) return method === 'POST' && !action.endsWith('prepare') ? unsupported() : json(null)
    if (action === 'undo' || action === 'redo') { model.cursor = Math.max(0, Math.min(model.sequence.length - 1, model.cursor + (action === 'undo' ? -1 : 1))); model.revision++; persist(); return json(detail()) }
    if (action === 'tools') {
      if (body.params.expected_revision !== undefined && body.params.expected_revision !== model.revision) return json({ detail: '版本已变化，请重新预览后应用' }, 409)
      if (['adjust_image','flip_layer','crop_canvas'].includes(body.tool)) return json(await pixels(body.tool, body.params))
      return unsupported()
    }
    if (action === 'messages' && method === 'GET') return json(model.turns)
    if (action === 'messages') {
      if (!/圆润|可爱|胖/.test(body.text)) return json({ detail: '试试“将猫变得圆润可爱”。演示不对任意指令实时生成图片。' }, 422)
      if (current().width !== 768 || current().height !== 1024) return json({ detail: '圆润预置结果对应完整原图，请先撤销裁剪，再体验。' }, 422)
      const turn: Turn = { id: `turn-${Date.now()}`, revision: model.revision, goal: body.text,
        reply: '将展示这张猫的圆润预置生成结果，并保留原图。该结果基于原图，不会继承当前调色；确认后点击执行计划。',
        status: 'queued', error: null, created_at: new Date().toISOString(),
        steps: [{ id: 'step', tool: 'replace_region', label: '猫咪圆润 · 预置结果', depends_on: [], run_id: null, status: 'waiting' }] }
      model.turns.push(turn); persist(); return json(turn)
    }
    const turnMatch = action.match(/^messages\/([^/]+)\/(confirm|cancel|retry)$/)
    if (turnMatch) {
      const turn = model.turns.find(t => t.id === turnMatch[1]); if (!turn) return unsupported()
      if (turnMatch[2] === 'cancel') { turn.status = 'canceled'; turn.steps[0].status = 'canceled' }
      else {
        if (turn.status !== 'queued' || turn.revision !== model.revision) return json({ detail: '计划已执行或画布已变化，请重新发送指令。' }, 409)
        await commit({ ...original, id: `rounded-${crypto.randomUUID()}`, kind: 'generated', source: 'generate', url: '/demo/cat-rounded.png', size_bytes: 1625308 }, 'replace_region', { demo_fixture: true })
        turn.status = 'succeeded'; turn.steps[0].status = 'succeeded'
      }
      persist(); return json(turn)
    }
    if (action === 'exports') {
      const selected = body.asset_ids?.length ? model.assets.filter(a => body.asset_ids.includes(a.id)) : [current()]
      const entries = await Promise.all(selected.map(async (asset, index) => ({ name: `${index + 1}-${asset.kind}.png`, data: new Uint8Array(await (blobs.get(asset.id) ?? await (await nativeFetch(asset.url)).blob()).arrayBuffer()) })))
      entries.push({ name: 'manifest.json', data: new TextEncoder().encode(JSON.stringify({ demo: true, session_id: SESSION, current_asset_id: current().id, assets: selected.map(({ id, width, height, kind }) => ({ id, width, height, kind })) }, null, 2)) })
      return new Response(zip(entries), { headers: { 'Content-Type': 'application/zip', 'Content-Disposition': 'attachment; filename="PhotoAI-demo.zip"' } })
    }
    return unsupported()
  } catch (error) { return json({ detail: error instanceof Error ? error.message : '演示操作失败，原图已保留' }, 422) }
}

// Run snapshots in this adapter are terminal; never open a network SSE connection.
window.EventSource = class extends EventTarget {
  static CONNECTING = 0; static OPEN = 1; static CLOSED = 2
  CONNECTING = 0; OPEN = 1; CLOSED = 2; readyState = 2; url = ''; withCredentials = false
  onopen = null; onerror = null; onmessage = null
  close() {}
} as unknown as typeof EventSource

window.addEventListener('message', async event => {
  if (event.origin !== location.origin || event.source !== parent || event.data?.type !== 'photoai:demo-save') return
  try {
    await ready
    const preview = useEditorUi.getState().adjustPreview
    const advice = readAdviceDraft(SESSION)
    if (Object.values(preview ?? {}).some(value => value !== 0) || advice && !advice.applied && advice.revision === model.revision && Object.values(advice.values).some(value => value !== 0)) throw new Error('请先应用或取消调色预览，再保存当前版本。')
    const asset = current(), blob = blobs.get(asset.id) ?? await (await nativeFetch(asset.url)).blob()
    const dataUrl = await new Promise<string>((resolve, reject) => { const reader = new FileReader(); reader.onload = () => resolve(String(reader.result)); reader.onerror = () => reject(reader.error); reader.readAsDataURL(blob) })
    parent.postMessage({ type: 'photoai:demo-saved', dataUrl, width: asset.width, height: asset.height }, location.origin)
  } catch { parent.postMessage({ type: 'photoai:demo-save-error' }, location.origin) }
})

// Uncompressed ZIP keeps selected image bytes unchanged, without another dependency.
function zip(entries: { name: string; data: Uint8Array }[]): Blob {
  const encoder = new TextEncoder(), chunks: Uint8Array[] = [], directory: Uint8Array[] = []
  let offset = 0
  const u16 = (view: DataView, at: number, value: number) => view.setUint16(at, value, true)
  const u32 = (view: DataView, at: number, value: number) => view.setUint32(at, value, true)
  for (const entry of entries) {
    let crc = 0xffffffff
    for (const byte of entry.data) { crc ^= byte; for (let i = 0; i < 8; i++) crc = (crc >>> 1) ^ ((crc & 1) ? 0xedb88320 : 0) }
    crc = (crc ^ 0xffffffff) >>> 0
    const name = encoder.encode(entry.name), local = new Uint8Array(30 + name.length), lv = new DataView(local.buffer)
    u32(lv, 0, 0x04034b50); u16(lv, 4, 20); u32(lv, 14, crc); u32(lv, 18, entry.data.length); u32(lv, 22, entry.data.length); u16(lv, 26, name.length); local.set(name, 30)
    const central = new Uint8Array(46 + name.length), cv = new DataView(central.buffer)
    u32(cv, 0, 0x02014b50); u16(cv, 4, 20); u16(cv, 6, 20); u32(cv, 16, crc); u32(cv, 20, entry.data.length); u32(cv, 24, entry.data.length); u16(cv, 28, name.length); u32(cv, 42, offset); central.set(name, 46)
    chunks.push(local, entry.data); directory.push(central); offset += local.length + entry.data.length
  }
  const size = directory.reduce((sum, item) => sum + item.length, 0), end = new Uint8Array(22), view = new DataView(end.buffer)
  u32(view, 0, 0x06054b50); u16(view, 8, entries.length); u16(view, 10, entries.length); u32(view, 12, size); u32(view, 16, offset)
  return new Blob([...chunks, ...directory, end] as BlobPart[], { type: 'application/zip' })
}
