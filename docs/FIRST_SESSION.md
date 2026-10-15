# 第一次会话的任务描述（复制到云端新会话）

```
读 CLAUDE.md、docs/DESIGN.md、docs/ROADMAP.md、docs/WORKFLOW.md、docs/VISUAL_TARGET.md，再看 refs/concept/ 里的全部概念图，以及 refs/layout/ 的总布置图和发动机图（先读该目录 README）。

完成 Z0：从 yjf206460798-afk/arcseq-hangar 的 main 复制 Three.js 引擎（按 CLAUDE.md「技术」一节），读那边的 docs/PATTERNS.md；删去歼-20 专用数据，空场景能构建、能截图；列出概念图三视图之间的矛盾和取舍，追加到 DESIGN 第 8 节。

然后开始 Z1 视觉开发（见 ROADMAP）：
1. 按 docs/BLENDER.md 装 bpy，用脚本建机头一段（光窗、座舱与眉骨、朱红棱线、一小片鳞片瓦），导出 GLB 进网页，再出一张 Cycles 渲染；
2. 同一段用 FIG.01 的代码凸体做法也做一版，三者并排比较，写下几何母版走哪条路的建议；
3. 做四项基础质感（AO 烘焙、抗锯齿、选择性发光、烘焙细节与贴花）和录制模式的电影画质开关；
4. 交三张目标帧和缩略图测试结果，自己先列出至少 3 个具体问题并修正。

截图和 SUMMARY.md 放进 review/，更新 ROADMAP 当前进度，提交并推送。然后停在 Z1 门禁，等我确认。
```

之后每次新会话只需要说：

```
读 CLAUDE.md 和 docs/ROADMAP.md 的当前进度，继续下一步。
```
