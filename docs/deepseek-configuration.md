# DeepSeek 模型配置

摄影主项目复用 Anthropic SDK，使用 DeepSeek 官方 Anthropic 兼容端点。
配置项目根目录 `model.env`（已被 Git 忽略）：

```dotenv
PHOTO_MODEL_PROVIDER=deepseek
DEEPSEEK_API_KEY=填写真实密钥
DEEPSEEK_BASE_URL=https://api.deepseek.com/anthropic
DEEPSEEK_MODEL=deepseek-flash
```

dotenv 行末不要加反斜杠、逗号；URL 中不要写成 `https\://`。

## 选择和优先级

- `PHOTO_MODEL_PROVIDER=deepseek` 时，只使用 `DEEPSEEK_*` 字段，不使用旧 `ANTHROPIC_*` 的凭据、地址或模型。
- 未指定 provider 时，存在 `DEEPSEEK_API_KEY` 自动选择 DeepSeek，否则保持旧 Anthropic 路径。
- 显式选择 DeepSeek 但没有密钥时直接报错，不回退到旧中转。
- 显式禁用 SDK 的旧 Token 读取，并移除 Authorization 请求头，避免空 Token 生成非法 Bearer 头；使用 x-api-key 鉴权。
- DeepSeek Key 只允许发送到官方 Anthropic 兼容端点；错误填写 DashScope 的 OpenAI 端点会在本地报错。
- 模型名通过运行时解析，规划、后期、学习及统一入口沿用同一模型配置。

依次查找当前工作目录、项目根目录、`agent_code` 下的 `.env`、`.env.local`、`model.env`，重复路径只加载一次。
已存在的进程变量优先，文件采用 override=False；空值会尝试读取 Windows 持久环境变量。同一字段应只在一个配置源维护。
修改配置后重启后端和 CLI；已导入模块中的 MODEL 不会自动更新。

## 旧配置如何处理

本次不修改 Windows 全局环境变量，也不改其他工具的配置。
旧 `ANTHROPIC_BASE_URL` / `ANTHROPIC_AUTH_TOKEN` 在本项目 DeepSeek 模式下不生效，可以先保留以免影响其他工具。
如日后清理：同一文件同名变量仅保留一条，让密钥和端点属于同一平台；不要用同一个变量名存放多个平台地址。
DashScope 的 `.../compatible-mode/v1` 是 OpenAI 协议端点，不能用于本项目 Anthropic SDK。
独立修图子服务仍需自己的 DashScope 配置，本次未迁移该服务。

## 低消耗连接验证

从项目根目录执行：

```powershell
python scripts/check_model_connection.py --output .test_artifacts/deepseek-connection.json
```

该命令消耗实际 API 额度：一条短文本请求，最多输出 64 tokens，关闭思考，30 秒超时且不自动重试。
报告只记录服务商、模型、Token 用量、延迟和错误类型，不输出密钥、原始异常体或账户资料。
成功仅证明这次文本调用可用，不代表高德查询、多模态、完整规划或摄影回答质量已经验证。

官方文档：https://api-docs.deepseek.com/guides/anthropic_api/

## 2026-10-17 验证结果

- 运行时、入口、后期对话、规划追问相关回归：28 passed，7 subtests passed。
- 检查规划、后期、学习模块：实际 MODEL 均为 deepseek-flash。
- 真实短文本请求成功；请求模型和返回模型均为 deepseek-flash，回复匹配 DEEPSEEK_OK。
- 单次成功请求输入 13 tokens、输出 5 tokens，耗时 2.285 秒。该延迟仅为本次连接测试，不代表业务延迟指标；费用未核算。
- 脱敏原始结果保存在 `.test_artifacts/deepseek-connection.json`，该目录不提交 Git。
- 初次检查遇到 SDK 空 Bearer 请求头引起的本地协议错误，已通过显式移除该头修复，并添加模拟传输回归用例。
- 本轮未调用高德、未验证图片理解、未运行完整拍摄规划，未迁移独立修图服务。
