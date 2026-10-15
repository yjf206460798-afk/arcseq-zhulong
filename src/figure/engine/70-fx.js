  // ———————————————— 尾焰（FIG.01 G4 补轮定，PATTERNS「尾焰」；照 anatomy references/webgl.md 第 7 节与 8.4） ————————————————
  /**
   * 每个喷口一个包围体，片元着色器沿视线积分：流柱（淡青蓝高斯截面）、唇边（品牌琥珀薄环，解析算）、激波透镜（淡奶油扁圆盘，解析算）。
   * 颜色、长度、亮度只由推力量 thrust.pc（临界阻尼弹簧追 flight.engine）驱动；点火时有一次 burst。屏幕混合，只加光、不写深度、无粒子。
   * FIG.02：加力环、马赫环（FIG.01 速度感）不进引擎通用部分，uAB 恒为 0；塞锥火箭的颜色在 Z5 定（FX.jet.* 换色即可）。
   */
  const JET = FX.jet;
  const JET_VERT = `
    varying vec3 vP;
    void main() {
      vP = position;
      gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
    }`;
  const JET_FRAG = `
    varying vec3 vP;
    uniform vec3 uView;
    uniform vec4 uGround;
    uniform float uPc;
    uniform float uGlow;
    uniform float uFlash;
    uniform float uReach;
    uniform float uTime;
    uniform float uR0;
    uniform float uRB;
    uniform float uLB;
    uniform float uSpread;
    uniform float uGain;
    uniform float uShocks;
    uniform vec3 uBlue;
    uniform vec3 uLip;
    uniform vec3 uCream;
    uniform vec4 uMix;
    uniform float uAB;
    uniform vec3 uABody;
    uniform vec4 uABMix;
    uniform vec4 uRing;
    uniform vec3 uRingAmber;
    uniform vec3 uRingWarm;
    float hash12(vec2 p) { vec3 q = fract(vec3(p.xyx) * .1031); q += dot(q, q.yzx + 33.33); return fract((q.x + q.y) * q.z); }
    void main() {
      vec3 d = -uView;
      vec3 o = vP;
      // 出射点：圆柱侧面与两端面里最先碰到的那个
      float a = d.y * d.y + d.z * d.z;
      float b = 2. * (o.y * d.y + o.z * d.z);
      float c = o.y * o.y + o.z * o.z - uRB * uRB;
      float tCyl = a > 1e-6 ? (-b + sqrt(max(b * b - 4. * a * c, 0.))) / (2. * a) : 1e3;
      float tX = d.x > 1e-6 ? -o.x / d.x : d.x < -1e-6 ? (-uLB - o.x) / d.x : 1e3;
      float tEnd = max(min(tCyl, tX), 0.);
      // 视线离轴最近的距离超过流柱最粗处 1.9 倍时，每一项都已 < 1/2000，直接输出 0（不是硬边：那里本来就是 0）
      float tc = a > 1e-6 ? clamp(-b / (2. * a), 0., tEnd) : 0.;
      vec3 pc = o + d * tc;
      if (length(pc.yz) > (uR0 + uSpread * uLB) * 1.9) { gl_FragColor = vec4(0.); return; }
      float n = 8.;
      float dt = tEnd / n;
      float dith = hash12(gl_FragCoord.xy + fract(uTime * .37) * 57.);
      float reach = uReach;
      // 激波透镜的位置：第 k 个在 s0 + k·P（与下面透镜循环同一公式）；加力时的环数 rings
      float P = uR0 * 2.1 * (.75 + .25 * uPc);
      float s0 = uR0 * 1.7 * (.75 + .25 * uPc);
      float rings = uShocks + uRing.x * uAB;
      vec3 sum = vec3(0.);
      for (int i = 0; i < 8; i++) {
        vec3 p = o + d * ((float(i) + dith) * dt);
        float s = -p.x;
        float r = length(p.yz);
        float R = uR0 * (.92 + .08 * smoothstep(0., .3, s)) + uSpread * s;
        float keep = smoothstep(-.005, .04, s) * (1. - smoothstep(reach * .45, reach, s)) * smoothstep(.02, .35, dot(uGround.xyz, p) + uGround.w);
        float flow = .9 + .1 * sin(s * 7. - uTime * 11.);
        // 2026-10-14 速度感：加力时流柱按激波透镜的间距明暗相间（环处亮 uRing.w、环间暗 uRing.z），马赫环读得出；干推力时 diam = 1
        float ph = (s - s0) / P;
        float band = pow(.5 + .5 * cos(6.2832 * ph), 6.);
        float diam = 1. + uAB * smoothstep(-.6, -.2, ph) * (1. - smoothstep(rings - .8, rings - .2, ph)) * (uRing.w * band - uRing.z * (1. - band));
        // 流柱：淡青蓝；加力时渐到暖琥珀、更亮（uABMix.y），喷口段加一段淡奶油的核心（沿长度 40%～90% 淡出）
        sum += mix(uBlue, uABody, uAB) * exp(-pow(r / R, 2.) * 2.2) * keep * flow * uMix.x * (1. + (uABMix.y - 1.) * uAB) * mix(1., diam, .6);
        sum += uCream * exp(-pow(r / (R * .42), 2.) * 2.5) * (1. - smoothstep(reach * .4, reach * .9, s)) * keep * uAB * uABMix.x * diam;

      }
      // 激波透镜：淡奶油色扁圆盘（半厚 0.22·Rk），外沿偏暖、边缘软。盘很薄，按视线穿过盘面那一点解析地算（取高斯 × 视线在盘里走的长度），
      // 不随积分步数出颗粒；只在推力 > 0.2 后出现，越往后越弱。
      vec3 lensSum = vec3(0.);
      // 2026-10-14 速度感：加力时多 uRing.x 个环（逐个淡入）、亮 uRing.y 倍，颜色由琥珀到暖白；干推力（uAB = 0）与 G4 完全一样
      for (int k = 0; k < 5; k++) {
        float fk = float(k);
        if (fk + .5 > rings + .5) break;
        float ringW = clamp(rings - fk, 0., 1.);
        float sk = uR0 * (1.7 + 2.1 * fk) * (.75 + .25 * uPc);
        float Rk = uR0 * (.8 - .1 * fk);
        float tk = abs(d.x) > 1e-4 ? (-sk - o.x) / d.x : -1.;
        if (tk < 0. || tk > tEnd) continue;
        vec3 pk = o + d * tk;
        float rr = length(pk.yz) / Rk;
        float lens = exp(-rr * rr * 2.4) * (Rk * .22 * 1.77) / max(abs(d.x), .3) * (1. - smoothstep(reach * .5, reach * .85, sk)) * smoothstep(.2, .7, uPc);
        vec3 tint = mix(uCream, mix(uCream, uLip, .55), smoothstep(.35, .95, rr));
        vec3 abTint = mix(mix(uRingAmber, uRingWarm, smoothstep(.3, 1., uAB)), uRingAmber, .35 * smoothstep(.35, .95, rr));
        tint = mix(tint, abTint, smoothstep(0., .25, uAB));
        lensSum += tint * lens * ringW * uMix.z * exp(-fk * .35) * (1. + (uABMix.z - 1.) * uAB) * (1. + (uRing.y - 1.) * uAB);
      }
      // 唇边：喷口一圈暖琥珀，几厘米（λ = 0.45·r0）内衰减。环很薄，采样会出颗粒，所以解析地算：取视线穿过 s = λ/2 那张面的点，
      // 按它离唇边半径的距离取高斯，再乘视线在 [0, λ] 里走过的长度（视线几乎平行于出口面时限幅）
      float lam = uR0 * .45;
      float tl = abs(d.x) > 1e-4 ? (-lam * .5 - o.x) / d.x : -1.;
      vec3 pl = o + d * clamp(tl, 0., tEnd);
      float lipK = tl >= 0. && tl <= tEnd ? exp(-pow((length(pl.yz) - uR0 * .88) / (uR0 * .22), 2.)) * lam / max(abs(d.x), .3) : 0.;
      sum = sum * dt + lensSum + uLip * lipK * .2 * uMix.y * (1. + uFlash + .5 * uAB);
      vec3 col = sum * uGlow * uGain;
      col = 1. - exp(-col * uMix.w);
      float m = max(col.r, max(col.g, col.b));
      float nz = (hash12(gl_FragCoord.xy + fract(uTime * .61) * 91.) + hash12(gl_FragCoord.yx * 1.37 + fract(uTime * .37) * 57.) - 1.) / 255.;
      col = max(col + nz * smoothstep(0., 1.5 / 255., m), 0.);
      gl_FragColor = vec4(col, max(col.r, max(col.g, col.b)));
    }`;
  const fxTime = { value: 0 };
  const jetShared = { uTime: fxTime, uBlue: { value: new THREE.Vector3(...JET.blue) }, uLip: { value: new THREE.Vector3(...JET.lip) }, uCream: { value: new THREE.Vector3(...JET.cream) }, uABody: { value: new THREE.Vector3(...JET.blue) }, uABMix: { value: new THREE.Vector4(0, 1, 1, 0) } };
  /** 一束尾焰：root 挂在组上，位于出口地标、沿 root 的 −x 喷出；spec 为 FX.jet 里的一项。 */
  function plume(parent, at, spec, rotation = null) {
    const root = new THREE.Group();
    root.position.set(...at);
    if (rotation) root.rotation.set(...rotation);
    parent.add(root);
    const length = spec.length;
    const RB = 1.9 * (spec.r0 + spec.spread * length);
    const g = new THREE.CylinderGeometry(RB, 1.9 * spec.r0, length, 24, 1, false);
    g.rotateZ(Math.PI / 2);
    g.translate(-length / 2, 0, 0);
    const uniforms = {
      ...jetShared,
      uView: { value: new THREE.Vector3() },
      uGround: { value: new THREE.Vector4(0, 0, 1, 10) },
      uPc: { value: 0 },
      uGlow: { value: 0 },
      uFlash: { value: 0 },
      uReach: { value: 0 },
      uR0: { value: spec.r0 },
      uRB: { value: RB },
      uLB: { value: length },
      uAB: { value: 0 },
      uRing: { value: new THREE.Vector4(0, 1, 0, 0) },
      uRingAmber: { value: new THREE.Vector3(...JET.lip) },
      uRingWarm: { value: new THREE.Vector3(...JET.cream) },
      uSpread: { value: spec.spread },
      uGain: { value: spec.gain },
      uShocks: { value: spec.shocks },
      uMix: { value: new THREE.Vector4(JET.column, JET.lipStrength, JET.shock, JET.exposure) },
    };
    const mesh = new THREE.Mesh(g, new THREE.ShaderMaterial({ vertexShader: JET_VERT, fragmentShader: JET_FRAG, uniforms, transparent: true, depthWrite: false, blending: THREE.CustomBlending, blendEquation: THREE.AddEquation, blendSrc: THREE.OneFactor, blendDst: THREE.OneMinusSrcColorFactor }));
    mesh.renderOrder = 2.5;
    mesh.frustumCulled = false;
    root.add(mesh);
    root.visible = false;
    return { root, mesh, uniforms, spec };
  }
  const flames = (DATA.plumes ?? []).map((p) => plume(groupObj(groupKey(p.joint)), DATA.landmarks[p.at], JET[p.spec], p.rotation ?? null));
  /** 推力量：pc 以临界阻尼弹簧追 flight.engine，不过冲；点火（越过 0.02）记下时刻，flash = burst；推力下降时亮度只降不升。 */
  const burstJs = (age, rise, fall) => (age > 0 ? smoothStepJs(0, rise, age) * Math.exp(-Math.max(0, age - rise) / fall) : 0);
  const thrust = { pc: 0, rate: 0, glow: 0, flash: 0, lit: false, at: -1, reach: { x: 0, v: 0 }, falling: null };
  function settleJs(state, goal, dt, seconds) {
    if (still.matches) {
      state.x = goal;
      state.v = 0;
      return;
    }
    const w = 1 / seconds;
    for (let i = 0; i < 4; i++) {
      const h = dt / 4;
      state.v += (w * w * (goal - state.x) - 2 * w * state.v) * h;
      state.x += state.v * h;
    }
    if (Math.abs(goal - state.x) < 1e-4 && Math.abs(state.v) < 1e-4) {
      state.x = goal;
      state.v = 0;
    }
  }
  function stepThrust(dt) {
    const T = thrust;
    const goal = flight.engine;
    if (still.matches) {
      T.pc = goal;
      T.rate = 0;
    } else {
      const k = JET.spring;
      for (let i = 0; i < 4; i++) {
        const h = dt / 4;
        T.rate += ((goal - T.pc) * k - T.rate * 2 * Math.sqrt(k)) * h;
        T.pc = Math.min(1, Math.max(0, T.pc + T.rate * h));
      }
      if (Math.abs(goal - T.pc) < 1e-4 && Math.abs(T.rate) < 1e-4) {
        T.pc = goal;
        T.rate = 0;
      }
    }
    if (!T.lit && T.pc > 0.02) {
      T.lit = true;
      T.at = clock;
    } else if (T.lit && T.pc < 0.005 && goal === 0) T.lit = false;
    const F = JET.flash;
    T.flash = still.matches || !T.lit ? 0 : F.amount * burstJs(clock - T.at, F.rise, F.fall);
    let g = smoothStepJs(0, 0.1, T.pc) * (1 + 0.5 * T.flash);
    if (goal < T.pc - 1e-3) {
      T.falling ??= Math.max(T.glow, 1e-3);
      g = Math.min(T.falling, g);
    } else T.falling = null;
    T.glow = T.lit || T.pc > 1e-4 ? g : 0;
    settleJs(T.reach, 0.3 + 0.7 * smoothStepJs(0.05, 0.8, T.pc), dt, T.falling ? 0.12 : 0.18);
    return T.pc > 1e-4 || T.flash > 1e-3;
  }
  function advanceFx(dt) {
    fxTime.value = clock;
    return stepThrust(dt);
  }
  const jetM = new THREE.Matrix4();
  const jetV = new THREE.Vector3();
  function placeFx(linesOn) {
    const on = linesOn && thrust.glow > 1e-4;
    for (const f of flames) {
      f.root.visible = on;
      if (!on) continue;
      const U = f.uniforms;
      const e = f.mesh.matrixWorld.elements;
      jetM.extractRotation(f.mesh.matrixWorld).transpose();
      U.uView.value.copy(jetV.copy(VIEW).applyMatrix4(jetM)).normalize();
      // 根坐标里的地面平面：世界 z = 第三行 · p
      U.uGround.value.set(e[2], e[6], e[10], e[14]);
      U.uPc.value = thrust.pc;
      U.uGlow.value = thrust.glow;
      U.uFlash.value = thrust.flash;
      U.uReach.value = f.spec.length * thrust.reach.x;
    }
  }
