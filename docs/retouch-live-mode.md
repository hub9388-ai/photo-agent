# 修图工作台真实模式

2026-10-18：独立修图服务已从 mock 切换至真实图像 provider，API 与 Worker 已重启。

## 实际配置

私有配置：`.test_artifacts/retouch-service.env`（Git 忽略）。

| 配置 | 当前值 |
| --- | --- |
| IMAGE_PROVIDER | dashscope |
| PLANNER_MODEL | qwen-plus |
| IMAGE_EDIT_MODEL | qwen-image-2.1-pro |
| TEXT_TO_IMAGE_MODEL | qwen-image-2.1-pro |
| DASHSCOPE_BASE_URL | https://dashscope.aliyuncs.com |
| DASHSCOPE_API_KEY | 已配置，不记录明文 |

主项目 model.env / DeepSeek 配置不变。这里使用阿里模型完成修图对话规划，不是 DeepSeek。图片额度与规划模型的 Token 用量独立计量，不能将图片免费额度当作规划模型额度；实际用量和账单以百炼控制台为准。

`scripts/check_qwen_image.py activate` 会更新上述私有配置，但不自动重启服务或发起模型调用。部署环境只修改变量后，API 与 Worker 都要重启，避免缓存旧 provider。

## 本次改进

- 规划调用最长 45 秒，不自动重试，避免无期限等待；原生 endpoint 拼接规范化。
- 系统提示词从电商图片适配为摄影修图，明确外形/眼神修改使用 replace_region；亮度/冷暖使用 adjust_image。
- qwen-image-2.1 不支持 negative_prompt 时在本地给出明确错误，不把不支持的参数发往模型。
- 提交原图时按实际 JPEG/PNG/WebP 格式声明 MIME，避免把 JPEG 错标为 PNG；超过模型的 10MB、8000 像素边长或 10:1 宽高比限制时在调用前报错，原图不被静默缩放。
- 修图健康检查增加 models 配置摘要，不暴露 Key、Cookie 或签名图片 URL。配置可见不等于模型已实测成功，具体证据见下文。
- 改动保存到 `integrations/retouch-photoai.patch`，主仓库不提交独立上游 checkout。补丁反向检查通过。

## 验证结果

1. 两次真实规划调用（只规划，不执行工具）：
   - “整张照片亮度提高20%” → adjust_image，brightness=0.2。
   - “猫咪脸颊圆润、眼神好奇迷惑” → replace_region。
   - 证据：`.test_artifacts/retouch-live/planner-report.json`。
2. 通过 7301 前端代理的真实对话调色链路：随机测试账号 → 上传合成 64×48 PNG → 创建会话 → POST messages → qwen-plus 规划 → Redis/ARQ 调色 → 导出 ZIP。
   - 会话：`c842bf36-b923-44c0-b315-34e090c0df90`。
   - 对话：`58c70cf2-acea-46d8-a50b-d07896ec9e5b`。
   - 工具任务：`bc7496ec-3b16-4121-a1e0-77b3ab8e71ce`。
   - 任务成功，导出图片逐像素匹配 RGB×1.2，尺寸保持。
   - 单次脚本总耗时 3865 ms，包含注册、轮询与导出；不是性能 Benchmark。
   - 证据：`.test_artifacts/retouch-minimal/dialogue/report.json`、`export.zip`、`exported.png`。
3. 新增离线适配检查：规划超时/重试配置、2.1 不支持参数、本地单图请求格式、JPEG MIME、无效图像，5 项通过；凭据隔离回归检查 4 项通过。
4. 修图 API 和 7301 代理的健康检查都返回 image_provider=dashscope、image_model=qwen-image-2.1-pro、planner_model=qwen-plus；PhotoAI /retouch 页面 HTTP 200。

本轮三次真实文本规划调用，没有新图片生成请求。猫咪单图生成沿用之前的已验证结果，见 `docs/qwen-image-2.1-single-test.md`。没有声称对话驱动的猫咪生成、复杂多步编辑或全部工具均已完成真实验收。

## 使用与恢复

打开 `http://localhost:3000/retouch` 并刷新。若 iframe 尚未连接，点击重新连接；注册/登录信息保留，不需新建账号。旧的“未配置 Key”错误属于历史消息，不会自动消失，发送一条新指令验证即可。

建议先输入“只将整张照片亮度提高20%，其他不变”。改变猫咪外形、眼神等会调用图像编辑模型并消耗图片额度；等待当前任务结束后再发送下一条，避免重复提交。

启动方式仍见 `docs/retouch-environment.md`。需要确认模式时打开：

- `http://localhost:7302/api/health`（修图后端）
- `http://localhost:7301/api/health`（编辑器前端代理）

`PlanSmoke` 会真实调用规划模型两次，但不执行图像工具：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\retouch-service.ps1 -Action PlanSmoke
```

完整调色链路复测（会新建测试账号和记录，调用一次文本模型）：

```powershell
.\.test_artifacts\retouch-runtime\Scripts\python.exe scripts/check_retouch_minimal.py dialogue
```

测试不会复用用户账号或修改用户正在编辑的会话。主工作台写回素材库、整页交互视觉验收、生成式编辑质量与更多摄影样本仍是后续范围。
