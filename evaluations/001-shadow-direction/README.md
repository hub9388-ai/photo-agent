# 评测案例 001：工具成功执行，阴影方向却反了

这是摄影 Multi-Agent 项目的第一条可重复评测案例，用于学习、故障复盘和面试准备。先读本页，再看 `review.md`，最后运行评测。

**当前状态：历史错误已固化，离线判定器已建立；生产转换逻辑尚未完成修复验收。**

## 1. 这个案例回答什么问题

用户希望两只猫的照片呈现“忧郁、沉闷”的风格。Post 给出阴影 -10 等摄影软件建议，但修图助手实际调用 `adjust_image(shadows=+0.12)`，并把没有对应工具项的黑色色阶、去朦胧临时替换为亮度/对比度、清晰度/锐化。任务在数据库显示 succeeded。

我们评测的是：**工具选择和参数是否遵守约定，而非请求是否返回成功。** 此处约定：已支持参数保留方向；不支持项明确跳过，不擅自替代。涉及歧义时先澄清也是合理产品策略，但需要另建用例，本条只覆盖“一次执行受支持项、跳过不支持项”。

这是一条失败案例、一次历史执行。5个失败检查不等于5次失败任务；不能由此报告成功率提升，也不能称为完整 Benchmark。

## 2. 文件导航

| 文件 | 用途 |
| --- | --- |
| `case.json` | 输入、明确的评测约定和不覆盖的范围 |
| `historical_trace.json` | 真实执行字段转录及源任务定位信息 |
| `evaluate.py` | 纯 Python 规则判定器，不连接数据库或模型 |
| `fixtures/synthetic_pass.json` | **人工构造**的判定器正向样例，绝非真实修复结果 |
| `test_evaluate.py` | 验证判定器能识别反向参数、伪解释、重复调用、非法参数等 |
| `reports/` | 本地运行报告，带输入和判定器 SHA256，可删除后重建 |
| `review.md` | 问题分析、证据、方案比较、局限和下一步 |
| `interview.md` | 产品经理与应用开发两种讲述方式、常见追问 |

完整历史审计见 [原审计报告](../../docs/retouch-adjust-audit-2026-10-18.md)。本目录不复制照片、凭据或上游项目源码，无需 Docker、独立修图环境或 API 余额即可重放。

## 3. 运行方式（Windows PowerShell）

在项目根目录运行，使用 Python 3.10+，无额外依赖：

```powershell
python -m unittest discover -s evaluations/001-shadow-direction -p test_evaluate.py -v
```

这是判定器自身检查，应全部通过。然后重放历史失败：

```powershell
python evaluations/001-shadow-direction/evaluate.py --output evaluations/001-shadow-direction/reports/historical-result.json
$LASTEXITCODE
```

**历史重放预期返回退出码1**，报告应为：

```json
{
  "tool_execution_status": "succeeded",
  "semantic_contract_passed": false,
  "failed_checks": [
    "direction.shadows",
    "no_substitution.brightness",
    "no_substitution.sharpness",
    "unsupported.Blacks2012",
    "unsupported.Dehaze"
  ]
}
```

这表示判定器成功抓到历史错误，不是脚本崩溃。退出码0表示本案例约定通过；退出码2表示输入读取或格式错误。

运行人工样例：

```powershell
python evaluations/001-shadow-direction/evaluate.py --trace evaluations/001-shadow-direction/fixtures/synthetic_pass.json --output evaluations/001-shadow-direction/reports/synthetic-result.json
```

预期退出码0，但 `trace_kind=synthetic_judge_test_only`、`tool_execution_status=not_executed`。不能把它写成“修复后的 Agent 验收通过”。

## 4. 判定标准

1. 恰好一次 `adjust_image`，参数对象有效，数值有限且在工具范围内，目标为默认/base图层。
2. 高光、阴影、饱和度、自然饱和度保持负向，对比度、清晰度保持正向；缺失或零值不算执行了方向建议。
3. 没有获得替代授权，brightness、sharpness、temperature、tint、vignette必须缺省或为零。
4. 黑色色阶、去朦胧在结构化记录中标记 skipped，并给出非空原因。

检查3与4相互补充：嘴上说“跳过”，却实际压暗/锐化，仍然失败。程序目前只检查原因是否存在，不判断解释的专业质量；结构化标记也需要与真实输出核对，不能随意手工标成 skipped。

规则只检查方向、范围和边界，不定义数值幅度的唯一正确答案。人工样例中的 -0.05 等数值仅服务于规则测试，不能作为推荐调色参数。

## 5. 如何用于后续改造与 EvalScope 学习

当前是**离线执行记录重放**：固定输入与历史记录，确定性判断。它不会运行当前 Agent，所以不能检测当前模型是否改变行为。

下一轮修复后，保留原失败记录；另存真实新规划记录（最好先只规划、不执行图片工具），按同样格式提取 `tool_calls`、来源与不支持项处理说明，再运行 `--trace`。真实记录中的 unsupported_handling 必须来自实际说明/结构化输出；没有说明就保留缺失，让检查失败。最终执行与图片效果还要单独验收。

EvalScope 接入尚未实现。未来可以把 `case.json` 作为样本、Agent 适配层负责采集真实计划、这里的规则作为自定义判定逻辑。届时再核对所安装版本的接口，不在本案例中增加框架依赖。规则判定也不需要先引入 LLM-as-a-Judge。

## 6. 证据与复现范围

报告保存 case、trace、evaluator 三个 SHA256，方便确认输入与规则是否变化；文件字段转录可追溯至审计中的原任务 ID，但不等于密码学验证过的数据库原始导出。运行报告由脚本生成，不手工修改。

本例不依赖上游代码，因此上游图像算法变更不会自动反映到判定器中。若工具参数正负含义、支持项或产品策略变化，必须复核并升级 case 版本。评价全图质量需要另行准备原图、结果图和人工标准。
