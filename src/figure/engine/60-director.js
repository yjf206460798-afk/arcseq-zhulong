  // ———————————————— 演出（Director）与中途干预（ActionDirector，FIG.01 G4 定） ————————————————
  /**
   * 演出 = DATA.shows 里的步骤表 { id, label, steps: [{ name, set: [[机构或组合项, 标准值, 秒数?], …], hold? }], prepare?, camera? }。
   * 每步把各项的 base 改成新值（command），全部定位（或被用户手动接管）后停 DIR.pause 秒进下一步。
   * 演出不另写动画：每一步都是 SceneState 的 start()。中途干预记成 offset，演出照常往下走。
   */
  const DIR = DATA.director;
  const shows = new Map((DATA.shows ?? []).map((sh) => [sh.id, sh]));
  let act = null; // 当前演出：{ def, steps, index, issued, wait, t, log, done }
  function command(id, base, seconds = null, options = {}) {
    for (const m of membersOf(id)) {
      const c = controls.get(m);
      c.base = clampTo(c, base);
      c.offset = clampTo(c, c.base + c.offset) - c.base;
      if (!c.manual) start(c, c.base + c.offset, { seconds, ...options });
    }
  }
  const actRunning = () => !!act && !act.done;
  const inAir = () => flight.lift > 0.005;
  function startShow(id) {
    const def = shows.get(id);
    if (!def || (actRunning() && !def.interrupt)) return false;
    thaw();
    const steps = [];
    if (def.prepare) {
      const off = [...controls.values()].filter((c) => Math.abs(c.value - c.rest) > 1e-6 && !c.keep);
      if (off.length) steps.push({ name: "收回到停机姿态", prep: true, set: off.map((c) => [c.id, c.rest, null]) });
    }
    steps.push(...def.steps);
    act = { def, steps, index: 0, issued: false, wait: 0, t: 0, log: [], done: false };
    follow.held = false;
    if (def.camera) {
      const delta = ((((def.camera.heading - target) % 360) + 540) % 360) - 180;
      follow.turn = delta ? { from: target, to: target + delta, t: 0, seconds: def.camera.seconds } : null;
    }
    refreshUi();
    run();
    return true;
  }
  /** 推进当前演出 dt 秒；返回演出是否还在进行。 */
  function advanceDirector(dt) {
    if (!actRunning()) return false;
    const step = act.steps[act.index];
    if (!act.issued) {
      if (step.prep) for (const [id] of step.set) for (const m of membersOf(id)) controls.get(m).offset = 0;
      for (const [id, value, seconds, options] of step.set) command(id, value, seconds ?? null, options);
      act.issued = true;
      act.wait = 0;
      act.stepAt = act.t;
      act.log.push({ name: step.name, start: Math.round(act.t * 1000) / 1000, end: null });
    }
    act.t += dt;
    const settled = act.t - act.stepAt >= (step.hold ?? 0) - 1e-9 && step.set.every(([id]) => membersOf(id).every((m) => {
      const c = controls.get(m);
      return !c.motion || c.manual || c.frozen;
    }));
    if (settled) {
      const entry = act.log[act.log.length - 1];
      if (entry.end === null) entry.end = Math.round(act.t * 1000) / 1000;
      act.wait += dt;
      if (act.wait >= DIR.pause - 1e-9) {
        act.index++;
        act.issued = false;
        if (act.index >= act.steps.length) act.done = true;
        if (!quiet) refreshUi();
      }
    }
    return true;
  }

  /** 把 flight + 浮动写进 free 组：T(pivot + 位移) · Rz(航向) · Ry(−俯仰) · Rx(滚转) · T(−pivot)；投影随之放到地面上。 */
  const PIVOT = new THREE.Vector3(...DIR.pivot);
  const bob = { z: 0, pitch: 0, bank: 0 };
  const airborne = () => smoothStepJs(DIR.airborne[0], DIR.airborne[1], flight.lift);
  function advanceFlight() {
    const k = still.matches ? 0 : airborne();
    const B = DIR.bob;
    const ph = (2 * Math.PI * clock) / B.period;
    bob.z = k * B.z * Math.sin(ph);
    bob.pitch = k * B.pitch * Math.sin(0.73 * ph + 1.1);
    bob.bank = k * B.bank * Math.sin(0.58 * ph + 2.3);
    return k > 0;
  }
  const freeEuler = new THREE.Euler();
  const freeAt = new THREE.Vector3();
  const shadowM = new THREE.Matrix4();
  const shadowS = new THREE.Matrix4();
  function placeFree() {
    const yaw = flight.yaw * D2R;
    const pitch = (flight.pitch + bob.pitch) * D2R;
    const bank = (flight.bank + bob.bank) * D2R;
    const h = flight.lift + bob.z;
    free.matrix.makeRotationFromEuler(freeEuler.set(bank, -pitch, yaw, "ZYX"));
    freeAt.copy(PIVOT).applyMatrix4(free.matrix);
    free.matrix.setPosition(PIVOT.x - freeAt.x, PIVOT.y - freeAt.y, PIVOT.z + h - freeAt.z);
    free.matrixWorldNeedsUpdate = true;
    // 投影：只取水平部分（偏航），按高度放大；变淡、变软在着色器里插值
    const A = FX.air;
    const t = ease(clamp01(h / A.height));
    const grow = 1 + A.grow * t;
    shadow.matrix.makeTranslation(PIVOT.x, PIVOT.y, 0.003).multiply(shadowM.makeRotationZ(yaw)).multiply(shadowS.makeScale(grow, grow, 1)).multiply(shadowM.makeTranslation(-PIVOT.x, -PIVOT.y, 0));
    shadow.matrixWorldNeedsUpdate = true;
    shadowUniforms.uSoft.value = t;
    shadowUniforms.uOpacity.value = FX.shadow.opacity * (1 - (1 - A.fade) * t);
    shadowUniforms.uContact.value = 1 - smoothStepJs(0, A.contactOff, h);
  }
  /** 相机跟随：相机随 pan × 离地高度同步升起；演出机位缓转（follow.turn）。用户一拖动立即交还相机。 */
  const reviewPan = new THREE.Vector3();
  const follow = { p: new THREE.Vector3(), held: false, turn: null };
  function advanceFollow(dt) {
    let turning = false;
    if (follow.turn && !follow.held) {
      const T = follow.turn;
      T.t += dt;
      const f = still.matches ? 1 : Math.min(1, T.t / T.seconds);
      heading = target = T.from + (T.to - T.from) * easeInOut(f);
      if (f >= 1) follow.turn = null;
      else turning = true;
    }
    follow.p.set(0, 0, DIR.follow.pan * flight.lift);
    return turning;
  }
  function parkNow() {
    act = null;
    for (const c of controls.values()) {
      c.motion = null;
      c.manual = false;
      c.frozen = false;
      c.base = c.rest;
      c.offset = 0;
      c.value = c.target = c.rest;
      c.phase = "locked";
      apply(c);
    }
    bob.z = bob.pitch = bob.bank = 0;
    clock = 0;
    follow.p.set(0, 0, 0);
    follow.held = false;
    follow.turn = null;
    thrust.pc = thrust.glow = thrust.flash = 0;
    thrust.lit = false;
    advanceFx(0);
    refreshShadowNow();
    refreshUi();
  }
  /** 推进整个场景 dt 秒（实时出帧与审图快进共用）：演出 → 机构 → 姿态与浮动 → 特效 → 相机。返回是否还要继续出帧。 */
  function advance(dt) {
    clock += dt;
    const directing = advanceDirector(dt);
    const moving = stepMotions(dt);
    const shading = stepShadow();
    const flying = advanceFlight(dt);
    placeFree();
    const fx = advanceFx(dt);
    const following = advanceFollow(dt);
    return directing || moving || shading || flying || fx || following || cinemaBusy();
  }
  /** 审图快进：按固定步长 1/60 秒推进 seconds 秒，不出帧。events：{ at, id, value, release? }、{ at, reset: id }、{ at, show: id }。 */
  function simulate(seconds, events = []) {
    quiet = true;
    const dt = 1 / 60;
    const queue = events.map((e) => ({ ...e, release: e.release ?? e.at + 0.6, state: 0 }));
    for (let t = 0; t < seconds - 1e-9; t += dt) {
      for (const e of queue) {
        if (e.show && e.state === 0 && t >= e.at - 1e-9) {
          startShow(e.show);
          e.state = 2;
        } else if (e.reset && e.state === 0 && t >= e.at - 1e-9) {
          resetOffset(e.reset);
          e.state = 2;
        } else if (e.id && e.state === 0 && t >= e.at - 1e-9) {
          setManual(e.id, e.value);
          e.state = 1;
        } else if (e.id && e.state === 1 && t >= e.release - 1e-9) {
          endManual(e.id);
          e.state = 2;
        }
      }
      advance(dt);
    }
    while (shadowJob) stepShadow();
    quiet = false;
    refreshUi();
  }
