// 审图截图：固定机位（方位角 30°、120°、210°、300°，俯仰角不变），可选 300 px 宽缩略图。
//   export CHROME_PATH="$PWD/scripts/chrome.sh"
//   node src/figure/shots.mjs review/<日期>-<阶段>-<轮次> --mode silhouette --prefix AFTER --thumb
// 方位角 φ：相机相对机头的方位，逆时针（φ = 90° 看左侧）。
// 局部特写：--views 30 --region x,y,w,h（舞台 CSS px）--scale 4 --tag intake，文件名加上 tag。

import { spawnSync } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = join(HERE, "..", "..");
const argv = process.argv.slice(2);
const option = (name, fallback) => argv.find((a) => a.startsWith(`--${name}=`))?.split("=")[1] ?? (argv.includes(`--${name}`) ? argv[argv.indexOf(`--${name}`) + 1] : fallback);
const out = resolve(argv[0] ?? "review/shots");
const mode = option("mode", "silhouette");
const prefix = option("prefix", "AFTER");
const views = option("views", "30,120,210,300").split(",").map(Number);
const page = resolve(option("page", join(ROOT, "dist", "index.html")));
const region = option("region", null)?.split(",").map(Number) ?? null;
const tag = option("tag", null);
/** --elevation：临时俯仰角（度，FIG.02 起），不给就用页面默认的 30°。 */
const elevation = option("elevation", "undefined");
/** --pre：截图前在页面里执行的脚本（摆机构姿态，例如 "__arcseq.set('canopy', 38)"）；--target：截哪个元素（默认舞台，".iso-plate" 截整张卡片含操作区）。 */
const pre = option("pre", null);
const target = option("target", ".af-stage");
/** 舞台 CSS 宽 1032 px（页面 1080 − 卡片内边距 2×24），缩略图按 300 px 宽缩放。 */
const STAGE = 1032;

mkdirSync(out, { recursive: true });
const pad = (deg) => String(deg).padStart(3, "0");
const actions = [["wait", 500]];
/** WebGL 画布按设备像素比渲染：特写放大 scale 倍时，先让画布按 scale 倍分辨率重画，否则只是放大位图。 */
const scale = Number(option("scale", 1));
if (scale !== 1) actions.push(["eval", `window.__arcseq.resolution?.(${scale})`]);
if (pre) actions.push(["eval", pre], ["wait", 60]);
const files = [];
for (const deg of views) {
  const file = join(out, `${prefix}-${mode}-az${pad(deg)}${tag ? `-${tag}` : ""}.png`);
  actions.push(["eval", `window.__arcseq.view(${deg}, ${JSON.stringify(mode)}, ${elevation})`], ["wait", 120], ["shot", file, target, scale, ...(region ? [region] : [])]);
  files.push(file);
}
if (argv.includes("--thumb")) {
  if (scale !== 1) actions.push(["eval", "window.__arcseq.resolution?.(1)"]);
  const deg = Number(option("thumb-view", views[0]));
  const file = join(out, `${prefix}-${mode}-thumb300-az${pad(deg)}.png`);
  actions.push(["eval", `window.__arcseq.view(${deg}, ${JSON.stringify(mode)}, ${elevation})`], ["wait", 120], ["shot", file, ".af-stage", 300 / STAGE]);
  files.push(file);
}
const steps = join(out, `.actions-${process.pid}.json`);
writeFileSync(steps, JSON.stringify(actions));
const run = spawnSync(process.execPath, [join(ROOT, ".claude/skills/anatomy/scripts/drive.mjs"), page, "--actions", steps, "--height", "1000"], { stdio: "inherit" });
spawnSync("rm", ["-f", steps]);
process.exit(run.status ?? 1);
