  // ———————————————— 明暗材质：n·L 分五档，档间 smoothstep（FIG.01 G2 定，PATTERNS「渲染」） ————————————————
  // 法线逐像素插值：曲面用平滑法线，档界是光滑曲线而不是多边形台阶；平面零件仍是面法线。
  // aMark.x：鼓包提亮（0～1）；aMark.y：唇口厚度边；aDepth：空腔由口沿到深处（0～1）。
  // FIG.02 新增（Z1）：aAO 顶点环境光遮蔽（1 = 开阔、0 = 全遮）；uv + uDetail 烘焙细节贴图（r 刻线压暗、g 涂装提亮、b 贴图 AO）；
  // aGlow 自发光权重（乘 uGlowColor × 通电量），同一份发光量也画进发光缓冲做选择性泛光（80-post.js）。
  const VERT = `
    attribute vec2 aMark;
    attribute float aDepth;
    attribute float aAO;
    attribute float aGlow;
    varying vec3 vN;
    varying vec2 vMark;
    varying float vDepth;
    varying float vAO;
    varying float vGlow;
    varying vec2 vUv;
    varying vec3 vM0;
    varying vec3 vM1;
    varying vec3 vM2;
    varying vec3 vW;
    #include <clipping_planes_pars_vertex>
    void main() {
      vec4 mvPosition = viewMatrix * modelMatrix * vec4(position, 1.0);
      #include <clipping_planes_vertex>
      vN = mat3(modelMatrix) * normal;
      vMark = aMark;
      vDepth = aDepth;
      vAO = aAO;
      vGlow = aGlow;
      vUv = uv;
      vM0 = modelMatrix[0].xyz;
      vM1 = modelMatrix[1].xyz;
      vM2 = modelMatrix[2].xyz;
      vW = (modelMatrix * vec4(position, 1.0)).xyz;
      gl_Position = projectionMatrix * viewMatrix * modelMatrix * vec4(position, 1.0);
    }`;
  const FRAG = `
    varying vec3 vN;
    varying vec2 vMark;
    varying float vDepth;
    varying float vAO;
    varying float vGlow;
    varying vec2 vUv;
    uniform vec3 uLight;
    uniform vec4 uBands;
    uniform float uSoft;
    uniform vec3 uTone[5];
    uniform vec3 uFlat;
    uniform float uUseFlat;
    uniform vec3 uBump;
    uniform vec3 uLip;
    uniform vec3 uMouth[2];
    uniform float uIsMouth;
    uniform float uGlint;
    uniform vec3 uGlintDir;
    uniform vec3 uGlintColor;
    uniform vec2 uGlintBand;
    uniform float uOpacity;
    uniform float uAOK;
    uniform sampler2D uDetail;
    uniform float uUseDetail;
    uniform vec3 uDetailK;
    uniform float uDetailMid;
    uniform vec3 uPaint;
    uniform vec3 uGlowColor;
    uniform float uGlowPower;
    uniform float uGlowPass;
    uniform float uDim;
    uniform float uSweep;
    uniform float uUseSweep;
    uniform vec3 uInside;
    uniform float uCap;
    uniform vec3 uCapColor;
    uniform float uCapOpacity;
    varying vec3 vM0;
    varying vec3 vM1;
    varying vec3 vM2;
    varying vec3 vW;
    uniform float uLook;
    uniform vec3 uPbr;
    uniform sampler2D uPbrMap;
    uniform float uUsePbrMap;
    uniform vec3 uViewDir;
    uniform vec3 uCamUp;
    uniform float uEnvK;
    #include <clipping_planes_pars_fragment>
    float st(float a, float b, float x) { float t = clamp((x - a) / (b - a), 0.0, 1.0); return t * t * (3.0 - 2.0 * t); }
    // —— B 画法（参考图那种金属质感）：工作室环境光 = 地暗顶亮的渐变 + 五块柔光箱（主光左上前、右上前副光、顶条、右后轮廓条、前下补光），
    // 世界坐标里固定（相机永远在 +x 看向转台，所以等于“跟着相机”）；粗糙度越大，柔光箱的边越软、越暗淡。
    float box(vec3 r, vec3 d, float size, float rough) {
      float c = dot(r, normalize(d));
      float w = size + 0.02 + rough * rough * 0.9;
      return st(1.0 - w, 1.0 - w * 0.35, c);
    }
    vec3 envRadiance(vec3 r, float rough) {
      // R3 反馈：明暗对比加大——地更暗、顶的过渡更陡，主光强、副光弱（两侧明暗分得开），轮廓条更亮
      vec3 col = mix(vec3(0.006, 0.007, 0.009), vec3(0.09, 0.10, 0.115), st(-0.1, 0.95, r.z));
      float k = 1.0 / (1.0 + rough * 4.0);
      col += vec3(1.00, 0.97, 0.92) * 7.0 * k * box(r, vec3(0.45, -0.6, 0.7), 0.12, rough);
      col += vec3(0.92, 0.95, 1.00) * 2.2 * k * box(r, vec3(0.45, 0.6, 0.7), 0.12, rough);
      col += vec3(0.85, 0.90, 1.00) * 1.3 * k * box(r, vec3(0.05, 0.1, 1.0), 0.06, rough) * st(-0.9, 0.2, r.x);
      col += vec3(0.80, 0.88, 1.00) * 4.6 * k * box(r, vec3(-0.55, 0.75, 0.25), 0.05, rough);
      col += vec3(0.60, 0.62, 0.65) * 0.7 * k * box(r, vec3(1.0, 0.25, -0.15), 0.14, rough);
      return col;
    }
    vec3 envIrradiance(vec3 n) {
      vec3 col = mix(vec3(0.03, 0.035, 0.04), vec3(0.22, 0.235, 0.25), st(-0.6, 0.9, n.z));
      col += vec3(1.00, 0.97, 0.92) * 1.1 * max(dot(n, normalize(vec3(0.45, -0.6, 0.7))), 0.0);
      col += vec3(0.92, 0.95, 1.00) * 0.8 * max(dot(n, normalize(vec3(0.45, 0.6, 0.7))), 0.0);
      col += vec3(0.85, 0.90, 1.00) * 0.35 * max(n.z, 0.0);
      col += vec3(0.80, 0.88, 1.00) * 0.35 * max(dot(n, normalize(vec3(-0.55, 0.75, 0.25))), 0.0);
      col += vec3(0.60, 0.62, 0.65) * 0.25 * max(dot(n, normalize(vec3(1.0, 0.25, -0.15))), 0.0);
      return col;
    }
    // 世界方向 → 相机坐标（x 朝相机、y 右、z 上）：工作室跟着相机，俯视审图时灯位不变
    vec3 camDir(vec3 r) { return vec3(dot(r, normalize(uViewDir)), r.y, dot(r, normalize(uCamUp))); }
    vec3 toLin(vec3 c) { return pow(c, vec3(2.2)); }
    vec3 toSrgb(vec3 c) { return pow(max(c, vec3(0.0)), vec3(1.0 / 2.2)); }
    void main() {
      #include <clipping_planes_fragment>
      // 沿 uv.x 点亮（朱红嵌条：与 accent 线同一个扫过量）
      float lit = uUseSweep > 0.5 ? 1.0 - smoothstep(uSweep - 0.06, uSweep, vUv.x) : 1.0;
      float glow = vGlow * uGlowPower * lit;
      // 发光缓冲：只有自发光量，其余写黑（但照常写深度，挡住后面的发光件）
      if (uGlowPass > 0.5) { gl_FragColor = vec4(uGlowColor * glow * (1.0 - uUseFlat), 1.0); return; }
      // 剖视：被剖切面切开的蒙皮从里面看是暗的内壁（不分档，只随朝上程度略变）
      // uCap：0 = 暗内壁（空心蒙皮）、1 = 实心剖面、2 = 薄壳（玻璃：背面照常着色，半透明）
      if (!gl_FrontFacing && uCap < 1.5) {
        if (uCap > 0.5) {
          // 剖面（被剖切面切开的实心零件）：比本体亮一档的平色 + 极淡的 45° 细斜线（屏幕空间，每 7 像素一道）
          float h = fract((gl_FragCoord.x + gl_FragCoord.y) / 7.0);
          float hatch = smoothstep(0.0, 0.12, h) * (1.0 - smoothstep(0.12, 0.26, h));
          gl_FragColor = vec4(uCapColor * (1.0 - 0.14 * hatch) * uDim, uCapOpacity);
          return;
        }
        gl_FragColor = vec4(uInside * (0.75 + 0.25 * abs(normalize(vN).z)), 1.0);
        return;
      }
      if (uLook > 0.5) {
        // —— B：金属质感 ——
        vec3 n = normalize(vN);
        float rough = uPbr.y;
        if (uUsePbrMap > 0.5) {
          vec4 pm = texture2D(uPbrMap, vUv);
          n = normalize(mat3(vM0, vM1, vM2) * (pm.rgb * 2.0 - 1.0));
          rough = clamp(rough * (pm.a / 0.55), 0.04, 1.0);
        }
        vec3 v = normalize(uViewDir);
        float nv = max(dot(n, v), 1e-3);
        vec3 base = toLin(uTone[3]) * uPbr.z;
        // 烘焙 AO 在 B 里压得更重（幂 1.8），缝隙与内角读得出体积
        float occl = pow(mix(1.0, vAO, uAOK), 1.8);
        float line = 1.0;
        if (uUseDetail > 0.5) {
          vec3 d = texture2D(uDetail, vUv).rgb;
          line = mix(1.0, d.r * (1.0 + uDetailMid), uDetailK.x);
          base = mix(base, toLin(uPaint) * 0.8, d.g * uDetailK.y);
          occl *= mix(1.0, d.b, uDetailK.z);
        }
        float metal = uPbr.x;
        vec3 F0 = mix(vec3(0.04), base, metal);
        vec3 F = F0 + (max(vec3(1.0 - rough), F0) - F0) * pow(1.0 - nv, 5.0);
        // 盒投影反射：环境当成转台四周约 6 m 的一个盒子，反射方向随位置偏一点——大块平切面上也有明暗渐变（金属感主要靠它）
        vec3 rr = normalize(reflect(-v, n) + (vW - vec3(0.0, 0.0, 1.6)) * 0.11);
        vec3 spec = envRadiance(camDir(rr), rough) * F * uEnvK;
        vec3 diff = base * (1.0 - metal) * envIrradiance(camDir(n)) * uEnvK;
        // 轮廓光：掠射角（n·v 小）处一圈冷色亮边，朝上、朝相机左后方的边更亮（跟着相机，审图机位不变）
        vec3 nc = camDir(n);
        float rim = pow(1.0 - nv, 4.0) * (0.3 + 0.7 * st(-0.3, 0.8, dot(nc, normalize(vec3(-0.4, 0.6, 0.7)))));
        vec3 lin = (diff * occl + spec * mix(1.0, occl, 0.85) + vec3(0.42, 0.5, 0.58) * rim * (0.35 + 0.65 * metal) * uEnvK * occl) * line;
        vec3 cb = toSrgb(lin);
        if (uIsMouth > 0.5) cb = mix(uMouth[0], uMouth[1], smoothstep(0.0, 0.85, vDepth));
        cb *= uDim;
        cb = mix(cb, uGlowColor, clamp(glow, 0.0, 1.0));
        gl_FragColor = vec4(mix(cb, uFlat, uUseFlat), uOpacity);
        return;
      }
      float score = dot(normalize(vN), uLight);
      float u = st(uBands.x - uSoft, uBands.x + uSoft, score) + st(uBands.y - uSoft, uBands.y + uSoft, score)
              + st(uBands.z - uSoft, uBands.z + uSoft, score) + st(uBands.w - uSoft, uBands.w + uSoft, score);
      float b = min(3.0, floor(u));
      float f = u - b;
      vec3 c = b < 0.5 ? mix(uTone[0], uTone[1], f) : b < 1.5 ? mix(uTone[1], uTone[2], f) : b < 2.5 ? mix(uTone[2], uTone[3], f) : mix(uTone[3], uTone[4], f);
      c += uBump * vMark.x;
      c = mix(c, uLip, vMark.y);
      if (uIsMouth > 0.5) c = mix(uMouth[0], uMouth[1], smoothstep(0.0, 0.85, vDepth));
      if (uGlint > 0.0) c = mix(c, uGlintColor, uGlint * st(uGlintBand.x, uGlintBand.y, dot(normalize(vN), uGlintDir)));
      // 烘焙细节：刻线 / 铆钉 / 鳞片缝压暗（r），涂装字样提亮（g），贴图 AO（b）
      if (uUseDetail > 0.5) {
        vec3 d = texture2D(uDetail, vUv).rgb;
        c *= mix(1.0, d.r * (1.0 + uDetailMid), uDetailK.x);
        c = mix(c, uPaint, d.g * uDetailK.y);
        c *= mix(1.0, d.b, uDetailK.z);
      }
      // 顶点 AO：只压暗，不改档位（档位仍由 n·L 决定，AO 是缝隙与内角里的一层薄暗）
      c *= mix(1.0, vAO, uAOK);
      // 环境压暗（太空段：机体沉进深蓝黑，线条与发光照旧）
      c *= uDim;
      c = mix(c, uGlowColor, clamp(glow, 0.0, 1.0));
      gl_FragColor = vec4(mix(c, uFlat, uUseFlat), uOpacity);
    }`;
  const P = DATA.palette;
  const blackTex = new THREE.DataTexture(new Uint8Array([255, 0, 255, 255]), 1, 1);
  blackTex.needsUpdate = true;
  const shared = {
    uLight: { value: LIGHT }, uUseFlat: { value: 0 }, uFlat: { value: rgb(P.silhouette) }, uBump: { value: rgb(P.bump ?? "#000000") }, uLip: { value: rgb(P.lip ?? P.body[2]) },
    uMouth: { value: (P.mouth ?? ["#192024", "#050708"]).map(rgb) }, uGlintDir: { value: new THREE.Vector3(0, 0, 1) }, uGlintColor: { value: rgb(DATA.fx.glint.color) },
    uGlintBand: { value: new THREE.Vector2(...DATA.fx.glint.band) }, uAOK: { value: DATA.fx.ao ?? 0 }, uGlowPass: { value: 0 }, uDim: { value: 1 }, uInside: { value: rgb(P.inside ?? "#0c0f11") },
    uLook: { value: DATA.look === "metal" ? 1 : 0 }, uViewDir: { value: VIEW }, uCamUp: { value: camera.up }, uEnvK: { value: DATA.metal?.env ?? 1 },
  };
  /** 发光通道：每个 key 一个通电量 uniform（0…1），零件写 glow: { key, color }。 */
  const glowPower = new Map();
  const powerOf = (key) => {
    if (!glowPower.has(key)) glowPower.set(key, { value: 0 });
    return glowPower.get(key);
  };
  const materials = [];
  function bandMaterial(shade, tones, { mouth = false, glint = 0, detail = null, glow = null, pbr = [0.3, 0.5, 1], pbrMap = null } = {}) {
    const m = new THREE.ShaderMaterial({
      vertexShader: VERT,
      fragmentShader: FRAG,
      // 表面稍往后推，贴在表面上的线不与之抢深度
      polygonOffset: true,
      polygonOffsetFactor: 1,
      polygonOffsetUnits: 1,
      uniforms: {
        ...shared,
        uBands: { value: new THREE.Vector4(...shade.bands) },
        uSoft: { value: shade.soft },
        uTone: { value: tones.map(rgb) },
        uIsMouth: { value: mouth ? 1 : 0 },
        uGlint: { value: glint },
        uOpacity: { value: 1 },
        uDetail: { value: detail?.texture ?? blackTex },
        uUseDetail: { value: detail ? 1 : 0 },
        uDetailK: { value: new THREE.Vector3(...(detail?.k ?? [0, 0, 0])) },
        uDetailMid: { value: detail?.mid ? 1 : 0 },
        uPaint: { value: rgb(detail?.paint ?? "#000000") },
        uGlowColor: { value: rgb(glow?.color ?? "#000000") },
        uGlowPower: glow ? powerOf(glow.key) : { value: 0 },
        uSweep: { value: 1 },
        uUseSweep: { value: 0 },
        uCap: { value: 0 },
        uCapColor: { value: new THREE.Color() },
        uCapOpacity: { value: 1 },
        uPbr: { value: new THREE.Vector3(...pbr) },
        uPbrMap: { value: pbrMap?.texture ?? blackTex },
        uUsePbrMap: { value: pbrMap ? 1 : 0 },
      },
    });
    materials.push(m);
    return m;
  }
  /** 细节贴图（Blender 烘焙，build.mjs 以 data URL 注入）：r 刻线、g 涂装、b AO。 */
  const detailTextures = new Map();
  for (const [name, spec] of Object.entries(DATA.detail ?? {})) {
    const image = new Image();
    const texture = new THREE.Texture(image);
    texture.colorSpace = THREE.NoColorSpace;
    texture.anisotropy = renderer.capabilities.getMaxAnisotropy();
    texture.flipY = false;
    image.onload = () => {
      texture.needsUpdate = true;
      if (typeof draw === "function") draw();
    };
    image.src = spec.src;
    detailTextures.set(name, { texture, k: spec.k, paint: spec.paint, mid: !!spec.mid });
  }
  /** 材质表：作品在 DATA.materials 里给出 { 名: { tones: 色板键, shade: 明暗键, glint?, mouth?, detail?, glow? } }。 */
  const MAT = {};
  for (const [name, spec] of Object.entries(DATA.materials)) MAT[name] = bandMaterial(DATA.shade[spec.shade ?? "hull"], P[spec.tones], { mouth: !!spec.mouth, glint: spec.glint ? DATA.fx.glint.strength : 0, detail: spec.detail ? detailTextures.get(spec.detail) : null, glow: spec.glow ?? null, pbr: spec.pbr, pbrMap: spec.pbrMap ? detailTextures.get(spec.pbrMap) ?? null : null });
  MAT.deck = bandMaterial(DATA.shade.deck, P.deck);
  MAT.deck.uniforms = { ...MAT.deck.uniforms, uLook: { value: 0 } }; // 地台在 B 画法里仍用五档明暗
  /** 零件的材质：part.material 指名；否则空腔 → void、玻璃 → glass、其余 → hull。带 glow 的零件另有一份发光材质。 */
  const glowMats = new Map();
  const materialOf = (part) => {
    const base = MAT[part.material ?? (part.system === "void" ? "void" : part.glass ? "glass" : part.kind === "round" ? "round" : "hull")] ?? MAT.hull;
    if (!part.glow) return base;
    const key = `${base.uuid}|${part.glow.key}|${part.glow.color}|${part.glow.sweep ?? ""}`;
    if (!glowMats.has(key)) {
      const m = base.clone();
      m.uniforms = { ...base.uniforms, uGlowColor: { value: rgb(part.glow.color) }, uGlowPower: powerOf(part.glow.key), uSweep: part.glow.sweep ? powerOf(part.glow.sweep) : { value: 1 }, uUseSweep: { value: part.glow.sweep ? 1 : 0 } };
      materials.push(m);
      glowMats.set(key, m);
    }
    return glowMats.get(key);
  };
  /** 跨刚体组的接触面：同一材质往后推一点画，深度打平时让外表面赢。 */
  const recessed = new Map();
  const recess = (material) => {
    if (!recessed.has(material)) {
      const m = material.clone();
      m.uniforms = material.uniforms;
      m.polygonOffsetFactor = 2;
      m.polygonOffsetUnits = 8;
      recessed.set(material, m);
    }
    return recessed.get(material);
  };

  /**
   * 剖视（FIG.02 复刻样板）：剖切面（模型坐标 y = 0，切掉 y > 0 一侧）。cut 的零件用材质的“可剖”副本：开 three 的局部剖切、
   * 双面画（背面是暗内壁）；剖切面每帧按转台换到世界坐标（placeCut）。不剖视时剖切面数组为空，与普通材质完全一样。
   */
  renderer.localClippingEnabled = true;
  const cutPlanes = [];
  const cutPlane = new THREE.Plane(new THREE.Vector3(0, -1, 0), 0);
  const cutMats = new Map();
  /** 剖视时半透明的玻璃（座舱盖：青色细边 + 半透明，K1 那样）；setCutaway 里切换。 */
  const cutGlass = [];
  /**
   * section：被切开处画什么。"cap"（默认，实心零件）= 剖面：比本体最亮一档再亮一档的平色 + 极淡斜线；玻璃的剖面是青色；
   * "inside"（空心的机身蒙皮）= 暗内壁，蒙皮自己的剖面由几何母版的剖面带（section.*）给出；
   * "shell"（座舱盖玻璃这类实心建模、实为薄壳的件）= 背面照常着色（半透明），玻璃的薄剖面由剖面带 section.canopy 给出。
   */
  const cutMaterial = (material, section = "cap") => {
    const key = `${material.uuid}|${section}`;
    if (!cutMats.has(key)) {
      const m = material.clone();
      const t = material.uniforms.uTone.value;
      const glass = material.uniforms.uGlint.value > 0;
      const cap = glass ? new THREE.Color(0x3f8f9c) : new THREE.Color().copy(t[4]).multiplyScalar(1.12).add(new THREE.Color().copy(t[4]).sub(t[2]).multiplyScalar(0.9));
      m.uniforms = { ...material.uniforms, uCap: { value: section === "cap" ? 1 : section === "shell" ? 2 : 0 }, uCapColor: { value: cap }, uCapOpacity: { value: 1 } };
      m.clipping = true;
      m.clippingPlanes = cutPlanes;
      m.side = THREE.DoubleSide;
      materials.push(m);
      cutMats.set(key, m);
      if (glass) cutGlass.push(m);
    }
    return cutMats.get(key);
  };
