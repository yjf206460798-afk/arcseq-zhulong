  // ———————————————— 转台、投影与灯（FIG.01 G2 定，PATTERNS「投影与灯」） ————————————————
  /** 转台上的次级线：外圈刻度（每 3° 短刻、每 15° 长刻）与三道同心环，不随转台转。 */
  const D = DATA.deck;
  const deckSegs = newSegs();
  const deckSeg = (a, b, w) => {
    deckSegs.a.push(...a);
    deckSegs.b.push(...b);
    deckSegs.n1.push(0, 0, 1);
    deckSegs.n2.push(0, 0, 1);
    deckSegs.kind.push(KIND.secondary);
    deckSegs.weight.push(w);
    deckSegs.u.push(0);
  };
  for (let i = 0; i < 120; i++) {
    const t = (i / 120) * 2 * Math.PI;
    const r0 = D.r * (i % 5 === 0 ? 0.955 : 0.975);
    deckSeg([r0 * Math.cos(t), r0 * Math.sin(t), 0], [D.r * 0.995 * Math.cos(t), D.r * 0.995 * Math.sin(t), 0], 0.8);
  }
  for (const r of [D.r, D.r * 0.92, D.r * 0.55])
    for (let i = 0; i < 240; i++) {
      const t0 = (i / 240) * 2 * Math.PI;
      const t1 = ((i + 1) / 240) * 2 * Math.PI;
      deckSeg([r * Math.cos(t0), r * Math.sin(t0), 0], [r * Math.cos(t1), r * Math.sin(t1), 0], 1);
    }
  const deckLineGroup = new THREE.Group();
  const deckLines = lineLayer(deckSegs, deckLineGroup);
  deckLines.mesh.renderOrder = 1;

  /** 转台：台面（z = 0）、台侧、底座；圆对称，不随转台转。 */
  const deck = new THREE.Group();
  deck.name = "deck";
  deck.add(new THREE.Mesh(new THREE.CircleGeometry(D.r, 160), MAT.deck));
  const deckSide = (r, z0, z1) => {
    const g = new THREE.CylinderGeometry(r, r, z1 - z0, 160, 1, true);
    g.rotateX(Math.PI / 2);
    g.translate(0, 0, (z0 + z1) / 2);
    return new THREE.Mesh(g, MAT.deck);
  };
  deck.add(deckSide(D.r, -D.h, 0), deckSide(D.base, -D.h - D.baseH, -D.h));
  const ledge = new THREE.Mesh(new THREE.RingGeometry(D.r, D.base, 160), MAT.deck);
  ledge.position.z = -D.h;
  deck.add(ledge);
  deck.add(deckLineGroup);
  for (const o of deck.children) {
    // 台面的属性与机体材质一致（没有 AO / 发光 / 细节）
    const g = o.geometry;
    if (!g) continue;
    const n = g.attributes.position.count;
    g.setAttribute("aMark", new THREE.Float32BufferAttribute(new Float32Array(n * 2), 2));
    g.setAttribute("aDepth", new THREE.Float32BufferAttribute(new Float32Array(n), 1));
    g.setAttribute("aAO", new THREE.Float32BufferAttribute(new Float32Array(n).fill(1), 1));
    g.setAttribute("aGlow", new THREE.Float32BufferAttribute(new Float32Array(n), 1));
  }
  scene.add(deck);

  const FX = DATA.fx;
  /**
   * halo 投影：光从正上方来。把机体每个朝下的面投到地面（越低的面越黑），模糊成软影，再在接地点各加一团接触影。
   * 影子贴在转台上，随机体转；只在加载和机构定位后重画（分帧做，见 shadowWork）。
   */
  const shadowCanvas = document.createElement("canvas");
  const SHADOW_LEVELS = 48;
  const footParts = DATA.parts.filter((p) => p.kind !== "round" && p.shadow !== false).map((p) => ({ part: p, faces: facesOf(p), moving: !!groupKey(p.joint) }));
  let staticFoot = null;
  let staticFootKey = "";
  function drawFoot(ctx, list, px, py, toAirframe) {
    const paths = Array.from({ length: SHADOW_LEVELS + 1 }, () => []);
    const rel = new THREE.Matrix4();
    const q = new THREE.Vector3();
    for (const { part, faces } of list) {
      let v = part.v;
      if (toAirframe) {
        rel.multiplyMatrices(toAirframe, groupObj(keyOf(part)).matrixWorld);
        v = new Float32Array(part.v.length);
        for (let i = 0; i < part.v.length; i += 3) {
          q.set(part.v[i], part.v[i + 1], part.v[i + 2]).applyMatrix4(rel);
          v[i] = q.x;
          v[i + 1] = q.y;
          v[i + 2] = q.z;
        }
      }
      for (const face of faces) {
        let nz = 0;
        let z = 0;
        for (let i = 0; i < face.length; i++) {
          const a = face[i] * 3;
          const b = face[(i + 1) % face.length] * 3;
          nz += (v[a] - v[b]) * (v[a + 1] + v[b + 1]);
          z += v[a + 2];
        }
        if (nz > -1e-6) continue;
        const w = Math.min(1, Math.max(FX.shadow.floor, 1.25 - 0.25 * (z / face.length)));
        paths[Math.round(w * SHADOW_LEVELS)].push(face.map((i) => [px(v[i * 3]), py(v[i * 3 + 1])]));
      }
    }
    paths.forEach((polys, level) => {
      if (!polys.length) return;
      const g = Math.round((255 * level) / SHADOW_LEVELS);
      ctx.fillStyle = `rgb(${g},${g},${g})`;
      ctx.beginPath();
      for (const poly of polys) poly.forEach(([x, y], k) => (k ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
      ctx.fill();
    });
  }
  const blurBuffers = new Map();
  const blurBuffer = (key, n) => {
    if (!blurBuffers.has(key) || blurBuffers.get(key).length !== n) blurBuffers.set(key, new Float32Array(n));
    return blurBuffers.get(key);
  };
  /** 盒式模糊 3 遍（横竖各一次为一遍），半径 r 像素；每遍之后让出一次（分帧）。 */
  function* boxBlur(src, size, r, key) {
    const n = size * size;
    let from = src;
    let to = blurBuffer(`${key}0`, n);
    const spare = blurBuffer(`${key}1`, n);
    const inv = 1 / (2 * r + 1);
    const last = size - 1;
    for (let p = 0; p < 6; p++) {
      const across = p % 2 === 0;
      const step = across ? 1 : size;
      const lane = across ? size : 1;
      for (let j = 0; j < size; j++) {
        const base = j * lane;
        let acc = 0;
        for (let k = -r; k <= r; k++) acc += from[base + Math.min(last, Math.max(0, k)) * step];
        for (let i = 0; i < size; i++) {
          to[base + i * step] = acc * inv;
          acc += from[base + Math.min(last, i + r + 1) * step] - from[base + Math.max(0, i - r) * step];
        }
      }
      from = to;
      to = to === spare ? blurBuffer(`${key}0`, n) : spare;
      if (p % 2 === 1) yield;
    }
    return from;
  }
  let shadowCtx = null;
  /** 投影重算（generator，分帧）：足迹 → 读回 → 地面软影 → 离地软影（半分辨率）→ 接触影 → 写回。R 地面、G 离地、B 接触。 */
  function* shadowWork(span, contacts, size = lowQuality() ? 192 : 256) {
    if (shadowCanvas.width !== size) shadowCanvas.width = shadowCanvas.height = size;
    shadowCtx ??= shadowCanvas.getContext("2d", { willReadFrequently: true });
    const ctx = shadowCtx;
    const px = (x) => (x / span + 0.5) * size;
    const py = (y) => (0.5 - y / span) * size;
    scene.updateMatrixWorld();
    const toAirframe = new THREE.Matrix4().copy(free.matrixWorld).invert();
    if (!staticFoot || staticFootKey !== String(size)) {
      staticFoot ??= document.createElement("canvas");
      staticFoot.width = staticFoot.height = size;
      const sctx = staticFoot.getContext("2d", { willReadFrequently: true });
      sctx.globalCompositeOperation = "copy";
      sctx.fillStyle = "#000";
      sctx.fillRect(0, 0, size, size);
      sctx.globalCompositeOperation = "lighten";
      drawFoot(sctx, footParts.filter((f) => !f.moving), (x) => px(x + airframe.position.x), (y) => py(y + airframe.position.y), null);
      staticFootKey = String(size);
    }
    ctx.globalCompositeOperation = "copy";
    ctx.drawImage(staticFoot, 0, 0);
    ctx.globalCompositeOperation = "lighten";
    drawFoot(ctx, footParts.filter((f) => f.moving), px, py, toAirframe);
    yield;
    const image = ctx.getImageData(0, 0, size, size);
    const a = blurBuffer("a", size * size);
    for (let i = 0; i < size * size; i++) a[i] = image.data[i * 4] / 255;
    yield;
    const sharp = yield* boxBlur(a, size, Math.max(1, Math.round((FX.shadow.blur / span) * size)), "s");
    const half = size >> 1;
    const small = blurBuffer("h", half * half);
    for (let j = 0; j < half; j++)
      for (let i = 0; i < half; i++) {
        const o = 2 * j * size + 2 * i;
        small[j * half + i] = 0.25 * (a[o] + a[o + 1] + a[o + size] + a[o + size + 1]);
      }
    const softHalf = yield* boxBlur(small, half, Math.max(1, Math.round((FX.air.soft / span) * half)), "g");
    yield;
    const touch = blurBuffer("touch", size * size);
    touch.fill(0);
    for (const key of contacts) {
      const p = DATA.landmarks[key];
      if (!p) continue;
      const cx = px(p[0] + airframe.position.x);
      const cy = py(p[1] + airframe.position.y);
      const rad = (FX.shadow.contact / span) * size;
      for (let j = Math.floor(cy - 2 * rad); j <= Math.ceil(cy + 2 * rad); j++)
        for (let i = Math.floor(cx - 2 * rad); i <= Math.ceil(cx + 2 * rad); i++) {
          if (i < 0 || j < 0 || i >= size || j >= size) continue;
          const d = Math.hypot(i - cx, j - cy) / rad;
          touch[j * size + i] = Math.min(1, touch[j * size + i] + 0.6 * Math.exp(-d * d * 2));
        }
    }
    for (let j = 0; j < size; j++)
      for (let i = 0; i < size; i++) {
        const k = j * size + i;
        const s = softHalf[Math.min(half - 1, j >> 1) * half + Math.min(half - 1, i >> 1)];
        image.data[k * 4] = Math.round(255 * Math.min(1, sharp[k]));
        image.data[k * 4 + 1] = Math.round(255 * Math.min(1, s));
        image.data[k * 4 + 2] = Math.round(255 * touch[k]);
        image.data[k * 4 + 3] = 255;
      }
    yield;
    ctx.globalCompositeOperation = "copy";
    ctx.putImageData(image, 0, 0);
  }
  const SPAN = 2 * D.r;
  const shadowMap = new THREE.CanvasTexture(shadowCanvas);
  shadowMap.colorSpace = THREE.NoColorSpace;
  const shadowUniforms = { uMap: { value: shadowMap }, uColor: { value: rgb(FX.shadow.color) }, uOpacity: { value: FX.shadow.opacity }, uSoft: { value: 0 }, uContact: { value: 1 } };
  const shadow = new THREE.Mesh(
    new THREE.PlaneGeometry(SPAN, SPAN),
    new THREE.ShaderMaterial({
      uniforms: shadowUniforms,
      transparent: true,
      depthWrite: false,
      vertexShader: `varying vec2 vUv; void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
      fragmentShader: `varying vec2 vUv; uniform sampler2D uMap; uniform vec3 uColor; uniform float uOpacity; uniform float uSoft; uniform float uContact;
        void main() { vec3 t = texture2D(uMap, vUv).rgb; gl_FragColor = vec4(uColor, min(1.0, mix(t.r, t.g, uSoft) + t.b * uContact) * uOpacity); }`,
    }),
  );
  shadow.matrixAutoUpdate = false;
  shadow.renderOrder = 1.5;
  turntable.add(shadow);
  let shadowJob = null;
  const contactsNow = () => (typeof DATA.contacts === "function" ? [] : DATA.contacts ?? []);
  /** 机构定位后重算投影：分帧做，新请求替换还没做完的旧请求。 */
  function refreshShadow() {
    shadowJob = shadowWork(SPAN, contactsNow());
  }
  function refreshShadowNow() {
    shadowJob = null;
    const job = shadowWork(SPAN, contactsNow());
    while (!job.next().done);
    shadowMap.needsUpdate = true;
  }
  function stepShadow() {
    if (!shadowJob) return false;
    if (shadowJob.next().done) {
      shadowJob = null;
      shadowMap.needsUpdate = true;
    }
    return true;
  }

  /** 光点：一颗亮点加一圈光晕（加色），屏幕上大小不变；往相机方向让 0.4 m 再做深度测试。颜色只用 FX 里定的几种。 */
  function glowTexture(size = 64) {
    const c = document.createElement("canvas");
    c.width = c.height = size;
    const ctx = c.getContext("2d");
    const g = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
    g.addColorStop(0, "rgba(255,255,255,1)");
    g.addColorStop(0.25, "rgba(255,255,255,0.5)");
    g.addColorStop(1, "rgba(255,255,255,0)");
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, size, size);
    const texture = new THREE.CanvasTexture(c);
    texture.colorSpace = THREE.NoColorSpace;
    return texture;
  }
  const glow = glowTexture();
  const lights = [];
  function addLight(key, colour, spec, parent = airframe) {
    const local = new THREE.Vector3(...DATA.landmarks[key]);
    const layers = [
      [spec.glow / K, spec.glowAlpha],
      [spec.core / K, spec.coreAlpha ?? 1],
    ].map(([size, alpha]) => {
      const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: glow, color: rgb(colour), transparent: true, opacity: alpha, depthWrite: false, blending: THREE.AdditiveBlending }));
      sprite.scale.set(size, size, 1);
      sprite.userData.lightAlpha = alpha;
      sprite.userData.size = size;
      sprite.renderOrder = 3;
      scene.add(sprite);
      return sprite;
    });
    const light = { key, local, parent, layers, level: () => 1 };
    lights.push(light);
    return light;
  }
  for (const L of DATA.lights ?? []) addLight(L.key, L.color, FX[L.spec] ?? L, L.joint ? groupObj(groupKey(L.joint)) : airframe).level = () => powerOf(L.power ?? "power").value;
  const lightAt = new THREE.Vector3();
  function placeLights(visible) {
    for (const { local, parent, layers, level } of lights) {
      const k = level();
      lightAt.copy(local).applyMatrix4(parent.matrixWorld).addScaledVector(VIEW, 0.4);
      for (const sprite of layers) {
        sprite.position.copy(lightAt);
        sprite.visible = visible && k > 1e-4;
        sprite.material.opacity = sprite.userData.lightAlpha * k;
        const s = sprite.userData.size / camera.zoom;
        sprite.scale.set(s, s, 1);
        sprite.updateMatrixWorld();
      }
    }
  }
  /** 玻璃反光方向：光与视线的半程向量，去掉沿座舱盖纵轴的分量，反光总是一条沿纵向的细线。 */
  const glintHalf = new THREE.Vector3();
  const glintAxis = new THREE.Vector3();
  function aimGlint() {
    glintHalf.copy(LIGHT).add(VIEW).normalize();
    glintAxis.setFromMatrixColumn(airframe.matrixWorld, 0).normalize();
    shared.uGlintDir.value.copy(glintHalf).addScaledVector(glintAxis, -glintHalf.dot(glintAxis)).normalize();
  }
