# 做法样板 · FIG.02 烛龙（由 Claude 维护，Codex 照做）

每一节对应一类已定型的做法。Codex 铺开同类工作时，严格照对应一节执行，不自行发明新做法。

**沿用 FIG.01 的做法**：`yjf206460798-afk/arcseq-hangar` 的 `docs/PATTERNS.md` 里下列各节在本仓库原样有效（引擎同一套代码，函数名不变）：「渲染：Three.js 页面」的明暗五档与色板规则、「线条分级」、「投影与灯」、「口盖、分割线」（分割线进 `seams`）、「关节、机构与状态」、「铰链类机构」「多段旋转」「顺序动作」（Z4 用）、「点选与操作区」、「演出与中途干预」（Z5 用）、「尾焰着色器」。下面只写 FIG.02 新定或改过的。

`[kit]` 标注的节可以原样抽进 `arcseq-kit` 素材库 / 独立引擎仓库。

---

## 引擎与作品分开（Z0 定）`[kit]`

- 适用于：一切代码改动先判断它属于引擎还是作品。
- 参考实现：
  - 引擎（与机型无关）：`src/figure/engine/NN-*.js`（浏览器端，按文件名顺序拼进同一个闭包、共享作用域：`00-setup` 渲染器与相机 → `10-materials` 明暗材质 → `20-model` 零件与关节 → `30-lines` 线条 → `40-deck` 转台、投影、灯 → `50-state` 机构状态 → `60-director` 演出 → `70-fx` 尾焰 → `80-post` 后处理 → `90-page` 环境、交互、审图入口）；`engine/pack.mjs`（取景 `fitView`、凸包打包 `packHulls`、页面拼装 `engineScript` / `pageHtml`）；`engine/glb.mjs`（GLB → 零件）；`src/figure/weld.mjs`、`shots.mjs`、`aa.mjs`、`perf.mjs`、`scripts/chrome.sh`、`scripts/strip.py`。
  - 作品：`src/figure/build.mjs`（几何来源、配色卡、材质表、线条、特效、环境、机构、演出、文字）、`blender/`（几何母版）。
- 规则：引擎文件里不出现机型专有名词（零件名、地标名只经 `DATA` 传入）；作品要新能力时，先在引擎里做成数据驱动的通用功能（例：`lineLevel`、`glow`、`accent`、`environments.backdrop`），再在 build.mjs 里填数。改引擎时在提交说明里写“引擎：……”。
- 常见错误：在引擎里写 `if (part.name === "…")`；把作品数值写进引擎（数值一律进 build.mjs 的 `FX` / `POST` / `LINES` / `ENVIRONMENTS`）。

## 几何母版：Blender 建模脚本（Z1 定）

- 适用于：一切机体零件。母版是脚本：`blender/build.py` + `blender/zl/*.py`，运行一次从零生成全部模型；`assets/zhulong.glb`、`.json`、`zhulong-skin.png` 是产物（提交进仓库，网页构建不需要 Blender），`.blend` 只在 `--blend` 时另存到 `dist/`。
- 命令：`.venv/bin/python blender/build.py`（建模 + 烘焙 + 导出，约 1 分钟）；`--fast` 只看形（写到 `dist/fast/`，不覆盖 assets）；`--render-only out.png [--shot hero|nose] [--power 0|1]` 出 Cycles 渲染（不改 assets）。装法见 `docs/BLENDER.md`。
- 步骤：
  1. 坐标与网页相同：米，x 前、y 左、z 上，原点在转台轴心；站位 s 自机头尖向后，`at(s, y, z)`（`zl/util.py`，x = 9.5 − s）。
  2. **命名即接口**：每个零件一个对象，对象名 = 网页零件名；左侧 `.l`，右侧用 `mirror_object` 镜像出 `.r`（自定义属性照抄，记得改 `skin` / `joint`）。
  3. **自定义属性即元数据**（导出 `export_extras`，网页原样并进零件）：`skin`（线条蒙皮组，同组之间不出接缝线；机身蒙皮一律 `"skin"`）、`joint`、`system`（`"void"` 空腔）、`glass`、`glow: { key, color }`（自发光，见「选择性发光」）、`lineLevel: "secondary"`（细密重复件的线一律降为 L2：鳞片瓦、虹膜片）、`shadow: false`（不进投影）。材质槽名 = 网页材质表键（`hull` / `belly` / `carbon` / `glass` / `interior` / `sensor` / `void`）。
  4. 两个零件要“长在一起”、交线要成为真实折边的（眉骨、背部整流并进机身），用 `boolean(target, cutter)`（EXACT 并）；要单独成件、交界出一级结构线的（座舱盖、滑轨、鸭翼），单独成对象、底部嵌进机身 1～3 cm。
  5. 分割线、棱线、地标、遮线区写进 `meta`（→ `assets/zhulong.json`）：`seams` 用 `surface_point(s, facet, t, lift)` 在切面上取点、抬 2 mm、带法线；`level` 为 `"secondary"`（L2）/ `"structure"`（L1）/ `"accent"`（朱红棱线）。
  6. 改完跑 `node src/figure/build.mjs`，再截图（`scripts/z1-review.sh` 里有现成的命令）。
- 验收：四方位线稿里新零件不悬空、不穿插；4× 特写里交线清楚；`build.py` 输出的三角形数不超过预算（`docs/BLENDER.md`）。
- 常见错误：薄片零件离蒙皮只有几毫米、又在 20 cm 以内被线的深度让出量透出来（加 `masks`，见眼珠）；忘了镜像件的 `skin`（左右两件同名蒙皮组，中间的接缝线消失）；`--fast` 以为会更新 assets（不会）。

## 切面机身：位似放样（Z1 定）

- 适用于：烛龙机身、以及之后一切“大块精确切面”的蒙皮。
- 参考实现：`blender/zl/nose.py` 的 `REAR` / `FORE_APEX` / `NEEDLE` / `ring` / `section` / `body`；代码凸体版 `src/geometry/nose.mjs` 同名函数。
- 步骤：
  1. 截面只用几条棱线点（R0 背脊、R1 肩线、R2 棱线、R3 腹缘，腹底平面 R3–R3′）。
  2. 每一段（例：针段 s 0.16～1.1、前机身 s 1.1～7.2）给**后端截面 + 一个顶点**，段内任一站的截面 = 后端截面绕顶点按 (s − s顶点)/(s后 − s顶点) 缩放。这样同一段里所有棱线都是汇向顶点的直线，**每张切面严格是平面**——平面着色不出斜纹，五档明暗在一张切面上是一整块。
  3. 段与段在接缝站位换顶点，形成折线；折角 < 22° 时不出线，只有明暗的一档变化（“刀刃”的层次）。
  4. 切面上的细分（站位每 0.1 m、横向 3～4 格）只为顶点 AO 有足够的顶点，不改形状。
- 验收：体积模式下同一切面是一块均匀的色；切面交线笔直。
- 常见错误：两站截面各自给值、直线插值（相邻两条棱线不共面，切面变成扭曲面，平面着色出三角斜纹）。

## 画面链：多重采样、超采样、选择性发光（Z1 定）`[kit]`

- 适用于：一切画面输出。参考实现：`src/figure/engine/80-post.js`（`sizePost`、`renderFrame`、`renderAll`、`backdrop`）；数值在 build.mjs 的 `POST`。
- 做法：
  1. 场景画进多重采样离屏缓冲（`POST.msaa` = 4，带深度纹理）；网页高画质档在 DPR < 2 的屏上按 `POST.ssaa` = 2 倍画、合成时盒式下采样；手机标准档不超采样。
  2. **只让发光部件发光**：发光量是零件的属性（`glow: { key, color }`）乘通电量（`powerOf(key)`，由机构的 `power` 键驱动）。有东西在发光时，同一场景按“发光通道”再画一遍进半分辨率缓冲：带状材质只输出自发光、其余写黑但照常挡深度；朱红 accent 线层画发光色；普通线、光点、尾焰、投影不画。这张图两级模糊后叠回画面（`POST.bloom`）。所以亮的蒙皮不会泛光，被机体挡住的发光件也不泛光。
  3. 新发光件：几何母版里写 `glow`，build.mjs 的 `CONTROLS` 里加一个 `power: "<key>"` 的机构；不要在材质里直接调亮。
- 验收：`QA-glow-off/on`：未通电时画面与没有发光完全一样；通电后只有烛光窗与朱红棱线有晕，晕不超过线宽的十几倍。
- 常见错误：把发光做成材质颜色调亮（会被当成蒙皮的一档明暗，且不泛光）；发光缓冲不清黑。

## 线条的精确覆盖（Z1 定，抗锯齿）`[kit]`

- 参考实现：`30-lines.js` 的 `LINE_FRAG`：覆盖率 = 像素（宽 1）与线（宽 2·vHalf）在法向上的重叠长度（一维盒式滤波的精确积分）。
- 为什么：细于 1 像素的线（L1 0.5 px、L2 0.42 px）落在两个像素之间时，两像素覆盖率之和恒等于线宽，转动时亮度不随亚像素位置起伏。FIG.01 的近似式在 0.42 px 线上约 ±15% 起伏。
- 验收：`node src/figure/aa.mjs <目录>`：0.1° 一步慢转 8 帧、与 4× 超采样参照逐像素比（只算边缘与线条像素）。Z1 实测：FIG.01 式 2.85 / 闪烁 2.01 → 精确覆盖 0.87 / 0.94 → 加 2× 超采样 0.35 / 0.45（`AA.txt`）。

## 顶点 AO 与烘焙细节贴图（Z1 定）

- 参考实现：`blender/zl/bake.py`（`vertex_ao`、`detail_texture`）、`blender/zl/detail.py`（`paint`、`rivets_along`、`decal`、`dilate`）；网页 `10-materials.js` 的 `aAO`、`uDetail`。
- 做法：
  1. 顶点 AO：Cycles 烘到每个零件的颜色属性 `ao`（导出为 COLOR_0），只看 45 cm 以内（缝隙、内角）。网页里只压暗、不改明暗档（`FX.ao` 为强度）。空腔薄片（`system: "void"`）烘焙时藏起来，不当遮挡物。
  2. 细节贴图（机身蒙皮一张 2048²）：按角度展 UV → 烘每个纹素的世界坐标与法线 → numpy 程序生成：**r** 刻线压暗（铆钉只沿已有接缝两侧各一行；鳞片缝只在棱线以下）、**g** 涂装（机号、名字、警示三角，PIL 画字再按切面平面投影，右侧读向反过来）、**b** 贴图 AO。边缘外扩 6 圈防漏色。
  3. 细节疏密：铆钉、涂装只在已有结构旁；大面积蒙皮保持安静。新增涂装改 `detail.py` 的 `paint`，不手画贴图。
- 验收：`QA-ao-off/on`（体积模式 3×：眉骨下、座舱盖底边、鸭翼根有一层薄暗）；`QA-detail-off/on`（4×：铆钉行、口盖、机号可读，1× 不抢眼）。
- 常见错误：浮点烘焙图的 alpha 判断有效纹素（未烘到的也是 1，要用法线长度）；贴着蒙皮的薄片参与 AO（周围一圈黑斑）。

## 朱红棱线（accent 线，Z1 定）

- 参考实现：几何母版 `seams` 里 `level: "accent", accent: "chine"`；引擎 `30-lines.js` 的 accent 层；数值 `LINES.accents.chine`。
- 规则：线宽同主描边（0.75 px），色 `#c8412c`（偏暗不荧光），未通电只亮 `idle` = 0.38；机构 `chine`（通电量）与 `chine.sweep`（0…1 沿线从机头扫到末端，前沿多一小段亮）一起驱动；通电后进发光缓冲（发光色 `#ff5a32`）。化剑“开锋”在 Z5 用同一对机构。
- 常见错误：用材质色画朱红（转到背面也亮、不会扫）。

## 环境与背景（Z1 定）`[kit]`

- 参考实现：`90-page.js` 的 `setEnvironment` / `backdropSpec`、`80-post.js` 的 `backdrop`；数值 `ENVIRONMENTS`。
- 规则：机库段 `hangar`（冷灰）；太空 / 天门段 `space`：机体压暗 `dim`、台面更暗、背景两端渐变 + 稀疏星点（5 像素一格的哈希，星约 1 像素，不画光芒）+ 地球弧（屏幕坐标里的大圆、一条细的大气辉线 + 很淡的外晕，弧顶正好从转台边缘后面升起）。入轨演出用 `environment(name, mix)` 在两者之间过渡（Z5）。

## 电影画质（录制模式，Z1 定，网页版不开）`[kit]`

- 参考实现：`80-post.js` 的 `renderCinemaFrame`、合成着色器里的景深与调色；审图入口 `__arcseq.cinema(opts)`、`__arcseq.cinemaFrame({ dt, spin })`。
- 四项：超采样 `ssaa`（2～4）；**真实运动模糊**（一帧快门内推进 `blur` 个子帧，每个子帧完整走一遍 `advance` 再画，在半浮点缓冲里平均——转台、机构、尾焰都按真实运动模糊）；**特写景深**（`dof: { focus: 模型坐标点, range 米, coc 像素 }`，正交相机深度线性，泊松盘 16 点、按样本自己的弥散圈加权）；**调色**（暗部偏冷亮部偏暖、以 0.18 为支点的轻 S、暗角、1 LSB 颗粒；数值 `POST.grade`）。
- 用法：录制脚本先 `cinema({...})`，然后每帧 `cinemaFrame()`；截图用 drive 的 `shot`（不要再调 `view()`，它会按网页版重画）。
- 常见错误：景深范围太窄（机头一米外全糊，朱红线也糊掉）——机头特写 range 取 1.5～2.5 m。

## 审图截图（FIG.02 补充）

- 在 FIG.01「审图截图」的基础上：`shots.mjs --elevation <度>`（临时俯仰）；`--pre "__arcseq.focus('<地标>' | [x,y,z], 倍数)"`（特写取景：把模型坐标点放到画面中心，处理了不对称视锥）；`__arcseq.look({ ao, detail, bloom })`（逐项关开对照）；`__arcseq.environment('space')`。
- Z1 全部交审图由 `sh scripts/z1-review.sh` 一次生成。

## 模板：<做法名称>

- 适用于：哪些零件 / 哪类效果
- 参考实现：文件路径与函数名
- 步骤：1. … 2. … 3. …
- 验收：截图路径；必须满足的检查项
- 常见错误：…
