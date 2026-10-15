// FIG.02 烛龙 · 机库转台页面：作品数据（几何来源、色板、线条、特效、机构、演出、文字）→ 引擎（src/figure/engine/）→ dist/<名>.html（单文件）。
//   node src/figure/build.mjs                         → dist/index.html（几何母版，Z1 起为机头段 look-dev）
//   node src/figure/build.mjs --variant=empty         → 空场景（只有转台，Z0 验收）
//   node src/figure/build.mjs --variant=hull --out=dist/hull.html   → 同一段机头的“代码凸体”做法（Z1 路线比较）
// 页面模式：silhouette（灰色剪影）、volume（只有明暗）、lines（明暗 + 线条）。
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { engineScript, fitView, pageHtml, pointsOf, r4 } from "./engine/pack.mjs";
import { glbParts } from "./engine/glb.mjs";
import { packMesh } from "./engine/meshpack.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = join(HERE, "..", "..");
const argv = process.argv.slice(2);
const option = (name, fallback) => argv.find((a) => a.startsWith(`--${name}=`))?.slice(name.length + 3) ?? fallback;
const VARIANT = option("variant", "glb");
/** --assets=dist/fast：用 blender/build.py --fast 的产物预览（不烘焙）。 */
const ASSETS = join(ROOT, option("assets", "assets"));
/**
 * 画法（作者 2026-10-15 定）：默认 metal = B 金属质感（工作室环境光 + 烘焙的法线 / 粗糙度贴图，线条降一级），
 * 页面上「图纸」按钮在运行时切到 A（线条 + 五档明暗）；--look=lines 出只有 A 的页面（不带 B 的贴图，小一些，审图用）。
 */
const LOOK = option("look", "metal");
/** --stress=N：常驻外形重复 N 份（同一位置），只为实测面数预算（docs/BLENDER.md），不用于发布。 */
const STRESS = Number(option("stress", 1));

/** 舞台画幅（CSS 宽高比 1000 : 670）与相机俯仰 30°（FIG.01 定，固定审图机位 30°/120°/210°/300°）。 */
const VIEW = { width: 1000, height: 670 };
const ELEVATION = Number(option("elevation", 30));

// ———————————————— 几何来源 ————————————————
/**
 * glb：Blender 建模脚本 blender/build.py 的产物 assets/zhulong.glb（零件）+ assets/zhulong.json（分割线、棱线、地标、关节、细节贴图）。
 * hull：src/geometry/nose.mjs 的代码凸体（FIG.01 做法），只为 Z1 路线比较保留。
 * empty：空场景。
 */
async function geometry() {
  if (VARIANT === "empty") return { parts: [], seams: [], landmarks: {}, joints: [], offset: [0, 0, 0], detail: {} };
  if (VARIANT === "hull") {
    const { buildNose } = await import("../geometry/nose.mjs");
    return buildNose();
  }
  const glb = join(ASSETS, "zhulong.glb");
  const meta = join(ASSETS, "zhulong.json");
  if (!existsSync(glb)) throw new Error("assets/zhulong.glb 不存在：先运行 .venv/bin/python blender/build.py");
  const M = JSON.parse(readFileSync(meta, "utf8"));
  const detail = {};
  for (const [name, spec] of Object.entries(M.detail ?? {})) {
    if (spec.look && spec.look !== LOOK) continue; // B 画法的贴图只进 B 版页面
    detail[name] = { ...spec, src: `data:image/png;base64,${readFileSync(join(ASSETS, spec.file)).toString("base64")}` };
  }
  // 零件与母版硬边一起打成量化网格包（engine/meshpack.mjs），浏览器端 engine/05-glb.js 解
  const one = glbParts(glb);
  const ext = STRESS > 1 ? Array.from({ length: STRESS }, (_, k) => one.map((p) => ({ ...p, name: k ? p.name.replace(/(#\d+)?$/, (m) => `~${k}${m}`) : p.name }))).flat() : one;
  const interiorGlb = join(ASSETS, "zhulong-interior.glb");
  const inner = existsSync(interiorGlb) ? glbParts(interiorGlb) : [];
  const edgeOf = (name) => M.edges?.[name.split("~")[0]] ?? null;
  return {
    parts: [],
    fitParts: ext,
    mesh: { pack: packMesh(ext, edgeOf) },
    modules: inner.length ? { interior: { pack: packMesh(inner, edgeOf), seams: M.interiorSeams ?? [] } } : {},
    tris: { exterior: ext.reduce((n, p) => n + p.f.length / 4, 0), interior: inner.reduce((n, p) => n + p.f.length / 4, 0) },
    seams: M.seams ?? [], landmarks: M.landmarks ?? {}, joints: M.joints ?? [], controls: M.controls ?? [], offset: M.offset ?? [0, 0, 0], detail, focus: M.focus, masks: M.masks ?? [], callouts: M.callouts ?? [],
  };
}
const G = await geometry();

// ———————————————— 配色卡（VISUAL_TARGET「烛龙配色卡」，Z1 look-dev 定） ————————————————
/**
 * 明暗：光随相机（从画面左上方来），n·L 按阈值分五档，档间 smoothstep，档内单色（FIG.01 G2 规则不变）。
 * 切面机身用 [0, .4, .64, .8]，与 FIG.01 机体相同。
 */
const SHADE = {
  hull: { bands: [0, 0.4, 0.64, 0.8], soft: 0.07 },
  facet: { bands: [0, 0.36, 0.6, 0.8], soft: 0.045 },
  round: { bands: [0, 0.2, 0.42, 0.62], soft: 0.035 },
  deck: { bands: [0, 0.2, 0.42, 0.62], soft: 0.035 },
};
/**
 * 色板（五档，暗 → 亮，sRGB 原值）。主色哑光石墨灰；辅色：机腹鳞片更暗偏冷、前缘碳-碳最暗；玻璃深茶。
 * 唯一底线：转灰度后分区与体积仍读得出（每轮先看灰度）。
 */
const PALETTE = {
  /** 复刻样板复测停机全景：机体对台面明度比 1.39 → 约 1.7（提一档；仍是 A1 那种低反差） */
  body: ["#272b2e", "#2f3336", "#373b3e", "#3f4447", "#484d50"],
  belly: ["#1d2126", "#22272c", "#272d32", "#2d3339", "#343a40"],
  carbon: ["#141618", "#17191b", "#1a1c1e", "#1e2022", "#232527"],
  glass: ["#0f1215", "#12161a", "#161b20", "#1b2127", "#232a31"],
  interior: ["#15181a", "#181b1d", "#1b1f21", "#1f2325", "#24282a"],
  sensor: ["#120d0a", "#16100b", "#1b130d", "#21170f", "#281c12"],
  /** 座舱盖框、滑轨：比机身略暗的金属 */
  frame: ["#1c1f21", "#212426", "#26292b", "#2c2f31", "#323538"],
  /** 小件金属（接头、滚轮座、格栅）与镀铬（活塞杆、探头管）、橡胶（密封圈、轮胎） */
  metal: ["#202426", "#272b2e", "#2f3336", "#373b3e", "#41464a"],
  chrome: ["#2a2f33", "#343a3e", "#40464b", "#4d5459", "#5c646a"],
  rubber: ["#0e0f10", "#111213", "#141516", "#17181a", "#1b1c1e"],
  iris: ["#3e4448", "#484e52", "#53595e", "#5f666b", "#6c7378"],
  vermilion: ["#4a1a14", "#5a1f17", "#6b251b", "#7d2b1f", "#8f3224"],
  stand: ["#0f1315", "#121618", "#15191b", "#181c1f", "#1c2023"],
  /** 内部（剖视）：结构框偏亮、设备箱暖灰、管线冷灰、线束暗、罐体浅；屏幕与座椅、压力服。R3：按 K1 的中灰提亮（A 的箱面原来暗到和底色分不开）；B 的增益同步降，B 画面不变 */
  structure: ["#353a3c", "#3d4244", "#464b4e", "#4f5558", "#5a6063"],
  avionics: ["#33332f", "#3b3b36", "#44443e", "#4d4d46", "#57574f"],
  panel: ["#2a2b29", "#30312e", "#363734", "#3d3e3b", "#444542"],
  pipe: ["#2a3134", "#323a3e", "#3b4448", "#444e52", "#4e595e"],
  cable: ["#161819", "#1a1c1d", "#1e2021", "#222526", "#272a2b"],
  tank: ["#2f3437", "#373d40", "#40474a", "#4a5155", "#555d61"],
  screen: ["#0c1417", "#0f191c", "#121e22", "#162428", "#1a2a2f"],
  seat: ["#1d1f20", "#222425", "#28292b", "#2d2f31", "#333537"],
  suit: ["#28292a", "#2f3031", "#363839", "#3e4042", "#47494b"],
  /** 銜燭软态：抗荷气囊贴片（比服装略浅、略冷）、挽具织带（更暗）、收起的遮光面罩（暗琥珀，不是镜面金） */
  pad: ["#2c2f31", "#333638", "#3b3e41", "#43474a", "#4c5053"],
  strap: ["#161718", "#1a1b1c", "#1e1f21", "#232426", "#28292b"],
  visor: ["#3a2610", "#472f14", "#553919", "#63431e", "#734f24"],
  /** 胸前铭文「銜燭」：浅灰小字 */
  inscription: ["#7d8688", "#8b9496", "#99a2a4", "#a7b0b2", "#b5bec0"],
  /** 剖视背景板（舱壁）：比结构件暗，只当底 */
  backwall: ["#1e2427", "#232a2d", "#283033", "#2e363a", "#343d41"],
  /** 剖视远侧内壁壁板与座舱侧壁（K1 的浅灰内衬，R4）：比设备箱浅、比剖面带暗 */
  liner: ["#3d4447", "#454c50", "#4e565a", "#575f63", "#61696d"],
  helmet: ["#3a3d3e", "#434748", "#4d5152", "#575b5d", "#626768"],
  section: ["#56605f", "#5d6766", "#646e6d", "#6b7574", "#727c7b"],
  /** 铭牌（设备箱上的浅色小牌）、警示件（弹射拉环等，暗琥珀） */
  label: ["#3c403f", "#434746", "#4a4e4d", "#525655", "#5a5e5d"],
  hazard: ["#3a2a14", "#453217", "#513a1b", "#5d431f", "#6a4c23"],
  inside: "#141c21",
  deck: ["#111619", "#13181b", "#151b1e", "#182023", "#1b2124"],
  bump: "#0a0c0d",
  lip: "#3a3f43",
  mouth: ["#1a1d20", "#050607"],
  silhouette: "#8d999e",
};
/** 材质表：名 → 色板键 + 明暗键 + 选项（glint 玻璃反光、mouth 空腔、detail 细节贴图名、glow 自发光）。 */
const MATERIALS = {
  hull: { tones: "body", shade: "facet", detail: G.detail.skin ? "skin" : undefined },
  belly: { tones: "belly", shade: "facet", detail: G.detail.skin ? "skin" : undefined },
  carbon: { tones: "carbon", shade: "facet" },
  glass: { tones: "glass", shade: "hull", glint: true },
  interior: { tones: "interior", shade: "hull" },
  sensor: { tones: "sensor", shade: "hull" },
  void: { tones: "body", shade: "hull", mouth: true },
  round: { tones: "body", shade: "round" },
};
for (const k of ["frame", "metal", "chrome", "rubber", "iris", "vermilion", "stand", "structure", "avionics", "panel", "pipe", "cable", "tank", "screen", "seat", "suit", "pad", "strap", "visor", "inscription", "helmet", "section", "label", "hazard", "backwall", "liner"]) MATERIALS[k] = { tones: k, shade: ["metal", "chrome", "rubber", "pipe", "cable", "tank", "helmet", "suit", "pad", "strap", "visor"].includes(k) ? "round" : "facet" };
/** B 画法的材质参数：[金属度, 粗糙度, 基色增益]（基色取色板第 4 档，换到线性空间再乘增益）。 */
const PBR = {
  hull: [0.8, 0.34, 0.75], belly: [0.6, 0.4, 2.4], carbon: [0.2, 0.35, 2.4], glass: [0.0, 0.05, 1.0], interior: [0.3, 0.55, 4.0], sensor: [0.0, 0.08, 1.6],
  void: [0.2, 0.6, 1.0], round: [0.5, 0.45, 3.0], frame: [0.7, 0.35, 3.2], metal: [0.85, 0.3, 4.5], chrome: [1.0, 0.12, 3.5], rubber: [0.0, 0.8, 2.2],
  iris: [0.75, 0.32, 2.4], vermilion: [0.2, 0.4, 1.7], stand: [0.5, 0.5, 2.0], structure: [0.75, 0.36, 3.1], avionics: [0.45, 0.42, 3.6], panel: [0.4, 0.45, 2.4],
  pipe: [0.85, 0.3, 3.45], cable: [0.1, 0.65, 3.0], tank: [0.85, 0.28, 4.5], screen: [0.0, 0.1, 1.5], seat: [0.25, 0.6, 4.5], suit: [0.05, 0.72, 1.3], pad: [0.08, 0.62, 1.7], strap: [0.05, 0.75, 3.0], visor: [0.6, 0.15, 2.0], inscription: [0.2, 0.5, 1.6],
  helmet: [0.35, 0.3, 2.2], section: [0.6, 0.4, 2.0], label: [0.1, 0.5, 3.5], hazard: [0.2, 0.5, 3.0], backwall: [0.3, 0.7, 0.65], liner: [0.25, 0.62, 1.2],
};
for (const [k, m] of Object.entries(MATERIALS)) {
  m.pbr = PBR[k] ?? [0.3, 0.5, 2.4];
  if (m.detail === "skin" && G.detail.skinPbr) m.pbrMap = "skinPbr";
}
// 剖视远侧内衬：K1 的浅灰壁板近乎平光（朝下的远侧屋面也是浅灰），按 0.85 混向平光
MATERIALS.liner.fill = 0.85;
// 机腹（下切面、腹底、鳞片瓦）朝下，工作室环境的地面是暗的，B 里会比地台还暗、鳞片瓦读不出（R4 独立审图）：补 0.6 的平光
MATERIALS.belly.fill = 0.6;
// 光窗虹膜叶片（亮钛）：在烟晶角膜后面、眼球腔里，补 0.4 平光才读得出叶片（R4）
MATERIALS.iris.fill = 0.4;
/**
 * 线条分级（FIG.01 G2，VISUAL_TARGET：L0 0.6～0.9 / L1 约 0.5 / L2 0.35～0.5 px）。
 * accents：作品标志色的线（朱红棱线）：线宽同主描边、偏暗不荧光；idle 为未通电时的亮度（三四成），通电后由机头沿线点亮并进发光缓冲。
 */
const LINES = {
  width: [0.9, 0.55, 0.35],
  color: ["#b9c7cb", "#7d939c", "#7d939c"],
  alpha: [0.78, 0.6, 0.3],
  bias: 0.02,
  contourBias: 0.2,
  accents: { chine: { color: "#c8412c", width: 0.75, alpha: 0.95, idle: 0.38, glow: "#ff5a32", key: "chine" } },
};
/** 特效与灯（克制）：投影、灯点、玻璃反光、顶点 AO 强度、尾焰（FIG.01 数值，Z5 定塞锥颜色）。 */
const FX = {
  shadow: { color: "#05080a", opacity: 0.5, blur: 0.45, contact: 0.32, floor: 0.3 },
  nav: { core: 5, glow: 22, glowAlpha: 0.55 },
  glint: { color: "#6a7c84", band: [0.988, 0.997], strength: 0.6 },
  air: { height: 4.0, fade: 1.25, grow: 0.16, soft: 0.6, contactOff: 0.15 },
  ao: 0.85,
  jet: {
    blue: [0.42, 0.66, 0.86],
    lip: [0.941, 0.741, 0.514],
    cream: [1, 0.95, 0.86],
    main: { r0: 0.3, length: 3.2, spread: 0.045, gain: 1, shocks: 3 },
    column: 0.45,
    lipStrength: 11,
    shock: 0.55,
    exposure: 1.15,
    spring: 20,
    flash: { rise: 0.08, fall: 0.13, amount: 0.6 },
  },
};
/**
 * 后处理（PATTERNS「画面链」）：msaa 多重采样数；bloom 只从发光缓冲来（strength 总强度、mix 半分辨率 / 四分之一分辨率两级的权重）。
 * grade 只在录制模式的电影画质里用：暗部 / 亮部偏色（加到线性值上的小量）、对比（以 0.18 为支点的幂）、暗角、颗粒（LSB）。
 */
const POST = {
  msaa: 4,
  ssaa: 2,
  bloom: { strength: 1.0, mix: [0.9, 0.7] },
  grade: { shadows: [-0.004, 0.0, 0.006], highlights: [0.008, 0.003, -0.004], contrast: 1.08, vignette: 0.22, grain: 1.2 },
};
/** 环境色（配色卡第 5 角色）：机库段冷灰；天门 / 太空段深蓝黑（入轨演出在两者之间过渡）。 */
const ENVIRONMENTS = {
  /** 机库：深蓝黑竖向渐变（R3 反馈：不用纯黑），中间值仍是品牌背景基准附近 */
  hangar: { background: "#0f171c", backdrop: { top: "#152029", bottom: "#0a0f13" } },
  /**
   * 太空 / 天门段：机体压暗 dim（沉进深蓝黑，靠线条与朱红、烛光读出），台面更暗；背景两端渐变 + 稀疏星点 + 地球弧。
   * 地球弧：屏幕坐标（以画幅宽为单位）里的大圆，centre 为圆心的 (u, v)，radius 为半径；辉线 rim（大气，淡青）宽 rimWidth、外晕 halo。
   */
  space: {
    background: "#090d14",
    dim: 0.62,
    deck: ["#0b0f14", "#0d1116", "#0f1419", "#11171c", "#141a1f"],
    backdrop: { top: "#0a1019", bottom: "#05080d", stars: { density: 0.035, alpha: 0.45 }, earth: { centre: [0.62, -2.4], radius: 2.0, color: "#08101c", rim: "#5aa2d4", rimWidth: 0.0022, halo: 0.22 } },
  },
  /** 在轨（入轨构图、剑形态巡航）：同太空，不要转台 */
  orbit: {
    background: "#090d14",
    dim: 0.62,
    stage: false,
    backdrop: { top: "#0a1019", bottom: "#05080d", stars: { density: 0.035, alpha: 0.45 }, earth: { centre: [0.62, -2.4], radius: 2.0, color: "#08101c", rim: "#5aa2d4", rimWidth: 0.0022, halo: 0.22 } },
  },
};
const MOTION = { unlock: 0.35, kick: 0.012, lock: 0.3, settle: 0.008 };
const DIRECTOR = { pause: 0.2, pivot: [0, 0, 1.2], airborne: [0.05, 0.4], bob: { period: 3.4, z: 0.035, pitch: 0.22, bank: 0.18 }, follow: { pan: 0.5 } };

// ———————————————— 机构与演出（Z1：只有通电、点亮棱线、烛光窗；化剑机构在 Z2/Z4） ————————————————
const CONTROLS = VARIANT === "empty" ? [] : [
  { id: "power", label: "通电", range: [0, 1], rest: 0, time: 1.2, power: "power", unit: "%" },
  { id: "chine", label: "朱红棱线", range: [0, 1], rest: 0, time: 1.6, power: "chine", unit: "%" },
  { id: "chine.sweep", label: "棱线点亮", range: [0, 1], rest: 0, time: 1.6, sweep: "chine.sweep", linear: true, unit: "%" },
  { id: "sensor", label: "烛光窗", range: [0, 1], rest: 0, time: 1.0, power: "sensor", unit: "%" },
  // Z2：化剑（几何母版 blender/zl/airframe.py 的 sword_steps：鸭翼、边条、翼尖鳍、折扇主翼、后缘边条、垂尾、进气门）
  ...(G.controls ?? []).map((c) => ({ ...c, unit: "%" })),
];
const SHOWS = VARIANT === "empty" ? [] : [
  { id: "wake", label: "睁眼", prepare: true, steps: [
    { name: "通电", set: [["power", 1, 0.6]] },
    { name: "烛光窗亮", set: [["sensor", 1, 0.8]] },
    { name: "朱红棱线由机头点亮", set: [["chine", 1, 0.3], ["chine.sweep", 1, 1.6]] },
  ] },
];

const offset = G.offset ?? [0, 0, 0];
const FIT = fitView(pointsOf(G.fitParts ?? G.parts), { view: VIEW, elevation: ELEVATION, offset, rise: 0, minR: 3.2 });
const DATA = {
  view: VIEW,
  elevation: ELEVATION,
  fit: FIT,
  deck: FIT.deck,
  offset,
  start: 30,
  palette: { ...PALETTE, background: ENVIRONMENTS.hangar.background },
  shade: SHADE,
  materials: MATERIALS,
  lines: LINES,
  fx: FX,
  post: POST,
  environments: ENVIRONMENTS,
  environment: "hangar",
  motion: MOTION,
  director: DIRECTOR,
  parts: G.parts,
  mesh: G.mesh,
  callouts: G.callouts ?? [],
  /** 剖视时的发光（R3 反馈：屏幕青光、平视显示器、红灯只作点缀，不过曝） */
  cutawayPower: { cockpit: 0.3, "cockpit.hud": 0.2, "cockpit.red": 0.1 },
  /** 编号标注：图例文字没定稿前不显示（__arcseq.callouts(true) 打开） */
  showCallouts: false,
  modules: Object.fromEntries(Object.keys(G.modules ?? {}).map((k) => [k, `zhulong-${k}.js`])),
  seams: G.seams,
  landmarks: Object.fromEntries(Object.entries(G.landmarks).map(([k, v]) => [k, v.map(r4)])),
  joints: G.joints,
  masks: G.masks ?? [],
  focus: G.focus ?? {},
  detail: G.detail,
  look: LOOK,
  /** B（默认画法）：外轮廓浅色、结构线与分割线深色细缝（刻出来的缝），三级不透明度见 lineAlpha。 */
  metal: { env: 1, lines: [1, 1, 1], lineColor: ["#c3d0d4", "#11181c", "#11181c"], lineAlpha: [0.5, 0.5, 0.42] },
  controls: CONTROLS,
  pairs: [],
  shows: SHOWS,
  lights: [],
  labels: [["^nose", "机头"], ["^aft", "中后机身"], ["^wing\\.hub", "主翼回转轴"], ["^wing", "主翼扇骨"], ["^strake", "前边条"], ["^fillet", "后缘边条"], ["^fin", "翼尖鳍"], ["^tail", "垂尾（剑格）"], ["^nozzle", "二元喷口"], ["^plug", "塞锥"], ["^intake", "进气门"], ["^stand", "托架"], ["^sensor", "烛光窗"], ["^canopy\\.glass", "座舱盖"], ["^canopy", "座舱盖框"], ["^brow", "眉骨"], ["^chine", "棱线边条"], ["^scale", "鳞片防热瓦"], ["^rcs", "姿态推进器"], ["^shield", "遮光盾滑轨"]],
  phoneView: { zoom: 1.12, centre: 0.5 },
};

const LABEL = "机库转台上的一架原创单座空天战机「烛龙」（整机体积样板，可一键化剑）。";
const stage = `<div class="af-stage" data-mode="lines" tabindex="0" role="slider" aria-label="${LABEL} 拖动或用方向键旋转；按 1 剪影 2 体积 3 线稿" aria-valuemin="0" aria-valuemax="359" aria-valuenow="30" aria-valuetext="机位 30°"><canvas class="af-canvas"></canvas><svg class="af-overlay" data-callouts aria-hidden="true"></svg><div class="af-legend" data-legend hidden></div></div>`;
const chip = (attr, label) => `<button type="button" class="af-chip" ${attr}>${label}</button>`;
const consoleHtml = `<section class="af-console" aria-label="控制台"><div class="af-actions">
<div class="af-row"><span class="af-key">MAIN</span><div class="af-chips" role="group" aria-label="演出">${SHOWS.map((s) => chip(`data-show="${s.id}"`, `▶ ${s.label}`)).join("")}<span class="af-state" data-show-state aria-live="polite">停机</span></div></div>
<div class="af-row"><span class="af-key">SYSTEMS</span><div class="af-chips" role="group" aria-label="机构">${CONTROLS.filter((c) => !c.sweep).map((c) => chip(`data-control="${c.id}"`, c.label)).join("")}${Object.keys(G.modules ?? {}).length ? chip('data-cutaway aria-pressed="false"', "剖视") : ""}${chip(`data-look aria-pressed="${LOOK === "lines"}"`, "图纸")}</div></div>
<div class="af-row"><span class="af-key">ACTIONS</span><div class="af-panel" data-panel><span class="af-hint">点选零件，或选上面的机构</span></div></div>
</div></section>`;
const page = pageHtml({
  title: "ARCSEQ / FIG.02",
  fig: "ARCSEQ / FIG.02",
  plateTitle: "弧序 · 烛龙",
  hint: "拖动旋转 · 点选零件 · ← → · 1 剪影 2 体积 3 线稿",
  caption: "本作品为原创构想机，与任何官方机构或影视、游戏作品无关。",
  css: readFileSync(join(HERE, "figure.css"), "utf8"),
  stage,
  console: consoleHtml,
  script: engineScript(DATA),
});
const target = option("out", join(ROOT, "dist", VARIANT === "empty" ? "empty.html" : "index.html"));
mkdirSync(dirname(target), { recursive: true });
writeFileSync(target, page);
// 按需模块：单独一个脚本（从本地文件打开也能用 <script src> 加载），第一次打开剖视时才拉
for (const [name, mod] of Object.entries(G.modules ?? {})) writeFileSync(join(dirname(target), `zhulong-${name}.js`), `window.__arcseqModule(${JSON.stringify(name)}, ${JSON.stringify(mod)});\n`);
if (G.tris) console.log(`triangles: exterior ${G.tris.exterior} · interior ${G.tris.interior} · module ${Object.keys(G.modules ?? {}).map((k) => `${k} ${(JSON.stringify(G.modules[k]).length / 1024).toFixed(0)} KB`).join(", ")}`);
console.log(`wrote ${target} · ${(page.length / 1024).toFixed(0)} KB · variant ${VARIANT} · ${G.parts.length} parts · ${(JSON.stringify(DATA).length / 1024).toFixed(0)} KB data · K ${FIT.K.toFixed(2)} px/m · deck r ${FIT.deck.r} m`);
