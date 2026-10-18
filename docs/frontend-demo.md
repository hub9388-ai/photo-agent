# 纯前端求职演示

此版本用于浏览器体验摄影产品流程，不部署后端、不配置模型 Key。
网页始终提示“演示模式 · 使用预置案例”，不会把固定结果呈现为实时模型分析。

## 案例与交互

- 原图：`frontend/public/demo/cat-original.png`，街角三花猫。
- 圆润效果：`frontend/public/demo/cat-rounded.png`，已有单图编辑测试结果。
- 图片已按用户确认的“第一张原图 → 第二张效果”顺序设置；直接复制已有 PNG，未再次生成。展示分辨率均为 768 × 1024。
- Post / Coach：针对原图与“自然、可爱的宠物摄影”偏好整理的固定示例；分析步骤是清楚标注的回放，不是现场模型请求。
- 调色：亮度、对比度、饱和度使用浏览器滤镜实时预览；点击应用才更新编辑版本，支持撤销。PNG 导出通过 Canvas 写入已应用的同一组滤镜。
- 圆润修改：载入预先生成的图片，调色归零后可继续微调。不是对任意图片的实时生成。
- 素材库：保留原图，另存已应用结果的快照；后续撤销不覆盖已保存快照。
- 学习：完整展示 Coach 反馈，可领取拍摄练习；不虚构能力评分、成长曲线或 AI 复评。
- Plan：固定“杭州西湖一日摄影游”案例，展示时段、地点、焦段与任务。其他目的地提示不支持，不伪装生成；无实时天气、日落、交通、门票或客流数据。
- 历史与进度：仅保存此浏览器的体验状态，可重置；不是云端个人账户。

## 启动与构建

在 `frontend/` 中运行：

```powershell
npm.cmd ci
npm.cmd run build:demo
npm.cmd run preview:demo
```

访问 `http://127.0.0.1:4175`。`out-demo/` 是可直接托管的静态文件，不包含后端服务。
日常真实系统仍使用原有 `npm run dev` / `npm run build`。真实部署不设置 `NEXT_PUBLIC_DEMO_MODE=1`。

演示模式通过构建开关选用独立页面组件，跳过现有页面的 API 与 iframe 挂载；不复用会请求 localhost 的实时修图页面。
浏览器持久化只保存版本号、滑杆与流程状态，不保存私密照片或 Key。

## Netlify

仓库根目录已有 `netlify.toml`：

| 项目 | 值 |
| --- | --- |
| Base directory | `frontend` |
| Build command | `npm run build:demo` |
| Publish directory | `out-demo`（相对 Base） |
| Node | 22 |
| 演示开关 | `NEXT_PUBLIC_DEMO_MODE=1` |
| 静态托管 | `NETLIFY_NEXT_PLUGIN_SKIP=true`，跳过 Next.js 服务端适配器 |

在 Netlify 导入 GitHub 仓库并选择包含本次修改的分支，按此配置发布；不要添加任何 API Key，也不要上传 `model.env` 或后端运行数据。
Netlify 提供 `*.netlify.app` 地址。构建输出是静态文件，无需启动 Next.js、FastAPI、数据库或修图 worker。
配置参考：[Netlify 构建配置](https://docs.netlify.com/build/configure-builds/file-based-configuration/)与[框架部署说明](https://www.netlify.com/knowledge-base/how-to-deploy-nextjs-astro-nuxt-or-sveltekit-to-netlify/)。实际构建命令使用本项目 Next 16 的 `output: export`，不运行已移除的 `next export` 命令。
根配置增加浏览器 CSP：连接仅允许本站，不允许外接 iframe；未配置后端转发。
如使用手动拖放部署，应上传构建后的 `frontend/out-demo` 内容；响应头需另外配置，不能仅依赖仓库的 `netlify.toml`。

## 验证

```powershell
# 构建后运行，默认使用电脑已安装的 Chrome：
npm.cmd run test:demo
# 若 CI 安装了 Playwright Chromium，可设置 DEMO_BROWSER_CHANNEL=chromium。
```

浏览器回归覆盖完整猫图流程、保存后刷新恢复、调色下载像素、撤销与素材快照隔离、规划输入边界、手机尺寸和各页面直接访问。
每条测试同时检查没有后端 / 模型请求与未捕获浏览器异常。测试产物放在被忽略的 `.test_artifacts/frontend-demo/`。

当前只覆盖这一个完整照片案例，不接受用户上传后套用预置分析。需要任意照片分析、真实生成和动态旅行规划时，请按完整服务部署文档启动后端。
