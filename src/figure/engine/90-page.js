  // ———————————————— 环境、选中、绘制、交互、审图入口 ————————————————
  /** 环境色（VISUAL_TARGET 配色卡第 5 角色）：DATA.environments 里每个环境一组颜色；env.mix 在两个环境之间插值（入轨演出用）。 */
  const env = { from: DATA.environment, to: DATA.environment, mix: 0 };
  const lerpHex = (a, b, t) => "#" + rgb(a).lerp(rgb(b), t).getHexString();
  const environmentColor = () => lerpHex(DATA.environments[env.from].background, DATA.environments[env.to].background, env.mix);
  /** 当前环境的背景（星点、地球弧）：两个环境之间过渡时，按 mix 淡入目标环境的背景。 */
  const backdropSpec = () => {
    const to = DATA.environments[env.to].backdrop;
    const from = DATA.environments[env.from].backdrop;
    const k = env.from === env.to ? 1 : env.mix;
    const B = to ?? from;
    if (!B) return null;
    const bg = environmentColor();
    return { ...B, top: B.top ?? bg, bottom: B.bottom ?? bg, k: to ? k : 1 - k };
  };
  function setEnvironment(name, mix = 1) {
    if (!DATA.environments[name]) throw new Error(`Unknown environment: ${name}`);
    env.from = mix >= 1 ? name : env.from;
    env.to = name;
    env.mix = mix >= 1 ? 0 : mix;
    const E2 = DATA.environments[name];
    // 台面色随环境（太空段台面压暗，线条照旧）；机体整体压暗 dim
    MAT.deck.uniforms.uTone.value = (E2.deck ?? DATA.palette.deck).map(rgb);
    shared.uDim.value = E2.dim ?? 1;
    stage.style.background = environmentColor();
    for (const hook of envHooks) hook(name);
  }
  const envHooks = [];

  // ———————————————— 选中与操作区 ————————————————
  const PHASE = { unlocking: "解锁", moving: "运动", locking: "定位", locked: "锁定", manual: "手动" };
  const labelOf = (name) => ((DATA.labels ?? []).find(([re]) => new RegExp(re).test(name)) ?? [null, name])[1];
  const pickRules = DATA.controls.filter((c) => c.pick).map((c) => [c.id, c.pick.map((p) => new RegExp(p))]);
  const controlOfPart = (name) => (pickRules.find(([, res]) => res.some((re) => re.test(name))) ?? [null])[0];
  let selected = null;
  let picked = null;
  const panel = document.querySelector("[data-panel]");
  function stateText(id) {
    const c = controls.get(membersOf(id)[0]);
    if (!c) return "";
    const v = c.unit === "%" ? `${Math.round(c.value * 100)}%` : `${Math.round(c.value * 10) / 10}${c.unit ?? ""}`;
    return `${PHASE[c.phase] ?? c.phase} · ${v}`;
  }
  function refreshUi() {
    if (quiet || !panel) return;
    const sel = selected ? controls.get(membersOf(selected)[0]) ?? pairs.get(selected) : null;
    const name = sel ? sel.label : picked ? picked.label : null;
    const text = selected ? stateText(selected) : picked ? picked.note : "点选零件，或选上面的机构";
    const html = name ? `<span class="af-name">${name}</span><span class="af-state">${text}</span>` : `<span class="af-hint">${text}</span>`;
    if (panel.innerHTML !== html) panel.innerHTML = html;
    for (const b of document.querySelectorAll("[data-control]")) b.setAttribute("aria-pressed", String(b.dataset.control === selected));
    const showState = document.querySelector("[data-show-state]");
    if (showState) showState.textContent = actRunning() ? `${act.def.label} · ${act.steps[act.index]?.name ?? ""}` : act?.done ? `${act.def.label} · 完成` : "停机";
    refreshTint();
  }
  function refreshTint() {
    for (const layer of airLayers) {
      if (layer.accent) continue;
      const moving = [...controls.values()].some((c) => (c.motion || c.manual) && jointsOf(c).some((j) => groupKey(j) === layer.group));
      const chosen = selected && membersOf(selected).some((m) => jointsOf(controls.get(m)).some((j) => groupKey(j) === layer.group));
      layer.tint(moving ? AMBER : chosen ? CYAN : null);
    }
  }
  function select(id, part = null) {
    selected = id;
    picked = part && !id ? { label: labelOf(part.name), note: part.joint ? "可动件 · 操作随后开放" : "固定结构" } : null;
    refreshUi();
    draw();
  }
  /** 两端切换：在静止值与另一端之间。 */
  function toggle(id) {
    const c = controls.get(membersOf(id)[0]);
    if (!c) return;
    const far = Math.abs(c.target - c.range[0]) < Math.abs(c.target - c.range[1]) ? c.range[1] : c.range[0];
    play(id, far);
  }
  const raycaster = new THREE.Raycaster();
  function pickAt(clientX, clientY) {
    const rect = canvas.getBoundingClientRect();
    const ndc = new THREE.Vector2(((clientX - rect.left) / rect.width) * 2 - 1, -((clientY - rect.top) / rect.height) * 2 + 1);
    scene.updateMatrixWorld();
    raycaster.setFromCamera(ndc, camera);
    const hit = raycaster.intersectObjects(pickables, false)[0];
    const part = hit ? partAt(hit) : null;
    if (!part) return select(null);
    select(controlOfPart(part.name), part);
  }
  for (const b of document.querySelectorAll("[data-control]")) b.addEventListener("click", () => (selected === b.dataset.control ? toggle(b.dataset.control) : select(b.dataset.control)));
  for (const b of document.querySelectorAll("[data-show]")) b.addEventListener("click", () => startShow(b.dataset.show));

  // ———————————————— 尺寸 ————————————————
  let forced = 0;
  const FRUSTUM0 = { left: camera.left, right: camera.right, top: camera.top, bottom: camera.bottom };
  const phoneFrame = () => matchMedia("(max-width:560px)").matches;
  function frameCamera(w, h) {
    const PV = DATA.phoneView;
    if (!phoneFrame() || !PV) Object.assign(camera, FRUSTUM0);
    else {
      const wv = W / PV.zoom;
      const hv = (wv * h) / w;
      Object.assign(camera, { left: -wv / 2 / K, right: wv / 2 / K, top: (PV.centre * hv) / K, bottom: (-(1 - PV.centre) * hv) / K });
    }
    camera.updateProjectionMatrix();
  }
  let size = { w: 1, h: 1 };
  function resize() {
    const fill = phoneFrame();
    const w = fill ? stage.clientWidth : Math.min(stage.clientWidth, (stage.clientHeight * W) / H);
    const h = fill ? stage.clientHeight : Math.round((w * H) / W);
    size = { w, h };
    frameCamera(w, h);
    const ratio = forced || Math.min(devicePixelRatio, lowQuality() ? 1.5 : 2);
    renderer.setPixelRatio(ratio);
    renderer.setSize(w, h, false);
    canvas.style.width = `${w}px`;
    canvas.style.height = `${h}px`;
    sizePost(w, h, ratio);
    // 线宽按 CSS 像素给，乘设备像素比与超采样倍数
    for (const layer of lineLayers) layer.resize(w, h, ratio * post.ss);
  }
  new ResizeObserver(() => {
    resize();
    draw();
  }).observe(stage);

  // ———————————————— 状态与绘制 ————————————————
  let heading = DATA.start;
  let target = DATA.start;
  let frame = 0;
  let last = 0;
  let visible = true;
  let held = false;
  const frameMs = new Float32Array(4096);
  let frameCount = 0;
  let frozenSim = false; // 审图快进之后定格，不再实时推进；任何用户操作解除
  const thaw = () => {
    frozenSim = false;
    run();
  };
  const showReadout = () => {
    const deg = Math.round(wrap(heading));
    const text = `机位 ${deg}° · ${MODES[stage.dataset.mode] ?? ""}`;
    if (readout && readout.textContent !== text) readout.textContent = text;
    stage.setAttribute("aria-valuenow", String(deg));
    stage.setAttribute("aria-valuetext", `机位 ${deg}°`);
  };
  function placePageCamera() {
    turntable.rotation.z = (-heading * Math.PI) / 180;
    turntable.updateMatrix();
    placeFree();
    camera.position.copy(CAM0).add(follow.p).add(reviewPan);
  }
  /** 摆好这一帧的一切（不画）：相机、可见性、线定级、灯。 */
  function prepareDraw() {
    placePageCamera();
    camera.updateMatrixWorld();
    const mode = stage.dataset.mode;
    const silhouette = mode === "silhouette";
    shared.uUseFlat.value = silhouette ? 1 : 0;
    shared.uLight.value = lightFor();
    const linesOn = mode === "lines";
    refreshFlush();
    for (const layer of airLayers) layer.mesh.visible = linesOn && (!layer.show || showOn(layer.show));
    for (const mesh of showMeshes) mesh.visible = showOn(mesh.userData.show);
    deckLineGroup.visible = linesOn;
    shadow.visible = !silhouette;
    scene.updateMatrixWorld();
    placeFx(linesOn);
    placeLights(linesOn);
    aimGlint();
    for (const hook of drawHooks) hook(mode);
    scene.updateMatrixWorld();
    if (linesOn) for (const layer of lineLayers) if (layer.mesh.visible) layer.update();
    return silhouette;
  }
  const drawHooks = [];
  /** 状态显隐（剖视等）：showState[名] 为真时，show 为该名的网格与线层才画；show 为 "!名" 的反过来（剖视时隐去的外部件）。 */
  const showState = {};
  const showOn = (k) => (k[0] === "!" ? !showState[k.slice(1)] : !!showState[k]);
  function draw() {
    const silhouette = prepareDraw();
    renderAll(silhouette);
  }
  function tick(now) {
    const dt = last ? Math.min((now - last) / 1000, 1 / 15) : 1 / 60;
    last = now;
    const t0 = performance.now();
    let live = false;
    if (!frozenSim) for (let remaining = dt; remaining > 1e-9; ) {
      const step = Math.min(remaining, 1 / 60);
      live = advance(step) || live;
      remaining -= step;
    }
    const before = heading;
    heading = still.matches ? target : heading + (target - heading) * (1 - Math.exp(-dt / 0.14));
    if (Math.abs(target - heading) < 1e-3) heading = target;
    if (heading !== before || live) {
      draw();
      showReadout();
    }
    frameMs[frameCount++ % frameMs.length] = performance.now() - t0;
    frame = visible && (heading !== target || live) ? requestAnimationFrame(tick) : 0;
  }
  const run = () => {
    if (!frame && visible && !recordOnly) {
      last = 0;
      frame = requestAnimationFrame(tick);
    }
  };
  let recordOnly = false;
  new IntersectionObserver((entries) => {
    visible = entries[entries.length - 1].isIntersecting;
    if (visible) run();
    else if (frame) {
      cancelAnimationFrame(frame);
      frame = 0;
    }
  }).observe(stage);

  // 拖动转台；按下到抬起移动不到 5 px、不到 0.5 s 算点选
  let drag = null;
  stage.addEventListener("pointerdown", (event) => {
    if (frozenSim) thaw();
    drag = { x: event.clientX, y: event.clientY, base: target, id: event.pointerId, at: performance.now(), far: false };
    stage.setPointerCapture(event.pointerId);
    held = false;
  });
  stage.addEventListener("pointermove", (event) => {
    if (!drag || event.pointerId !== drag.id) return;
    if (Math.hypot(event.clientX - drag.x, event.clientY - drag.y) > 5) {
      drag.far = true;
      follow.held = true;
      follow.turn = null;
    }
    target = drag.base + (event.clientX - drag.x) * 0.45;
    run();
  });
  const release = (event) => {
    if (drag && event.pointerId === drag.id) drag = null;
    follow.held = false;
  };
  stage.addEventListener("pointerup", (event) => {
    if (drag && event.pointerId === drag.id && !drag.far && performance.now() - drag.at < 500) pickAt(event.clientX, event.clientY);
    release(event);
  });
  stage.addEventListener("pointercancel", release);
  const setMode = (mode) => {
    if (!MODES[mode]) return;
    stage.dataset.mode = mode;
    draw();
    showReadout();
  };
  stage.addEventListener("keydown", (event) => {
    if (event.key === "1") setMode("silhouette");
    else if (event.key === "2") setMode("volume");
    else if (event.key === "3") setMode("lines");
    else if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
      event.preventDefault();
      follow.turn = null;
      target = Math.round(target / 15) * 15 + (event.key === "ArrowLeft" ? 15 : -15);
      run();
      return;
    } else return;
    event.preventDefault();
  });

  /** 审图与测试入口（与 FIG.01 同名同义，见 PATTERNS「审图截图」）。 */
  const api = {
    view(deg, mode, elevation) {
      held = true;
      if (mode) stage.dataset.mode = mode;
      setElevation(elevation ?? DATA.elevation);
      if (deg !== null && deg !== undefined) heading = target = deg;
      draw();
      showReadout();
      return `${deg} ${stage.dataset.mode}`;
    },
    /** 审图特写：按 r 倍像素比重画（0 = 恢复按设备像素比）。 */
    resolution(r) {
      forced = r;
      resize();
      draw();
      return renderer.getPixelRatio();
    },
    /** 取景缩放（1 = 标准取景）与平移（米，世界坐标）：特写机位用。 */
    zoom(z = 1, pan = [0, 0, 0]) {
      camera.zoom = z;
      camera.updateProjectionMatrix();
      reviewPan.set(...pan);
      draw();
      return camera.zoom;
    },
    /** 特写取景：把模型坐标里的一点（或地标名）放到画面中心，放大 z 倍；z = 1、point = null 复原。在 view() 之后调用。 */
    focus(point = null, z = 1) {
      camera.zoom = z;
      camera.updateProjectionMatrix();
      if (!point) reviewPan.set(0, 0, 0);
      else {
        placePageCamera();
        scene.updateMatrixWorld();
        const p = new THREE.Vector3(...(typeof point === "string" ? DATA.landmarks[point] ?? DATA.focus[point] : point)).applyMatrix4(airframe.matrixWorld);
        const aim = new THREE.Vector3(...(DATA.aim ?? [0, 0, 0]));
        p.sub(aim);
        reviewPan.copy(p).addScaledVector(VIEW, -p.dot(VIEW));
        // 视锥不对称（转台轴心不在画幅中心）：减去画幅中心相对相机轴的偏移（three 的缩放绕视锥中心，偏移不随缩放变）
        camera.updateMatrixWorld();
        const right = new THREE.Vector3().setFromMatrixColumn(camera.matrixWorld, 0);
        const up = new THREE.Vector3().setFromMatrixColumn(camera.matrixWorld, 1);
        reviewPan.addScaledVector(right, -(camera.left + camera.right) / 2).addScaledVector(up, -(camera.top + camera.bottom) / 2);
      }
      draw();
      return reviewPan.toArray().map((v) => Math.round(v * 1000) / 1000);
    },
    /** 审图对照：逐项关掉基础质感（ao 顶点 AO 强度、detail 细节贴图开关、bloom 泛光强度）；不传的项不变，返回当前值。 */
    look(opts = {}) {
      // 画法：mode "lines"（A，线条 + 五档明暗）/ "metal"（B，金属质感，线条降一级）
      if (opts.mode) {
        const metal = opts.mode === "metal";
        shared.uLook.value = metal ? 1 : 0;
        lineLook.levels = metal ? DATA.metal.lines : [1, 1, 1];
        for (const layer of airLayers) if (!layer.accent) layer.levels(...lineLook.levels);
      }
      if (opts.ao !== undefined) shared.uAOK.value = opts.ao;
      if (opts.detail !== undefined) for (const m of materials) if (m.uniforms.uDetail.value !== blackTex) m.uniforms.uUseDetail.value = opts.detail ? 1 : 0;
      if (opts.bloom !== undefined) composeMat.uniforms.uBloom.value = opts.bloom;
      draw();
      return { ao: shared.uAOK.value, bloom: composeMat.uniforms.uBloom.value, mode: shared.uLook.value ? "metal" : "lines" };
    },
    /** 审图：模型坐标里的点（或地标名）投到舞台上的 CSS 像素位置（叠图对位用）。 */
    project(point) {
      prepareDraw();
      const p = new THREE.Vector3(...(typeof point === "string" ? DATA.landmarks[point] : point)).applyMatrix4(airframe.matrixWorld).project(camera);
      const rect = canvas.getBoundingClientRect();
      const host = stage.getBoundingClientRect();
      return [rect.left - host.left + ((p.x + 1) / 2) * rect.width, rect.top - host.top + ((1 - p.y) / 2) * rect.height];
    },
    set(id, value) {
      setNow(id, value);
      draw();
      return membersOf(id).map((m) => controls.get(m).value);
    },
    play(id, value) {
      play(id, value);
      return new Promise((done) => {
        const wait = () => (membersOf(id).some((m) => controls.get(m).motion || controls.get(m).manual) ? setTimeout(wait, 50) : done(stateText(id)));
        wait();
      });
    },
    scrub(id, value, seconds) {
      scrub(id, value, seconds);
      draw();
      return stateText(id);
    },
    select(id) {
      select(id);
      return selected;
    },
    state: () => Object.fromEntries([...controls.values()].map((c) => [c.id, { value: Math.round(c.value * 1000) / 1000, phase: c.phase }])),
    show(id) {
      if (!startShow(id)) return Promise.resolve(false);
      return new Promise((done) => {
        const wait = () => (actRunning() ? setTimeout(wait, 100) : done(true));
        wait();
      });
    },
    park() {
      parkNow();
      draw();
      return true;
    },
    /** 审图：从停机开演，固定步长快进 seconds 秒并定格。 */
    showAt(seconds, events = [], id = null) {
      parkNow();
      frozenSim = true;
      if (id && !startShow(id)) return false;
      frozenSim = true;
      simulate(seconds, events);
      draw();
      showReadout();
      return act ? `${act.def.label} · t ${seconds}s` : `t ${seconds}s`;
    },
    /** 审图：快进 seconds 秒（不重置）。 */
    advance(seconds, events = []) {
      frozenSim = true;
      simulate(seconds, events);
      frozenSim = true;
      draw();
      return clock;
    },
    environment(name, mix = 1) {
      setEnvironment(name, mix);
      draw();
      return { ...env };
    },
    /**
     * 电影画质（录制模式，网页版不开）：opts = { ssaa, blur, shutter, dof: { focus, range, coc } | null, grade } 或 null 关闭。
     * frame(dt) 按电影画质画一帧（运动模糊的子帧沿真实的 advance 推进）。
     */
    cinema(opts) {
      cinema = opts ? { ssaa: 2, blur: 1, shutter: 0.5, dof: null, grade: true, ...opts } : null;
      resize();
      draw();
      return cinema;
    },
    /** 录制一帧：spin = 这一帧里转台转过的角度（度/帧），dt = 场景推进秒数。运动模糊在快门内的子帧上积分。 */
    cinemaFrame({ dt = 1 / 30, spin = 0 } = {}) {
      if (!cinema) throw new Error("cinema() first");
      frozenSim = true;
      recordOnly = true;
      const per = spin / Math.max(dt, 1e-6);
      renderCinemaFrame((h) => {
        quiet = true;
        advance(h);
        heading = target = heading + per * h;
        quiet = false;
      }, dt);
      return { heading, clock };
    },
    frames(since = 0) {
      const n = Math.min(frameCount - since, frameMs.length);
      const list = Array.from({ length: n }, (_, i) => frameMs[(frameCount - n + i) % frameMs.length]).sort((a, b) => a - b);
      return { count: frameCount, n, median: list[n >> 1] ?? 0, p95: list[Math.floor(n * 0.95)] ?? 0, max: list[n - 1] ?? 0 };
    },
    /** 画质档（perf.mjs 用）："standard" 手机档（不超采样、像素比 ≤ 1.5、不画次级线）/ "high"；不传返回当前。 */
    quality(mode) {
      if (mode && mode !== "auto") {
        quality.mode = mode === "standard" ? "standard" : "high";
        resize();
        draw();
      }
      return { mode: quality.mode, sampled: true, pixelRatio: renderer.getPixelRatio(), ssaa: post.ss };
    },
    thaw,
    controls: [...controls.keys(), ...pairs.keys()],
    scene,
    renderer,
    camera,
    draw,
  };
  window.__arcseq = api;

  for (const c of controls.values()) apply(c);
  setEnvironment(DATA.environment);
  resize();
  refreshShadowNow();
  refreshUi();
  // 着色器在加载时先编译好
  {
    for (const f of flames) f.root.visible = true;
    scene.updateMatrixWorld();
    renderer.compile(scene, camera);
    for (const f of flames) f.root.visible = false;
  }
  draw();
  showReadout();
