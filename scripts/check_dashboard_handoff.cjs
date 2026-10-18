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
      return route.fulfill({ body: original, contentType: 'image/png', headers: { ...headers,
        'X-Retouch-Source': 'original', 'X-Retouch-Filename': 'original.png',
        'Access-Control-Expose-Headers': 'X-Retouch-Source, X-Retouch-Filename' } })
    })
    await page.route('**/photoai-import', route => route.fulfill({ contentType: 'text/html', body: `<!doctype html><title>Controlled editor</title><script>
      window.addEventListener('message', async event => {
        if (event.data?.type !== 'photoai:import') return;
        const {file, advice, requestId} = event.data;
        const bytes = await file.arrayBuffer();
        const sha256 = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes))).map(b => b.toString(16).padStart(2,'0')).join('');
        window.received = {name:file.name, size:file.size, type:file.type, sha256, advice};
        parent.postMessage({type:'photoai:imported',version:1,requestId},event.origin);
      });
      setInterval(() => parent.postMessage({type:'photoai:ready',version:1},'*'), 200);
      </script>` }))
    const target = `${base}/retouch?media_id=${mediaId}&job_id=${jobId}`
    async function importPhoto(localFile) {
      await page.goto(target)
      const frame = page.frameLocator('iframe[title="AI 修图编辑器"]')
      if (localFile) await page.getByLabel('选择修图照片').setInputFiles({ name: 'override.png', mimeType: 'image/png', buffer: override })
      await page.getByRole('button', { name: localFile ? '发送所选照片' : '发送素材库照片', exact: true }).click()
      await page.getByText('照片已导入，下方可开始编辑。完成后可在编辑器导出图片。', { exact: true }).waitFor()
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
    assert.deepEqual(errors, [])
    const report = { status: 'passed', scope: 'Real-mode frontend; controlled API and iframe fixtures, no real backend/model execution',
      query_ids_reach_api: true, original_file_hash_matches: true, post_advice_payload_matches: true,
      local_override_has_no_foreign_advice: true, browser_errors: 0 }
    const out = path.join(root, '.test_artifacts/dashboard-handoff')
    await fs.mkdir(out, { recursive: true })
    await fs.writeFile(path.join(out, 'report.json'), JSON.stringify(report, null, 2))
    console.log(JSON.stringify(report, null, 2))
  } finally { await browser.close() }
}
main().catch(error => { console.error(error.message); process.exitCode = 1 })
