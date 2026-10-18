// Contract checks only; not a browser screenshot or a visual-quality evaluation.
const assert = require('node:assert/strict')
const fs = require('node:fs')
const vm = require('node:vm')
const ts = require('../frontend/node_modules/typescript')
const storage = new Map()
const context = { exports: {}, sessionStorage: {
  getItem: k => storage.get(k) ?? null,
  setItem: (k, v) => storage.set(k, v),
} }
const source = fs.readFileSync('integrations/ai-retouch-agent/frontend/src/lib/postAdvice.ts', 'utf8')
vm.runInNewContext(ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText, context)
const { parsePostAdvice, saveAdviceDraft, readAdviceDraft } = context.exports
const advice = { policy_version: 'post-sliders-v1', source_job_id: 'job_a', source_media_id: 'media_a', source_result_id: 'result_a',
  params: { shadows: -.1 }, converted: [{parameter:'Shadows2012',label:'阴影',source_value:-10,source_unit:'参考刻度',target:'shadows',value:-.1,approximate:true,clamped:false,rule:'v/100',preview:true}],
  skipped: [{parameter:'Blacks2012',reason:'没有对应规则'}] }
assert.equal(parsePostAdvice(advice).params.shadows, -.1)
for (const params of [{ brightness: -.1 }, { shadows: Infinity }, { shadows: -.1, sharpness: .1 }]) {
  assert.throws(() => parsePostAdvice({ ...advice, params }))
}
saveAdviceDraft('session_a', { advice, values: { shadows: -.08 }, revision: 1, applied: false })
assert.equal(readAdviceDraft('session_a').values.shadows, -.08)
assert.equal(readAdviceDraft('session_b'), null)
saveAdviceDraft('session_a', { advice, values: {}, revision: 1, applied: true })
assert.equal(readAdviceDraft('session_a').applied, true)
storage.set('photoai:post-advice:broken', '{')
assert.equal(readAdviceDraft('broken'), null)
console.log('PASS: advice validation, photo-session isolation, manual values, applied state, corrupt draft handling.')
