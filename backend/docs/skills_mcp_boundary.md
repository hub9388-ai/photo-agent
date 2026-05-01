# Stage 8.5 Skills / MCP Boundary

## 目标

阶段 8.5 不正式接入 MCP，也不新建独立 `SkillRegistry`。本阶段只确认边界：保留 legacy 已有的本地 Skills 知识加载能力，并确保 Skills 缺失或读取失败不会破坏 post / coach / plan / asset 主链路。

## 当前策略

- 不移动 `agent_code/`。
- 不重写 legacy skills loading。
- 不新增 MCP Server。
- 不新增外部摄影知识 MCP 资源。
- 不让前端直接调用 Skills 或 MCP 工具。
- 前端仍只调用后端 API，例如 `/api/jobs`、`/api/agents/plan/run`、`/api/handoff`。
- PostAgentService、CoachAgentService、PlanAgentService 继续调用 legacy 中的 skills loader。

## 降级规则

legacy skills loader 正常返回文本时，wrapper 将该文本传入旧 prompt 构造函数。

legacy skills loader 返回空字符串时，wrapper 继续运行 Agent，并在结果 payload 中写入：

- `legacy_skills_status: "missing"`
- `warnings` 中追加“未检测到本地 Skills 知识，已按无额外 Skills 知识降级运行。”

legacy skills loader 抛出异常时，wrapper 继续运行 Agent，并在结果 payload 中写入：

- `legacy_skills_status: "failed"`
- `warnings` 中追加“本地 Skills 知识加载失败，已按无额外 Skills 知识降级运行。”

这类 warning 是产品可见的轻量提示，不应包含本地路径、API Key、token 或 MCP 连接细节。

## 后续升级方向

等 post + coach、asset 后台化、plan 条件触发都稳定后，再评估：

- 将本地 Skills 文件整理为正式 SkillRegistry。
- 为后期、学习、规划、素材管理分别定义 Skill 接口。
- 建立自建摄影课程库或知识库。
- 再评估是否通过 MCP Server 暴露摄影知识、素材检索或拍摄规划工具。

在此之前，MCP 只能是后置可选能力，不能成为主链路依赖。
