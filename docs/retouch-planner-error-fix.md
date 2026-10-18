# 修图对话 HTTP 500 排查与修复（2026-10-18）

## 故障与原因

工作台发送自然语言指令后显示 `Internal Server Error`。后端日志显示两个先后发生的错误：

1. qwen-plus 返回 HTTP 400、结构化错误码 `Arrearage`。阿里官方错误码说明将其归为账户欠费或账务问题，需要核查 Key 所属账户：https://help.aliyun.com/zh/model-studio/error-code 。图像模型的免费额度不能证明文本规划模型一定可用。
2. 后端捕获异常并回滚数据库事务后，又访问了已失效 ORM 对象的 user_id/id，触发 `MissingGreenlet`。因此未能保存原来的失败原因，最终返回 HTTP 500。

此前的成功路径检查遗漏了数据库回滚后的异常分支。本次补充针对性回归检查。

## 改动

- 在规划开始前保存用户 ID、会话 ID、修订号，回滚后使用这些普通值保存失败记录。
- 根据结构化错误信息区分欠费、认证/权限、限流、超时，返回可读提示，不将上游原始响应或密钥发送到前端。
- 规划失败时清空未执行计划。没有工具步骤的失败对话不再显示无法使用的“重试失败步骤”按钮，提示处理问题后重新发送。
- 已更新 `integrations/retouch-photoai.patch`，并通过反向应用检查；服务已重启加载修复。

## 验证与当前状态

- `tests/test_retouch_live.py`：8 项离线检查通过，包含回滚后读取 ORM 属性会报错的模拟对象、失败记录保存、包装异常识别及脱敏提示。这里是模拟错误回归，不是再次真实触发欠费。
- 修图前端 `npm.cmd run build` 通过，仍有原有单包大于 500 kB 的构建提示。
- 通过 7301 前端代理新建独立测试账号、上传 64×48 测试图、创建会话，然后发送一次纯文字摄影知识解释请求。POST messages 返回 201，turn_status=succeeded，历史查询确认记录已保存，工具提交数为 0。
- 证据：`.test_artifacts/retouch-minimal/planner-error/report.json`。会话 `4a564845-0df1-4ad0-92b3-8889968c1515`，对话 `205a3c43-a997-474f-bbf2-77d007dae7cd`。

因此，最新一次真实文本调用已恢复，没有再次出现 Arrearage；无法仅凭请求结果确认账务状态发生变化的具体原因。仍需在用户原会话中验收交互。此次没有调用图像生成，也没有证明对话驱动的猫咪语义编辑已经通过。

## 复测

```powershell
.\.test_artifacts\retouch-runtime\Scripts\python.exe -m unittest discover -s tests -p test_retouch_live.py
.\.test_artifacts\retouch-runtime\Scripts\python.exe scripts/check_retouch_minimal.py planner-error
```

第二条会真实调用一次文本模型，并创建独立测试账号、图片及会话。模式名称表示检查规划错误的返回与保存行为；如果模型恢复，也会记录成功结果，不会人为宣称复现了欠费。该脚本不执行图像工具。
