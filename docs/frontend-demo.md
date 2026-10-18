# 纯前端求职演示

在线体验：[PhotoAI 演示工作台](https://photo-agent-hub9388.netlify.app/)。

此版本用于浏览器体验摄影产品流程，不部署后端、不配置模型 Key。
网页始终标明演示模式。工作台、分析、素材库、学习、规划和历史直接复用原页面组件；修图加载原编辑器的静态构建，保留聊天、画布、工具栏、调色和导出页。演示只替换数据与执行来源。

## 案例与交互

- 原图：`frontend/public/demo/cat-original.png`，街角三花猫。
- 圆润效果：`frontend/public/demo/cat-rounded.png`，已有单图编辑测试结果。
- 图片已按用户确认的“第一张原图 → 第二张效果”顺序设置；直接复制已有 PNG，未再次生成。展示分辨率均为 768 × 1024。
- Post / Coach：默认选好猫图，点击原有“开始智能分析”回放分析过程。可切换自然可爱或纪实偏好；展示对应的固定建议，保留结果切换、报告导出、保存结果及发送素材库。
- 调色：使用原调色面板及其逐像素预览算法；应用在浏览器 Canvas 生成真实版本。保留亮度、对比度、高光、阴影、饱和度等控制，锐化与清晰度在应用时近似计算，不宣称等同 RAW / Lightroom。可裁剪、翻转、撤销、重做，原导出页打包真实 PNG 和 manifest.json。
- 圆润修改：在原聊天区输入圆润指令，确认“执行计划”后载入预置结果；回复会明确说明它基于原图，不继承先前调色。其他生成需求明确返回不支持，当前图片不变。
- 素材库：保留原图，另存已应用结果的快照；后续撤销不覆盖已保存快照。
- 学习：原学习页面聚合本案例 Coach 反馈，显示对应照片，可展开、领取练习。领取仅记录意向，不代表完成拍摄或 AI 复评；页面原有画像均属于演示数据。
- Plan：原表单预填杭州西湖一日游，点击生成，支持切换 A/B/C、采用、导出和预设草稿。其他目的地提示不支持；无实时天气、日落、交通、门票或客流数据，修改表单不代表任意实时生成。
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

主站 API 层在演示构建中读取固定案例并回放事件，不发真实 API 请求。原修图编辑器从本站 `/demo-editor/` 加载；构建脚本校验固定源码版本和现有补丁，再注入仅在演示中使用的浏览器适配层，拦截编辑器 API。真实服务源码和启动入口保持独立。

首次构建会获取 `integrations/retouch-source.json` 固定版本并安装修图前端依赖，需要 Git、Node 和网络；不需要 Python、数据库或模型 Key。只发布静态构建，不把完整 checkout 提交到主仓库。

主站演示缓存使用 `photoai.demo.*` 命名空间，修图建议仅写入演示会话专用键。编辑生成的 PNG 存入演示专用 IndexedDB，保存到素材库时另存一份已应用快照。重置只清理演示记录，不清理真实模式缓存。

## Netlify

当前站点通过 CLI 将本地验证后的 `frontend/out-demo` 发布到 Netlify，访客无需登录。尚未连接 GitHub 自动部署；推送源码不会自动更新网站。后续修改需重新执行 `npm run build:demo`，再使用 `netlify deploy --prod --no-build --dir <out-demo 的绝对路径>` 发布，或按下方配置连接 GitHub。

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
根配置增加浏览器 CSP：连接和 iframe 仅允许本站；`/demo-editor/*` 回退到原编辑器的静态入口，不配置后端转发。
如使用手动拖放部署，应上传构建后的 `frontend/out-demo` 内容；响应头需另外配置，不能仅依赖仓库的 `netlify.toml`。

## 验证

```powershell
# 构建后运行，默认使用电脑已安装的 Chrome：
npm.cmd run test:demo
# 若 CI 安装了 Playwright Chromium，可设置 DEMO_BROWSER_CHANNEL=chromium。
```

浏览器回归覆盖原页面完整猫图流程、练习领取、原编辑器发送与确认、保存后刷新恢复、调色下载像素、ZIP 导出、撤销、规划切换采用、偏好选择与真实缓存隔离，以及页面和编辑器深链接直接访问。预览服务器同时应用 Netlify 的 CSP 以验证同源 iframe。
每条测试同时检查没有后端 / 模型请求与未捕获浏览器异常。测试产物放在被忽略的 `.test_artifacts/frontend-demo/`。

当前只覆盖这一个完整照片案例，不接受用户上传后套用预置分析。需要任意照片分析、真实生成和动态旅行规划时，请按完整服务部署文档启动后端。
