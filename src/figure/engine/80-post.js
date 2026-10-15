  // ———————————————— 后处理（FIG.02 Z1 定，PATTERNS「画面链」） ————————————————
  /**
   * 每帧：① 场景画进多重采样离屏缓冲 main（MSAA 4×，带深度纹理）；
   *       ② 有东西在发光时，同一场景按“发光通道”再画一遍进半分辨率的 glowRT（所有带状材质只输出自发光量、其余写黑但照常挡深度；
   *          只有 accent 线层画、普通线层与光点不画）——这就是“只让发光部件发光”：泛光只从这张图来，亮的蒙皮不会泛光；
   *       ③ glowRT 两级降采样 + 可分离高斯模糊，得到 bloom；
   *       ④ 合成：main（超采样时按 ssaa×ssaa 盒式下采样）+ bloom × 强度，网页版到此为止直接上屏。
   * 录制模式的电影画质（cinema，网页版不开）：超采样 ssaa 倍、特写景深（按深度纹理算弥散圈，泊松盘采样）、
   *   真实运动模糊（一帧快门内推进 blur 个子帧、各画一遍、在半浮点缓冲里平均）、调色（轻 S 曲线、暗部偏冷亮部偏暖、暗角、1 LSB 颗粒）。
   */
  const FS_VERT = `varying vec2 vUv; void main() { vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }`;
  const fsGeo = new THREE.BufferGeometry();
  fsGeo.setAttribute("position", new THREE.Float32BufferAttribute([-1, -1, 0, 3, -1, 0, -1, 3, 0], 3));
  fsGeo.setAttribute("uv", new THREE.Float32BufferAttribute([0, 0, 2, 0, 0, 2], 2));
  const fsCam = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
  const fsMesh = new THREE.Mesh(fsGeo);
  fsMesh.frustumCulled = false;
  const fsScene = new THREE.Scene();
  fsScene.add(fsMesh);
  const pass = (material, target, clear = true) => {
    fsMesh.material = material;
    renderer.setRenderTarget(target);
    if (clear) renderer.clear();
    renderer.render(fsScene, fsCam);
  };
  const BLUR_FRAG = `
    varying vec2 vUv; uniform sampler2D uSrc; uniform vec2 uStep; uniform float uGain;
    void main() {
      // 9 抽头高斯（σ ≈ 2 抽头），步长 uStep（含方向）
      vec3 c = texture2D(uSrc, vUv).rgb * 0.2270270270;
      c += (texture2D(uSrc, vUv + uStep * 1.3846153846).rgb + texture2D(uSrc, vUv - uStep * 1.3846153846).rgb) * 0.3162162162;
      c += (texture2D(uSrc, vUv + uStep * 3.2307692308).rgb + texture2D(uSrc, vUv - uStep * 3.2307692308).rgb) * 0.0702702703;
      gl_FragColor = vec4(c * uGain, 1.0);
    }`;
  const blurMat = new THREE.ShaderMaterial({ vertexShader: FS_VERT, fragmentShader: BLUR_FRAG, uniforms: { uSrc: { value: null }, uStep: { value: new THREE.Vector2() }, uGain: { value: 1 } }, depthTest: false, depthWrite: false });
  const COMPOSE_FRAG = `
    varying vec2 vUv;
    uniform sampler2D uMain; uniform sampler2D uDepth; uniform sampler2D uBloomA; uniform sampler2D uBloomB;
    uniform vec2 uTexel; uniform int uSS; uniform float uBloom; uniform vec2 uBloomMix; uniform float uUseBloom;
    uniform float uDof; uniform float uFocus; uniform float uFocusRange; uniform float uMaxCoc; uniform vec2 uNearFar;
    float linearDepth(vec2 uv) { float d = texture2D(uDepth, uv).r; return uNearFar.x + d * (uNearFar.y - uNearFar.x); }
    vec3 boxed(vec2 uv) {
      // 超采样下采样：画面缓冲是 uSS 倍，按 uSS×uSS 盒式平均（uSS = 1 时就是取原像素）
      if (uSS <= 1) return texture2D(uMain, uv).rgb;
      vec3 c = vec3(0.0);
      float n = 0.0;
      for (int i = 0; i < 4; i++) for (int j = 0; j < 4; j++) {
        if (i >= uSS || j >= uSS) continue;
        vec2 o = (vec2(float(i), float(j)) - 0.5 * float(uSS - 1)) * uTexel;
        c += texture2D(uMain, uv + o).rgb;
        n += 1.0;
      }
      return c / n;
    }
    const vec2 DISK[16] = vec2[16](vec2(-0.613,0.617),vec2(0.170,-0.040),vec2(-0.299,0.791),vec2(0.645,0.493),vec2(-0.651,0.717),vec2(0.421,0.027),vec2(-0.817,-0.271),vec2(-0.705,-0.668),
      vec2(0.977,-0.108),vec2(0.063,-0.992),vec2(-0.150,-0.416),vec2(0.330,-0.698),vec2(-0.346,0.124),vec2(0.761,-0.584),vec2(-0.928,0.161),vec2(0.150,0.535));
    void main() {
      vec3 c = boxed(vUv);
      if (uDof > 0.5) {
        // 景深：弥散圈 = 离焦平面的距离 / 景深范围，限幅 uMaxCoc 像素；按样本自己的弥散圈加权，前景的虚化不被背景吃掉
        float z = linearDepth(vUv);
        float coc = clamp(abs(z - uFocus) / uFocusRange, 0.0, 1.0) * uMaxCoc;
        if (coc > 0.5) {
          vec3 acc = c; float wsum = 1.0;
          for (int k = 0; k < 16; k++) {
            vec2 uv = vUv + DISK[k] * coc * uTexel * float(uSS);
            float zk = linearDepth(uv);
            float ck = clamp(abs(zk - uFocus) / uFocusRange, 0.0, 1.0) * uMaxCoc;
            float w = smoothstep(0.0, 1.0, ck / max(coc, 1e-3)) + (zk < z ? 1.0 : 0.0) * smoothstep(0.0, 1.0, ck / uMaxCoc);
            acc += boxed(uv) * w; wsum += w;
          }
          c = acc / wsum;
        }
      }
      if (uUseBloom > 0.5) c += (texture2D(uBloomA, vUv).rgb * uBloomMix.x + texture2D(uBloomB, vUv).rgb * uBloomMix.y) * uBloom;
      gl_FragColor = vec4(c, 1.0);
    }`;
  const composeMat = new THREE.ShaderMaterial({
    // three 在 WebGL2 上按 GLSL ES 3.00 编译（自动换 varying / texture2D / gl_FragColor），数组构造可以直接用
    vertexShader: FS_VERT,
    fragmentShader: COMPOSE_FRAG,
    uniforms: { uMain: { value: null }, uDepth: { value: null }, uBloomA: { value: null }, uBloomB: { value: null }, uTexel: { value: new THREE.Vector2() }, uSS: { value: 1 }, uBloom: { value: DATA.post.bloom.strength }, uBloomMix: { value: new THREE.Vector2(...DATA.post.bloom.mix) }, uUseBloom: { value: 0 }, uDof: { value: 0 }, uFocus: { value: 50 }, uFocusRange: { value: 4 }, uMaxCoc: { value: 8 }, uNearFar: { value: new THREE.Vector2(camera.near, camera.far) } },
    depthTest: false,
    depthWrite: false,
  });
  // 累积（运动模糊）：加色混合、每个子帧乘 1/N
  const accumMat = new THREE.ShaderMaterial({ vertexShader: FS_VERT, fragmentShader: `varying vec2 vUv; uniform sampler2D uSrc; uniform float uK; void main() { gl_FragColor = vec4(texture2D(uSrc, vUv).rgb * uK, 1.0); }`, uniforms: { uSrc: { value: null }, uK: { value: 1 } }, depthTest: false, depthWrite: false, transparent: true, blending: THREE.CustomBlending, blendEquation: THREE.AddEquation, blendSrc: THREE.OneFactor, blendDst: THREE.OneFactor });
  const GRADE_FRAG = `
    varying vec2 vUv; uniform sampler2D uSrc; uniform float uGrade; uniform vec3 uShadowTint; uniform vec3 uHighTint; uniform float uContrast; uniform float uVignette; uniform float uGrain; uniform float uSeed; uniform vec2 uAspect;
    float hash(vec2 p) { vec3 q = fract(vec3(p.xyx) * .1031); q += dot(q, q.yzx + 33.33); return fract((q.x + q.y) * q.z); }
    void main() {
      vec3 c = texture2D(uSrc, vUv).rgb;
      if (uGrade > 0.5) {
        float l = dot(c, vec3(0.2126, 0.7152, 0.0722));
        // 分离色调：暗部偏冷、亮部偏暖（按明度插值，幅度很小）
        c += mix(uShadowTint, uHighTint, smoothstep(0.08, 0.55, l));
        // 轻 S 曲线：以 0.18 为支点，只拉一点对比
        c = max(c, 0.0);
        c = min(0.18 * pow(c / 0.18, vec3(uContrast)), vec3(1.0));
        vec2 d = (vUv - 0.5) * uAspect;
        c *= 1.0 - uVignette * smoothstep(0.35, 0.95, length(d));
        c += (hash(gl_FragCoord.xy + uSeed) - 0.5) * uGrain / 255.0;
      }
      gl_FragColor = vec4(c, 1.0);
    }`;
  const gradeMat = new THREE.ShaderMaterial({ vertexShader: FS_VERT, fragmentShader: GRADE_FRAG, uniforms: { uSrc: { value: null }, uGrade: { value: 0 }, uShadowTint: { value: new THREE.Vector3(...DATA.post.grade.shadows) }, uHighTint: { value: new THREE.Vector3(...DATA.post.grade.highlights) }, uContrast: { value: DATA.post.grade.contrast }, uVignette: { value: DATA.post.grade.vignette }, uGrain: { value: DATA.post.grade.grain }, uSeed: { value: 0 }, uAspect: { value: new THREE.Vector2(1, 1) } }, depthTest: false, depthWrite: false });

  /**
   * 背景（环境的第 5 角色，FIG.02 Z1）：全屏一张，画在场景之前、不写深度。底色两端渐变；可选星点（按像素哈希，稀、淡、不闪）
   * 与地球弧（屏幕坐标里的大圆：暗的球面 + 一条细的大气辉线 + 很淡的外晕）。参数在 DATA.environments.<名>.backdrop。
   */
  const BACK_FRAG = `
    varying vec2 vUv;
    uniform vec3 uTop; uniform vec3 uBottom; uniform vec2 uAspect; uniform float uStars; uniform float uStarAlpha;
    uniform vec3 uEarth; uniform vec3 uEarthColor; uniform vec3 uRim; uniform float uRimW; uniform float uHalo; uniform float uEarthOn; uniform vec2 uPx;
    float hash(vec2 p) { vec3 q = fract(vec3(p.xyx) * .1031); q += dot(q, q.yzx + 33.33); return fract((q.x + q.y) * q.z); }
    void main() {
      vec3 c = mix(uBottom, uTop, smoothstep(0.0, 1.0, vUv.y));
      // 星点：每 3 像素一格，格里按哈希决定有没有星、亮度与位置；星只有 1～1.5 像素，不画十字光芒
      // 星点：每 5 像素一格，格里按哈希决定有没有星、亮度与位置（偏移限在格中部，星不被格边截掉）；星只有约 1 像素，不画十字光芒
      vec2 cell = floor(gl_FragCoord.xy / (5.0 * uPx.y));
      float h = fract(sin(dot(cell, vec2(12.9898, 78.233))) * 43758.5453);
      if (h > 1.0 - uStars) {
        vec2 o = 0.25 + 0.5 * vec2(fract(h * 91.7), fract(h * 37.3));
        vec2 d = (gl_FragCoord.xy / (5.0 * uPx.y) - cell - o) * 5.0;
        float b = pow(fract(h * 13.1), 3.0);
        c += vec3(0.75, 0.82, 0.95) * uStarAlpha * (0.25 + b) * exp(-dot(d, d) * 1.6);
      }
      if (uEarthOn > 0.5) {
        // 地球：屏幕坐标里的圆（以画幅宽为单位），r 为离圆心的距离
        vec2 p = (vUv - uEarth.xy) * uAspect;
        float r = length(p) - uEarth.z;
        float inside = 1.0 - smoothstep(-0.5 * uPx.x, 0.5 * uPx.x, r);
        // 球面：靠边缘一点点变亮（大气散射），中心是深的夜面
        vec3 globe = uEarthColor * (0.55 + 0.45 * smoothstep(-0.12, 0.0, r));
        c = mix(c, globe, inside);
        // 辉线：边缘外侧一条细线（宽 uRimW），再加很淡的外晕
        c += uRim * exp(-pow(r / uRimW, 2.0)) * 0.9;
        c += uRim * uHalo * exp(-max(r, 0.0) / (uRimW * 18.0)) * step(0.0, r);
      }
      gl_FragColor = vec4(c, 1.0);
    }`;
  const backMat = new THREE.ShaderMaterial({ vertexShader: FS_VERT, fragmentShader: BACK_FRAG, depthTest: false, depthWrite: false, uniforms: { uTop: { value: new THREE.Color() }, uBottom: { value: new THREE.Color() }, uAspect: { value: new THREE.Vector2(1, 1) }, uStars: { value: 0 }, uStarAlpha: { value: 0 }, uEarth: { value: new THREE.Vector3(0.5, -1, 1) }, uEarthColor: { value: new THREE.Color() }, uRim: { value: new THREE.Color() }, uRimW: { value: 0.002 }, uHalo: { value: 0 }, uEarthOn: { value: 0 }, uPx: { value: new THREE.Vector2(0.001, 1) } } });
  function backdrop(target) {
    const B = backdropSpec();
    if (!B) return false;
    const U = backMat.uniforms;
    U.uTop.value.set(B.top);
    U.uBottom.value.set(B.bottom);
    U.uAspect.value.set(1, post.h / post.w);
    U.uStars.value = B.stars?.density ?? 0;
    U.uStarAlpha.value = (B.stars?.alpha ?? 0) * (B.k ?? 1);
    U.uEarthOn.value = B.earth ? 1 : 0;
    if (B.earth) {
      U.uEarth.value.set(...B.earth.centre, B.earth.radius);
      U.uEarthColor.value.set(B.earth.color);
      U.uRim.value.set(B.earth.rim).multiplyScalar(B.k ?? 1);
      U.uRimW.value = B.earth.rimWidth;
      U.uHalo.value = B.earth.halo;
    }
    U.uPx.value.set(1 / (post.w * post.ratio * post.ss), post.ratio * post.ss);
    fsMesh.material = backMat;
    renderer.setRenderTarget(target);
    renderer.render(fsScene, fsCam);
    return true;
  }

  /** 电影画质（录制模式）：null = 网页版；{ ssaa, blur, shutter, dof: { focus: [x,y,z] 世界点, range 米, coc 像素 } | null, grade }。 */
  let cinema = null;
  const post = { w: 1, h: 1, ratio: 1, ss: 1, main: null, glow: null, glowB: null, quarter: null, quarterB: null, accum: null, view: null };
  const rtOpts = { minFilter: THREE.LinearFilter, magFilter: THREE.LinearFilter, depthBuffer: false };
  function sizePost(w, h, ratio) {
    // 超采样：电影画质按 cinema.ssaa；网页高画质档在 DPR < 2 的屏上按 2 倍画、合成时盒式下采样（细线与切面边缘转动不闪），手机标准档不超采样
    const ss = cinema?.ssaa ?? (!lowQuality() && ratio < 1.5 && DATA.post.ssaa ? DATA.post.ssaa : 1);
    Object.assign(post, { w, h, ratio, ss });
    const fw = Math.max(1, Math.round(w * ratio));
    const fh = Math.max(1, Math.round(h * ratio));
    for (const k of ["main", "glow", "glowB", "quarter", "quarterB", "accum", "view"]) post[k]?.dispose();
    const depthTexture = new THREE.DepthTexture(fw * ss, fh * ss);
    depthTexture.type = THREE.UnsignedIntType;
    post.main = new THREE.WebGLRenderTarget(fw * ss, fh * ss, { samples: DATA.post.msaa, depthTexture, minFilter: THREE.LinearFilter, magFilter: THREE.LinearFilter });
    // 发光缓冲带深度：发光件被机体挡住的部分不发光
    post.glow = new THREE.WebGLRenderTarget(Math.ceil(fw / 2), Math.ceil(fh / 2), { minFilter: THREE.LinearFilter, magFilter: THREE.LinearFilter });
    post.glowB = new THREE.WebGLRenderTarget(Math.ceil(fw / 2), Math.ceil(fh / 2), rtOpts);
    post.quarter = new THREE.WebGLRenderTarget(Math.ceil(fw / 4), Math.ceil(fh / 4), rtOpts);
    post.quarterB = new THREE.WebGLRenderTarget(Math.ceil(fw / 4), Math.ceil(fh / 4), rtOpts);
    post.view = new THREE.WebGLRenderTarget(fw, fh, { ...rtOpts, type: THREE.HalfFloatType });
    post.accum = new THREE.WebGLRenderTarget(fw, fh, { ...rtOpts, type: THREE.HalfFloatType });
  }
  const glowing = () => [...glowPower.entries()].some(([k, u]) => !k.endsWith(".sweep") && u.value > 1e-3);
  function blur(src, tmp, dst, w, h, scale) {
    blurMat.uniforms.uSrc.value = src.texture;
    blurMat.uniforms.uStep.value.set(scale / w, 0);
    blurMat.uniforms.uGain.value = 1;
    pass(blurMat, tmp);
    blurMat.uniforms.uSrc.value = tmp.texture;
    blurMat.uniforms.uStep.value.set(0, scale / h);
    pass(blurMat, dst);
  }
  const hiddenInGlow = [];
  /** 画一个子帧：场景 → main（→ glow → bloom）→ 合成到 target（null = 画布）。 */
  function renderFrame(target, silhouette) {
    const bg = rgb(environmentColor());
    renderer.setClearColor(bg, 1);
    renderer.setRenderTarget(post.main);
    renderer.clear();
    if (!silhouette) backdrop(post.main);
    renderer.render(scene, camera);
    const bloomOn = !silhouette && glowing();
    if (bloomOn) {
      // 发光通道：带状材质只出自发光，accent 线出发光色，其余线、光点、尾焰、投影不画
      shared.uGlowPass.value = 1;
      lineShared.uGlowPass.value = 1;
      hiddenInGlow.length = 0;
      scene.traverseVisible((o) => {
        if ((o.isSprite || o === shadow || o.parent === deckLineGroup || (o.material?.blending === THREE.CustomBlending && o.material.uniforms?.uPc) || (o.material?.length && !accentLayers.some((l) => l.mesh === o))) && o.visible) hiddenInGlow.push(o);
      });
      for (const o of hiddenInGlow) o.visible = false;
      renderer.setClearColor(0x000000, 1);
      renderer.setRenderTarget(post.glow);
      renderer.clear();
      renderer.render(scene, camera);
      for (const o of hiddenInGlow) o.visible = true;
      shared.uGlowPass.value = 0;
      lineShared.uGlowPass.value = 0;
      const gw = post.glow.width;
      const gh = post.glow.height;
      blur(post.glow, post.glowB, post.glow, gw, gh, 1);
      blurMat.uniforms.uSrc.value = post.glow.texture;
      blurMat.uniforms.uStep.value.set(0, 0);
      pass(blurMat, post.quarter);
      blur(post.quarter, post.quarterB, post.quarter, post.quarter.width, post.quarter.height, 1.5);
    }
    const U = composeMat.uniforms;
    U.uMain.value = post.main.texture;
    U.uDepth.value = post.main.depthTexture;
    U.uBloomA.value = post.glow.texture;
    U.uBloomB.value = post.quarter.texture;
    U.uUseBloom.value = bloomOn ? 1 : 0;
    U.uSS.value = post.ss;
    U.uTexel.value.set(1 / post.main.width, 1 / post.main.height);
    U.uNearFar.value.set(camera.near, camera.far);
    const dof = cinema?.dof && !silhouette;
    U.uDof.value = dof ? 1 : 0;
    if (dof) {
      // 正交相机：深度与视线方向距离成正比；焦点 = 世界点到相机平面的距离
      const p = new THREE.Vector3(...cinema.dof.focus).applyMatrix4(airframe.matrixWorld);
      U.uFocus.value = -p.applyMatrix4(camera.matrixWorldInverse).z;
      U.uFocusRange.value = cinema.dof.range;
      U.uMaxCoc.value = cinema.dof.coc * post.ratio;
    }
    pass(composeMat, target);
  }
  /** 一整帧：网页版直接合成上屏；电影画质先在半浮点缓冲里累积子帧（运动模糊）、再调色上屏。 */
  function renderAll(silhouette) {
    if (!cinema) {
      renderFrame(post.view, silhouette);
      gradeMat.uniforms.uSrc.value = post.view.texture;
      gradeMat.uniforms.uGrade.value = 0;
      pass(gradeMat, null);
      return;
    }
    renderFrame(post.view, silhouette);
    gradeMat.uniforms.uSrc.value = post.view.texture;
    gradeMat.uniforms.uGrade.value = cinema.grade === false ? 0 : 1;
    gradeMat.uniforms.uSeed.value = (clock * 60) % 97;
    gradeMat.uniforms.uAspect.value.set(post.w / post.h, 1);
    pass(gradeMat, null);
  }
  /**
   * 电影画质的一帧（录制用）：快门时间 shutter 秒内推进 blur 个子帧，每个子帧完整推进场景、摆相机、画一遍，加权平均后调色。
   * step(dt) 由调用方给：推进场景 dt 秒并摆好相机（审图转台、演出都走同一个 advance）。
   */
  function renderCinemaFrame(step, frameDt) {
    const n = Math.max(1, cinema.blur ?? 1);
    const shutter = cinema.shutter ?? 0.5;
    renderer.setRenderTarget(post.accum);
    renderer.setClearColor(0x000000, 1);
    renderer.clear();
    for (let i = 0; i < n; i++) {
      step(i === 0 ? frameDt * (1 - shutter) + (frameDt * shutter) / n : (frameDt * shutter) / n);
      prepareDraw();
      renderFrame(post.view, false);
      accumMat.uniforms.uSrc.value = post.view.texture;
      accumMat.uniforms.uK.value = 1 / n;
      pass(accumMat, post.accum, false);
    }
    gradeMat.uniforms.uSrc.value = post.accum.texture;
    gradeMat.uniforms.uGrade.value = cinema.grade === false ? 0 : 1;
    gradeMat.uniforms.uSeed.value = (clock * 60) % 97;
    gradeMat.uniforms.uAspect.value.set(post.w / post.h, 1);
    pass(gradeMat, null);
  }
  const cinemaBusy = () => false;
