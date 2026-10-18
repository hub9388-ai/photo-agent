# 独立修图 API 最小链路验收

日期：2026-10-18（北京时间）。结论：**本地真实 HTTP 最小链路通过**。

## 验收对象与范围

- 修图上游提交：`49f6ad8c96740a68b7e6228a47e8e2be6876eb34`，保留此前图片交接补丁；本轮未改变其业务处理逻辑。
- API：http://127.0.0.1:7302；独立 PostgreSQL、Redis、S3 存储及 ARQ Worker。
- 输入：脚本生成的 64×48 不透明合成 PNG，非摄影实拍样本。
- 操作：`adjust_image`，`brightness=0.2`；Pillow 将 RGB 乘以 1.2，不是 +0.2 EV。
- 验收不启动 PhotoAI 前端，也不经过 iframe；不调用模型、messages 或生成式图像工具。

## 实际结果

| 阶段 | 实测结果 |
| --- | --- |
| 健康检查 | HTTP 200，api/database/storage 均正常 |
| 随机测试账号注册，Cookie 留在进程内 | HTTP 201 |
| multipart 上传真实 PNG 文件到对象存储 | HTTP 201 |
| 创建编辑会话 | HTTP 201 |
| 提交 adjust_image | HTTP 202 |
| 通过 Redis / ARQ Worker 执行并查询任务 | succeeded |
| 导出 ZIP（含 manifest.json 和图片） | HTTP 200 |
| 解码 ZIP 中的输出图，与独立计算的期望像素比较 | 逐像素一致，64×48 尺寸保持 |

测试会话：`a47325de-b101-4d3c-a5c7-27aac5a14563`。
工具任务：`9a8029f8-a866-4cd4-bda6-486ef1d8c45c`。
脚本计时总耗时 2626 ms，仅为本机这次小图验收记录，含注册、轮询和下载，不能用作生产延迟指标或专业照片性能结论。

主证据（本地 Git 忽略目录，不含密码/Cookie）：

- `.test_artifacts/retouch-minimal/api/report.json`：各 HTTP 阶段状态、耗时、任务/会话 ID、像素检查、源码 SHA256。
- `.test_artifacts/retouch-minimal/api/input.png`：上传输入。
- `.test_artifacts/retouch-minimal/api/export.zip`：API 实际返回的归档。
- `.test_artifacts/retouch-minimal/api/exported.png`：从 ZIP 读取的结果。
- `.test_artifacts/retouch-images.json`：实际容器镜像身份快照。

## 运行问题及处理

1. **Docker 先于 WSL 就绪启动**：Ubuntu 初始化后 Docker 仍报无法启动；通过 Docker CLI 重启 Desktop 后引擎正常，版本 29.8.2。
2. **旧终端 PATH 未更新**：Docker CLI 能找到，但 docker-credential-desktop 找不到。启动脚本仅给自身进程补充 Docker bin 路径，未修改系统 PATH。
3. **上游 MinIO 镜像失效**：Docker Hub minio/minio:latest 拉取失败，指定 Quay 标签也不存在。官方仓库声明社区版改为源码分发，因此按固定官方提交 `7aac2a2c5b7c882e68c1ce017d8256be2feea27f` 构建本地镜像 `photoai-minio-smoke:7aac2a2`，保持真实 S3 服务，没有换成 mock。构建定义 `integrations/minio-smoke.Dockerfile` 固定 Go / Alpine 基础镜像 digest 并保留 LICENSE。官方来源：https://github.com/minio/minio#source-only-distribution 。这是本地验收运行方案，尚未决定作为正式部署依赖。
4. **构建客户端认证地址直连超时**：仅在本次命令进程设置 HTTP_PROXY / HTTPS_PROXY 为现有本机代理 `http://127.0.0.1:7897` 后成功，未修改系统代理。代理端口属于本机环境，不能假设其他机器相同。
5. **Alembic 按 Windows GBK 读取含中文的 INI 失败**：新建 `scripts/migrate_retouch.py`，使用 Alembic 公共 Python API 设置迁移目录、模块路径并执行未修改的上游迁移；限制目标为本机独立测试库。7 次上游迁移成功，head 为 `fa850313b768`。

PostgreSQL / Redis 镜像已按本轮拉取结果固定 digest。MinIO 本地镜像 digest：`sha256:bd8c2e89673b01fc0bbdaa0f9f2b222442fe2303687bfe75aa705f6d027f8d1f`；它是本地构建结果，不代表可从公共 registry 下载。Go 依赖使用上游模块版本及 Go checksum 校验机制；不是对依赖安全性的完整审计。

## 复现与当前边界

按 `docs/retouch-environment.md` 启动 Infra、Migrate、Api、Worker；然后运行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\retouch-service.ps1 -Action Smoke
```

若需首次构建且直连失败，可在该 PowerShell 窗口临时设置上述本机代理后再运行 Infra，不修改全局配置。重复 Smoke 将生成新的测试账号和测试数据，并覆盖最近一次报告/输出；已有服务器端测试数据保留。

此次只证明独立服务能完成确定参数的基础亮度处理。尚未验证：PhotoAI 页面连接 7301 编辑器、用户实际照片和大图、色彩管理/EXIF、自然语言修图、生成式编辑、编辑结果写回主项目、长时间运行或并发可靠性。

当前架构判断：上游并非基础 API 不适配，但运行完整应用确有另一套数据库、存储、账号、队列的成本。需要多图层画布/撤销/复杂工具时可继续评估独立服务；若产品范围仅为基础调色及建议落地，现有 FastAPI + Pillow 自行实现轻量模块更合适。此轮先保留可复现验收方案，不做主项目重构。下一独立任务可验证编辑器的导入、手动调色及导出，再决定是否保留整套 UI。
