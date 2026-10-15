# 可复用的开源资源（2026-10-15 调研，已核实许可）

调研由三个子代理分头做（角色与服装 / 网页端 / Blender 硬表面），只收录核实过许可的条目。引入任何一项前，在 `THIRD_PARTY_NOTICES.md` 登记。

## 许可规矩

- **可以直接用、可以拷代码**：MIT、Apache-2.0、BSD、Zlib、ISC、CC0。CC-BY 资产要署名。
- **GPL 的 Blender 插件**（MPFB2、Tissue、Bolt Factory、3D-Print Toolbox、NodeToPython……）：只能当**外部工具**在构建时调用，**代码不拷进仓库、不 import 进我们的脚本、不进网页包**；它们生成的网格归我们。
- **不用**：AGPL（Theatre.js studio）、非商用（SMPL / SMPL-X 拓扑、Shadertoy 默认条款）、许可缺失或自相矛盾的（al1brn/geonodes、easy.panelling、explodeview）。
- **不用仿现有 IP 的资产**：MakeHuman suits02 资产包里的 rei_ayanami、spider-gwen、yoko_tsuno、hero_suit 等一律不用；Sketchfab「Aircraft Kit」许可冲突且非原创，只能当比例参考。

## 现在就采用

| 方向 | 资源 | 许可 | 解决什么 | 谁用 |
|---|---|---|---|---|
| 銜燭 · 服装 | **MakeClothes2 的 mhclo 绑定**（https://github.com/makehumancommunity/community-plugins-makeclothes） | MIT | 服装做成独立的干净低模（缝线是自己画的边环），每个顶点按身体最近 3 点的重心坐标 + 偏移跟随，权重插值继承，delete group 遮掉衣服下的身体——**根治胸肌腹肌透出、缝线锯齿** | 銜燭 X1 |
| 銜燭 · 服装 | MakeHuman CC0 紧身衣 `mc-skinsuit_2022` / `mc-bodysuit-2021`（suits02 资产包） | CC0 | 飞行服拓扑起点 | 銜燭 X1 |
| 銜燭 · 服装 | Blender 内置 Corrective Smooth（delta mush）、顶点组 Laplacian Smooth、Curve bevel / GN Curve to Mesh | 内置 | 抹平解剖细节；冷却管、脐带、织带扫出 | 銜燭 X1–X2 |
| 网页 · 线条 | **GPU 条件线**：r168 `LDrawLoader.js` 里的 `LDrawConditionalLineMaterial` 拷出来用，参考 gkjohnson/threejs-sandbox conditional-lines；屏幕空间描边兜底（OmarShehata/webgl-outlines） | MIT | 边线载入时生成一次，每帧由 GPU 判断轮廓——去掉剖视每帧 25 ms 的 JS 线分级 | 烛龙 Z1 尾 / Z3 |
| 网页 · 剖视 | r168 官方示例 `webgl_clipping_stencil`（模板封口）+ **three-mesh-bvh** `clippedEdges`（切口轮廓线） | MIT | 剖切封口与切口线；BVH 射线也用于标签遮挡判断 | 烛龙剖视模式 |
| 网页 · 后处理 | **pmndrs/postprocessing 6.39.x**（peer 明确支持 r168）+ **N8AO**（halfRes） | Zlib / CC0 | SMAA、选择性泛光、景深、LUT 调色、SSAO（“电影画质”与 B 画法） | 烛龙 Z1 尾 / Z6 |
| 网页 · 相机 | **camera-controls**（yomotsu） | MIT | 阻尼、机位间平滑过渡、`lerpLookAt`——六机位与观众接管视角（DESIGN 7.1） | 烛龙 Z6 |
| 网页 · 三视图 | **three-edge-projection**（gkjohnson，需 `npm i github:gkjohnson/three-edge-projection`） | MIT | 实时正交三视图的消隐线（PAGE_LAYOUT 右栏） | 烛龙 Z4 |
| 网页 · 资产 | **glTF-Transform**（meshopt / KTX2）+ **InstancedMesh2** / r168 `BatchedMesh` | MIT | 模型压缩、上千个重复件（鳞片瓦、铆钉）高效渲染 | Codex：二进制 GLB 直读 |
| 网页 · 性能 | stats-gl | MIT | 帧时间、GPU 计时 | 全程 |
| Blender · 布尔 | **manifold3d** / Blender 4.5+ 内置 Manifold 布尔求解器 | Apache-2.0 | 切缝、开口、进气口挖切更稳；化剑转轴开槽 | 烛龙 Z2 |
| Blender · 干涉检查 | `mathutils.bvhtree.BVHTree.overlap`（内置） | 内置 | 化剑每个关键姿态两两求交，写进 check 脚本（“收拢不穿模”验收） | 烛龙 Z2 |
| Blender · AO 提速 | 全部零件合并后一次烘焙 `VERTEX_COLORS` 再拆回；或在 Blender 外用 **Open3D RaycastingScene** / **trimesh + embreex** 多线程算逐顶点 AO | MIT / BSD-2 | 现在 1300 件逐件烘焙要 13 分钟 | 烛龙 |
| Blender · UV | **xatlas-python** 或 GN 内置 UV Unwrap / Pack UV Islands | MIT / 内置 | 几百个零件批量展开打包，不依赖 GUI 上下文 | 烛龙 |
| 材质 / 环境 | **Poly Haven API**、**ambientCG API v3** | CC0 | 构建时拉取 HDRI 与金属面板材质（B 画法的工作室环境光） | 烛龙 |

## 没有现成的（自己写）

- 程序化 greeble、管线走线、面板线 / 铆钉 / 口盖：好用的都是付费插件，许可不清的不用 → 继续用我们的参数化零件库（bmesh + 几何节点 + 布尔）。
- 3D 锚定编号引线：没有成熟库 → r168 `CSS2DRenderer` + SVG 引线 + three-mesh-bvh 遮挡判断。
- 尾焰马赫环、再入等离子鞘、磁力线、烛心等离子柱：自己写着色器（射线步进圆锥 + 噪声；磁力线用 `Line2`）。
- 现代硬壳飞行头盔：没有 CC0 可用的 → 在 bpy 里按 DESIGN 9.1.1 自己建。

## 暂缓（要先升级 three.js 或已停更）

- `@takram/three-atmosphere` / `three-clouds`（物理大气、太空视角地球边缘、体积云）：要求 three ≥ 0.170；云层很重，最多用于录制模式。
- `three.quarks`（粒子尾焰）：新版要求 ≥ 0.182，r168 只能锁 0.16.0。
- `realism-effects`（运动模糊、TRAA）：2023 年后停更，只考虑录制模式。
- 升级 three.js 本身是引擎级决定，等 Z6 做环境时再评估。
