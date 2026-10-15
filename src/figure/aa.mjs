// 抗锯齿验收（Z1）：转台以 0.1° 一步慢转 8 帧，截同一块局部（1×，不放大），与 4× 超采样的参照帧逐像素比较。
//   node src/figure/aa.mjs review/<目录> [--page dist/index.html] [--region x,y,w,h] [--views 30]
// 每个配置输出：与参照的平均误差（0～255）、时间闪烁（逐像素误差在 8 帧里的标准差的均值）；并把第 0 帧拼成对照条。
// 配置：A = FIG.01 的线覆盖近似式、不超采样；B = 精确盒式覆盖、不超采样；C = B + 2× 超采样（网页高画质档）；REF = 4× 超采样。
import { spawnSync } from "node:child_process";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";

const ROOT = resolve(new URL("../..", import.meta.url).pathname);
const argv = process.argv.slice(2);
const opt = (n, d) => (argv.includes(`--${n}`) ? argv[argv.indexOf(`--${n}`) + 1] : d);
const out = resolve(argv[0] ?? "review/aa");
const page = resolve(opt("page", join(ROOT, "dist/index.html")));
const region = opt("region", "560,250,220,150").split(",").map(Number);
const base = Number(opt("views", 30));
mkdirSync(join(out, "aa-frames"), { recursive: true });
// A：把精确覆盖式换回 FIG.01 的近似式（只在临时页面里）
const html = readFileSync(page, "utf8");
const OLD = "float cover = clamp(vHalf + 0.5 - abs(vDist), 0.0, 1.0);\n      if (vHalf < 0.5) cover *= 2.0 * vHalf;";
const NEW = "float cover = clamp(min(vDist + 0.5, vHalf) - max(vDist - 0.5, -vHalf), 0.0, 1.0);";
if (!html.includes(NEW)) throw new Error("page lacks the exact-coverage line shader");
const oldPage = join(out, "aa-frames", "page-A.html");
writeFileSync(oldPage, html.replace(NEW, OLD));
const configs = [
  { id: "A", page: oldPage, pre: "__arcseq.resolution(1);__arcseq.cinema({ssaa:1,grade:false})" },
  { id: "B", page, pre: "__arcseq.resolution(1);__arcseq.cinema({ssaa:1,grade:false})" },
  // C：网页高画质档本身（DPR 1 的屏上自动 2× 超采样）
  { id: "C", page, pre: "__arcseq.resolution(1)" },
  { id: "REF", page, pre: "__arcseq.resolution(1);__arcseq.cinema({ssaa:4,grade:false})" },
];
for (const c of configs) {
  const actions = [["wait", 400], ["eval", c.pre]];
  for (let k = 0; k < 8; k++) actions.push(["eval", `__arcseq.view(${base + k * 0.1}, "lines")`], ["wait", 60], ["shot", join(out, "aa-frames", `${c.id}-${k}.png`), ".af-stage", 1, region]);
  const steps = join(out, "aa-frames", `${c.id}.json`);
  writeFileSync(steps, JSON.stringify(actions));
  const r = spawnSync("timeout", ["-k", "5", "240", process.execPath, join(ROOT, ".claude/skills/anatomy/scripts/drive.mjs"), c.page, "--actions", steps, "--height", "1000"], { encoding: "utf8" });
  if (r.status !== 0) throw new Error(r.stderr || r.stdout);
}
const py = spawnSync("python3", ["-c", `
import numpy as np, sys
from PIL import Image
d = sys.argv[1]
def load(i, k): return np.asarray(Image.open(f"{d}/aa-frames/{i}-{k}.png").convert("L"), dtype=np.float32)
ref = np.stack([load("REF", k) for k in range(8)])
# 只在边缘与线条像素上算（参照帧里梯度明显的像素，外扩 1 像素）：平坦蒙皮上没有锯齿可言
gy, gx = np.gradient(ref.mean(0))
edge = np.hypot(gx, gy) > 2.5
edge = edge | np.roll(edge, 1, 0) | np.roll(edge, -1, 0) | np.roll(edge, 1, 1) | np.roll(edge, -1, 1)
rows = [f"edge pixels: {edge.sum()} / {edge.size}"]
for i in ("A", "B", "C"):
    f = np.stack([load(i, k) for k in range(8)])
    e = (f - ref)[:, edge]
    rows.append(f"{i}: mean |err| {np.abs(e).mean():.2f} · p95 |err| {np.percentile(np.abs(e), 95):.1f} · flicker {e.std(0).mean():.2f}")
print("\\n".join(rows))
strip = np.concatenate([load(i, 0) for i in ("A", "B", "C", "REF")], 1)
Image.fromarray(np.clip(strip, 0, 255).astype(np.uint8)).resize((strip.shape[1] * 3, strip.shape[0] * 3), Image.NEAREST).save(f"{d}/AA-strip-A-B-C-REF.png")
`, out], { encoding: "utf8" });
console.log(py.stdout || py.stderr);
writeFileSync(join(out, "AA.txt"), py.stdout);
