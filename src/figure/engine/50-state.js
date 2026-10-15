  // ———————————————— 机构状态（SceneState，FIG.01 G3 定） ————————————————
  /**
   * 每个机构（DATA.controls）一个状态：value、target、phase、motion，以及 base（演出给的标准姿态）+ offset（用户的手动偏移）。
   *   · start(c, to)：解锁（unlock 秒，沿运动方向顶一下再回来）→ 运动（三次缓入缓出；顺序动作匀速推进、每步在自己的分段里缓入缓出）
   *     → 定位（lock 秒，到位后反向回弹一点）→ 锁定。中途再下指令从当前值接着走。
   *   · 用户指令只改 offset；演出指令（command）只改 base；目标 = clamp(base + offset)。演出之外 base = rest。
   *   · 值换关节：drive（线性跟随）、steps（顺序动作）；flight 键写进 flight（空中状态）；power 键写进发光通电量（powerOf）。
   */
  const MOTION = DATA.motion;
  const AMBER = "#f0bd83";
  const CYAN = "#7bdbec";
  const controls = new Map(DATA.controls.map((c) => [c.id, { ...c, value: c.rest, target: c.rest, base: c.rest, offset: 0, phase: "locked", motion: null, manual: false, frozen: false }]));
  const pairs = new Map((DATA.pairs ?? []).map((p) => [p.id, p]));
  const membersOf = (id) => (pairs.has(id) ? pairs.get(id).members : controls.has(id) ? [id] : []);
  const spanOf = (c) => c.range[1] - c.range[0];
  const clampTo = (c, v) => (c.cyclic ? v : Math.min(c.range[1], Math.max(c.range[0], v)));
  /** 空中状态：通电、发动机 0…1、离地高度 m、航向 / 俯仰 / 滚转 °、前飞速度 m/s。 */
  const flight = { power: 0, engine: 0, lift: 0, yaw: 0, pitch: 0, bank: 0, speed: 0 };
  function apply(c) {
    const v = c.value;
    const k = (v - c.range[0]) / spanOf(c);
    for (const d of c.drive ?? []) setJoint(d.joint, (d.from ?? 0) + (d.to - (d.from ?? 0)) * k);
    for (const st of c.steps ?? []) setJoint(st.joint, st.to * ease(clamp01((v - st.span[0]) / (st.span[1] - st.span[0]))));
    if (c.flight) flight[c.flight] = v;
    if (c.power) powerOf(c.power).value = k;
    if (c.sweep) powerOf(c.sweep).value = k;
  }
  const jointsOf = (c) => [...(c.drive ?? []).map((d) => d.joint), ...(c.steps ?? []).map((st) => st.joint), ...(c.tint ?? [])];
  const stepAt = (c, v) => (c.steps ?? []).reduce((found, st) => (v > st.span[0] - 1e-6 ? st : found), c.steps?.[0]);

  function start(c, to, { unlock = true, seconds = null, linear = false } = {}) {
    to = clampTo(c, to);
    c.manual = false;
    c.frozen = false;
    if (Math.abs(to - c.value) < 1e-6 && !c.motion) return;
    const dir = Math.sign(to - c.value) || 1;
    const quick = still.matches;
    const move = seconds ?? (c.time * Math.abs(to - c.value)) / spanOf(c);
    const plain = c.flight || c.power || c.sweep;
    c.motion = { from: c.value, to, dir, t: 0, linear: linear || !!c.linear, unlock: quick || !unlock || c.motion || plain ? 0 : MOTION.unlock, move: quick ? 0 : Math.max(0.4, move), lock: quick || plain ? 0 : MOTION.lock };
    c.target = to;
  }
  function motionAt(c, m) {
    // 顺序动作、空中状态、通电量不做“顶一下 / 回弹”
    const plain = c.steps || c.flight || c.power || c.sweep;
    const kick = plain ? 0 : MOTION.kick * spanOf(c);
    const settle = plain ? 0 : MOTION.settle * spanOf(c);
    if (m.t < m.unlock) return { phase: "unlocking", value: clampTo(c, m.from + m.dir * kick * Math.sin((Math.PI * m.t) / m.unlock)) };
    const t2 = m.t - m.unlock;
    if (t2 < m.move) {
      const f = t2 / m.move;
      return { phase: "moving", value: m.from + (m.to - m.from) * (c.steps || m.linear ? f : easeInOut(f)) };
    }
    const t3 = t2 - m.move;
    if (t3 < m.lock) return { phase: "locking", value: clampTo(c, m.to - m.dir * settle * Math.sin((Math.PI * t3) / m.lock)) };
    return { phase: "locked", value: m.to };
  }
  /** 推进 dt 秒；返回是否还有机构在动。关节类机构定位完成的那一帧重画投影。 */
  function stepMotions(dt) {
    let active = false;
    let settled = false;
    let changed = false;
    for (const c of controls.values()) {
      if (c.motion && !c.frozen) {
        c.motion.t += dt;
        const { phase, value } = motionAt(c, c.motion);
        c.value = value;
        c.phase = phase;
        if (phase === "locked") {
          c.motion = null;
          if (jointsOf(c).length && c.shadow !== false) settled = true;
        } else active = true;
        apply(c);
        changed = true;
      } else if (c.manual) {
        const next = c.value + (c.target - c.value) * (1 - Math.exp(-dt / 0.08));
        c.value = Math.abs(c.target - next) < 1e-4 * spanOf(c) ? c.target : next;
        apply(c);
        active = true;
        changed = true;
      }
    }
    if (settled) refreshShadow();
    if (changed && !quiet) refreshUi();
    return active;
  }
  function play(id, to) {
    thaw();
    for (const m of membersOf(id)) {
      const c = controls.get(m);
      c.offset = clampTo(c, to) - c.base;
      start(c, to);
    }
    run();
  }
  /** 复位：偏移归零，平滑回到当前（演出步骤的）标准姿态。 */
  function resetOffset(id) {
    thaw();
    for (const m of membersOf(id)) {
      const c = controls.get(m);
      c.offset = 0;
      start(c, c.base);
    }
    run();
  }
  function beginManual(id) {
    for (const m of membersOf(id)) {
      const c = controls.get(m);
      c.motion = null;
      c.frozen = false;
      c.manual = true;
      c.phase = "manual";
      c.target = c.value;
    }
    refreshUi();
    run();
  }
  function setManual(id, v) {
    thaw();
    for (const m of membersOf(id)) {
      const c = controls.get(m);
      if (!c.manual) beginManual(id);
      c.target = clampTo(c, v);
      c.offset = c.target - c.base;
    }
    run();
  }
  function endManual(id) {
    for (const m of membersOf(id)) {
      const c = controls.get(m);
      if (!c.manual) continue;
      const to = c.target;
      c.manual = false;
      c.offset = to - c.base;
      c.motion = { from: c.value, to, dir: Math.sign(to - c.value) || 1, t: 0, unlock: 0, move: still.matches ? 0 : 0.15, lock: still.matches ? 0 : MOTION.lock };
    }
    run();
  }
  /** 立即设值（审图、复原）：跳过过程，直接锁定。 */
  function setNow(id, v) {
    for (const m of membersOf(id)) {
      const c = controls.get(m);
      c.motion = null;
      c.manual = false;
      c.frozen = false;
      c.value = c.target = clampTo(c, v);
      c.offset = c.value - c.base;
      c.phase = "locked";
      apply(c);
    }
    refreshShadowNow();
    refreshUi();
  }
  /** 审图：把机构定格在“从当前值出发、过了 seconds 秒”的那一刻。 */
  function scrub(id, to, seconds) {
    for (const m of membersOf(id)) {
      const c = controls.get(m);
      start(c, to);
      if (!c.motion) continue;
      c.motion.t = seconds;
      const { phase, value } = motionAt(c, c.motion);
      c.value = value;
      c.phase = phase;
      c.frozen = true;
      apply(c);
    }
    refreshUi();
  }
  /** 关着的贴面舱门：边按一级结构线画，不画成 L0 的亮框；门一打开恢复。DATA.flush：[[关节, 机构, 关着的值域端]]。 */
  function refreshFlush() {
    for (const [joint, id] of DATA.flush ?? []) {
      const layer = groupLines.get(joint);
      const c = controls.get(id);
      if (layer && c) layer.demote = Math.abs(c.value - c.rest) < 1e-3;
    }
  }
