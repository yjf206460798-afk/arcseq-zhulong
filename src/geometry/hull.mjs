// 凸包工具：几何母版里每个零件都是凸多面体 { verts, faces }，faces 从外侧看逆时针。
// 与渲染无关：Anatomy 3D（T.hull）和以后可能的 Three.js 都直接吃这个结构。

const sub = (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
const add = (a, b) => [a[0] + b[0], a[1] + b[1], a[2] + b[2]];
const mul = (a, k) => [a[0] * k, a[1] * k, a[2] * k];
const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
const cross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
const len = (a) => Math.hypot(a[0], a[1], a[2]);
const unit = (a) => mul(a, 1 / (len(a) || 1));

export const V3 = { sub, add, mul, dot, cross, len, unit };

/** 增量凸包，O(n²)；共面三角形合并成一个面。eps 相对于点集尺度。 */
export function convexHull(input, eps = 1e-7) {
  const pts = [];
  for (const p of input) if (!pts.some((q) => Math.abs(q[0] - p[0]) + Math.abs(q[1] - p[1]) + Math.abs(q[2] - p[2]) < 1e-9)) pts.push([p[0], p[1], p[2]]);
  const n = pts.length;
  if (n < 4) throw new Error(`hull: only ${n} distinct points`);
  const scale = Math.max(...pts.map((p) => Math.abs(p[0]) + Math.abs(p[1]) + Math.abs(p[2])), 1);
  const tol = eps * scale;
  let i1 = 1;
  for (let i = 1; i < n; i++) if (len(sub(pts[i], pts[0])) > len(sub(pts[i1], pts[0]))) i1 = i;
  let i2 = -1;
  let best = tol;
  for (let i = 0; i < n; i++) {
    const a = len(cross(sub(pts[i1], pts[0]), sub(pts[i], pts[0])));
    if (a > best) [best, i2] = [a, i];
  }
  if (i2 < 0) throw new Error("hull: points are collinear");
  const n0 = cross(sub(pts[i1], pts[0]), sub(pts[i2], pts[0]));
  let i3 = -1;
  best = tol * len(n0);
  for (let i = 0; i < n; i++) {
    const v = Math.abs(dot(n0, sub(pts[i], pts[0])));
    if (v > best) [best, i3] = [v, i];
  }
  if (i3 < 0) throw new Error("hull: points are coplanar");
  const plane = (a, b, c) => {
    const u = unit(cross(sub(pts[b], pts[a]), sub(pts[c], pts[a])));
    return { v: [a, b, c], n: u, d: dot(u, pts[a]) };
  };
  const centre = mul(add(add(pts[0], pts[i1]), add(pts[i2], pts[i3])), 0.25);
  let tris = [];
  for (const [a, b, c] of [[0, i1, i2], [0, i1, i3], [0, i2, i3], [i1, i2, i3]]) {
    const t = plane(a, b, c);
    tris.push(dot(t.n, centre) - t.d > 0 ? plane(a, c, b) : t);
  }
  const used = new Set([0, i1, i2, i3]);
  const order = [...pts.keys()].filter((i) => !used.has(i)).sort((a, b) => len(sub(pts[b], centre)) - len(sub(pts[a], centre)));
  for (const i of order) {
    const p = pts[i];
    const seen = tris.filter((t) => dot(t.n, p) - t.d > tol);
    if (!seen.length) continue;
    const edges = new Map();
    for (const t of seen)
      for (let e = 0; e < 3; e++) {
        const a = t.v[e];
        const b = t.v[(e + 1) % 3];
        if (edges.has(`${b},${a}`)) edges.delete(`${b},${a}`);
        else edges.set(`${a},${b}`, [a, b]);
      }
    tris = tris.filter((t) => !seen.includes(t));
    for (const [a, b] of edges.values()) tris.push(plane(a, b, i));
  }
  const keep = [...new Set(tris.flatMap((t) => t.v))].sort((a, b) => a - b);
  const remap = new Map(keep.map((v, j) => [v, j]));
  const groups = [];
  for (const t of tris) {
    const g = groups.find((x) => dot(x.n, t.n) > 1 - 1e-8 && Math.abs(x.d - t.d) < tol * 4);
    if (g) g.tris.push(t);
    else groups.push({ n: t.n, d: t.d, tris: [t] });
  }
  // 每组共面三角形的外环：取该组顶点在面内的二维凸包（逆时针，保留边上的共线点）。
  // 不从三角形边界拼环——近乎共面的细三角形会让边界不是简单环，拼出重复顶点的坏环。
  const faces = groups.map((g) => {
    const ids = [...new Set(g.tris.flatMap((t) => t.v))];
    const n = g.n;
    const u = unit(Math.abs(n[0]) < 0.9 ? cross(n, [1, 0, 0]) : cross(n, [0, 1, 0]));
    const w = cross(n, u);
    const flat = ids.map((i) => ({ i, x: dot(pts[i], u), y: dot(pts[i], w) })).sort((a, b) => a.x - b.x || a.y - b.y);
    const turn = (o, a, b) => (a.x - o.x) * (b.y - o.y) - (a.y - o.y) * (b.x - o.x);
    const flatTol = tol * scale * 1e-3 + 1e-12;
    const chain = (list) => {
      const out = [];
      for (const p of list) {
        while (out.length >= 2 && turn(out[out.length - 2], out[out.length - 1], p) < -flatTol) out.pop();
        out.push(p);
      }
      return out;
    };
    const lower = chain(flat);
    const upper = chain(flat.slice().reverse());
    const ring = [...lower.slice(0, -1), ...upper.slice(0, -1)];
    const loop = [];
    for (const p of ring) if (!loop.includes(p.i)) loop.push(p.i);
    return loop.map((v) => remap.get(v));
  });
  return { verts: keep.map((v) => pts[v]), faces };
}

/** 外法线 (Newell)。 */
export function faceNormal(verts, face) {
  let nn = [0, 0, 0];
  for (let i = 0; i < face.length; i++) {
    const a = verts[face[i]];
    const b = verts[face[(i + 1) % face.length]];
    nn = add(nn, [(a[1] - b[1]) * (a[2] + b[2]), (a[2] - b[2]) * (a[0] + b[0]), (a[0] - b[0]) * (a[1] + b[1])]);
  }
  return unit(nn);
}

export function planesOf(H) {
  return H.faces.map((face) => {
    const n = faceNormal(H.verts, face);
    return { n, d: dot(n, H.verts[face[0]]) };
  });
}

/** 竖直线 (x, y) 与凸包的上表面 / 下表面交点的 z；不相交时返回 null。 */
export function zOn(H, x, y, side = "bottom") {
  let lo = -Infinity;
  let hi = Infinity;
  for (const { n, d } of planesOf(H)) {
    const rest = d - n[0] * x - n[1] * y;
    if (Math.abs(n[2]) < 1e-9) {
      if (rest < -1e-9) return null;
      continue;
    }
    const z = rest / n[2];
    if (n[2] > 0) hi = Math.min(hi, z);
    else lo = Math.max(lo, z);
  }
  if (lo > hi + 1e-9) return null;
  return side === "bottom" ? lo : hi;
}

/** 射线 o + t·dir 穿过凸包的区间 [tIn, tOut] 与出射面外法线；不相交时返回 null。 */
export function rayThrough(H, o, dir) {
  let tIn = -Infinity;
  let tOut = Infinity;
  let normal = null;
  for (const { n, d } of planesOf(H)) {
    const nd = dot(n, dir);
    const rest = d - dot(n, o);
    if (Math.abs(nd) < 1e-12) {
      if (rest < -1e-9) return null;
      continue;
    }
    const t = rest / nd;
    if (nd > 0) {
      if (t < tOut) [tOut, normal] = [t, n];
    } else tIn = Math.max(tIn, t);
  }
  return tIn <= tOut + 1e-9 && normal ? { tIn, tOut, normal } : null;
}

/** 水平线 (x, ·, z) 与凸包表面的交点中 y 最大（"max"，左侧外表面）或最小（"min"）者；不相交时返回 null。 */
export function yOn(H, x, z, side = "max") {
  let lo = -Infinity;
  let hi = Infinity;
  for (const { n, d } of planesOf(H)) {
    const rest = d - n[0] * x - n[2] * z;
    if (Math.abs(n[1]) < 1e-9) {
      if (rest < -1e-9) return null;
      continue;
    }
    const y = rest / n[1];
    if (n[1] > 0) hi = Math.min(hi, y);
    else lo = Math.max(lo, y);
  }
  if (lo > hi + 1e-9) return null;
  return side === "max" ? hi : lo;
}

/** 凸包与半空间 n·p ≤ d 的交（仍是凸包）：保留内侧顶点，加上穿过平面的棱与平面的交点。 */
export function clipHull(H, n, d) {
  const side = (p) => dot(n, p) - d;
  const pts = H.verts.filter((p) => side(p) <= 1e-9);
  for (const face of H.faces)
    for (let i = 0; i < face.length; i++) {
      const a = H.verts[face[i]];
      const b = H.verts[face[(i + 1) % face.length]];
      const sa = side(a);
      const sb = side(b);
      if ((sa < -1e-9 && sb > 1e-9) || (sa > 1e-9 && sb < -1e-9)) pts.push(add(a, mul(sub(b, a), sa / (sa - sb))));
    }
  return convexHull(pts);
}

/** 关于 y = 0 的镜像（左 → 右），面的绕向随之翻转。 */
export function mirrorY(H) {
  return { verts: H.verts.map(([x, y, z]) => [x, -y, z]), faces: H.faces.map((face) => face.slice().reverse()) };
}

/** 两个凸包之间的最大分离间隙（> 0 分开，< 0 互相嵌入）；用于自检接触。 */
export function gapBetween(A, B) {
  let best = -Infinity;
  for (const [P, Q, sign] of [[A, B, 1], [B, A, -1]])
    for (const { n } of planesOf(P)) {
      const m = mul(n, sign);
      const hiA = Math.max(...A.verts.map((p) => dot(m, p)));
      const loB = Math.min(...B.verts.map((p) => dot(m, p)));
      best = Math.max(best, loB - hiA);
      void Q;
    }
  return best;
}
