# Stage 8 Smoke Test

## Result

阶段 8 有 AMAP_KEY 手动 smoke 通过。

- `/api/agents/plan/run` 成功创建 `trip_planning` job。
- `PlanAgent` 真实模型链路跑通。
- 高德 POI provider 可用。
- 天气因目标日期超出高德 3 天预报范围而降级为规则建议。
- job completed。
- plan result succeeded。
- 结果包含 `plans`、`execution_timeline`、`provider_note`、`style_handoff`。
- 未触发 post/coach 默认主链路。

## Notes

本次 smoke 使用已配置的 `AMAP_KEY`。真正无 `AMAP_KEY` 的手动 smoke 暂不阻塞阶段 8 提交；旧 `photo_provider_adapter.py` 已有未配置 Key 时的降级路径，后续可在配置治理或 provider 回归测试中单独补测。

PowerShell 中文乱码仍属于终端显示问题；浏览器/API 原始 JSON 响应为正常中文。
