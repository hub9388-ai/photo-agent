// Browser contract check against the real-mode frontend. API/editor are controlled
// fixtures: no user media, credentials, model calls or actual image edits.
const assert = require('node:assert/strict')
const fs = require('node:fs/promises')
const path = require('node:path')
const crypto = require('node:crypto')
const { chromium } = require('../frontend/node_modules/playwright')
const root = path.resolve(__dirname, '..')
const base = process.env.HANDOFF_CHECK_URL || 'http://127.0.0.1:3000'
const mediaId = 'media_navigation_check'
const jobId = 'job_navigation_check'

async function main() {
  const original = await fs.readFile(path.join(root, 'frontend/public/demo/cat-original.png'))
  const override = await fs.readFile(path.join(root, 'frontend/public/demo/cat-rounded.png'))
  const advice = { policy_version: 'post-sliders-v1', source_job_id: jobId, source_media_id: mediaId,
    source_result_id: 'result_navigation_check', params: { contrast: .08, highlights: -.15, shadows: .1 }, converted: [], skipped: [] }
  const browser = await chromium.launch({ channel: 'chrome' })
  try {
    const page = await browser.newPage()
    const apiRequests = []
    const errors = []
    let editorReady = true
    let sourceFails = false
    page.on('pageerror', error => errors.push(error.message))
    await page.route('**/api/**', async route => {
      const url = new URL(route.request().url())
      assert.equal(route.request().method(), 'GET', 'No writes or model submissions allowed')
      apiRequests.push(url.pathname + url.search)
      const headers = { 'Access-Control-Allow-Origin': '*' }
      if (url.pathname === `/api/jobs/${jobId}/retouch-advice`) {
        assert.equal(url.searchParams.get('media_id'), mediaId)
        return route.fulfill({ json: advice, headers })
      }
      assert.equal(url.pathname, `/api/media/${mediaId}/retouch-source`, 'Unexpected API request')
      if (sourceFails) return route.fulfill({ status: 503, body: 'Unavailable', headers })
      return route.fulfill({ body: original, contentType: 'image/png', headers: { ...headers,
        'X-Retouch-Source': 'original', 'X-Retouch-Filename': 'original.png',
        'Access-Control-Expose-Headers': 'X-Retouch-Source, X-Retouch-Filename' } })
    })
    await page.route('**/photoai-import', route => route.fulfill({ contentType: 'text/html', body: `<!doctype html><title>Controlled editor</title><script>
      window.addEventListener('message', async event => {
        if (event.data?.type !== 'photoai:import') return;
        window.importCount = (window.importCount || 0) + 1;
        const {file, advice, requestId} = event.data;
        const bytes = await file.arrayBuffer();
        const sha256 = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes))).map(b => b.toString(16).padStart(2,'0')).join('');
        window.received = {name:file.name, size:file.size, type:file.type, sha256, advice};
        parent.postMessage({type:'photoai:imported',version:1,requestId},event.origin);
      });
      window.allowReady = ${editorReady};
      setInterval(() => { if (window.allowReady) parent.postMessage({type:'photoai:ready',version:1},'*'); }, 200);
      </script>` }))
    const target = `${base}/retouch?media_id=${mediaId}&job_id=${jobId}`
    async function importPhoto(localFile) {
      await page.goto(localFile ? `${base}/retouch` : target)
      const frame = page.frameLocator('iframe[title="AI 修图编辑器"]')
      if (localFile) await page.getByLabel('选择修图照片').setInputFiles({ name: 'override.png', mimeType: 'image/png', buffer: override })
      await page.getByText('照片已导入，下方可开始编辑。完成后可在编辑器导出图片。', { exact: true }).waitFor()
      // Repeated ready notifications must never create another editing session.
      await frame.locator('html').evaluate(async () => {
        for (let i = 0; i < 3; i++) parent.postMessage({type:'photoai:ready',version:1}, '*');
        await new Promise(resolve => setTimeout(resolve, 300));
        if (window.importCount !== 1) throw new Error('Duplicate automatic import');
      })
      return frame.locator('html').evaluate(() => window.received)
    }
    const first = await importPhoto(false)
    assert.equal(first.sha256, crypto.createHash('sha256').update(original).digest('hex'))
    assert.equal(first.type, 'image/png')
    assert.deepEqual(first.advice, advice)
    assert.equal(apiRequests.length, 2)
    const second = await importPhoto(true)
    assert.equal(second.sha256, crypto.createHash('sha256').update(override).digest('hex'))
    assert.equal(second.advice, undefined, 'Local override must not inherit another photo advice')
    assert.equal(apiRequests.length, 2, 'Local override must not fetch original media or Post advice')
    // Selecting another file after import remounts the import screen automatically.
    await page.getByLabel('选择修图照片').setInputFiles({ name: 'another.png', mimeType: 'image/png', buffer: original })
    await page.getByText('照片已导入，下方可开始编辑。完成后可在编辑器导出图片。', { exact: true }).waitFor()
    assert.equal(await page.frameLocator('iframe').locator('html').evaluate(() => window.received.sha256), crypto.createHash('sha256').update(original).digest('hex'))
    assert.equal(apiRequests.length, 2)
    // No source/advice fetch before authentication signals readiness.
    editorReady = false
    await page.goto(target)
    const waitingFrame = page.frameLocator('iframe')
    await waitingFrame.locator('html').waitFor()
    assert.equal(apiRequests.length, 2)
    await waitingFrame.locator('html').evaluate(() => { window.allowReady = true })
    await page.getByText('照片已导入，下方可开始编辑。完成后可在编辑器导出图片。', { exact: true }).waitFor()
    assert.equal(apiRequests.length, 4)
    editorReady = true
    sourceFails = true
    await page.goto(target)
    await page.getByRole('status').filter({ hasText: '读取素材失败（503）' }).waitFor()
    await page.frameLocator('iframe').locator('html').evaluate(async () => {
      for (let i = 0; i < 3; i++) parent.postMessage({type:'photoai:ready',version:1}, '*');
      await new Promise(resolve => setTimeout(resolve, 300));
      if (window.importCount) throw new Error('Failed source must not be imported');
    })
    assert.equal(apiRequests.length, 6, 'Failure must not automatically retry')
    sourceFails = false
    await page.getByRole('button', { name: '重新连接', exact: true }).click()
    await page.getByText('照片已导入，下方可开始编辑。完成后可在编辑器导出图片。', { exact: true }).waitFor()
    assert.equal(apiRequests.length, 8)
    assert.deepEqual(errors, [])
    const report = { status: 'passed', scope: 'Real-mode frontend; controlled API and iframe fixtures, no real backend/model execution',
      query_ids_reach_api: true, original_file_hash_matches: true, post_advice_payload_matches: true,
      local_override_has_no_foreign_advice: true, automatic_import_once: true,
      waits_for_editor_auth: true, upload_replaces_session: true, failed_source_requires_explicit_retry: true, browser_errors: 0 }
    const out = path.join(root, '.test_artifacts/dashboard-handoff')
    await fs.mkdir(out, { recursive: true })
    await fs.writeFile(path.join(out, 'report.json'), JSON.stringify(report, null, 2))
    console.log(JSON.stringify(report, null, 2))
  } finally { await browser.close() }
}
main().catch(error => { console.error(error.message); process.exitCode = 1 })
