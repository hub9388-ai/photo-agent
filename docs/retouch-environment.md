# 独立修图环境：安装进度与继续验收

记录日期：2026-10-18（北京时间）。范围仅为独立修图最小 API 验收，不代表自然语言或生成式编辑已完成。

**进度更新：WSL / Ubuntu 初始化后，Docker 已正常启动，真实 API 最小链路通过。以下安装阻塞段保留为历史记录；最新结果和修复见 `docs/retouch-api-acceptance.md`。MinIO 已改为固定官方源码构建，PostgreSQL / Redis 已固定 digest，具体以当前 Compose 文件为准。**

## 已完成

- 项目内创建 `.test_artifacts/retouch-bootstrap`，安装 uv 0.13.1。
- 使用上游 `uv.lock`、`--frozen --extra agent --no-dev`，将 76 个依赖装入 `.test_artifacts/retouch-runtime`。未安装 cv 可选依赖，不下载抠图模型。
- 在该环境成功导入上游 `app.main`；生成 OpenAPI 并断言最小链路 7 个路径/方法存在。这是导入及接口定义检查，不是 HTTP 成功证据。
- 生成独立随机数据库、S3 和 JWT 测试凭据：`.test_artifacts/retouch-service.env`。Git ignore 已验证；未读取主项目模型 Key，未把凭据写入跟踪文件。
- 新建 `integrations/retouch-smoke.compose.yml`：独立 Compose 项目和卷，端口仅绑定 127.0.0.1，配置内存上限，不复用主项目数据。
- 通过 winget 官方清单安装 Docker Desktop 4.95.0，下载包 SHA256 校验通过。Docker CLI 报版本 29.8.2。
- 安装日志 `C:\ProgramData\DockerDesktop\install-log-admin.txt` 最终记录 `Installation succeeded`。

## 当前阻塞

Docker 安装器启用了 `Microsoft-Windows-Subsystem-Linux`，明确记录该 Windows 功能需要重启。未自动重启电脑。`docker info` 尚不能连接本机 Docker 引擎。

先前 `wsl --install --no-distribution --no-launch` 未成功；单独通过 winget 指定代理安装 WSL 也因本机未启用 ProxyCommandLineOptions 被拒绝，未修改该设置。后续 Docker 安装器完成了 Windows 功能启用；这不代表 WSL 内核版本或 Docker 引擎已就绪，重启后仍需检查 Docker Desktop 的实际提示。

因此本轮未启动数据库/存储/Redis，也未执行迁移、HTTP 上传或修图任务。未调用付费模型。

## 重启后继续

1. 保存工作并手动重启 Windows。
2. 从开始菜单打开 Docker Desktop，等待引擎就绪；如提示 WSL 更新，按官方说明处理，再确认引擎正常。
3. 在项目根目录 PowerShell 执行：

```powershell
cd 'C:\AI\AI 产品\项目\项目2-摄影_前后端'
# 首次已完成 Prepare；此命令可重复执行，不覆盖已有测试凭据。
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\retouch-service.ps1 -Action Prepare
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\retouch-service.ps1 -Action Infra
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\retouch-service.ps1 -Action Migrate
```

`Infra` 会检查引擎、拉取容器镜像、启动并等待健康检查；端口已占用或镜像下载失败应排查，不自动终止其他进程。当前镜像标签沿用上游的 postgres:17-alpine、redis:7-alpine、minio/minio:latest，首次成功拉取后记录实际镜像身份到 `.test_artifacts/retouch-images.json`。标签可变化，尚未把它们称为固定 digest 的完整可复现环境。

4. 开两个 PowerShell 窗口，均进入项目根目录，分别执行并保持窗口打开：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\retouch-service.ps1 -Action Api
```

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\retouch-service.ps1 -Action Worker
```

5. 第三个窗口进入根目录执行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\retouch-service.ps1 -Action Smoke
```

验收门槛：报告 `status=passed`，真实上传、编辑会话、队列工具任务、ZIP 导出成功，并校验导出的实际像素变化。报告位于 `.test_artifacts/retouch-minimal/api/report.json`；输出 ZIP 和图片位于同目录。失败时按 stage 定位；不能将健康检查或 queued 状态作为验收通过。

这条链路无需启动 PhotoAI 前端或上游前端，不经过 iframe，从而先独立定位后端问题。脚本配置 IMAGE_PROVIDER=mock，但本轮只调用 Pillow adjust_image 工具并校验实际像素，不使用生成式编辑、不调用 messages/planner。不能据此宣称 AI 生成式修图通过。

完成后在 Api/Worker 窗口按 Ctrl+C，再执行以下命令停止基础设施（保留测试卷）：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\retouch-service.ps1 -Action Stop
```

PowerShell 的 ExecutionPolicy Bypass 仅作用于该次子进程，不修改系统执行策略。脚本将配置加载到当前子进程并在退出时恢复；不修改系统模型环境变量。

安装与 WSL 要求参考 [Docker 官方 Windows 安装文档](https://docs.docker.com/desktop/setup/install/windows-install/)。完整接口分析见 `docs/retouch-minimal-api-review.md`。待真实验收后再决定保留独立服务或自行实现轻量调色模块。
