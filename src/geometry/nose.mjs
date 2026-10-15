// 烛龙机头段 · 代码凸体版（FIG.01 的几何母版做法，只为 Z1 路线比较；外形与 blender/zl/nose.py 同一套设计数）。
// 每个零件是凸包 { verts, faces }；凹的地方拆成几块凸体；相邻零件贴面坐落（眉骨、座舱盖底面取在机身上表面上）。
// 做不到的（与 Blender 版的差别，见 review/20261015-Z1-lookdev/SUMMARY.md）：布尔并（眉骨与机身的交线靠贴面凑）、
// 圆环（窗框环拆成 24 段凸体）、顶点 AO 与 UV 细节贴图（没有烘焙器）。
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { convexHull, mirrorY } from "./hull.mjs";
import { packHulls } from "../figure/engine/pack.mjs";

const XN = 9.5;
const at = (s, y, z) => [XN - s, y, z];
const lerp = (a, b, t) => a + (b - a) * t;
const REAR = { R0: [0, 2.18], R1: [0.56, 2.08], R2: [1.08, 1.52], R3: [0.55, 0.87] };
const S_END = 7.2;
const FORE_APEX = [-1.24, 1.43];
const NEEDLE = [1.1, [0, 1.45]];
const BALL = { s: 0.11, z: 1.45, r: 0.11 };

export function ring(s) {
  const [sa, za] = FORE_APEX;
  if (s >= NEEDLE[0] - 1e-9) {
    const k = (s - sa) / (S_END - sa);
    return Object.fromEntries(Object.entries(REAR).map(([key, [y, z]]) => [key, [y * k, za + (z - za) * k]]));
  }
  const base = ring(NEEDLE[0]);
  const [s0, z0] = NEEDLE[1];
  const k = (s - s0) / (NEEDLE[0] - s0);
  return Object.fromEntries(Object.entries(base).map(([key, [y, z]]) => [key, [y * k, z0 + (z - z0) * k]]));
}
/** 整圈截面（左 R0→R3，右 R3'→R1'）。 */
const section = (s) => {
  const R = ring(s);
  return [R.R0, R.R1, R.R2, R.R3, [-R.R3[0], R.R3[1]], [-R.R2[0], R.R2[1]], [-R.R1[0], R.R1[1]]].map(([y, z]) => at(s, y, z));
};
export function topZ(s, y) {
  const R = ring(s);
  y = Math.abs(y);
  if (y <= R.R1[0]) return lerp(R.R0[1], R.R1[1], y / R.R1[0]);
  return lerp(R.R1[1], R.R2[1], (y - R.R1[0]) / (R.R2[0] - R.R1[0]));
}

export function buildNose() {
  const parts = [];
  const add = (name, pts, extra = {}) => parts.push({ name, hull: convexHull(pts), ...extra });
  // 机身：针段、前机身两块凸体（每段截面位似，所以两块都是凸的、每张切面是平面）
  add("nose.needle", [...section(0.16), ...section(NEEDLE[0])], { skin: "skin", material: "hull" });
  add("nose.fore", [...section(NEEDLE[0]), ...section(S_END)], { skin: "skin", material: "hull" });
  // 眼珠：球（48×24 点的凸包）、光窗球冠、虹膜六片、窗框环 24 段
  const c = at(BALL.s, 0, BALL.z);
  const sph = (r, a0, a1, phi0 = 0, phi1 = 2 * Math.PI, na = 8, np = 48, hex = false) => {
    const pts = [];
    for (let i = 0; i <= na; i++)
      for (let k = 0; k <= np; k++) {
        let a = lerp(a0, a1, i / na);
        const phi = lerp(phi0, phi1, k / np);
        if (hex && i === 0) a = Math.atan(Math.tan(a0) / Math.cos((phi % (Math.PI / 3)) - Math.PI / 6));
        pts.push([c[0] + r * Math.cos(a), c[1] + r * Math.sin(a) * Math.cos(phi), c[2] + r * Math.sin(a) * Math.sin(phi)]);
      }
    return pts;
  };
  add("sensor.ball", sph(BALL.r, 0, Math.PI, 0, 2 * Math.PI, 24, 48), { skin: "sensor.ball", material: "carbon", smooth: "ball" });
  const WIN = (34 * Math.PI) / 180;
  const APER = (13 * Math.PI) / 180;
  add("sensor.window", [...sph(BALL.r * 1.004, 0, WIN, 0, 2 * Math.PI, 6, 48), c], { skin: "sensor.window", material: "sensor", smooth: "window", glow: { key: "sensor", color: "#ffb060" } });
  for (let b = 0; b < 6; b++) {
    const p0 = (b * Math.PI) / 3;
    add(`sensor.iris.${b}`, [...sph(BALL.r * 1.03, APER, WIN, p0, p0 + Math.PI / 3, 4, 8, true), ...sph(BALL.r * 1.01, APER, WIN, p0, p0 + Math.PI / 3, 4, 8, true)], { skin: `sensor.iris.${b}`, material: "carbon", lineLevel: "secondary" });
  }
  const rr = BALL.r * Math.sin(WIN) * 1.03;
  const xx = BALL.r * Math.cos(WIN) * 1.03;
  for (let i = 0; i < 24; i++) {
    const pts = [];
    for (const phi of [(i / 24) * 2 * Math.PI, ((i + 1) / 24) * 2 * Math.PI])
      for (let k = 0; k < 8; k++) {
        const th = (k / 8) * 2 * Math.PI;
        const rad = rr + 0.007 * Math.cos(th);
        pts.push([c[0] + xx + 0.007 * Math.sin(th), rad * Math.cos(phi), c[2] + rad * Math.sin(phi)]);
      }
    add(`sensor.bezel.${i}`, pts, { skin: "sensor.bezel", material: "carbon", lineLevel: "secondary", smooth: "bezel" });
  }
  // 眉骨：底面取在机身上表面上（贴面坐落，接触面自动去掉，交线成为眉骨的一级结构线）
  {
    const pts = [];
    const s0 = 4.05, s1 = 5.18, s2 = 5.24;
    for (const side of [1, -1]) {
      for (const [s, y, dz] of [[s0, 0, 0], [4.6, 0.19, 0.06], [s1, 0.4, 0.12], [s2, 0.4, 0.12], [4.9, 0.33, 0.09]]) pts.push(at(s, y * side, topZ(s, y) + dz));
      for (const s of [s0, 4.6, s1, s2]) for (const y of [0, 0.4]) pts.push(at(s, Math.min(y, ring(s).R1[0] * 0.98) * side, topZ(s, Math.min(y, ring(s).R1[0] * 0.98))));
    }
    pts.push(at(s1, 0, 2.31), at(s2, 0, 2.3));
    add("brow", pts, { skin: "brow", material: "hull" });
  }
  // 座舱盖：玻璃两块 + 弓形框；底面取在上表面上
  const glass = (stations) => stations.flatMap(([s, ridge, [ys, zs], yb]) => [at(s, 0, ridge), at(s, 0, topZ(s, 0)), ...[1, -1].flatMap((side) => [at(s, ys * side, zs), at(s, yb * side, topZ(s, yb))])]);
  add("canopy.glass.front", glass([[5.22, 2.24, [0.22, 2.17], 0.33], [5.65, 2.42, [0.24, 2.34], 0.36], [6.13, 2.42, [0.24, 2.34], 0.36]]), { skin: "glass", glass: true, material: "glass" });
  add("canopy.glass.rear", glass([[6.17, 2.42, [0.24, 2.34], 0.36], [6.35, 2.42, [0.24, 2.34], 0.36], [6.95, 2.2, [0.14, 2.15], 0.2]]), { skin: "glass", glass: true, material: "glass" });
  add("canopy.bow", glass([[6.125, 2.43, [0.245, 2.35], 0.365], [6.175, 2.43, [0.245, 2.35], 0.365]]), { skin: "canopy.frame", material: "carbon" });
  add("fairing", glass([[6.85, 2.3, [0.17, 2.21], 0.25], [7.2, 2.31, [0.2, 2.24], 0.3]]), { skin: "fairing", material: "hull" });
  // 遮光盾滑轨
  for (const [side, tag] of [[1, "l"], [-1, "r"]]) {
    const pts = [];
    for (const s of [5.24, 6.88]) for (const dy of [0, 0.028]) pts.push(at(s, (0.375 + dy) * side, topZ(s, 0.375 + dy)), at(s, (0.375 + dy) * side, topZ(s, 0.375 + dy) + 0.026));
    add(`shield.rail.${tag}`, pts, { skin: `shield.rail.${tag}`, material: "carbon" });
  }
  // 鸭翼（左，右侧镜像）
  {
    const z0 = ring(5.9).R2[1] - 0.05;
    const R = ring(6.0);
    const yr = lerp(R.R2[0], R.R3[0], (R.R2[1] - z0) / (R.R2[1] - R.R3[1])) - 0.03;
    const pts = [];
    for (const [sl, st, span, th] of [[5.45, 6.55, 0, 0.04], [6.58, 6.86, 0.95, 0.015]]) {
      const m = (sl + st) / 2;
      pts.push(at(sl, yr + span, z0), at(st, yr + span, z0), at(m, yr + span, z0 + th / 2), at(m, yr + span, z0 - th / 2));
    }
    add("canard.l", pts, { skin: "canard.l", material: "hull" });
    const H = convexHull(pts);
    parts.push({ name: "canard.r", hull: mirrorY(H), skin: "canard.r", material: "hull" });
  }
  // 鳞片瓦样片：与 Blender 版同一套菱形错排（每片一个凸包）
  {
    const facet = (s, t, lift) => {
      const R = ring(s);
      const y = lerp(R.R2[0], R.R3[0], t);
      const z = lerp(R.R2[1], R.R3[1], t);
      const n = [0, R.R2[1] - R.R3[1], -(R.R2[0] - R.R3[0])];
      const l = Math.hypot(...n);
      return at(s, y + (n[1] / l) * lift, z + (n[2] / l) * lift);
    };
    const p = 0.085, w = 0.15, gap = 0.006;
    let row = 0;
    let n = 0;
    for (let s = 3.3; s < 5.3; s += p, row++) {
      const R = ring(s);
      const slant = Math.hypot(R.R2[0] - R.R3[0], R.R2[1] - R.R3[1]);
      for (let v = 0.1 + (row % 2 ? w / 2 : 0); v + w / 2 < slant * 0.9; v += w) {
        const outline = [[-p + gap, 0], [0, -w / 2 + gap]];
        for (let i = 1; i < 6; i++) {
          const a = -Math.PI / 2 + (Math.PI * i) / 6;
          outline.push([(p - gap) * 0.95 * Math.cos(a), (w / 2 - gap) * Math.sin(a)]);
        }
        outline.push([0, w / 2 - gap]);
        const pts = outline.flatMap(([du, dv]) => {
          const ss = s + du;
          const rr2 = ring(ss);
          const sl = Math.hypot(rr2.R2[0] - rr2.R3[0], rr2.R2[1] - rr2.R3[1]);
          const t = (v + dv) / sl;
          return [facet(ss, t, 0.002 + 0.005 * Math.max(0, (du + p) / (2 * p))), facet(ss, t, -0.003)];
        });
        const H = convexHull(pts);
        parts.push({ name: `scale.l.${n}`, hull: H, skin: "scale", material: "belly", lineLevel: "secondary", shadow: false });
        parts.push({ name: `scale.r.${n}`, hull: mirrorY(H), skin: "scale", material: "belly", lineLevel: "secondary", shadow: false });
        n++;
      }
    }
  }
  // 展示支架
  {
    const s = 4.6, zb = ring(s).R3[1];
    const box = (rows) => rows.flatMap(([ds, dy, z]) => [1, -1].flatMap((a) => [1, -1].map((b) => at(s + ds * a, dy * b, z))));
    add("stand.post", box([[0.11, 0.11, 0], [0.06, 0.06, zb - 0.05]]), { skin: "stand.post", material: "interior" });
    add("stand.cradle", box([[0.26, 0.2, zb - 0.05], [0.26, 0.2, zb]]), { skin: "stand.cradle", material: "interior" });
  }
  const { parts: packed } = packHulls(parts, { meta: (p) => ({ skin: p.skin, material: p.material, smooth: p.smooth, glow: p.glow, lineLevel: p.lineLevel, shadow: p.shadow }) });
  // 分割线、棱线、地标与 Blender 版同一份（几何母版的解析数据，与建模工具无关）
  const meta = JSON.parse(readFileSync(join(dirname(fileURLToPath(import.meta.url)), "..", "..", "assets", "zhulong.json"), "utf8"));
  return { parts: packed, seams: meta.seams, landmarks: meta.landmarks, joints: [], offset: meta.offset, detail: {}, masks: meta.masks };
}
