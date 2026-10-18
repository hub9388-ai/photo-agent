# PhotoAI 修图服务接入

当前版本已包含 Post 建议转换、调色预览、人物选区保护和真实模型接入。调色规则见 [Post 到滑杆](post-to-sliders.md)，人物操作见 [笔刷说明](portrait-brush-improvements.md)，公网部署见 [部署说明](../deploy/full-demo/README.md)。

## 当前范围

将已有摄影工作台的素材发送到独立修图服务，创建编辑会话并在 PhotoAI 页面中打开画布。

- 顶部新增“修图”入口，可直接选择本地 JPG / PNG / WebP。
- 素材详情新增“进入修图”，传递真实 media_id；需 PhotoAI 真实 API 模式。
- 上传文件最大 20 MB。兼容格式优先发送原图，RAW 等使用已有 JPEG 预览图，画面会提示。不会覆盖原照片。
- 修图账号在子服务内登录/注册，PhotoAI 不读取或存储其密码、Cookie。
- 跨窗口消息检查精确 origin、窗口来源、协议版本与 requestId；子服务保留图片格式与大小校验。
- 导入超时不会自动重复上传，防止创建多个会话。上传成功但会话创建失败时，素材可能留在上游素材库；当前不自动清理。
- 编辑完成在编辑器导出；已支持 Post 建议转换为滑杆初值、用户预览微调后应用。结果自动回写主素材库、统一账号尚未实现。

## 来源及边界

用户提供的仓库地址 https://github.com/yuyuanweb/ai-retouch-agent 当前重定向到 https://github.com/yuyuanweb/ai-picture-editor。
固定提交与地址见 `integrations/retouch-source.json`。
独立 checkout 被主项目忽略，主项目仅保存自己的桥接代码、补丁和来源清单，避免误提交嵌套仓库。
检查固定提交时未发现 LICENSE 文件。保留上游归属；在解决授权前不要把其代码重新发布为自己的项目。

## 本地准备

所有命令从项目根目录的 PowerShell 开始。需要 Node/npm、Python >= 3.13、uv，以及运行中的 Docker Desktop / Docker Compose。

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\integrations\setup-retouch.ps1 -InstallFrontend
```

首次克隆固定版本并应用本项目补丁；已应用时可重复运行，不重置已有工作。
此命令的执行策略仅作用于本次 PowerShell 进程，不修改系统策略。

PhotoAI 前端 `frontend/.env.local` 添加或合并以下配置，保留已有其他配置，随后重启 Next.js：

```dotenv
NEXT_PUBLIC_RETOUCH_URL=http://localhost:7301
NEXT_PUBLIC_API_MODE=real
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

如 PhotoAI 实际使用 3001、127.0.0.1 或其他地址，在修图服务的 `frontend/.env.local` 设置准确的父页面 origin 后重启 Vite：

```dotenv
VITE_PHOTOAI_ORIGIN=http://localhost:3000
```

默认使用 localhost，两个应用请保持相同主机名。线上 HTTPS 页面需搭配 HTTPS 子服务和明确的嵌入策略。

## 启动子服务

首次在独立目录复制示例配置（不覆盖已存在的 .env）：

```powershell
Set-Location integrations/ai-retouch-agent
if (-not (Test-Path -LiteralPath '.env')) { Copy-Item -LiteralPath '.env.example' -Destination '.env' }
docker compose up -d
Set-Location backend
uv sync --all-extras
uv run alembic upgrade head
uv run uvicorn app.main:app --host 127.0.0.1 --port 7302
```

另开终端启动 worker：

```powershell
Set-Location integrations/ai-retouch-agent/backend
uv run arq app.worker.WorkerSettings
```

另开终端启动修图前端：

```powershell
Set-Location integrations/ai-retouch-agent/frontend
npm.cmd run dev
```

PhotoAI 原有前后端仍按原方式启动。访问 `http://localhost:3000/retouch`。
修图服务后端健康检查：`http://localhost:7302/api/health`。依赖包括 PostgreSQL 7311、Redis 7312、MinIO 7313/7314。

## 模型与额度

PhotoAI 主 Agent 当前的 DeepSeek 配置与修图服务的 DashScope 配置相互独立。
上游默认 `IMAGE_PROVIDER=mock` 的生图/生成式编辑是模拟结果，不是真实 AI 编辑。
自然语言规划函数会检查 `DASHSCOPE_API_KEY`，缺失时不可用；不能因为 mock 模式就宣称自然语言 Agent 已跑通。
手动调色、裁剪等本地图像操作与模型生成不同，应分别验证。首次启用 rembg/SAM 等可能下载模型。
真实生成式编辑按上游现有实现需配置 DashScope；当前适配未将其改为 DeepSeek/豆包。

## 验收及证据

1. 服务未启动：页面保持未就绪，不能发送；可重连或独立打开服务排查。
2. 登录后发送一张 JPG：图片上传后创建 session，进入 `/editor/{sessionId}`；对比编辑器原图。
3. 从真实素材详情发送 PNG：网络请求 `GET /api/media/{id}/retouch-source` 返回原图；响应头 `X-Retouch-Source=original`。
4. RAW 素材：返回 JPEG 预览，需确认提示，不能宣称 RAW 无损编辑。
5. 手动调整亮度、撤销、导出，保留前后图。该项尚需运行完整子服务后人工验证。
6. 无模型 Key 时测试自然语言功能：保留真实不可用提示；配置后再测任务完成与费用。
7. 本地自动检查：主前端 TypeScript、子前端构建、后端导出/路径边界/缺失媒体/超限回归测试。

验证记录应区分代码检查、模拟测试和真实端到端。未运行完整依赖链时，不将本次接入描述为已完成运行验收。

## 2026-10-15 验证记录

- 主前端 `tsc --noEmit`：通过；新增修图页面与工作区 ESLint：通过。
- 子前端 `npm run build`：通过。`npm run lint` 返回成功，但上游原有代码有 React refs、effect 和依赖项警告，尚未逐项修复。
- `python -m pytest backend/tests/test_retouch_source.py backend/tests/test_media_upload.py -q`：8 passed。
- 当前命令环境未找到 Docker 和 uv，未启动 PostgreSQL / Redis / MinIO / worker，完整编辑链路尚未实测。
- 未调用付费模型，未验证自然语言修图效果，也未更改现有模型 Key。
