// Offline regression of the actual analysis mapper. No model/API requests.
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const assert = require('node:assert/strict')
const ts = require('../frontend/node_modules/typescript')
const source = fs.readFileSync(path.join(__dirname, '../frontend/src/components/analysis/AnalysisWorkspace.tsx'), 'utf8')
const pure = source.slice(source.indexOf('function toStringList('), source.indexOf('function compactFeedbackItem('))
const js = ts.transpileModule(pure, {compilerOptions: {target: ts.ScriptTarget.ES2020}}).outputText
const context = vm.createContext({})
vm.runInContext(js, context)
const payload = {
  summary: 'Cat behind glass', visibleText: 'Preserve fur and reduce glass highlights.',
  structuredPayload: {xmp_params: {Exposure2012: 0.2, Highlights2012: -40, Shadows2012: 40, Vibrance: -3}},
  status: 'succeeded',
}
context.result = payload
const withStyle = vm.runInContext('mapPostResult(result, "ins")', context)
const withoutStyle = vm.runInContext('mapPostResult(result, "")', context)
const params = withStyle.suggestions.at(-1).items
assert.deepEqual(Array.from(params), Array.from(withoutStyle.suggestions.at(-1).items))
assert.ok(params[0].includes('+0.2 EV'))
assert.ok(params[1].includes('-40'))
assert.ok(params[3].includes('-3'))
assert.ok(params.every(item => !item.includes('~')))
assert.equal(withStyle.originalText, payload.visibleText)
assert.ok(!withStyle.suggestions.some(section => section.items.includes(payload.visibleText)))
context.result = {...payload, structuredPayload: {style_directions: ['Preserve glass reflections gently.']}}
assert.equal(vm.runInContext('mapPostResult(result, "ins").suggestions[0].items[0]', context), 'Preserve glass reflections gently.')
context.result = {...payload, structuredPayload: {
  xmp_params: {Shadows2012: -10, Vibrance: -10, Exposure2012: 0.25},
  adjustments: ['● 阴影：小幅下压', '● 构图：裁掉右侧干扰'],
  source_note: 'Preview analysis only.',
}}
const negative = vm.runInContext('mapPostResult(result, "dark")', context)
assert.equal(negative.parameters[0].value, '-10')
assert.equal(negative.parameters[0].effect, '压暗暗部')
assert.equal(negative.parameters[1].effect, '降低自然饱和度')
assert.equal(negative.parameters[2].value, '+0.25 EV')
assert.ok(!negative.suggestions.at(-1).items[0].includes('提亮'))
assert.ok(negative.suggestions.find(section => section.category === '调整建议').items.includes('构图：裁掉右侧干扰'))
assert.equal(negative.originalText, payload.visibleText)
assert.equal(negative.sourceNote, 'Preview analysis only.')
const reportSource = source.slice(source.indexOf('function markdownList('), source.indexOf('function downloadTextFile('))
vm.runInContext(ts.transpileModule(reportSource, {compilerOptions: {target: ts.ScriptTarget.ES2020}}).outputText, context)
context.post = negative
const report = vm.runInContext('buildAnalysisReport({jobId:"test",media:null,preference:"dark",postResult:post,coachResult:{sections:[]},events:[]})', context)
assert.ok(report.includes(payload.visibleText))
assert.ok(report.includes('构图：裁掉右侧干扰'))
const coachSource = source.slice(source.indexOf('function compactFeedbackItem('), source.indexOf('function statusLabel('))
vm.runInContext(ts.transpileModule(coachSource, {compilerOptions: {target: ts.ScriptTarget.ES2020}}).outputText, context)
const fullImprovement = '裁切太满，建议退半步把完整头型收进来，留一点呼吸空间。还要保留胡须边缘，不能省略这条补充建议。'
context.coachInput = {status:'succeeded', visibleText:'Complete coach transcript.', structuredPayload:{
  improvements:[fullImprovement, 'second', 'third', 'fourth'],
  next_exercise:{title:'完整头型练习',scene:'窗边',requirements:['眼睛对焦','保留耳尖'],acceptance:['胡须不被切断']},
}}
const coach = vm.runInContext('mapCoachResult(coachInput)', context)
assert.equal(coach.sections[0].items[0], fullImprovement)
assert.equal(coach.sections[0].items.length, 4)
assert.equal(coach.practiceTask.requirements.length, 2)
assert.equal(coach.practiceTask.acceptance[0], '胡须不被切断')
assert.equal(coach.originalText, 'Complete coach transcript.')
context.coach = coach
const fullReport = vm.runInContext('buildAnalysisReport({jobId:"test",media:null,preference:"test",postResult:post,coachResult:coach,events:[]})', context)
assert.ok(fullReport.includes(fullImprovement))
assert.ok(fullReport.includes('胡须不被切断'))
assert.ok(fullReport.includes('Complete coach transcript.'))
console.log('PASS: original values/directions preserved; concise display; full actions and original text retained in export.')
