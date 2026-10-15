// 叠图比对（PATTERNS「复刻标准」）：页面按正交视图截图，用两个锚点（模型坐标 ↔ 参考图像素）求相似变换，对齐到参考图上，
// 输出 REFERENCE / AFTER / OVERLAY（50%）三张。
//   node scripts/overlay.mjs <输出目录> <spec.json>
// spec：[{ name, ref, crop: [x0, y0, x1, y1], heading, elevation, mode, pre?, page?, scale?, anchors: [[[x, y, z], [px, py]], [[…], […]]] }]
// 云端截图前 export CHROME_PATH="$PWD/scripts/chrome.sh"。
import { spawnSync } from "node:child_process";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";

const ROOT = resolve(new URL("..", import.meta.url).pathname);
const [outArg, specArg] = process.argv.slice(2);
const out = resolve(outArg);
const specs = JSON.parse(readFileSync(specArg, "utf8"));
mkdirSync(join(out, "overlay-tmp"), { recursive: true });
for (const sp of specs) {
  const page = resolve(sp.page ?? join(ROOT, "dist/index.html"));
  const scale = sp.scale ?? 2;
  const shot = join(out, "overlay-tmp", `${sp.name}.png`);
  const actions = [["wait", 500]];
  if (sp.pre) actions.push(["eval", sp.pre]);
  actions.push(["eval", `__arcseq.resolution(${scale})`], ["eval", `__arcseq.view(${sp.heading}, ${JSON.stringify(sp.mode ?? "lines")}, ${sp.elevation})`]);
  if (sp.after) actions.push(["eval", sp.after]);
  actions.push(["wait", 200], ["eval", `JSON.stringify(${JSON.stringify(sp.anchors.map((a) => a[0]))}.map((p) => __arcseq.project(p)))`], ["shot", shot, ".af-stage", scale]);
  const steps = join(out, "overlay-tmp", `${sp.name}.json`);
  writeFileSync(steps, JSON.stringify(actions));
  const r = spawnSync("timeout", ["-k", "5", "300", process.execPath, join(ROOT, ".claude/skills/anatomy/scripts/drive.mjs"), page, "--actions", steps, "--height", "1000"], { encoding: "utf8" });
  if (r.status !== 0) throw new Error(r.stderr || r.stdout);
  const line = r.stdout.split("\n").filter((l) => l.startsWith("eval: ")).at(-1);
  const model = JSON.parse(JSON.parse(line.slice(6)));
  const job = { ...sp, shot, model: model.map(([x, y]) => [x * scale, y * scale]), refPts: sp.anchors.map((a) => a[1]), ref: resolve(ROOT, sp.ref), out };
  const py = spawnSync("python3", ["-c", `
import json, sys, math
import numpy as np
from PIL import Image
j = json.loads(sys.argv[1])
ref = Image.open(j["ref"]).convert("RGB")
x0, y0, x1, y1 = j["crop"]
R = ref.crop((x0, y0, x1, y1))
(m1, m2), (r1, r2) = j["model"], j["refPts"]
# 相似变换：模型截图像素 → 参考图像素（缩放 + 旋转 + 平移），用两锚点解
zm = complex(m2[0] - m1[0], m2[1] - m1[1])
zr = complex(r2[0] - r1[0], r2[1] - r1[1])
a = zr / zm
b = complex(*r1) - a * complex(*m1)
# PIL 的 AFFINE 要的是“输出像素 → 输入像素”的逆变换；输出坐标再加上裁剪原点
ai = 1 / a
bi = -b / a
# 输入 = ai * (输出 + crop原点) + bi
c, s = ai.real, ai.imag
tx = bi.real + c * x0 - s * y0
ty = bi.imag + s * x0 + c * y0
shot = Image.open(j["shot"]).convert("RGB")
A = shot.transform(R.size, Image.AFFINE, (c, -s, tx, s, c, ty), resample=Image.BICUBIC, fillcolor=(16, 21, 24))
n = j["name"]
R.save(f"{j['out']}/REFERENCE-{n}.png")
A.save(f"{j['out']}/AFTER-{n}.png")
Image.blend(R, A, 0.5).save(f"{j['out']}/OVERLAY-{n}.png")
print(n, "scale", round(abs(a), 4), "rot", round(math.degrees(math.atan2(a.imag, a.real)), 2))
`, JSON.stringify(job)], { encoding: "utf8" });
  console.log(py.stdout.trim() || py.stderr);
}
