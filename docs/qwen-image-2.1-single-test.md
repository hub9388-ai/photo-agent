# Qwen-Image-2.1-Pro 兼容性核对与单图编辑实测

日期：2026-10-18。范围：复用上游图像编辑适配器进行一次真实单图编辑；不经过对话规划、队列或 PhotoAI 界面。

后续进度：工作台已切换真实模式，见 `docs/retouch-live-mode.md`。下文 IMAGE_PROVIDER=mock 等状态保留为单图测试时的历史记录。

## 兼容性结论

官方说明：https://help.aliyun.com/zh/model-studio/qwen-image-generation-and-editing-api-reference 。

| 项目 | 官方要求 / 本次选择 | 上游兼容情况 |
| --- | --- | --- |
| 模型 | qwen-image-2.1-pro | 通过 IMAGE_EDIT_MODEL 配置 |
| 协议 | DashScope 同步 | 现有 edit 实现已支持 |
| 路径 | /api/v1/services/aigc/multimodal-generation/generation | 与上游 _EDIT_PATH 一致 |
| 图片输入 | input.messages 中 image + text | 已支持 Base64；本次先转换 PNG，匹配声明 MIME |
| 输出 | output.choices[].message.content[].image | 现有解析器和下载器可用 |
| 参数 | n=1，size=768*1024，watermark=false | 本次全部兼容 |
| negative_prompt | 2.1 系列不支持 | 本次不发送；现有适配器在非空时会发送，后续通用接入需增加模型参数校验 |
| Function Calling | 该图像模型不支持 | 不能代替规划模型，不能把 PLANNER_MODEL 直接改成它 |

本次不需改上游 provider 的路径或响应结构。并不代表其所有生成、放大、任意参数组合都已验证；只覆盖这个同步单图编辑请求。

## 凭据与配置

model.env 中未使用独立 DASHSCOPE_API_KEY 变量，而是重复使用 ANTHROPIC_AUTH_TOKEN / ANTHROPIC_BASE_URL 存放不同供应商配置。脚本按记录顺序找到唯一与官方阿里域名配对的凭据，未把最后一条重复变量当作阿里配置，也未使用 DeepSeek 或中转平台 Key。

从旧配置的 `https://dashscope.aliyuncs.com/compatible-mode/v1` 提取官方 origin `https://dashscope.aliyuncs.com`，避免在原生接口路径前错误拼接 compatible-mode。该域名在本次模型列表查询和图片编辑中均实际返回 HTTP 200。后续可按业务空间迁移到控制台的专属域名，但无需猜测 WorkspaceId。

已写入 Git 忽略的 `.test_artifacts/retouch-service.env`：

- DASHSCOPE_API_KEY：从本地匹配的阿里配置复制，未输出到日志/文档。
- DASHSCOPE_BASE_URL：https://dashscope.aliyuncs.com。
- IMAGE_EDIT_MODEL：qwen-image-2.1-pro。

IMAGE_PROVIDER 保持原设置 mock；本次直接实例化 DashScopeImageProvider 完成真实请求，没有通过 mock provider 处理图片。未重启正在运行的 API/Worker，因此不能声称工作台对话已接通。主项目 model.env、DeepSeek 配置和系统环境变量未改动。

## 单次真实调用

测试输入来自用户已在修图页使用的猫咪照片：`media/originals/media_5422d0e6fb714a649736a69ffa74db88.jpg`。原文件不变；提交副本缩至 768×1024 并转成不带 EXIF/GPS 的 PNG。

指令：让猫咪脸颊、身体略微圆润，眼神带好奇和迷惑；保留三花花纹、坐姿、四肢、尾巴、街景和真实摄影质感。

- 只读模型列表预检：HTTP 200，包含 qwen-image-2.1-pro。
- 图片生成 POST：恰好 1 次，n=1，无生成重试。
- 响应：HTTP 200，request_id=`e0888057-2712-9ee4-977e-da78b3f89864`。
- usage：image_count=1，width=768，height=1024。
- 下载并解码：有效 PNG，768×1024，与输入像素不同。
- 图片请求及下载耗时：15743 ms；单样本记录，不作为稳定性能指标。
- 实际扣费、是否消耗免费额度及剩余张数以百炼账单/模型用量为准；API usage 不证明具体抵扣方式。

证据目录 `.test_artifacts/qwen-image-single-test/`：

- `preflight-report.json`：鉴权、模型列表检查结果。
- `attempt.json`：提交前创建的独占标记；脚本禁止再次生成，不会自动删除。
- `run-report.json`：请求路径、参数、request_id、usage、输出尺寸、哈希和耗时，不含 Key、签名 URL 或原始响应。
- `input.png`：实际提交的测试副本。
- `edited.png`：真实模型生成结果。

已人工查看结果：猫咪外形更圆、眼睛更突出，整体姿态和街景仍可辨认。生成式编辑会重绘细节，不能按像素不变来承诺背景或动物身份完全保真。审美是否满足“自然、可爱、迷惑”仍待用户确认；没有构造量化质量分数。

## 验证与复现边界

`scripts/check_qwen_image.py` 提供 inspect/configure/preflight/run。run 使用固定提交标记避免重复消费，已有标记时直接退出并保留原报告。**不要为了重新执行而直接删除标记**；如需新实验，应先明确新测试范围和成本，再建立独立实验记录。

四项离线测试通过（`tests/test_qwen_image_config.py`）：重复变量按供应商分组、拒绝非官方目的地、拒绝冲突 Key、配置不自动开启全局生成或修改数据库地址。

尚未验证：工作台对话规划、qwen-plus 权限及调用、图层工具通过队列调用新模型、主项目中的导出/写回、完整尺寸原图和更多样本。下一步若启用界面真实编辑，需要设置 IMAGE_PROVIDER=dashscope 并重启 API/Worker，再分别验证规划模型与图像工具；不应将本次适配器测试描述为整条 Agent 链路通过。
