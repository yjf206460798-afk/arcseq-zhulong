  // ———————————————— 几何：零件 → 网格 ————————————————
  // 零件格式（build.mjs 统一）：
  //   kind "hull"：凸包（FIG.01 几何母版），v 平铺坐标、f 面环 [n, i0…], c 接触面、x 跨组接触面、lip 唇口面、t 顶点提亮；
  //   kind "mesh"：任意多边形网格（Blender GLB 转来），同样的 v / f，另可带 n（逐顶点法线，Blender 的平滑 / 锐边）、ao（逐顶点 AO）、uv；
  //   kind "round"：圆柱 / 圆台 { o, a, s0, s1, r }。
  // 通用字段：name、joint、system（"void" 空腔 / "interior" / …）、material、skin（线条蒙皮组）、smooth（平滑组）、glow { key, color }。
  const facesOf = (part) => {
    const faces = [];
    for (let at = 0; at < part.f.length; ) faces.push(Array.from(part.f.slice(at + 1, at + 1 + part.f[at]))), (at += part.f[at] + 1);
    return faces;
  };
  function newell(v, face) {
    let nx = 0;
    let ny = 0;
    let nz = 0;
    for (let i = 0; i < face.length; i++) {
      const a = face[i] * 3;
      const b = face[(i + 1) % face.length] * 3;
      nx += (v[a + 1] - v[b + 1]) * (v[a + 2] + v[b + 2]);
      ny += (v[a + 2] - v[b + 2]) * (v[a] + v[b]);
      nz += (v[a] - v[b]) * (v[a + 1] + v[b + 1]);
    }
    const l = Math.hypot(nx, ny, nz) || 1;
    return { n: [nx / l, ny / l, nz / l], area: l / 2 };
  }
  const posKey = (v, i) => `${Math.round(v[i * 3] * 1e4)},${Math.round(v[i * 3 + 1] * 1e4)},${Math.round(v[i * 3 + 2] * 1e4)}`;
  /**
   * 平滑法线（凸包零件）：同一平滑组（part.smooth）里共用一个顶点位置、且彼此折角小于 SMOOTH 的面按面积加权平均；
   * 折角大的保持折边。接触面、唇口面不参加。没有平滑组的平板零件保持平面着色。网格零件带 n 时直接用它（Blender 里定好的锐边）。
   */
  const SMOOTH = Math.cos((35 * Math.PI) / 180);
  const smoothGroupOf = (part) => part.smooth ?? null;
  const around = new Map();
  for (const part of DATA.parts) {
    const group = part.kind !== "round" && !part.n && smoothGroupOf(part);
    if (!group) continue;
    const skip = new Set([...(part.c ?? []), ...(part.lip ?? [])]);
    facesOf(part).forEach((face, k) => {
      if (skip.has(k)) return;
      const { n, area } = newell(part.v, face);
      for (const i of face) {
        const key = posKey(part.v, i);
        if (!around.has(key)) around.set(key, []);
        around.get(key).push({ n, area, group });
      }
    });
  }
  /** 空腔深度（aDepth，0 = 口沿、1 = 最深）：depth { c, r[, axis] } 按到中心点（或中心线）的距离渐深，否则面形心为 1、顶点为 0。 */
  function depthOf(part) {
    const spec = part.depth;
    if (!spec) return null;
    return (p) => {
      let d = [p[0] - spec.c[0], p[1] - spec.c[1], p[2] - spec.c[2]];
      if (spec.axis) {
        const k = d[0] * spec.axis[0] + d[1] * spec.axis[1] + d[2] * spec.axis[2];
        d = d.map((v, i) => v - k * spec.axis[i]);
      }
      return Math.max(0, Math.min(1, 1 - Math.hypot(...d) / spec.r));
    };
  }
  const newBucket = () => ({ pos: [], nor: [], mark: [], depth: [], ao: [], glow: [], uv: [] });
  /** 多边形零件：三角形原样；多边形按形心扇形三角化（面环上有补 T 形接缝插入的共线点，不能生成零面积三角形）。跨组接触面另放一桶。 */
  function polyGeometry(part) {
    const v = part.v;
    const group = smoothGroupOf(part);
    const flatFaces = new Set([...(part.c ?? []), ...(part.lip ?? [])]);
    const lip = new Set(part.lip ?? []);
    const crossFaces = new Set(part.x ?? []);
    const mouth = part.system === "void";
    const deep = depthOf(part);
    const glowW = part.glow ? 1 : 0;
    const out = { main: newBucket(), recess: newBucket() };
    facesOf(part).forEach((face, k) => {
      const B = crossFaces.has(k) ? out.recess : out.main;
      const { n: nf } = newell(v, face);
      const normals = face.map((i) => {
        if (part.n && !flatFaces.has(k)) return [part.n[i * 3], part.n[i * 3 + 1], part.n[i * 3 + 2]];
        if (!group || flatFaces.has(k)) return nf;
        let x = 0;
        let y = 0;
        let z = 0;
        for (const e of around.get(posKey(v, i)) ?? []) {
          if (e.group !== group || e.n[0] * nf[0] + e.n[1] * nf[1] + e.n[2] * nf[2] < SMOOTH) continue;
          x += e.n[0] * e.area;
          y += e.n[1] * e.area;
          z += e.n[2] * e.area;
        }
        const l = Math.hypot(x, y, z);
        return l > 1e-9 ? [x / l, y / l, z / l] : nf;
      });
      const isLip = lip.has(k) ? 1 : 0;
      const P = (i) => [v[i * 3], v[i * 3 + 1], v[i * 3 + 2]];
      const T = (i) => (part.t ? part.t[i] : 0);
      const A = (i) => (part.ao ? part.ao[i] : 1);
      const U = (i) => (part.uv ? [part.uv[i * 2], part.uv[i * 2 + 1]] : [0, 0]);
      const dv = (p) => (deep ? deep(p) : 0);
      const put = (p, n, t, d, ao, uv) => {
        B.pos.push(...p);
        B.nor.push(...n);
        B.mark.push(t, isLip);
        B.depth.push(d);
        B.ao.push(ao);
        B.glow.push(glowW);
        B.uv.push(...uv);
      };
      const vert = (j) => put(P(face[j]), normals[j], T(face[j]), dv(P(face[j])), A(face[j]), U(face[j]));
      if (face.length === 3) {
        for (let j = 0; j < 3; j++) vert(j);
        return;
      }
      const m = face.length;
      const avg = (f, n) => face.reduce((acc, i) => acc.map((a, q) => a + f(i)[q] / m), new Array(n).fill(0));
      const c = avg(P, 3);
      const cn = normals.reduce((acc, n) => acc.map((a, q) => a + n[q]), [0, 0, 0]);
      const cl = Math.hypot(...cn) || 1;
      const ct = face.reduce((a, i) => a + T(i), 0) / m;
      const ca = face.reduce((a, i) => a + A(i), 0) / m;
      const cu = avg(U, 2);
      for (let j = 0; j < m; j++) {
        put(c, cn.map((a) => a / cl), ct, deep ? deep(c) : mouth ? 1 : 0, ca, cu);
        vert(j);
        vert((j + 1) % m);
      }
    });
    return out;
  }
  /** 圆柱 / 圆台：沿轴 a，从 s0 到 s1，半径 r0 → r1；侧面平滑法线，两端平面。 */
  function roundGeometry({ o, a, s0, s1, r }, segments = 48) {
    const Ax = new THREE.Vector3(...a).normalize();
    const U = new THREE.Vector3(Math.abs(Ax.z) < 0.9 ? 0 : 1, 0, Math.abs(Ax.z) < 0.9 ? 1 : 0).cross(Ax).normalize();
    const V = new THREE.Vector3().crossVectors(Ax, U);
    const O = new THREE.Vector3(...o);
    const B = newBucket();
    const slope = (r[0] - r[1]) / (s1 - s0);
    const ring = (s, rad, t) => O.clone().addScaledVector(Ax, s).addScaledVector(U, rad * Math.cos(t)).addScaledVector(V, rad * Math.sin(t));
    const radial = (t) => U.clone().multiplyScalar(Math.cos(t)).addScaledVector(V, Math.sin(t)).addScaledVector(Ax, slope).normalize();
    const push = (p, n) => {
      B.pos.push(p.x, p.y, p.z);
      B.nor.push(n.x, n.y, n.z);
      B.mark.push(0, 0);
      B.depth.push(0);
      B.ao.push(1);
      B.glow.push(0);
      B.uv.push(0, 0);
    };
    for (let i = 0; i < segments; i++) {
      const t0 = (i / segments) * 2 * Math.PI;
      const t1 = ((i + 1) / segments) * 2 * Math.PI;
      const [a0, a1, b0, b1] = [ring(s0, r[0], t0), ring(s0, r[0], t1), ring(s1, r[1], t0), ring(s1, r[1], t1)];
      const [n0, n1] = [radial(t0), radial(t1)];
      push(a0, n0), push(a1, n1), push(b1, n1);
      push(a0, n0), push(b1, n1), push(b0, n0);
      const back = Ax.clone().negate();
      push(O.clone().addScaledVector(Ax, s0), back), push(a1, back), push(a0, back);
      push(O.clone().addScaledVector(Ax, s1), Ax), push(b0, Ax), push(b1, Ax);
    }
    return { main: B };
  }

  // ———————————————— 关节与刚体组（FIG.01 G3 定，PATTERNS「关节、机构与状态」） ————————————————
  /**
   * 每个关节一个组（Object3D），按 parent 嵌套；组的矩阵 = 绕关节点转动（hinge）或沿轴平移（slide），零件几何保持静止坐标。
   * 零件按（所属刚体组、材质、是否跨组接触面）合并成少数几个网格；ranges 记下每段顶点属于哪个零件，点选时查回零件。
   */
  const jointObj = new Map();
  const jointDef = new Map(DATA.joints.map((j) => [j.name, j]));
  for (const j of DATA.joints) {
    const o = new THREE.Group();
    o.name = `joint:${j.name}`;
    o.matrixAutoUpdate = false;
    jointObj.set(j.name, o);
  }
  for (const j of DATA.joints) (j.parent ? jointObj.get(j.parent) : airframe).add(jointObj.get(j.name));
  /** 被机构驱动的关节（及其上级）才单独成组；没接机构的关节并进静止组。 */
  const driven = new Set();
  for (const c of DATA.controls) for (let j of [...(c.drive ?? []).map((d) => d.joint), ...(c.steps ?? []).map((st) => st.joint)]) for (; j; j = jointDef.get(j)?.parent) driven.add(j);
  const keyOf = (part) => (part.joint && driven.has(part.joint) ? part.joint : "");
  const groupKey = (joint) => (joint && driven.has(joint) ? joint : "");
  const groupObj = (key) => (key && driven.has(key) ? jointObj.get(key) : airframe);
  const jointValue = new Map();
  const tmpM = new THREE.Matrix4();
  const tmpV = new THREE.Vector3();
  /** 关节取值：hinge 为度、slide 为米；只改组矩阵。 */
  function setJoint(name, value) {
    const j = jointDef.get(name);
    const o = jointObj.get(name);
    if (!j || !o || jointValue.get(name) === value) return;
    jointValue.set(name, value);
    const [px, py, pz] = j.point;
    if (j.type === "slide") o.matrix.makeTranslation(j.axis[0] * value, j.axis[1] * value, j.axis[2] * value);
    else {
      o.matrix.makeTranslation(px, py, pz);
      o.matrix.multiply(tmpM.makeRotationAxis(tmpV.set(...j.axis).normalize(), value * D2R));
      o.matrix.multiply(tmpM.makeTranslation(-px, -py, -pz));
    }
    o.matrixWorldNeedsUpdate = true;
  }

  const pickables = [];
  const glowMeshes = [];
  /** 带 show 的网格（剖视面带等）：按状态显隐；cut 的网格在剖视时被剖切面切开。modules：模块名 → 它的网格与线层。 */
  const showMeshes = [];
  const cutMeshes = [];
  /**
   * 零件 → 网格：按（刚体组、材质、跨组接触面、show、cut）合并成少数网格。parts 已在 DATA.parts 里，first 为第一个的序号
   * （点选按序号查回零件）。按需模块（剖视内部）加载后再调一次。返回新建的网格。
   */
  function buildMeshes(parts, first = 0) {
    const buckets = new Map();
    const made = [];
    parts.forEach((part, k) => {
      const index = first + k;
      const material = materialOf(part);
      const geo = part.kind === "round" ? roundGeometry(part) : polyGeometry(part);
      for (const [kind, data] of Object.entries(geo)) {
        if (!data.pos.length) continue;
        const key = `${keyOf(part)}|${kind}|${material.uuid}|${part.show ?? ""}|${part.cut ? 1 : 0}`;
        if (!buckets.has(key)) buckets.set(key, { joint: keyOf(part), glow: !!part.glow, show: part.show ?? null, cut: !!part.cut, material: kind === "recess" ? recess(material) : material, ...newBucket(), ranges: [] });
        const b = buckets.get(key);
        b.ranges.push([b.pos.length / 3, (b.pos.length + data.pos.length) / 3, index]);
        for (const q of ["pos", "nor", "mark", "depth", "ao", "glow", "uv"]) for (let i = 0; i < data[q].length; i++) b[q].push(data[q][i]);
      }
    });
    for (const b of buckets.values()) {
      const g = new THREE.BufferGeometry();
      g.setAttribute("position", new THREE.Float32BufferAttribute(b.pos, 3));
      g.setAttribute("normal", new THREE.Float32BufferAttribute(b.nor, 3));
      g.setAttribute("aMark", new THREE.Float32BufferAttribute(b.mark, 2));
      g.setAttribute("aDepth", new THREE.Float32BufferAttribute(b.depth, 1));
      g.setAttribute("aAO", new THREE.Float32BufferAttribute(b.ao, 1));
      g.setAttribute("aGlow", new THREE.Float32BufferAttribute(b.glow, 1));
      g.setAttribute("uv", new THREE.Float32BufferAttribute(b.uv, 2));
      g.computeBoundingSphere();
      const mesh = new THREE.Mesh(g, b.cut ? cutMaterial(b.material) : b.material);
      mesh.userData.ranges = b.ranges;
      mesh.userData.show = b.show;
      groupObj(b.joint).add(mesh);
      pickables.push(mesh);
      if (b.glow) glowMeshes.push(mesh);
      if (b.show) showMeshes.push(mesh);
      if (b.cut) cutMeshes.push(mesh);
      made.push(mesh);
    }
    return made;
  }
  buildMeshes(DATA.parts);
  /** 点选：射线打到的三角形 → 所在零件。 */
  function partAt(hit) {
    const ranges = hit.object.userData.ranges;
    if (!ranges) return null;
    const vertex = hit.faceIndex * 3;
    let lo = 0;
    let hi = ranges.length - 1;
    while (lo < hi) {
      const mid = (lo + hi + 1) >> 1;
      if (ranges[mid][0] <= vertex) lo = mid;
      else hi = mid - 1;
    }
    return DATA.parts[ranges[lo][2]];
  }
