  // ———————————————— 线条：外轮廓 > 一级结构 > 次级工艺（FIG.01 G2 定，PATTERNS「线条分级」） ————————————————
  /**
   * 线从几何本身取，不做屏幕后处理：所有零件面合成一张表面，按边归并，每条边记下两侧面的法线：
   *   · 两侧面一前一后（每帧判断）→ 外轮廓 L0；
   *   · 折角 > CREASE，或两侧属于不同的“蒙皮组”→ 一级结构 L1（至少一侧朝向相机时画）；
   *   · 只有一侧面的边 → 一级结构 L1（蒙皮组 "skin" 自己的边界不画）；
   *   · 几何母版给出的分割线 / 口盖线（seams）→ 次级工艺 L2，level "structure" 的按 L1。
   * 同一蒙皮里相邻凸格（或同一网格里相邻三角形）之间的接缝不出线。
   * FIG.02 新增：level "accent" 的线（朱红棱线）单独一层，颜色 / 线宽 / 不透明度用 DATA.lines.accent，
   * 通电量 power 由 0 到 1 沿线点亮（aU = 沿线 0…1 的位置，uSweep 为点亮到哪里），并画进发光缓冲。
   */
  const LINE = { contour: 1, structure: 2, secondary: 3 };
  const CREASE_FROM = 22;
  const CREASE_FULL = 34;
  const CREASE = Math.cos((CREASE_FROM * Math.PI) / 180);
  /** 蒙皮组：part.skin 指名；没有就按 smooth 组；再没有就自成一组（独立零件，与相邻零件的接缝出 L1）。 */
  const skinOf = (part) => part.skin ?? part.smooth ?? part.name;
  const KIND = { smooth: 0, crease: 1, seam: 2, boundary: 3, secondary: 4 };
  const newSegs = () => ({ a: [], b: [], n1: [], n2: [], kind: [], weight: [], u: [] });
  /** 遮线区（几何母版 masks）：空腔底板连同其下 3 cm，蒙皮在这里的边不出线（门关着时线会穿过薄门）。 */
  const masked = (a, b) => {
    const m = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2, (a[2] + b[2]) / 2];
    return (DATA.masks ?? []).some((planes) => planes.every(([nx, ny, nz, d]) => nx * m[0] + ny * m[1] + nz * m[2] - d < -1e-4));
  };
  function roundFaces({ o, a, s0, s1, r }, n = 48) {
    const A = new THREE.Vector3(...a).normalize();
    const U = new THREE.Vector3(Math.abs(A.z) < 0.9 ? 0 : 1, 0, Math.abs(A.z) < 0.9 ? 1 : 0).cross(A).normalize();
    const V = new THREE.Vector3().crossVectors(A, U);
    const O = new THREE.Vector3(...o);
    const verts = [];
    for (const [s, rad] of [[s0, r[0]], [s1, r[1]]]) for (let i = 0; i < n; i++) verts.push(O.clone().addScaledVector(A, s).addScaledVector(U, rad * Math.cos((i / n) * 2 * Math.PI)).addScaledVector(V, rad * Math.sin((i / n) * 2 * Math.PI)).toArray());
    const faces = [Array.from({ length: n }, (_, i) => n - 1 - i), Array.from({ length: n }, (_, i) => n + i)];
    for (let i = 0; i < n; i++) faces.push([i, (i + 1) % n, n + ((i + 1) % n), n + i]);
    return { v: verts.flat(), faces };
  }
  /** 一个刚体组的线：组内零件的边按边归并定类，加上属于这组的分割线 / 口盖线。 */
  function buildLines(parts, seams) {
    const segs = newSegs();
    const addSeg = (a, b, n1, n2, kind, weight = 1, u = 0) => {
      if (masked(a, b)) return;
      segs.a.push(...a);
      segs.b.push(...b);
      segs.n1.push(...n1);
      segs.n2.push(...n2);
      segs.kind.push(kind);
      segs.weight.push(weight);
      segs.u.push(u);
    };
    const edges = new Map();
    const key = (v, i) => `${Math.round(v[i * 3] * 1e4)},${Math.round(v[i * 3 + 1] * 1e4)},${Math.round(v[i * 3 + 2] * 1e4)}`;
    // 带 edges 的零件（Blender 母版，PATTERNS「复刻标准」）：折边只用母版标记的硬边（线落在倒角中线上，不出双线）；
    // 网格本身只出“曲面轮廓”候选：曲面件（curved）的每条非共面边，平面件里折角 < 11° 的缓边（倒角条的边不算），只在轮廓处画。
    const SMOOTH_MAX = Math.cos((11 * Math.PI) / 180);
    for (const part of parts) {
      if (!part.edges) continue;
      const E = part.edges;
      for (let i = 0; i + 11 < E.length; i += 12) addSeg([E[i], E[i + 1], E[i + 2]], [E[i + 3], E[i + 4], E[i + 5]], [E[i + 6], E[i + 7], E[i + 8]], [E[i + 9], E[i + 10], E[i + 11]], KIND.crease, 1);
      const v = part.v;
      const own = new Map();
      const F = part.f;
      for (let at = 0; at < F.length; at += F[at] + 1) {
        const n = F[at];
        const face = F.subarray ? F.subarray(at + 1, at + 1 + n) : F.slice(at + 1, at + 1 + n);
        const { n: normal, area } = newell(v, face);
        if (area < 1e-10) continue;
        for (let i = 0; i < n; i++) {
          const ka = key(v, face[i]);
          const kb = key(v, face[(i + 1) % n]);
          if (ka === kb) continue;
          const k = ka < kb ? `${ka}|${kb}` : `${kb}|${ka}`;
          let e = own.get(k);
          if (!e) own.set(k, (e = { a: face[i], b: face[(i + 1) % n], sides: [] }));
          e.sides.push(normal);
        }
      }
      for (const { a, b, sides } of own.values()) {
        if (sides.length !== 2) continue;
        const [p, q] = sides;
        const d = p[0] * q[0] + p[1] * q[1] + p[2] * q[2];
        if (d > 0.99995) continue;
        if (!part.curved && d < SMOOTH_MAX) continue;
        addSeg([v[a * 3], v[a * 3 + 1], v[a * 3 + 2]], [v[b * 3], v[b * 3 + 1], v[b * 3 + 2]], p, q, KIND.smooth, 1);
      }
    }
    for (const part of parts) {
      if (part.lines === false || part.edges) continue;
      const skin = part.system === "void" ? "void" : skinOf(part);
      let v;
      let faces;
      if (part.kind !== "round") {
        v = part.v;
        const contact = new Set(part.c ?? []);
        faces = facesOf(part).filter((_, k) => !contact.has(k));
      } else ({ v, faces } = roundFaces(part));
      for (const face of faces) {
        const n = face.length;
        const { n: normal, area } = newell(v, face);
        if (area < 1e-10) continue;
        for (let i = 0; i < n; i++) {
          const ka = key(v, face[i]);
          const kb = key(v, face[(i + 1) % n]);
          if (ka === kb) continue;
          const k = ka < kb ? `${ka}|${kb}` : `${kb}|${ka}`;
          if (!edges.has(k)) edges.set(k, { a: v.slice(face[i] * 3, face[i] * 3 + 3), b: v.slice(face[(i + 1) % n] * 3, face[(i + 1) % n] * 3 + 3), sides: [] });
          edges.get(k).sides.push({ normal, skin });
        }
      }
    }
    const dotOf = (p, q) => p.normal[0] * q.normal[0] + p.normal[1] * q.normal[1] + p.normal[2] * q.normal[2];
    for (const { a, b, sides } of edges.values()) {
      if (sides.length === 1) {
        if (sides[0].skin !== "skin") addSeg(a, b, sides[0].normal, sides[0].normal, KIND.boundary);
        continue;
      }
      // 三张及以上面共边：取最接近连续的一对作外表面
      let [p, q] = sides;
      for (let i = 0; i < sides.length; i++) for (let j = i + 1; j < sides.length; j++) if (dotOf(sides[i], sides[j]) > dotOf(p, q)) [p, q] = [sides[i], sides[j]];
      const angle = (Math.acos(Math.min(1, Math.max(-1, dotOf(p, q)))) * 180) / Math.PI;
      const kind = p.skin !== q.skin ? KIND.seam : dotOf(p, q) < CREASE ? KIND.crease : KIND.smooth;
      addSeg(a, b, p.normal, q.normal, kind, kind === KIND.crease ? Math.min(1, (angle - CREASE_FROM) / (CREASE_FULL - CREASE_FROM)) : 1);
    }
    for (const seam of seams) {
      const total = seam.points.reduce((s, p, i) => (i ? s + Math.hypot(...p.map((c, k) => c - seam.points[i - 1][k])) : 0), 0) || 1;
      let run = 0;
      seam.points.forEach((p, i) => {
        const j = (i + 1) % seam.points.length;
        if (!(i + 1 < seam.points.length || seam.closed)) return;
        const n = seam.normals ? seam.normals[i].map((x, k) => x + seam.normals[j][k]) : [0, 0, 1];
        const l = Math.hypot(...n) || 1;
        const unitN = n.map((x) => x / l);
        const u = run / total;
        run += Math.hypot(...p.map((c, k) => c - seam.points[j][k]));
        // accent 的 aU 是沿线位置（点亮扫过用），其余 seam 不用
        addSeg(p, seam.points[j], unitN, unitN, seam.level === "structure" || seam.level === "accent" ? KIND.boundary : KIND.secondary, 1, (seam.u0 ?? 0) + (seam.u1 - (seam.u0 ?? 0) || 1) * u);
      });
    }
    return segs;
  }

  // 定级在着色器里做（R4 起，原来每帧在 JS 里逐条判断，剖视时 1300 多个内部件的边在手机上要 25 ms）：每条边一个实例，
  // 带两侧面法线与边类；顶点着色器按当前视向（每层一个 uView）判出 外轮廓 / 一级结构 / 次级工艺 / 不画，不画的裁到视锥外。
  // 着色器另做屏幕空间加宽与抗锯齿；投影矩阵每帧算好一次传进去。
  const LINE_VERT = `
    attribute vec3 aA;
    attribute vec3 aB;
    attribute vec3 aN1;
    attribute vec3 aN2;
    attribute float aKind;
    attribute float aWeight;
    attribute float aU;
    uniform vec3 uView;
    uniform float uCap;
    uniform float uDemote;
    uniform float uLow;
    uniform float uAccent;
    uniform float uCreaseDown;
    uniform mat4 uPVM;
    uniform vec2 uRes;
    uniform vec3 uWidth;
    uniform float uBias;
    uniform float uContourBias;
    varying float vDist;
    varying float vHalf;
    varying float vClass;
    varying float vWeight;
    varying float vU;
    varying float vSide;
    void main() {
      // 边类（KIND）：0 缓边（只在轮廓处画）、1 折边、2 蒙皮组接缝、3 一侧面的边、4 分割线 / 口盖线
      float f1 = dot(aN1, uView);
      float f2 = dot(aN2, uView);
      float c = 0.0;
      if (aKind > 3.5) c = (uLow < 0.5 && f1 > 0.02) ? 3.0 : 0.0;
      else if (aKind > 2.5) c = f1 > 0.0 ? (uAccent > 0.5 ? 1.0 : (uCreaseDown > 0.5 ? 3.0 : 2.0)) : 0.0;
      else if (f1 * f2 < 0.0) c = uDemote > 0.5 ? 2.0 : 1.0;
      else if (aKind > 0.5 && (f1 > 0.0 || f2 > 0.0)) c = uCreaseDown > 0.5 ? 3.0 : 2.0;
      if (c > 0.5 && uCap > 0.5) c = max(c, uCap);
      vClass = c;
      vSide = mix(aA, aB, position.x).y;
      vWeight = c < 1.5 ? 1.0 : aWeight;
      vU = aU;
      if (c < 0.5) {
        gl_Position = vec4(0.0, 0.0, 2.0, 1.0);
        vDist = 0.0;
        vHalf = 0.0;
        return;
      }
      vec4 ca = uPVM * vec4(aA, 1.0);
      vec4 cb = uPVM * vec4(aB, 1.0);
      vec2 sa = ca.xy * 0.5 * uRes;
      vec2 sb = cb.xy * 0.5 * uRes;
      vec2 d = sb - sa;
      float len = length(d);
      d = len > 1e-6 ? d / len : vec2(1.0, 0.0);
      vec2 perp = vec2(-d.y, d.x);
      float w = c < 1.5 ? uWidth.x : c < 2.5 ? uWidth.y : uWidth.z;
      float halfW = 0.5 * w + 1.0;
      vec2 corner = position.xy;
      // 段与段首尾相接、不外伸：线条半透明时外伸部分会叠出一串亮珠
      vec2 sc = mix(sa, sb, corner.x) + perp * corner.y * halfW;
      vec4 cc = mix(ca, cb, corner.x);
      cc.xy = sc / (0.5 * uRes);
      cc.z -= c < 1.5 ? uContourBias : uBias;
      gl_Position = cc;
      vDist = corner.y * halfW;
      vHalf = 0.5 * w;
    }`;
  const LINE_FRAG = `
    varying float vDist;
    varying float vHalf;
    varying float vClass;
    varying float vWeight;
    varying float vU;
    uniform vec3 uColor[3];
    uniform vec3 uAlpha;
    uniform float uScale;
    uniform vec3 uLevel;
    uniform vec3 uTint;
    uniform float uTintMix;
    uniform float uAccent;
    uniform float uPower;
    uniform float uSweep;
    uniform float uIdle;
    uniform float uGlowPass;
    uniform vec3 uGlowColor;
    uniform float uCut;
    uniform float uDepthFade;
    varying float vSide;
    void main() {
      // 剖视：cut 层切掉剖切面近侧（零件坐标 y > 0）
      if (uCut > 0.5 && vSide > 0.0015) discard;
      if (vHalf <= 0.0) discard;
      // 覆盖率 = 像素（宽 1）与线（宽 2·vHalf）在法向上的重叠长度：一维盒式滤波的精确积分。细于 1 像素的线落在两个像素之间时，
      // 两个像素的覆盖率之和恒等于线宽——线转动时亮度不随亚像素位置起伏（FIG.01 的近似式在 0.42 px 线上有约 ±15% 的闪）
      float cover = clamp(min(vDist + 0.5, vHalf) - max(vDist - 0.5, -vHalf), 0.0, 1.0);
      int i = vClass < 1.5 ? 0 : vClass < 2.5 ? 1 : 2;
      float alpha = i == 0 ? uAlpha.x : i == 1 ? uAlpha.y : uAlpha.z;
      vec3 col = mix(uColor[i], uTint, i == 2 ? 0.5 * uTintMix : uTintMix);
      alpha = mix(alpha, max(alpha, 0.9), i == 0 ? uTintMix : 0.0);
      alpha *= uScale * (i == 0 ? uLevel.x : i == 1 ? uLevel.y : uLevel.z);
      if (uAccent > 0.5) {
        // 朱红棱线：未通电只亮 uIdle；通电从 aU = 0（机头）扫到 uSweep，扫过处带一小段更亮的前沿
        float lit = 1.0 - smoothstep(uSweep - 0.06, uSweep, vU);
        float front = exp(-pow((vU - uSweep) / 0.04, 2.0)) * step(0.001, uSweep) * (1.0 - step(0.999, uSweep));
        float k = mix(uIdle, 1.0, lit * uPower) + 0.6 * front * uPower;
        if (uGlowPass > 0.5) { gl_FragColor = vec4(uGlowColor, cover * (lit * uPower + front * uPower)); return; }
        gl_FragColor = vec4(col, cover * alpha * k);
        return;
      }
      // 剖视的远近分档：离剖切面越远（零件坐标 −y）线越淡
      alpha *= 1.0 - 0.5 * uDepthFade * smoothstep(0.05, 0.55, -vSide);
      gl_FragColor = vec4(col, cover * alpha * vWeight);
    }`;
  const STYLE = DATA.lines;
  // 四个角 + 索引（顶点缓存复用，每条边 4 次顶点着色而不是 6 次；剖视时几十万条边，顶点量是 GPU 的大头）
  const QUAD = new THREE.Float32BufferAttribute([0, -1, 0, 1, -1, 0, 1, 1, 0, 0, 1, 0], 3);
  const QUAD_INDEX = new THREE.Uint16BufferAttribute([0, 1, 2, 0, 2, 3], 1);
  const lineShared = { uGlowPass: { value: 0 } };
  const lineCut = { value: 0 };
  /** 剖视时线条按离剖切面远近变淡（与 10-materials 的 uDepthFade 同开同关）。 */
  const lineDepthFade = { value: 0 };
  /** 画法对线条的影响：B（metal）线条降一级（各级不透明度乘 DATA.metal.lines）；后加载的模块线层也按当前画法建。 */
  /** B 的线：外轮廓保留浅色，结构线与分割线改成深色细缝（浅色金属面上读成刻出来的缝）；颜色 / 不透明度在 DATA.metal。 */
  const metalLines = () => ({ levels: DATA.metal.lines, color: DATA.metal.lineColor ?? null, alpha: DATA.metal.lineAlpha ?? null });
  const drawingLines = () => ({ levels: [1, 1, 1], color: null, alpha: null });
  const lineLook = DATA.look === "metal" ? metalLines() : drawingLines();
  const lineLayers = [];
  function lineLayer(list, parent, { style = STYLE, accent = false } = {}) {
    const count = list.kind.length;
    // 每条边一个实例：基础几何是一个四边形（4 顶点 + 索引），端点、两侧面法线、边类、权重、沿线位置是实例属性
    const g = new THREE.InstancedBufferGeometry();
    g.setAttribute("position", QUAD);
    g.setIndex(QUAD_INDEX);
    const inst = (data, size) => new THREE.InstancedBufferAttribute(data, size);
    g.setAttribute("aA", inst(Float32Array.from(list.a), 3));
    g.setAttribute("aB", inst(Float32Array.from(list.b), 3));
    g.setAttribute("aN1", inst(Float32Array.from(list.n1), 3));
    g.setAttribute("aN2", inst(Float32Array.from(list.n2), 3));
    g.setAttribute("aKind", inst(Float32Array.from(list.kind), 1));
    g.setAttribute("aWeight", inst(Float32Array.from(list.weight), 1));
    g.setAttribute("aU", inst(Float32Array.from(list.u, (x) => x ?? 0), 1));
    g.instanceCount = count;
    const uniforms = {
      ...lineShared,
      uPVM: { value: new THREE.Matrix4() },
      uRes: { value: new THREE.Vector2(1, 1) },
      uWidth: { value: new THREE.Vector3() },
      uBias: { value: (2 * STYLE.bias) / (camera.far - camera.near) },
      uContourBias: { value: (2 * STYLE.contourBias) / (camera.far - camera.near) },
      uColor: { value: (!accent && lineLook.color ? lineLook.color : style.color).map(rgb) },
      uAlpha: { value: new THREE.Vector3(...(!accent && lineLook.alpha ? lineLook.alpha : style.alpha)) },
      uTint: { value: new THREE.Color() },
      uTintMix: { value: 0 },
      uScale: { value: 1 },
      uLevel: { value: new THREE.Vector3(...(accent ? [1, 1, 1] : lineLook.levels)) },
      uAccent: { value: accent ? 1 : 0 },
      uPower: accent ? powerOf(accent.key) : { value: 0 },
      uSweep: accent ? powerOf(`${accent.key}.sweep`) : { value: 0 },
      uIdle: { value: accent ? accent.idle : 0 },
      uGlowColor: { value: rgb(accent ? accent.glow : "#000000") },
      uCut: { value: 0 },
      uDepthFade: lineDepthFade,
      uView: { value: new THREE.Vector3(1, 0, 0) },
      uCap: { value: 0 },
      uDemote: { value: 0 },
      uLow: { value: 0 },
      uCreaseDown: { value: 0 },
    };
    const mat = new THREE.ShaderMaterial({ vertexShader: LINE_VERT, fragmentShader: LINE_FRAG, transparent: true, depthWrite: false, uniforms });
    const mesh = new THREE.Mesh(g, mat);
    mesh.frustumCulled = false;
    mesh.renderOrder = accent ? 2.1 : 2;
    parent.add(mesh);
    const inverse = new THREE.Matrix4();
    let contourBase = STYLE.contourBias;
    const layer = {
      mesh,
      accent: !!accent,
      demote: false,
      cap: 0,
      creaseDown: false,
      width: style.width,
      contourBias(m) {
        contourBase = m;
      },
      scale(k) {
        uniforms.uScale.value = k;
      },
      levels(a, b, c) {
        uniforms.uLevel.value.set(a, b, c);
      },
      /** 画法切换：三级线的颜色与不透明度（null = 回到线层自己的样式）。 */
      colors(color, alpha) {
        uniforms.uColor.value = (color ?? style.color).map(rgb);
        uniforms.uAlpha.value.set(...(alpha ?? style.alpha));
      },
      /** 剖视时切掉 y > 0 一侧（只对 cut 层）。 */
      clip(on) {
        uniforms.uCut.value = on ? 1 : 0;
      },
      tint(hex, k = 1) {
        uniforms.uTintMix.value = hex ? k : 0;
        if (hex) uniforms.uTint.value.set(hex);
      },
      /** 视向换到零件所在坐标系交给着色器（定级在 GPU 上），投影矩阵与深度偏移每帧更新。 */
      update() {
        // 线条的深度偏移随取景放大缩小（特写 14× 时 2 cm 的偏移会让线透过贴着蒙皮的零件露出来）
        const k = 1 / Math.max(camera.zoom, 1);
        uniforms.uBias.value = (2 * Math.max(STYLE.bias * k, 0.0015)) / (camera.far - camera.near);
        uniforms.uContourBias.value = (2 * Math.max(contourBase * k, 0.01)) / (camera.far - camera.near);
        uniforms.uPVM.value.multiplyMatrices(camera.projectionMatrix, camera.matrixWorldInverse).multiply(mesh.matrixWorld);
        uniforms.uView.value.copy(VIEW).applyMatrix4(inverse.copy(mesh.matrixWorld).invert().setPosition(0, 0, 0)).normalize();
        uniforms.uCap.value = this.cap;
        uniforms.uDemote.value = this.demote ? 1 : 0;
        uniforms.uLow.value = lowQuality() ? 1 : 0;
        uniforms.uCreaseDown.value = this.creaseDown ? 1 : 0;
      },
      resize(w, h, ratio) {
        uniforms.uRes.value.set(w * ratio, h * ratio);
        uniforms.uWidth.value.set(...style.width.map((x) => x * ratio));
      },
    };
    lineLayers.push(layer);
    return layer;
  }
  /** 每个刚体组一层线（挂在组上，随关节动）；分割线按 seam.joint 归组；accent 线另成一层。groupLines：组键 → 线层。 */
  const groupLines = new Map();
  const airLayers = [];
  const accentLayers = [];
  /** 零件与分割线 → 线层（按刚体组、降级、show、cut 分层）；按需模块加载后再调一次。返回新建的线层。 */
  function buildLayers(parts, seams) {
    const slots = new Map();
    const made = [];
    // lineLevel "secondary"：这一层所有边一律降为次级线（细密的重复件：鳞片瓦、虹膜遮片），单独一层
    const slot = (group, cap = 0, show = null, cut = false, glass = false, creaseDown = false) => {
      const key = `${group}|${cap}|${show ?? ""}|${cut ? 1 : 0}|${glass ? 1 : 0}|${creaseDown ? 1 : 0}`;
      if (!slots.has(key)) slots.set(key, { group, cap, show, cut, glass, creaseDown, parts: [], seams: [] });
      return slots.get(key);
    };
    // 玻璃件的线单独一层（剖视时转青色）；剖视内部件（module interior、lineLevel structure）：外轮廓 L1、折边降到 L2（R4：内部次要线降一级）
    for (const part of parts) slot(keyOf(part), part.lineLevel === "secondary" ? LINE.secondary : part.lineLevel === "structure" ? LINE.structure : 0, part.show ?? null, !!part.cut, !!part.glass, part.module === "interior" && part.lineLevel === "structure").parts.push(part);
    const accents = new Map();
    for (const seam of seams ?? []) {
      const key = groupKey(seam.joint);
      if (seam.level === "accent") {
        const k = `${key}|${seam.accent ?? "accent"}`;
        if (!accents.has(k)) accents.set(k, { key, spec: DATA.lines.accents[seam.accent ?? "accent"], seams: [] });
        accents.get(k).seams.push(seam);
      } else slot(key, 0, seam.show ?? null, seam.cut ?? true).seams.push(seam);
    }
    for (const [key, { group, cap, show, cut, glass, creaseDown, parts: ps, seams: ss }] of slots) {
      const segs = buildLines(ps, ss);
      if (!segs.kind.length) continue;
      const layer = lineLayer(segs, groupObj(group));
      layer.group = group;
      layer.cap = cap;
      layer.show = show;
      layer.cut = cut;
      layer.glass = glass;
      layer.creaseDown = !!creaseDown;
      groupLines.set(key, layer);
      airLayers.push(layer);
      made.push(layer);
    }
    for (const { key, spec, seams: ss } of accents.values()) {
      const segs = buildLines([], ss);
      const layer = lineLayer(segs, groupObj(key), { style: { width: [spec.width, spec.width, spec.width], color: [spec.color, spec.color, spec.color], alpha: [spec.alpha, spec.alpha, spec.alpha] }, accent: spec });
      layer.group = key;
      layer.cut = true;
      airLayers.push(layer);
      accentLayers.push(layer);
      made.push(layer);
    }
    return made;
  }
  buildLayers(DATA.parts, DATA.seams);
