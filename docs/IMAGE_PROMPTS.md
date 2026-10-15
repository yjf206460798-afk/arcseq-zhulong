# GPT 出图提示词

概念图只锁定剪影、比例和大构件位置；细节（眉骨、鳞片瓦等）以几何母版为准。出新图时把定稿三视图作为附件，并在开头写“Same aircraft as the attached three-view”。

## 已用

| 图 | 文件 | 提示词 |
|---|---|---|
| 剪影探索（选 C） | `refs/concept/C0_剪影探索_选定C.png` | P1 |
| 大气形态三视图初版 | `refs/concept/C1_大气形态三视图_初版.png` | P2（基于 C） |
| 大气形态三视图定稿 | `refs/concept/C2_大气形态三视图_定稿.png` | P3（在 C1 上改） |
| 剑形态三视图 | `refs/concept/C3_剑形态三视图.png` | P4 |
| 总布置图（侧视 + 俯视） | `refs/layout/L0_总布置图.png` | PL（第二版） |
| 发动机纵剖 | `refs/layout/E1_发动机纵剖.png` | PE1 |
| 发动机横剖 A-A / B-B / C-C | `refs/layout/E2_发动机横剖.png` | PE2 |
| 发动机爆炸图 | `refs/layout/E3_发动机爆炸图.png` | PE3 |
| 发动机三模式 | `refs/layout/E4_发动机三模式.png` | PE4 |
| 驾驶舱侧剖 | `refs/layout/K1_驾驶舱侧剖.png` | PK1 + 修改一轮 |
| 大气形态三视图 · 分色建模用图 | `refs/concept/C2_大气形态三视图_分色.png`（+ calib、叠图） | 建模用图 B |
| 剑形态三视图 · 分色建模用图 | `refs/concept/C3_剑形态三视图_分色.png`（+ calib、叠图） | 建模用图 B + C3 专用开头 |
| 飞行员服 · 分色建模用图 | `refs/concept/X1_衔烛设定图_分色.png`（+ calib、叠图） | 建模用图 C |
| 地台 · 天门弹射托架 | `refs/concept/S1_天门弹射托架.png` | PS1（取舍见 DESIGN 7.2「概念图」） |
| 飞行员服「銜燭」设定图 | `refs/concept/X1_衔烛设定图.png` | PX1（取舍见 DESIGN 9.1.1「概念图」） |

### P1 · 剪影探索
```
Concept design exploration sheet: 6 different top-view (planform) silhouettes of an ORIGINAL single-seat aerospace fighter, shown as solid black silhouettes on a white background, arranged in a 3x2 grid, each labeled A to F.

Shared design brief for all six: overall shape reads like a sword or arrowhead. Long, needle-sharp faceted forward body (about 40% of length) flowing via long chine strakes into a cranked double-delta wing; a wide, flat, heavy rear "engine block" carrying twin vertical tails and three exhaust outlets side by side. Strong contrast between the blade-thin front and the massive rear. Length about 19 m, span about 10.5 m.

Vary between the six: chine width, wing crank position, wingtip shape, tail placement, and the outline of the rear block. Every silhouette must be instantly recognizable even at thumbnail size. Original design: must not resemble any existing film, game or anime aircraft, nor any real aircraft.
```

### P2 · 三视图
```
Orthographic three-view technical drawing sheet (top, side, front) on ONE sheet, all views to the same scale and perfectly consistent, of the ORIGINAL single-seat aerospace fighter "Zhulong", based on silhouette C from the previous sheet. Dark charcoal background, thin light-gray linework, flat gray fills, museum-blueprint style.

Form language: upper surfaces made of large, precise flat facets with crisp ridge lines (no blobby curves); completely flat waverider underside. Proportions: very low profile, needle nose, blade-like front 40%, wide heavy rear engine block. Length 19 m, span 10.5 m, height about 3.4 m.

Key features:
- Nose tip: a small round sensor aperture with an iris shutter.
- Tiny low single-seat canopy set under a faceted "brow" ridge, with a track for a sliding metal heat shield.
- Small canards that retract into slots in the chine.
- Cranked double-delta wing; outer wingtips hinge downward.
- One wide, flat 2D air intake on the belly, split by a central divider, hidden under the flat underside.
- Twin outward-canted vertical tails on the rear block, hinged to fold inward flat.
- Rear: two rectangular 2D jet nozzles flanking a central linear aerospike rocket nozzle.
- Reaction-control thruster clusters on the nose and wingtips; a row of small dorsal thrusters and vents along the spine.
- Dorsal payload bay door.
- Belly fully covered in thermal tiles in a fine scale-like pattern; dark carbon leading edges.

Fine, sparse, functional panel lines, hinge lines and hatches only where parts actually open or move. Matte graphite; a single very thin vermilion line along each chine from nose to wingtip. Original design, not resembling any existing aircraft from films, games, anime or real life. No text except small view labels.
```

### P3 · 在 C1 上修改
```
Edit the attached three-view drawing. Keep EVERYTHING the same (planform, proportions, faceted surfaces, the thin red chine lines, colors, style, layout, the dorsal bay, nozzles, wingtip fins), and change ONLY the following:

1. FRONT view: remove the two large dark trapezoid openings beside the cockpit. The only air intake is the wide flat slot on the belly.
2. Add a small round sensor aperture at the very tip of the nose with a thin iris-shutter outline, visible in top and side views.
3. Add a sharp faceted "brow" ridge directly above and in front of the canopy, and a thin track line showing where a metal heat shield slides forward to cover the canopy.
4. Belly thermal tiles: change the hexagonal pattern into overlapping, staggered scale-shaped tiles (like fish or dragon scales, pointing rearward), fine and subtle.
5. Make the twin vertical tails consistent in all three views: they rise from the outer edges of the rear engine block, canted outward.

All three views must remain perfectly consistent with each other and to the same scale.
```
结果：1、2、5 改到位；3、4 未改（建模时自己做）。

### P4 · 剑形态
```
Same aircraft as the attached three-view ("Zhulong"), now shown in its transformed SWORD MODE, as a new three-view sheet (top, side, front) in the same style, scale and colors.

Transformation: the canards are stowed inside the chine slots; both main wings pivot fully rearward until parallel to the fuselage, and their outer panels fold downward to lie flush against the sides of the rear body, so the planform becomes a long, narrow blade; the wingtip fins fold flat; the twin vertical tails rotate outward to horizontal and stick out sideways from the rear block, forming the crossguard of a sword; the rear engine block reads as the grip, and the central aerospike cone reads as the pommel; a metal heat shield covers the canopy. The thin red chine lines now run continuously from the nose tip to the crossguard like a sharpened blade edge, faintly glowing.

From the top view the whole aircraft must clearly read as a straight sword (blade, crossguard, grip, pommel), while still being believable as the same machine with all parts accounted for. Original design, not resembling any existing transforming vehicle from films, games or anime.
```
结果：俯视、前视成立；侧视把剑格画成竖片（忽略）；主翼收拢关系未交代（Z1 自己设计）。

### PL · 总布置图（第二版）
原文未留存。第一版缺主翼、没画进气道、烛心正对镜头、风扇太靠前；第二版的修正要点：俯视图必须带 C2 的曲折双三角主翼与小鸭翼，画出翼根回转关节盒；两条进气道 Y 形汇入烛心，烛心轴线沿飞行方向、侧面看是短圆柱；风扇紧跟进气口。
结果：主翼、鸭翼、Y 形进气道、风扇位置、半躺座舱到位；烛心仍是正面圆盘、关节盒没画、图例重号（见 `refs/layout/README.md`）。

### PE1 · 发动机纵剖（附 C2 + L0）
```
Engineering cutaway drawing, LONGITUDINAL SECTION (side view, cut along the centerline) of the propulsion system of the original single-seat aerospace fighter "Zhulong" shown in the attached images. Show ONLY the engine bay and the fuselage skin around it as a thin outline; nose and cockpit may be cropped off to the left.

Front to back, label with clean numbered callouts 1–14, each number used once:
1 ventral intake with adjustable ramp, 2 S-shaped intake duct, 3 folding fan (drawn deployed, with its stowed position as a dashed outline in the duct wall), 4 Y-merge plenum, 5 annular injector ring with propellant feed line rising to 6 dorsal propellant tank, 7 the ring core "Zhulong Heart", 8 superconducting coil windings, 9 central heating channel, 10 battery banks around the core, 11 rotating diverter valve, 12 side rectangular 2D nozzle, 13 central plug nozzle, 14 coil ring exposed when the plug retracts (magnetic nozzle).

CRITICAL: the ring core's axis runs ALONG the flight direction. In this side section it is a short cylinder cut in half: two stacked rectangular blocks of coil windings (above and below), with a straight horizontal glowing channel passing through between them. Do NOT draw it as a round disk, oval, or face-on ring.

Style: dark blue-black background, industrial vector illustration, ultra-fine hierarchical linework in pale cyan-white, structural lines in muted blue-grey, a single restrained warm white-amber glow only inside the heating channel, one vermilion accent line on the core casing. Flat precise facets, no photorealism, no lens effects. Small scale bar in meters. Legend at bottom right. Small corner text "ARCSEQ / FIG.02". Original design, not based on any film, game, or existing IP.
```
结果：烛心剖面正确；喷口与进气道画成上下（以 E2 为准）。

### PE2 · 发动机横剖（附 E1 + L0）
```
Engineering drawing sheet: three CROSS SECTIONS (viewed from behind, looking forward) of the propulsion system of the original aerospace fighter "Zhulong", matching the attached longitudinal section. Top of the sheet: a small side-view key plan of the fuselage with three cut lines marked A-A, B-B, C-C. Below: the three sections side by side, same scale, each with a thin fuselage-skin outline (flat ventral waverider bottom, faceted upper surfaces, wing roots cropped).

A-A (at the fans): TWO intake ducts SIDE BY SIDE (left and right of centerline), each round with a folding fan seen face-on; slots in the duct walls where the fan blades stow; landing-gear bays below the ducts; dorsal propellant tank above.

B-B (through the middle of the core): concentric rings from outside in — fuselage skin; battery banks arranged around the core; superconducting coil windings in about 12 segmented blocks forming a ring; the central heating channel (inner diameter half the core's outer diameter, drawn dim); at the exact center a thin, brightest warm white-amber plasma column. The core is a ring seen face-on ONLY in this section.

C-C (at the exhaust): two rectangular 2D nozzles LEFT and RIGHT at the same height, with the central plug nozzle between them; diverter vanes visible as thin blades.

Label with numbered callouts using the SAME numbers as the attached longitudinal section (3 fan, 6 tank, 8 coil windings, 9 heating channel, 10 battery banks, 11 diverter valve, 12 side nozzle, 13 plug nozzle), plus 15 landing-gear bay, 16 plasma column. Each number used once per section.

Style: dark blue-black background, industrial vector illustration, ultra-fine hierarchical pale cyan-white linework, muted blue-grey structural lines, glow ONLY at the plasma column and faintly in the channel, one vermilion accent line on the core casing. Flat precise facets, no photorealism. Scale bar in meters, legend at bottom right, corner text "ARCSEQ / FIG.02". Original design, not based on any film, game, or existing IP.
```
结果：左右关系与同心层次正确；截面偏胖、比例尺不可信。

### PE3 · 发动机爆炸图（附 E1 + E2）
```
Engineering EXPLODED VIEW of the propulsion system of the original aerospace fighter "Zhulong", matching the attached longitudinal and cross sections. Three-quarter view from above-left-rear, components pulled apart ALONG the flight axis, connected by thin dashed assembly lines. Fuselage omitted except a faint ghosted outline.

Front to back: intake ramps and the two side-by-side S-ducts each with its folding fan (one fan shown with blades folded into its wall slots); Y-merge plenum; annular injector ring with its feed line to the dorsal tank (tank lifted above); the core "Zhulong Heart" with its outer casing split into upper and lower halves and lifted apart to reveal about 12 segmented coil blocks; battery banks pulled RADIALLY outward around the core; rotating diverter valve; the two rectangular side nozzles pulled LEFT and RIGHT; the central plug nozzle pulled backward, revealing the coil ring behind it.

Use the same numbered callouts as the attached sheets (3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14), each number used once.

Style: dark blue-black background, industrial vector illustration, ultra-fine hierarchical pale cyan-white linework, muted blue-grey structural lines, a faint warm glow only on the exposed coil segments and the plasma channel, one vermilion accent line on the core casing halves. Flat precise facets, no photorealism. Legend at bottom right, corner text "ARCSEQ / FIG.02". Original design, not based on any film, game, or existing IP.
```
结果：拆分方式可直接作为「开心」交互的零件划分；自带口号要裁掉。

### PE4 · 发动机三模式（附 E1～E3）
```
Engineering diagram sheet: THREE OPERATING MODES of the "Zhulong" propulsion system, stacked as three horizontal panels, each a simplified TOP-VIEW plan section of the engine bay (two side-by-side ducts, core, diverter, two side nozzles, central plug), same scale, same position. Flow drawn as fine streamlines whose color shifts from pale cyan (cold intake air) to warm amber (heated exhaust).

Panel 1 "AIR-BREATHING · 0–2.5 MACH": intake ramps lowered, both fans deployed and spinning, air passes through the core's heating channel (moderate glow), diverter routes flow to the TWO SIDE nozzles; plug nozzle closed and dark.

Panel 2 "RAM · 2.5–6 MACH": fans folded into duct walls, ramps steepened, air flows straight through the core (stronger glow), exits through the two side nozzles, which are narrowed.

Panel 3 "ROCKET · VACUUM": intake doors closed flush, propellant line from dorsal tank active, core at maximum glow, side nozzles closed, plug retracted exposing the coil ring, single exhaust plume from the CENTER only, shaped by a faint magnetic-nozzle field outline.

Small mode label and a 3-item status line on each panel (e.g. "FANS DEPLOYED / RAMPS DOWN / SIDE NOZZLES"). Style: dark blue-black background, industrial vector illustration, ultra-fine pale cyan-white linework, muted blue-grey structure, glow only in the core and exhaust, one vermilion accent on the core casing. Flat, no photorealism. Corner text "ARCSEQ / FIG.02". Original design, not based on any film, game, or existing IP.
```
结果：三模式与出口数变化正确；两侧多画了长罐，自带口号要裁掉。

### PK1 · 驾驶舱侧剖（附 C2 + L0），再在结果上修改一轮
初稿要点：机头到座舱后约 10 m 的侧剖，编号 1～14（光窗虹膜、传感器组、机头姿控喷口、航电舱、眉骨、遮光盾收起 / 合上两态、低座舱盖、半躺 30° 的飞行员与弹射座椅、平视显示器、环形屏幕墙、侧杆 / 油门、头顶开关板、前起落架舱），座舱盖低于眉骨线。
修改轮要点：座舱盖做成看得见的低矮切面玻璃、透出头盔；眉骨前凸；遮光盾实线收在眉骨里、虚线盖住座舱盖并画滑动箭头；弹射弧线从座椅正上方起；座椅再后仰；修正 11 / 13 / 7 的指向。
结果：内部排布可用；外部座舱盖 / 眉骨关系仍不准，以几何母版为准。

## 待用（可选，不影响开工）

### 建模用图（在已定稿的参考图上做图片编辑，配合 WORKFLOW「拆图」）

每次只附一张图、只编辑一张。三套固定配色（拆零件表的脚本按这三张色表认颜色，**不要改**）：

**A · 内部图**（K1、L0、E1、E2、E4；E3 可选）
```
Edit the attached drawing into a flat MODELING REFERENCE with exactly the same content, composition and part positions. Do not move, resize, add or remove any part. Keep every view and panel of the sheet in the same place and size (main views, small inset views, section panels).

Remove all text, titles, numbers, numbered callouts, leader lines, legend boxes, scale bars, dashed motion paths, arrows, flow streamlines and decorative thumbnails. Remove all glows, reflections, gradients and shading.

Draw every part as a flat solid fill with a thin black outline, color-coded by type:
- fuselage skin, structural frames, floors and brackets: light gray
- boxes, electronics, avionics, batteries and tanks: green
- air intake ducts and plenums: pale blue
- pipes, hoses and cable bundles: blue
- mechanisms, actuators, hinges, rails, valves and doors: orange
- engine core casing and coil windings: red
- fans and any rotating blades: pink
- nozzles and the central plug: dark gray
- seat, pilot and helmet: purple
- glass and displays: cyan
- glowing elements (sensor window, plasma channel, lights): yellow
- wheels and landing gear: brown

Pure white background. Strictly orthographic, no perspective. Keep the image size and framing identical to the original.
```

**B · 外形图**（C2 大气形态三视图、C3 剑形态三视图）
```
Edit the attached three-view drawing into a flat MODELING REFERENCE with exactly the same views, composition, outlines and part positions. Do not move, resize, add or remove any part; keep the top, side and front views in exactly the same places and sizes.

Remove all text, labels, dimension lines, panel lines, rivets, scale patterns, glows, reflections and shading. Draw every part as a flat solid fill with a thin black outline, color-coded:
- main fuselage body and engine block: light gray
- main wings: green
- canards: dark green
- vertical tails and wingtip fins: blue
- canopy glass: cyan
- brow ridge and heat-shield track: purple
- intake opening and intake doors: orange
- nozzles and the central plug: dark gray
- nose sensor eye: yellow
- the thin chine line: red (keep it as a thin line)
- belly thermal-tile area (as one flat region, no tile pattern): brown
- hinge and fold lines of moving parts: thin black dashed lines

Pure white background. Strictly orthographic. Keep the image size and framing identical to the original.
```

**C · 人物与服装**（X1 銜燭设定图）
```
Edit the attached suit concept sheet into a flat MODELING REFERENCE with exactly the same figures, panels, poses and part positions. Do not move, resize, add or remove anything; keep every panel (soft mode, armored mode, helmet details, exploded layers, connector close-up) in the same place and size.

Remove all text, titles, numbers, callouts, legends, the name logo and the small aircraft drawing. Remove all glows, reflections, gradients and shading. Draw every part as a flat solid fill with a thin black outline, color-coded:
- base suit fabric: light gray
- anti-G bladders: green
- harness and straps, buckles: orange
- scale plates: blue
- helmet shell: purple
- visors: cyan (clear visor) and yellow (gold sun visor)
- the spine line: red
- umbilical connector, hoses and boots: brown
- liquid-cooling tube network: pale blue
- face and exposed skin: white

Pure white background. Strictly orthographic. Keep the image size and framing identical to the original.
```

**C3 剑形态专用开头**（B 段前面加这一段，否则 GPT 容易拿上一张大气形态的图当底图）：
```
The attached image is the SWORD MODE three-view of the aircraft: a long, narrow blade-like body with NO spread wings. The main wings are folded back flush against the sides of the rear body, and the two tails stick out sideways near the rear as a horizontal crossguard. If your output shows spread wings or upright tails in the top view, it is wrong — use ONLY the attached image as the base.
```
剑形态配色在 B 表基础上改：折叠后的主翼（贴在后机身两侧的窄带）绿、剑格（转平的两片垂尾）蓝、盖住座舱的遮光盾紫、前视两块闭合进气门橙；不出现鸭翼和座舱玻璃。

**每张图新开一个 GPT 对话、只附那一张**：同一对话里做图片编辑，GPT 常拿它上一张生成图当底图。

用法：出图后由 Claude 与原图做 50% 叠图和锚点标定（`<图名>_分色.calib.json`），锚点残差都 ≤ 2% 画幅才用；画幅被改过就按轴分别换算（见 K1 的 calib）。

### P5 · 主视觉
```
Same aircraft as the attached three-view: the "Zhulong" aerospace fighter, three-quarter top-down isometric view, parked on a dark circular hangar turntable, background #101518. Industrial technical illustration: crisp thin outlines, soft four-tone flat shading on faceted surfaces, very fine panel lines, small red (left) and green (right) navigation lights, a faint warm amber glow in the nose sensor aperture. Calm, precise, premium, like a museum exhibit poster. Not a game render, no lens flares, no dramatic effects.
```

### P6 · 双形态对比
```
Same aircraft as the attached three-views, two states side by side in the same isometric view and style: LEFT atmosphere mode (canards out, wings spread, canopy visible, tails canted up); RIGHT sword mode (as in the sword-mode three-view: wings folded back flush, tails flat as a crossguard, heat shield over the canopy, red chine edges faintly glowing). Dark hangar turntable, industrial illustration style.
```

### PX1 · 飞行员服「衔烛」设定图（附 K1；软态 + 披甲态 + 分层）
```
Character equipment concept sheet for an ORIGINAL aerospace pilot suit named "Xianzhu" (銜燭), worn by the single pilot of the "Zhulong" aerospace fighter (cockpit section attached for context). One sheet, dark blue-black background, industrial vector illustration, ultra-fine hierarchical pale cyan-white linework, muted blue-grey structural lines, flat precise shading, no photorealism. A real engineered suit, slim and practical, NOT a superhero armor and NOT bulky.

Layout:
TOP ROW — the suit in SOFT MODE (inside the atmosphere), orthographic FRONT, SIDE and BACK views of a standing pilot, same scale: a close-fitting matte graphite flight suit with anti-G bladders on thighs and abdomen, harness straps, a chest-side umbilical connector, a helmet with a clear visor raised slightly. A single thin vermilion line runs down the center of the back from helmet base to waist (unlit, dark red).
MIDDLE ROW — the same suit in ARMORED MODE (outside the atmosphere): FRONT and SIDE views. The suit is pressurized and stiffer; small overlapping scale plates (pointing downward, like dragon scales, fine and subtle) are locked over the shoulders, forearms and along the spine; the gold sun-shield visor is lowered over the clear visor; the vermilion back line now glows softly.
RIGHT COLUMN — HELMET detail in two states side by side: "OPEN EYE" clear visor; "CLOSED EYE" gold visor down, with a faint wireframe synthetic-vision display visible on the inside.
BOTTOM ROW — EXPLODED LAYERS from inside out, pulled apart along a vertical axis with thin dashed assembly lines: 1 liquid-cooling undergarment with a fine tube network, 2 anti-G bladder layer, 3 restraint layer, 4 scale-armor outer layer, 5 double-visor helmet; plus a small close-up of 6 the umbilical connector (oxygen, cooling, power, data) plugging into the seat.

Numbered callouts 1–6, each used once, small legend at bottom right. Small text "銜燭" on the left chest patch. Corner text "ARCSEQ / FIG.02". No slogans or other text. Original design: must not resemble any suit, armor or pilot outfit from films, games, anime or comics.
```

### PS1 · 地台：天门弹射托架（附 C2 定稿三视图）
```
Concept design sheet for an ORIGINAL launch cradle and stage for the "Zhulong" aerospace fighter (attached three-view), set inside a launch bay on an orbital megastructure 100 km above the Earth. One sheet, dark blue-black background, industrial vector illustration, ultra-fine hierarchical pale cyan-white linework, muted blue-grey structural lines, flat precise shading, no photorealism.

The stage: a round rotating turntable set into the start of a long electromagnetic launch rail. Two parallel rails with a row of coil segments between them run forward from the turntable toward a giant two-leaf airlock door. On the turntable sits a launch sled that holds the aircraft with four clamp arms (two front, two rear), a power umbilical plugged into the belly, and a blast deflector behind the tail. Floor markings: center line, alignment marks and a bay number plate with the small text "天門 · 四層 · 彈射位 3".

Layout:
TOP — a large three-quarter view from above-left: the aircraft (as in the attached three-view, parked, canopy open) on the sled, the turntable rotated to align with the rail, the rail stretching to the closed airlock door; cool white bay lights along the rail; the coil segments unlit.
MIDDLE LEFT — TOP VIEW of the turntable and the first part of the rail with the sled (aircraft drawn as a thin outline only).
MIDDLE RIGHT — SIDE VIEW of the sled with clamp arms closed and open, the umbilical attached and released.
BOTTOM — three small frames of the launch: 1 turntable aligned, clamps released; 2 airlock door opening onto black sky, stars and the curved Earth below; 3 coil segments lighting up in sequence from cyan to vermilion as the sled accelerates.

Restrained colors: only the bay lights (cool white), the coils (cyan / vermilion) and a thin vermilion accent on the sled. Corner text "ARCSEQ / FIG.02". No slogans or other text. Original design, not based on any film, game, anime or existing IP.
```

### P7 · 彩蛋剪影（机甲构思到剪影层之后再用）
留空，待构思。

### G1～G5 · 给 Tripo 用的干净单件图（2026-10-15，配合 WORKFLOW「AI 起稿」）

每张单独开新对话，上传从 X1 设定图裁出的参考（`refs/ai_draft/` 里对应的 `*_GPT.png` 是结果）。共同的结尾“通用要求”：

> 通用要求：这张图要喂给图生 3D 模型软件，所以单个主体、完整入画、居中、四周留白；纯浅灰背景，无地面、无阴影、无文字、无标注、无编号、无边框、无参考线；柔和均匀的工作室布光，不要强高光、辉光、反射和景深模糊；真实感三维渲染风格（不要线稿和插画），结构清晰、边缘利落；1:1 方图（全身用 2:3 竖图），高清。

- **G1 头盔（闭眼）修正**：保留分块硬壳、分缝小模块、头顶细天线、两侧铰链、镀铬颈环、盔脊暗朱红细线；加盔顶前凸眉骨，面罩收窄成环绕的横向宽带（高度约原来一半），深烟色琥珀（暗、半透，不是金色镜面），去掉面罩图案；避免像知名游戏 / 电影的装甲头盔；左前 35° 的 3/4 略俯视，只画头盔与颈环。→ 下一版：去掉护颌，下半脸换成氧气面罩 + 软管。
- **G2 披甲态全身**（附 G2 参考 + G1 结果）：保留肩、上臂、前臂、脊背、大腿外侧、小腿前侧的人字形鳞甲，胸前挽具与腰带扣，黑护膝，靴，脊背暗朱红线，左胸脐带接口；去掉胸前文字；A 字站姿正面；身形中性。
- **G3 第 1 层液冷内衣**：见下方“重画版”。
- **G4 第 2 层抗荷气囊层**：浅灰连体服，腹部左右、两大腿前侧各两块、两小腿前侧各一块气囊贴片（略鼓、带缝线），两侧调节束带；无肌肉起伏，不画头，A 字站姿正面。
- **G5 脐带接头**：矩形金属快接本体 + 快拆扳手，一侧并排 4 个接口各插一小截短软管（蓝冷却、黑数据、两灰氧气 / 电源），一道暗朱红标记；前侧 3/4 略俯视，只这一个物件。
- **G3 重画版**：一件贴身连体液冷内衣（带手套、袜套、高领），穿在一个**完全光滑、没有任何肌肉起伏的中性人台**上（像服装店的哑光人台，胸、腹、大腿都是平滑曲面）；冷却细管**沿平行直线**排布——四肢上是纵向平行的直管，躯干上是等间距的水平平行管，在身体两侧用竖直总管连接，**管线不得勾勒出胸肌、腹肌或任何肌肉轮廓**；哑光蓝灰；不画头；A 字站姿正面。

### PC4 · 大气形态 3/4 斜视（气质参照，附 C2 定稿三视图，2026-10-15）

> 附图是我原创空天战机「烛龙」大气形态的定稿三视图。请画出同一架飞机的一张 3/4 斜视立体图，作为建模的整体气质参照。视角：左前上方，水平方位约 30°、俯视约 30°，整机完整、居中，机头朝左下。外形以三视图的俯视和侧视为准（长三角剑形机身、鸭翼、大后掠主翼、外倾双垂尾、下垂的翼尖小鳍、尾部两侧矩形喷口夹中央塞锥、腹底扁宽进气口）。机身修长扁平：后机身截面是压扁的六边形（平顶 + 大斜肩 + 平腹底），宽约为高的 2.5 倍，最厚处约全长 9%，侧面从座舱往后上下沿都收向尾部，主翼薄。细节：机头圆形传感器“眼珠”（虹膜叶片合拢成尖盖）、座舱上方前凸的眉骨、暗朱红细棱线从机头到主翼前缘转折、机腹前后错叠的深色鳞片防热瓦、上表面精确大切面。哑光石墨灰，机腹更暗偏冷。深蓝黑渐变背景，柔和工作室光，真实感三维渲染，无文字标注，16:9。不要像任何现有电影、游戏或动画里的飞行器。

结果 `refs/concept/C4_大气形态斜视_气质参照.png`：比例与气质采信；翼尖鳍方向、配色、喷口排布、眉骨不采信（DESIGN 8.1 #15）。
