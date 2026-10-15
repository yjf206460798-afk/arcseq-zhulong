// 渲染前处理（不改几何母版）。

/**
 * 补 T 形接缝：相邻凸格在同一站位截面上取同一圈点，但凸包会丢掉恰在直边上或共面的点，于是一侧的顶点落在另一侧的边中间，
 * 栅格化时那条边两侧不严丝合缝，露出一串背景色的点。这里把每个零件落在别的零件边上的顶点插进那条边（只改渲染用的面环，不改几何母版）。
 */
export function weldTJunctions(hulls, eps = 2e-4) {
  const boxes = hulls.map((H) => {
    const lo = [Infinity, Infinity, Infinity];
    const hi = [-Infinity, -Infinity, -Infinity];
    for (const p of H.verts) for (let c = 0; c < 3; c++) (lo[c] = Math.min(lo[c], p[c])), (hi[c] = Math.max(hi[c], p[c]));
    return { lo: lo.map((v) => v - eps), hi: hi.map((v) => v + eps) };
  });
  const inside = (p, b) => p.every((v, c) => v >= b.lo[c] && v <= b.hi[c]);
  let inserted = 0;
  for (let i = 0; i < hulls.length; i++) {
    const A = hulls[i];
    const extra = new Map();
    for (let j = 0; j < hulls.length; j++) {
      if (i === j || !boxes[j].lo.every((v, c) => v <= boxes[i].hi[c] && boxes[j].hi[c] >= boxes[i].lo[c])) continue;
      for (const p of hulls[j].verts) {
        if (!inside(p, boxes[i]) || A.verts.some((q) => Math.abs(q[0] - p[0]) + Math.abs(q[1] - p[1]) + Math.abs(q[2] - p[2]) < eps)) continue;
        A.faces.forEach((face, fi) =>
          face.forEach((ia, k) => {
            const a = A.verts[ia];
            const b = A.verts[face[(k + 1) % face.length]];
            const ab = [b[0] - a[0], b[1] - a[1], b[2] - a[2]];
            const L2 = ab[0] ** 2 + ab[1] ** 2 + ab[2] ** 2;
            if (L2 < 1e-12) return; // 取整后重合的两点：零长边
            const t = ((p[0] - a[0]) * ab[0] + (p[1] - a[1]) * ab[1] + (p[2] - a[2]) * ab[2]) / L2;
            if (!(t > 1e-3 && t < 1 - 1e-3)) return;
            const d = Math.hypot(a[0] + t * ab[0] - p[0], a[1] + t * ab[1] - p[1], a[2] + t * ab[2] - p[2]);
            if (!(d <= eps)) return;
            const key = `${fi}:${k}`;
            if (!extra.has(key)) extra.set(key, []);
            const list = extra.get(key);
            if (!list.some((e) => Math.abs(e.t - t) < 1e-4)) list.push({ t, p });
          }),
        );
      }
    }
    if (!extra.size) continue;
    const verts = A.verts.slice();
    const faces = A.faces.map((face, fi) =>
      face.flatMap((ia, k) => {
        const list = (extra.get(`${fi}:${k}`) ?? []).sort((x, y) => x.t - y.t);
        return [
          ia,
          ...list.map((e) => {
            inserted++;
            verts.push(e.p);
            return verts.length - 1;
          }),
        ];
      }),
    );
    hulls[i] = { verts, faces };
  }
  return inserted;
}

/**
 * 去掉接触面：两个零件贴面相接时（相邻凸格的站位端面、座舱盖底面贴在座舱口平面上……），两张面共面、法线相反，
 * 都在机体里面看不见，但在外表面的接缝上会和外表面抢深度，沿接缝露出一串暗点。
 *   · 一张面整个落在对面那张里（顶点全在其内）→ 不画；
 *   · 一张大面被几张整落其中的小面拼满（≥ 99% 面积）→ 也不画（例：一格的端面对着中柱 + 左右外筒三张端面）；
 *   · 只部分重叠的（座舱盖底面跨过好几格前机身顶面）两边都保留——画出来也被外表面盖住——但记为“接触面”，
 *     取线时当它不存在，于是座舱盖底边成为一级结构线而不是外轮廓。
 *   · 两个零件分属不同的刚体组（groups[i] ≠ groups[j]，例如座舱盖与机身、舱门与机腹）时一律保留：零件动起来后这些面会露出来。
 *     它们也记为接触面，另记在 cross 里，页面把它们往后推一点画（深度打平时让外表面赢）。
 * 返回 { dropped, contact, cross }，contact[i] / cross[i] 是第 i 个零件（去掉不画的面之后）的面序号表。
 */
export function dropContactFaces(hulls, groups = hulls.map(() => ""), eps = 1e-3) {
  const planeOf = (H, face) => {
    let n = [0, 0, 0];
    for (let i = 0; i < face.length; i++) {
      const a = H.verts[face[i]];
      const b = H.verts[face[(i + 1) % face.length]];
      n = [n[0] + (a[1] - b[1]) * (a[2] + b[2]), n[1] + (a[2] - b[2]) * (a[0] + b[0]), n[2] + (a[0] - b[0]) * (a[1] + b[1])];
    }
    const area = Math.hypot(...n) / 2;
    n = n.map((v) => v / (2 * area || 1));
    const c = face.reduce((s, i) => s.map((v, k) => v + H.verts[i][k] / face.length), [0, 0, 0]);
    return { n, d: n[0] * c[0] + n[1] * c[1] + n[2] * c[2], area, c };
  };
  /** p 是否在面内（含边，容差 tol 米）。 */
  const inside = (H, face, n, p, tol = 2e-4) => {
    for (let i = 0; i < face.length; i++) {
      const a = H.verts[face[i]];
      const b = H.verts[face[(i + 1) % face.length]];
      const e = [b[0] - a[0], b[1] - a[1], b[2] - a[2]];
      const q = [p[0] - a[0], p[1] - a[1], p[2] - a[2]];
      const x = [e[1] * q[2] - e[2] * q[1], e[2] * q[0] - e[0] * q[2], e[0] * q[1] - e[1] * q[0]];
      if (x[0] * n[0] + x[1] * n[1] + x[2] * n[2] < -tol * Math.hypot(...e)) return false;
    }
    return true;
  };
  const planes = hulls.map((H) => H.faces.map((f) => planeOf(H, f)));
  const drop = hulls.map(() => new Set());
  const touch = hulls.map(() => new Set());
  const across = hulls.map(() => new Set());
  // 跨组接触面的对面零件（G4.6 补轮：拆解时哪些贴面会露出来要按“对面是不是另一个总成”判断）
  const partner = hulls.map(() => new Map());
  const covered = hulls.map((H) => H.faces.map(() => 0));
  for (let i = 0; i < hulls.length; i++)
    for (let j = i + 1; j < hulls.length; j++)
      planes[i].forEach((P, fi) =>
        planes[j].forEach((Q, fj) => {
          // 法线相反、且对面那张的形心到本面的距离小于 eps（不直接比 d：法线差一点，离原点远处 d 就差出毫米）
          if (Math.abs(P.n[0] + Q.n[0]) + Math.abs(P.n[1] + Q.n[1]) + Math.abs(P.n[2] + Q.n[2]) > 1e-3) return;
          if (Math.abs(P.n[0] * Q.c[0] + P.n[1] * Q.c[1] + P.n[2] * Q.c[2] - P.d) > eps || Math.abs(Q.n[0] * P.c[0] + Q.n[1] * P.c[1] + Q.n[2] * P.c[2] - Q.d) > eps) return;
          const [si, sf, SP, li, lf, LP] = P.area <= Q.area ? [i, fi, P, j, fj, Q] : [j, fj, Q, i, fi, P];
          const small = hulls[si].faces[sf];
          const large = hulls[li].faces[lf];
          const within = small.every((v) => inside(hulls[li], large, LP.n, hulls[si].verts[v]));
          const overlap = within || inside(hulls[li], large, LP.n, SP.c) || large.some((v) => inside(hulls[si], small, SP.n, hulls[li].verts[v]));
          if (!overlap) return;
          touch[si].add(sf);
          touch[li].add(lf);
          if (groups[si] !== groups[li]) {
            across[si].add(sf);
            across[li].add(lf);
            if (!partner[si].has(sf)) partner[si].set(sf, new Set());
            if (!partner[li].has(lf)) partner[li].set(lf, new Set());
            partner[si].get(sf).add(li);
            partner[li].get(lf).add(si);
            return;
          }
          if (!within) return;
          drop[si].add(sf);
          covered[li][lf] += SP.area;
        }),
      );
  covered.forEach((list, i) => list.forEach((area, f) => area >= 0.99 * planes[i][f].area && !across[i].has(f) && drop[i].add(f)));
  let dropped = 0;
  const cross = [];
  const crossWith = [];
  const contact = hulls.map((H, i) => {
    dropped += drop[i].size;
    const keep = H.faces.map((_, f) => f).filter((f) => !drop[i].has(f));
    H.faces = keep.map((f) => H.faces[f]);
    cross.push(keep.map((f, k) => (across[i].has(f) ? k : -1)).filter((k) => k >= 0));
    crossWith.push(keep.flatMap((f, k) => (partner[i].has(f) ? [[k, [...partner[i].get(f)]]] : [])));
    return keep.map((f, k) => (touch[i].has(f) ? k : -1)).filter((k) => k >= 0);
  });
  return { dropped, contact, cross, crossWith };
}
