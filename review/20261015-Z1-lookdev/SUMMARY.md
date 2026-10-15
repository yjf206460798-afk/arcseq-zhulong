# Z1 · 视觉开发 look-dev（2026-10-15）· 待作者门禁

**做了什么**：机头一段（s 0～7.2 m：球形烛光窗 + 六片虹膜、针状机头、位似放样的切面前机身、V 形眉骨、切面座舱盖、遮光盾滑轨、鸭翼、朱红棱线、鳞片瓦样片）用 Blender 脚本建模（`blender/build.py`，约 1 分钟含烘焙）→ GLB → ARCSEQ 引擎；同一段又用 FIG.01 代码凸体做了一版（`src/geometry/nose.mjs`）；同一 Blender 源出 Cycles 渲染。

| 看什么 | 图 |
|---|---|
| 三条路并排 / 4× 特写 | `ROUTE-three-way.png`、`ROUTE-closeups.png`、`CYCLES-hero-az030.png`、`CYCLES-nose.png` |
| 四项基础质感 | `QA-ao.png`（顶点 + 贴图 AO）、`AA-strip-A-B-C-REF.png` + `AA.txt`、`QA-glow.png` + `QA-glow-on-…-eye6x.png`、`QA-detail.png` |
| 电影画质（录制模式） | `TARGET-2-nose.png`（3× 超采样 + 景深 + 调色）对 `TARGET-2-nose-web.png`；运动模糊见下 |
| 目标帧 / 缩略图 | `TARGET-1-parked…`、`TARGET-2-nose.png`、`TARGET-3-orbit…`；`THUMB-feed.png` |
| 固定机位 | `AFTER-{silhouette,volume,lines}-az{030,120,210,300}.png`（BEFORE = Z0 空场景） |

**结论（DESIGN 8.2）**：建议几何母版走 Blender 脚本——布尔开槽、AO 与细节贴图、Cycles 镜头只有这条路有；代价是 bpy 依赖与页面体积（本段 2.5 MB），Z2 前改成二进制 GLB 直读。
**抗锯齿实测**（边缘像素对 4× 参照）：FIG.01 线覆盖式 误差 2.84 / 闪烁 2.00 → 精确盒式覆盖 0.86 / 0.93 → 网页高画质档（再加 2× 超采样）0.35 / 0.45。
**性能**（390 宽、DPR 3、4× 节流）：每帧脚本 5.8 ms，FIG.01 同条件 13.5 ms。
**缩略图测试**：② ③ 在 300 px 下一眼抓人（琥珀眼、朱红线、蓝色地球弧）；① 停机全景太安静、机体与台面明度太近——整机做出来后转台不再空，届时复测，封面用 ③。

**自查出的问题与修正**（BEFORE 在 `FIX*-BEFORE.png`，AFTER 见对应新图）：
1. 针段棱线被线的深度让出量透过眼珠 → 几何母版加遮线区（`masks`，14 面体）；2. 姿态推进器口的薄片在 AO 里烘出黑斑 → 空腔件烘焙时不当遮挡物；3. 机号「02」过大过亮、支架过粗 → 缩小、减淡、支架收细；4. Cycles 主光从下方来（相机上向量符号错）；5. Cycles 台面比机身亮（与网页相反）→ 按网页最亮档定反照率；6. 星点成排、地球弧被转台挡住 → 换哈希、弧顶从转台边缘升起；7. 鳞片样片四周一圈脏黑 AO → 贴面件两遍烘焙（`aoOccluder: false`）；8. 特写取景没算不对称视锥（`focus` 偏下）。

**还错在哪**：眼珠 12× 下仍有一小段针段棱线头；贴图鳞片缝读起来是菱形网格、不如几何样片像鳞——机腹大面积走实例化几何还是贴图，Z3 定；机头段之外全部未建。Gemini Argon 多模态对照审查需作者转交（`GEMINI.md`），本轮未做。
**下一步**：作者确认路线与三张目标帧 → `[Codex]` 二进制 GLB 直读 → Z2 双形态剪影与化剑转轴。
