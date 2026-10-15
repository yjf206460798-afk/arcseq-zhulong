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

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = join(HERE, "..", "..");
const argv = process.argv.slice(2);
const option = (name, fallback) => argv.find((a) => a.startsWith(`--${name}=`))?.slice(name.length + 3) ?? fallback;
const VARIANT = option("variant", "glb");

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
  const glb = join(ROOT, "assets", "zhulong.glb");
  const meta = join(ROOT, "assets", "zhulong.json");
  if (!existsSync(glb)) throw new Error("assets/zhulong.glb 不存在：先运行 .venv/bin/python blender/build.py");
  const M = JSON.parse(readFileSync(meta, "utf8"));
  const detail = {};
  for (const [name, spec] of Object.entries(M.detail ?? {})) detail[name] = { ...spec, src: `data:image/png;base64,${readFileSync(join(ROOT, "assets", spec.file)).toString("base64")}` };
  return { parts: glbParts(glb), seams: M.seams ?? [], landmarks: M.landmarks ?? {}, joints: M.joints ?? [], offset: M.offset ?? [0, 0, 0], detail, focus: M.focus, masks: M.masks ?? [] };
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
  body: ["#202326", "#26292c", "#2c3033", "#33373a", "#3b3f42"],
  belly: ["#181c20", "#1c2025", "#20252a", "#252a30", "#2b3036"],
  carbon: ["#141618", "#17191b", "#1a1c1e", "#1e2022", "#232527"],
  glass: ["#0f1215", "#12161a", "#161b20", "#1b2127", "#232a31"],
  interior: ["#15181a", "#181b1d", "#1b1f21", "#1f2325", "#24282a"],
  sensor: ["#120d0a", "#16100b", "#1b130d", "#21170f", "#281c12"],
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
/**
 * 线条分级（FIG.01 G2，VISUAL_TARGET：L0 0.6～0.9 / L1 约 0.5 / L2 0.35～0.5 px）。
 * accents：作品标志色的线（朱红棱线）：线宽同主描边、偏暗不荧光；idle 为未通电时的亮度（三四成），通电后由机头沿线点亮并进发光缓冲。
 */
const LINES = {
  width: [0.75, 0.5, 0.42],
  color: ["#b9c7cb", "#7d939c", "#7d939c"],
  alpha: [0.72, 0.62, 0.34],
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
  hangar: { background: "#111518" },
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
};
const MOTION = { unlock: 0.35, kick: 0.012, lock: 0.3, settle: 0.008 };
const DIRECTOR = { pause: 0.2, pivot: [0, 0, 1.2], airborne: [0.05, 0.4], bob: { period: 3.4, z: 0.035, pitch: 0.22, bank: 0.18 }, follow: { pan: 0.5 } };

// ———————————————— 机构与演出（Z1：只有通电、点亮棱线、烛光窗；化剑机构在 Z2/Z4） ————————————————
const CONTROLS = VARIANT === "empty" ? [] : [
  { id: "power", label: "通电", range: [0, 1], rest: 0, time: 1.2, power: "power", unit: "%" },
  { id: "chine", label: "朱红棱线", range: [0, 1], rest: 0, time: 1.6, power: "chine", unit: "%" },
  { id: "chine.sweep", label: "棱线点亮", range: [0, 1], rest: 0, time: 1.6, sweep: "chine.sweep", linear: true, unit: "%" },
  { id: "sensor", label: "烛光窗", range: [0, 1], rest: 0, time: 1.0, power: "sensor", unit: "%" },
];
const SHOWS = VARIANT === "empty" ? [] : [
  { id: "wake", label: "睁眼", prepare: true, steps: [
    { name: "通电", set: [["power", 1, 0.6]] },
    { name: "烛光窗亮", set: [["sensor", 1, 0.8]] },
    { name: "朱红棱线由机头点亮", set: [["chine", 1, 0.3], ["chine.sweep", 1, 1.6]] },
  ] },
];

const offset = G.offset ?? [0, 0, 0];
const FIT = fitView(pointsOf(G.parts), { view: VIEW, elevation: ELEVATION, offset, rise: 0, minR: 3.2 });
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
  seams: G.seams,
  landmarks: Object.fromEntries(Object.entries(G.landmarks).map(([k, v]) => [k, v.map(r4)])),
  joints: G.joints,
  masks: G.masks ?? [],
  focus: G.focus ?? {},
  detail: G.detail,
  controls: CONTROLS,
  pairs: [],
  shows: SHOWS,
  lights: [],
  labels: [["^nose", "机头"], ["^sensor", "烛光窗"], ["^canopy\\.glass", "座舱盖"], ["^canopy", "座舱盖框"], ["^brow", "眉骨"], ["^chine", "棱线边条"], ["^scale", "鳞片防热瓦"], ["^rcs", "姿态推进器"], ["^shield", "遮光盾滑轨"]],
  phoneView: { zoom: 1.12, centre: 0.5 },
};

const LABEL = "机库转台上的一架原创单座空天战机「烛龙」的机头段视觉样板。";
const stage = `<div class="af-stage" data-mode="lines" tabindex="0" role="slider" aria-label="${LABEL} 拖动或用方向键旋转；按 1 剪影 2 体积 3 线稿" aria-valuemin="0" aria-valuemax="359" aria-valuenow="30" aria-valuetext="机位 30°"><canvas class="af-canvas"></canvas></div>`;
const chip = (attr, label) => `<button type="button" class="af-chip" ${attr}>${label}</button>`;
const consoleHtml = `<section class="af-console" aria-label="控制台"><div class="af-actions">
<div class="af-row"><span class="af-key">MAIN</span><div class="af-chips" role="group" aria-label="演出">${SHOWS.map((s) => chip(`data-show="${s.id}"`, `▶ ${s.label}`)).join("")}<span class="af-state" data-show-state aria-live="polite">停机</span></div></div>
<div class="af-row"><span class="af-key">SYSTEMS</span><div class="af-chips" role="group" aria-label="机构">${CONTROLS.filter((c) => !c.sweep).map((c) => chip(`data-control="${c.id}"`, c.label)).join("")}</div></div>
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
console.log(`wrote ${target} · ${(page.length / 1024).toFixed(0)} KB · variant ${VARIANT} · ${G.parts.length} parts · ${(JSON.stringify(DATA).length / 1024).toFixed(0)} KB data · K ${FIT.K.toFixed(2)} px/m · deck r ${FIT.deck.r} m`);
