# 上游修图最小链路盘点与验证

日期：2026-10-18。固定上游提交：`49f6ad8c96740a68b7e6228a47e8e2be6876eb34`。
来源与授权状态见 `integrations/retouch-source.json`。本轮未修改上游、未把其源码复制到主后端、未调用模型。

**后续进度：独立环境补齐后真实 HTTP 最小链路已通过，详见 `docs/retouch-api-acceptance.md`。下文“本轮实测”的 blocked 状态记录的是首次盘点时的状态。**

## 最少 API

上游 `backend/app/main.py` 为以下路由统一添加 `/api` 前缀。直接调用 7302 后端即可，不需要 iframe 或上游前端。

| 顺序 | 接口 | 输入 / 返回 | 来源（相对上游 backend/app） |
| --- | --- | --- | --- |
| 前置 | GET /api/health | api、database、storage 都应为 ok；不检查 Redis/Worker | routers/health.py |
| 1 | POST /api/auth/register 或 /api/auth/login | username/password；返回用户及 HttpOnly 会话 Cookie；客户端保留 Cookie | routers/auth.py |
| 2 | POST /api/assets | multipart/form-data，字段 file；返回素材 id | routers/assets.py |
| 3 | POST /api/sessions | current_asset_id，title 可选；返回会话 id、document | routers/sessions.py |
| 4 | POST /api/sessions/{id}/tools | 下方 JSON；202 返回 run.id，表示已提交，不代表处理完成 | routers/sessions.py、tools/retouch.py |
| 5 | GET /api/runs/{run_id} | 轮询，直到 succeeded / failed / canceled；必须设置总时限 | routers/runs.py |
| 6 | POST /api/sessions/{id}/exports | {"asset_ids":[]}；返回 ZIP，含 images/ 和 manifest.json | routers/sessions.py、services/exports.py |

亮度请求：

```json
{"tool":"adjust_image","params":{"brightness":0.2}}
```

`layer_id` 可省略，默认选择目标图像层；本次只创建单图层会话。亮度范围 [-1, 1]；0 不改变，0.2 用 Pillow 将 RGB 乘以 1.2，-1 为黑色。它不是 EV 曝光模型，也不承诺专业 RAW 工作流。输出 PNG；处理函数另有 JPEG 编码能力，但不能由此推断 exports 接口支持指定 JPEG 格式。

导出默认 asset_ids=[] 时，只默认选择营销图、投放图等特定种类；本链路无这些素材，因此回退为导出当前拍平画布。传原图 id 可能导出原图，不能只凭 ZIP 下载成功就判断亮度修改成功。

## 依赖与边界

- Python >=3.13（本机 3.13.7），及上游 pyproject.toml 依赖。
- PostgreSQL：账号、素材、会话、工具任务；模型使用 PostgreSQL JSONB，不能直接把 URL 换为 SQLite。
- MinIO / S3：图片对象；应用 lifespan 启动时就检查 bucket。
- Redis + ARQ Worker：`adjust_image` 标记 queued=True；API 服务启动但没 Worker，任务可能一直 queued。
- `services/tools.py` 执行后还调用 Agent continuation；独立 API 的整体导入/启动依赖不能仅由 pixels.py 的导入情况推断。
- 明确参数的亮度处理不调用大模型，不需要 DashScope Key；自然语言规划与生成式图片编辑不在此次范围。

## 可复现验收

在项目根目录执行：

```powershell
python scripts/check_retouch_minimal.py core
python scripts/check_retouch_minimal.py api
```

core 模式直接加载本地固定上游的 `edits/pixels.py`，无数据库/模型替身；api 模式只请求 `http://127.0.0.1:7302`，不读主项目 Key，不使用代理。它先检查健康状态，成功后会在独立修图服务创建随机测试账号、64×48 合成图片和会话，提交亮度任务、最多轮询 60 秒、下载 ZIP，再验证清单、尺寸和实际输出像素。账号密码与 Cookie 仅在进程内存中，不保存。后端测试数据会保留；报告记录测试用户/会话/任务 id 以便定位，不会自动删除用户数据。

合成图使用不发生饱和截断的不透明 RGB 像素，按通道计算 1.2 倍期望结果进行精确比对，避免“HTTP 200 但没有改图”误判。此用例只验证一个基础路径，不能证明真实摄影照片质量、EXIF 保留、色彩管理或整体可靠性。

### 本轮实测

| 验收项 | 结果 |
| --- | --- |
| 原函数 brightness=0.2 与预期逐像素一致 | 通过 |
| 保持 64×48 尺寸 | 通过 |
| brightness=0 像素不变 | 通过 |
| brightness=-1 输出黑色 | 通过 |
| PNG 输出、JPEG 编码及重新解码 | 通过 |
| 真实 HTTP /api/health | 连接失败，blocked |
| HTTP 上传、账号、会话、任务、ZIP 导出 | 未执行，不能记为通过 |

证据（Git 忽略目录）：

- `.test_artifacts/retouch-minimal/core/report.json`：原函数检查结果及源码 SHA256。
- 同目录 `input.png`、`brightened.png`、`brightened.jpg`。
- `.test_artifacts/retouch-minimal/api/report.json`：实际阻塞阶段 `/api/health`。

本机未找到 docker、uv 命令。未安装系统组件、未修改数据库、未启动上游基础设施，未用 mock API 替代真实验收。完整运行需要先准备依赖、数据库迁移并启动 API 和 Worker；既有启动说明见 `docs/retouch-integration.md`。上游默认 Compose 使用固定开发密码及对外端口映射，不宜原样用于公开部署。

## 方案判断（暂定）

完整上游 HTTP 链路尚未通过，因此本轮不决定正式架构。

- 若保留多图层画布、账号、历史、撤销及多工具编辑，继续复用独立服务更可能减少重复开发，但需承担整套依赖的运行成本。
- 若 MVP 只要曝光/亮度、对比度等确定参数处理并存回素材库，现有 FastAPI + Pillow 可以自行实现小模块，避免引入另一套账号和任务系统。可参考接口与行为，但上游未找到 LICENSE，复制或再发布代码前需解决授权。
- 下一验收门槛：真实 API 模式通过，或明确选择自行实现轻量参数处理模块并单独验收；当前修图页面仍不应展示为“已验收可用”。
