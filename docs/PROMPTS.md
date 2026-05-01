# PhotoAI 关键 Prompt 模板

本文档整理 PhotoAI 项目中最有代表性的 Prompt 类型。它不是完整聊天记录，而是展示我如何把复杂任务拆成可执行、可验证、可交给 AI 协作的小任务。

## 1. 后端盘点 Prompt

```text
你现在是我的资深全栈架构顾问 + Python 后端重构专家 + Agent 系统架构顾问。

请先不要进行任何代码修改、不要创建文件、不要重构。
当前目标只是完整理解项目目标、现有代码结构、当前进度和未来规划。

请阅读项目文件后输出：
1. 我对最终目标的理解；
2. 我对当前 14 个 Python 文件职责的理解；
3. 哪些模块可以保留，哪些需要拆分；
4. 当前代码阻碍 API 化、流式化、持久化、并行化的问题；
5. 推荐后端改造总体路线；
6. 第一阶段 MVP 任务清单；
7. 真正开始改造前需要确认的问题。
```

使用目的：避免 AI 上来直接改代码，先建立共同上下文和迁移边界。

实际产出：明确 `agent_code/` 是 legacy source of truth，形成阶段 0-8.5 的渐进式后端改造路线。

## 2. 阶段 0 回归基线 Prompt

```text
开始阶段 0：最小代码盘点与回归基线。

目标不是重复大篇幅文档盘点，而是做能指导改造的最小盘点。
请确认：
1. 旧代码真实来源路径是 agent_code/；
2. 14 个文件均可导入；
3. CLI 主流程仍可运行；
4. 四个 Agent 的实际入口函数；
5. import 依赖风险；
6. 最小回归用例。

注意：
- 不移动文件；
- 不重写函数；
- 不破坏旧 import；
- 自动化测试用 MockModelClient；
- 真实模型只做手动 smoke。
```

使用目的：让 AI 先建立安全改造基线，不把旧系统改坏。

实际产出：最小导入检查、CLI smoke、import 风险记录和 pytest 回归基线。

## 3. FastAPI 骨架 Prompt

```text
开始阶段 1：FastAPI 后端骨架。

严格边界：
- 不移动 agent_code/；
- 不重写 14 个旧文件；
- 新增 FastAPI 骨架时只做 wrapper；
- 每次改动后跑 python -m pytest；
- 真实模型调用只做手动 smoke。

请建立：
backend/app/main.py
backend/app/core/settings.py
backend/app/core/legacy_path.py
backend/app/api/health.py

要求：
1. app.main 最先调用 ensure_agent_code_on_path()；
2. /api/health 返回 200；
3. API wrapper 能 import agent_code 中关键模块；
4. 旧 CLI 仍可运行。
```

使用目的：把后端从脚本入口变成 Web API 外壳，但不破坏 legacy。

实际产出：`backend/app` FastAPI 骨架、`/api/health`、`ensure_agent_code_on_path()` 和测试配置。

## 4. API 契约 Prompt

```text
开始阶段 2：数据模型与 API 契约。

请先定义 Media、Job、Event、Result、Handoff、AgentRequest。

注意：
- AgentRequest 描述用户要做什么；
- 不包含 client、system、messages、media_items；
- AgentService 负责把 AgentRequest 转换成 legacy 参数；
- messages 在 Web MVP 阶段默认 []；
- media_items 由 MediaStore 根据 media_ids 准备。

Response Model 要和前端契约对齐：
- CreateJobResponse 对前端返回 jobId/status/eventsUrl/resultsUrl；
- JobDetailResponse 映射内部 id 为 jobId；
- AgentResultResponse 对前端使用 visibleText/structuredPayload；
- SSE data 使用 eventId，协议层 id 使用 seq。
```

使用目的：避免前端直接依赖内部 Python 对象，减少后续字段混乱。

实际产出：`schemas/response.py`、Response mapper、前端 `src/types/api.ts`，以及统一 camelCase 的 API Client。

## 5. SSE 状态机 Prompt

```text
请为前端分析页接入真实 SSE 链路。

流程：
1. uploadMedia(file)；
2. createJob({ type: "photo_review", agents: ["post", "coach"], media_ids })；
3. EventSource(eventsUrl)；
4. 按 agent 字段分流；
5. post 事件更新 PostAgent 卡片；
6. coach 事件更新 CoachAgent 卡片；
7. job 事件更新整体任务状态；
8. job completed 或 partial_completed 后调用 getJobResults。

要求：
- Post 失败不影响 Coach 成功结果展示；
- Coach 失败不影响 Post 成功结果展示；
- agent.delta 不入库；
- SSE 断开后支持重新连接；
- 页面不要因为单个事件异常崩溃。
```

使用目的：把后端事件协议映射为可视化 Agent 状态。

实际产出：分析页 EventSource 订阅、Post/Coach 分流、Agent 进度卡片、SSE 断线提示和结果恢复。

## 6. 前端页面设计 Prompt

```text
你现在是资深前端工程师 + 产品体验顾问。

请按照 Pencil 页面设计搭建 PhotoAI 前端。
不要先接后端，先做静态页面和组件拆分。

页面包括：
1. 工作台首页；
2. 分析页；
3. 素材库页；
4. 学习页；
5. 规划页；
6. 历史页。

要求：
- 不做普通聊天框；
- 摄影应用以图片预览、任务状态和结果卡片为中心；
- 多 Agent 状态必须可视化；
- 所有页面先用 mock 数据；
- 组件拆分清晰，不把页面写成一个大文件。
```

使用目的：先确定产品体验和页面结构，再接真实接口。

实际产出：工作台、分析、素材库、学习、规划、历史 6 个页面和组件化页面结构。

## 7. API Client Prompt

```text
请封装前端 API Client，但先不改页面逻辑。

要求：
- 不要在组件里直接 fetch；
- 支持 mock mode 和 real API mode；
- 后端地址集中配置；
- 封装 uploadMedia/createJob/getJob/getJobResults/listJobs/retryAgent/createHandoff/subscribeJobEvents；
- 请求体按 snake_case；
- 响应按 camelCase；
- SSE 单独封装。

验收标准：
- API Client 可单独测试；
- 页面仍可使用 mock；
- 后续接真实链路时只替换数据来源。
```

使用目的：稳定前后端边界，避免组件里散落请求逻辑。

实际产出：`src/lib/api/*` API Client、mock/real 模式切换、SSE helper 和 handoff fallback。

## 8. 历史页 Job Center Prompt

```text
请把历史页设计为整个系统的 Job Center，而不是普通浏览记录。

历史页需要：
- GET /api/jobs；
- 展示任务类型、状态、标题、缩略图、摘要；
- completed / partial_completed / failed / running / cancelled；
- loading / empty / error / demo fallback；
- 点击不同任务类型跳转不同页面：
  photo_review -> /analysis/{job_id}
  trip_planning -> /planning?job_id={job_id}
  asset_indexing -> /assets?job_id={job_id}
  coach_feedback -> /learning?job_id={job_id}

注意：
- 打开历史页不要触发模型调用；
- 只读取 Job/Result；
- running 任务重新订阅 SSE；
- partial_completed 重点展示成功和失败 Agent。
```

使用目的：让历史页成为分析、学习、规划、素材的恢复入口。

实际产出：历史页 Job Center、任务筛选、状态标签、查看跳转、失败任务重试和 demo fallback。

## 9. 素材库轻量真实化 Prompt

```text
请实现素材库页轻量真实化，不要做完整 DAM。

目标：
1. 多图上传；
2. 缩略图网格；
3. metadata / EXIF；
4. 选择素材；
5. 右侧详情；
6. 送去后期 / 送去学习 handoff；
7. A/B/C/淘汰/重复先用轻量规则或 AssetAgent 视觉评分；
8. 支持搜索和筛选；
9. Demo fallback。

要求：
- 不依赖完整 asset_indexing job 才能工作；
- /api/handoff 不可用时 fallback 到 /api/jobs；
- 上传失败、metadata 缺失、缩略图失败都要有 UI；
- 轻量规则必须明确标注，不伪装成完整 AI 筛片系统。
```

使用目的：在有限时间内展示素材管理和 Agent-to-Agent 流转。

实际产出：素材页多图上传、AssetAgent 评分、文件夹管理、筛选搜索、`asset -> post/coach` handoff。

## 10. 学习页 Practice Task Prompt

```text
请把学习页从历史反馈看板改造成练习闭环。

链路：
1. CoachAgent 在分析页返回学习反馈；
2. 学习页展示 Coach 布置的 practice_tasks；
3. 每个练习任务有“上传练习照片”按钮；
4. 上传后创建 coach_feedback job；
5. job.context 携带 practice_task_id/practice_goal/source_job_id/source_agent；
6. CoachAgent 根据练习目标复盘；
7. 学习页把结果归档到对应任务 attempts。

要求：
- 学习页打开时不要自动调用模型；
- 没有练习任务时显示空状态；
- structuredPayload 缺字段时用 visibleText 兜底；
- Coach 失败可重试或查看示例复盘；
- 支持 local recovery。
```

使用目的：体现 Agent 结果再利用和持续学习闭环。

实际产出：学习页 Practice Task、练习照片上传、`coach_feedback` job、attempt 归档和 local recovery。

## 11. 规划页 Prompt

```text
请接入规划页真实链路。

用户填写城市、日期、时段、题材、器材、预算、其他要求。
前端创建 trip_planning job，并通过 SSE 展示状态。

要求：
- PlanAgent 只能显式触发，不随照片上传默认运行；
- 其他要求和迭代优化必须作为重要约束；
- 用户指定开始/结束时间时要遵守；
- 结果要结构化为方案、时间线、机位、器材建议、天气提示、后期风格目标；
- provider 失败时降级，不伪造实时数据。
```

使用目的：让 PlanAgent 表现为可执行拍摄方案生成器，而不是景点清单。

实际产出：规划页 `trip_planning` job、SSE 状态、方案 A/B/C、时间线、机位和 provider 降级提示。

## 12. 错误态 / Fallback Prompt

```text
请为核心页面补充错误态、fallback 和 Demo 稳定性。

需要覆盖：
- 上传失败；
- 创建 job 失败；
- SSE 断开；
- Agent timeout / failed；
- partial_completed；
- result missing；
- structuredPayload 缺字段；
- provider 不可用；
- demo fallback；
- local recovery。

要求：
- 页面不能空白；
- 不暴露 API key、provider 鉴权细节；
- Demo fallback 必须明确提示；
- 一个任务失败不能拖垮整个页面。
```

使用目的：让 Demo 不依赖模型和网络始终成功。

实际产出：分析页 partial_completed、学习页 demo task、素材页 partial upload、规划页 provider fallback 和公网演示说明。

## 13. 文档生成 Prompt

```text
请帮我完善 PhotoAI 项目说明文档。

文档逻辑：
1. 先让面试官快速理解项目；
2. 再展示可运行 Demo；
3. 再解释工程化思路；
4. 最后说明 AI 工具使用和项目取舍。

要求：
- 明确真实完成度；
- 技术栈按实际使用写；
- 不把预留依赖写成核心依赖；
- 不把 demo fallback 包装成真实生产能力；
- 补充 AI 工作流和 Prompt 文档入口。
```

使用目的：形成符合笔试要求的提交材料，而不是普通 README。

实际产出：项目说明文档、`AI_WORKFLOW.md`、`PROMPTS.md`、Demo 脚本和提交清单。

## 14. Prompt 使用原则

我在项目中遵循几个 Prompt 原则：

- 先要求 AI 读代码和输出计划，再允许改代码。
- 每次任务限制边界，例如“不移动 agent_code/”“不做前端”“不接真实模型”。
- 大任务拆成阶段，每阶段有验收标准。
- 让 AI 列出文件修改清单，便于检查 diff。
- 改完必须跑类型检查、lint 或后端测试。
- 对涉及真实完成度和产品取舍的内容，必须人工复核。

## 15. 提交前一致性检查 Prompt

```text
请检查 README、项目说明文档、AI_WORKFLOW、PROMPTS、Demo 脚本之间是否存在矛盾。

重点检查：
- 技术栈是否按真实使用填写；
- 前端 API 字段命名是否统一为 camelCase；
- 请求体 snake_case 与响应 camelCase 是否说明清楚；
- 功能完成度是否把真实链路、轻量实现和后续规划区分开；
- fallback 是否明确标注为 fallback；
- 未做事项是否和后续规划一致；
- 提交材料是否明确为网页体验链接、Demo 视频、说明文档和 AI 工作流 / Prompt 文档。

要求：
1. 先列出发现的矛盾；
2. 再给出建议修改位置；
3. 不要把未完成能力包装成已完成。
```

使用目的：提交前做文档一致性自检，避免评审读到字段命名、技术栈或完成度矛盾。

实际产出：统一说明文档和 Prompt 文档中的 `jobId/eventsUrl/eventId` 等字段命名，补充公网 tunnel 边界说明。

## 16. 防止过度工程化 Prompt

```text
请检查当前方案是否引入了笔试阶段不必要的复杂度。

重点识别：
- 登录、支付、多用户权限；
- Redis / Celery / PostgreSQL / 对象存储；
- 完整 DAM 系统；
- 生产级图片相似度去重；
- 完整地图路线引擎；
- 复杂 MCP 编排协议；
- 与核心 Demo 无关的大型重构。

要求：
1. 如果某项能力不是本次笔试必须，移入后续规划；
2. 保留能证明核心能力的 Web MVP；
3. 不牺牲上传、Job、SSE、Result、History 的核心闭环。
```

使用目的：控制项目边界，让有限时间集中在可演示、可验证、信息密度高的能力上。

实际产出：阶段 10 生产基础设施后置，素材库先做轻量真实化，PlanAgent 条件触发，Skills/MCP 后置。

## 17. Agent Runtime Prompt 设计

本节记录 PhotoAI 中各 Agent 的运行时提示词设计思路。这里不直接贴完整生产 prompt、few-shot 或内部规则，而是说明每个 Agent 的目标、输入、约束和输出结构，展示我如何把摄影任务转成可控的 AI 工作流。

这样处理有两个原因：

- 运行时 prompt 仍会持续迭代，完整贴出容易让文档变得冗长。
- 提交材料更需要体现设计方法、输出约束和工程化思路，而不是暴露所有内部实现细节。

### 17.1 PostAgent：后期辅助 Prompt 摘要

目标：根据照片和用户审美偏好，输出可执行但不绝对化的后期方向。

核心输入：

- 用户上传图片或预览图；
- 用户偏好，例如“电影感”“INS 风格”“保留天空细节”；
- EXIF / metadata；
- 历史 profile 或 skills knowledge；
- 上游 handoff context。

约束：

- 不把参数写成唯一正确答案，而是给区间和调参含义；
- 用户已经指定风格时，只围绕该风格收敛，不罗列所有可能风格；
- 高光、阴影、色温、对比度等参数要解释“调什么、调多少、为什么”；
- 对不确定内容标注为建议，不伪装成 RAW 精确诊断。

精简模板：

```text
你是摄影后期辅助 Agent。
请根据照片内容、EXIF 和用户偏好，输出后期建议。

用户偏好：{user_preference}
素材信息：{media_metadata}
上下文：{handoff_context}

要求：
1. 先判断主要问题；
2. 如果用户指定风格，只给该风格方向；
3. 参数给参考区间，不给绝对值；
4. 每个参数说明含义；
5. 输出结构化 payload，便于前端渲染。
```

建议输出结构：

```json
{
  "summary": "一句话结论",
  "main_issues": ["问题 1", "问题 2"],
  "style_directions": ["围绕用户偏好的后期风格方向"],
  "adjustments": {
    "exposure": "-0.4 EV ~ -0.2 EV",
    "highlights": "-50 ~ -25",
    "shadows": "0 ~ +15"
  },
  "source_note": "置信度或限制说明"
}
```

### 17.2 CoachAgent：学习反馈 Prompt 摘要

目标：把照片点评转化为用户能理解、能练习、能追踪的摄影学习反馈。

核心输入：

- 当前照片；
- 用户目标；
- 上一次练习任务或 `context.practice_task_id`；
- Coach 历史结果；
- PostAgent 或 AssetAgent 传来的问题点。

约束：

- 学习反馈要简洁，不输出大段散文；
- 优点、问题和下次怎么拍要分开；
- 如果是练习任务复盘，要判断是否完成目标、哪里进步、下一步怎么练；
- 尽量沉淀 `practice_tasks`，供学习页归档。

精简模板：

```text
你是摄影学习教练 Agent。
请从学习角度点评照片，并给出下一步练习。

练习目标：{practice_goal}
用户诉求：{user_text}
上下文：{context}

要求：
1. 反馈简洁明了；
2. 输出优点、可改进点、下次怎么拍；
3. 如有练习目标，判断完成情况；
4. 生成可归档的 practice_tasks；
5. 不输出空泛鼓励。
```

建议输出结构：

```json
{
  "summary": "一句话学习反馈",
  "strengths": ["优点 1", "优点 2"],
  "improvements": ["改进点 1", "改进点 2"],
  "next_exercise": ["下一次练习建议"],
  "practice_tasks": [
    {
      "title": "练习题目",
      "goal": "练习目标",
      "related_issue": "对应问题"
    }
  ],
  "practice_review": {
    "completed": true,
    "progress": "哪里进步",
    "next_steps": ["下一步"]
  }
}
```

### 17.3 PlanAgent：拍摄规划 Prompt 摘要

目标：把用户的城市、日期、时段、题材、器材和额外要求转成可执行拍摄方案，而不是景点清单。

核心输入：

- 城市 / 地点；
- 日期 / 时间范围；
- 题材 / 器材 / 预算；
- 用户写在“其他要求”和“迭代优化”里的硬约束；
- 地图、天气、日出日落等 provider 结果；
- 来自分析页的风格目标。

约束：

- 用户明确写出的开始/结束时间必须优先遵守；
- “其他要求”和“迭代优化”不是备注，而是硬约束；
- provider 失败时说明降级，不伪造实时天气或地点数据；
- 输出要包含时间线、具体机位、光线、拍法、午饭/休息等执行节点；
- 规划结果要像执行表，而不是旅游推荐。

精简模板：

```text
你是拍摄规划 Agent。
请把用户需求转成 2-3 套可执行拍摄方案。

表单信息：{planning_form}
用户硬约束：{requirements}
provider 数据：{provider_context}
风格目标：{style_handoff}

要求：
1. 严格遵守用户指定时间范围；
2. 机位必须具体；
3. 标注光线、站位和拍法；
4. 若天气/地点不可用，明确说明降级；
5. 输出结构化方案，便于前端渲染。
```

建议输出结构：

```json
{
  "summary": "规划总览",
  "provider_note": "数据来源和降级说明",
  "plans": [
    {
      "title": "方案 A",
      "timeline": [
        {
          "time": "09:00",
          "title": "具体机位",
          "position": "站位说明",
          "lighting": "光线判断",
          "method": "拍法建议"
        }
      ],
      "gear_advice": "器材建议",
      "weather_note": "天气与光线提醒",
      "style_handoff": "后期风格目标"
    }
  ]
}
```

### 17.4 AssetAgent：素材管理 Prompt 摘要

目标：对上传素材进行质量评分、分档、标签、问题识别和 handoff 建议。

核心输入：

- 多张照片或预览图；
- metadata / EXIF；
- 视觉质量评分结果；
- 用户选择的文件夹或项目上下文；
- 上游导入/筛选任务信息。

约束：

- A/B/C/淘汰/重复要说明原因；
- 重复判断必须说明依据和置信度，不自动删除；
- 没有 EXIF 时不能直接判定照片差，只能说明 metadata 缺失；
- 可建议 `asset -> post` 或 `asset -> coach`，但不替用户自动执行删除。

精简模板：

```text
你是素材管理 Agent。
请对一组摄影素材做轻量筛选、评分和归档建议。

素材列表：{media_items}
项目上下文：{project_context}

要求：
1. 给每张素材 grade 和 score；
2. 给出标签、问题和筛选理由；
3. 重复组必须说明相似依据；
4. 不自动删除素材；
5. 输出可用于 handoff 的上下文。
```

建议输出结构：

```json
{
  "assets": [
    {
      "media_id": "media_xxx",
      "grade": "A",
      "score": 88,
      "tags": ["曝光准确", "主体明确"],
      "issues": [],
      "ai_reasons": ["适合后期精修"],
      "handoff_targets": ["post"]
    }
  ],
  "duplicate_groups": [
    {
      "group_id": "dup_001",
      "media_ids": ["media_a", "media_b"],
      "confidence": 0.87,
      "reason": "构图和主体高度相似"
    }
  ]
}
```
