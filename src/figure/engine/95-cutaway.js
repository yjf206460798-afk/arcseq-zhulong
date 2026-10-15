  // ———————————————— 剖视模式（FIG.02 复刻样板）与按需模块 ————————————————
  /**
   * 剖视：沿模型坐标 y = 0 切开（切掉 y > 0 一侧，从左侧看进去，与 K1 同一个剖切面）。蒙皮等 cut 零件被剖切面切开、背面画暗内壁，
   * cut 线层同样切掉；内部模块（DATA.modules.interior：GLB 与硬边，单独一个 dist/<名>.js）第一次打开剖视时才加载；
   * 带编号的标注（DATA.callouts + 模块里的 callouts）画在画布上方的 SVG 里：圆圈编号 + 竖直引线，右下角一张图例。
   */
  const cutaway = { on: false, loading: null, modules: new Set() };
  const callouts = [...(DATA.callouts ?? [])];
  window.__arcseqModule = (name, data) => {
    const parts = parseGlb(b64(data.glb), data.edges ?? {}).map((p) => ({ ...p, show: p.show ?? "cutaway" }));
    const first = DATA.parts.length;
    DATA.parts.push(...parts);
    buildMeshes(parts, first);
    const layers = buildLayers(parts, data.seams ?? []);
    for (const layer of layers) {
      layer.show ??= "cutaway";
      layer.resize(size.w, size.h, renderer.getPixelRatio() * post.ss);
    }
    callouts.push(...(data.callouts ?? []));
    cutaway.modules.add(name);
    window.dispatchEvent(new CustomEvent("arcseq-module", { detail: name }));
  };
  function loadModule(name) {
    if (cutaway.modules.has(name)) return Promise.resolve(true);
    const src = DATA.modules?.[name];
    if (!src) return Promise.resolve(false);
    return new Promise((done, fail) => {
      const tag = document.createElement("script");
      tag.src = src;
      const ok = (e) => {
        if (e.detail !== name) return;
        window.removeEventListener("arcseq-module", ok);
        done(true);
      };
      window.addEventListener("arcseq-module", ok);
      tag.onerror = () => fail(new Error(`module ${name} failed to load`));
      document.head.appendChild(tag);
    });
  }
  async function setCutaway(on) {
    if (on) await loadModule("interior");
    cutaway.on = !!on;
    showState.cutaway = cutaway.on;
    for (const layer of airLayers) if (layer.cut) layer.clip(cutaway.on);
    const button = document.querySelector("[data-cutaway]");
    if (button) button.setAttribute("aria-pressed", String(cutaway.on));
    refreshShadowNow();
    draw();
    return cutaway.on;
  }
  for (const b of document.querySelectorAll("[data-cutaway]")) b.addEventListener("click", () => setCutaway(!cutaway.on));
  const cutWorld = new THREE.Plane();
  const overlay = stage.querySelector("[data-callouts]");
  const legend = stage.querySelector("[data-legend]");
  const NS = "http://www.w3.org/2000/svg";
  function placeCallouts() {
    if (!overlay) return;
    overlay.replaceChildren();
    if (legend) legend.hidden = !cutaway.on || !callouts.length;
    if (!cutaway.on) return;
    const rect = canvas.getBoundingClientRect();
    const host = stage.getBoundingClientRect();
    const items = callouts.map((c) => {
      const p = new THREE.Vector3(...c.at).applyMatrix4(airframe.matrixWorld).project(camera);
      return { ...c, x: rect.left - host.left + ((p.x + 1) / 2) * rect.width, y: rect.top - host.top + ((1 - p.y) / 2) * rect.height };
    });
    // 两条标注线：画布上沿（点在画面上半）与下沿（下半）；同一条里按 x 排开，最小间距 28 px
    const top = rect.top - host.top + rect.height * 0.12;
    const bottom = rect.top - host.top + rect.height * 0.9;
    const midY = rect.top - host.top + rect.height * 0.5;
    for (const lane of [items.filter((i) => i.y < midY), items.filter((i) => i.y >= midY)]) {
      lane.sort((a, b) => a.x - b.x);
      let last = -Infinity;
      for (const it of lane) {
        it.lx = Math.max(it.x, last + 28);
        last = it.lx;
        it.ly = it === lane[0] || true ? (it.y < midY ? top : bottom) : 0;
      }
    }
    for (const it of items) {
      const line = document.createElementNS(NS, "polyline");
      line.setAttribute("points", `${it.x},${it.y} ${it.lx},${it.ly + (it.ly < it.y ? 11 : -11)}`);
      line.setAttribute("class", "af-co-line");
      const dot = document.createElementNS(NS, "circle");
      Object.entries({ cx: it.x, cy: it.y, r: 1.8, class: "af-co-dot" }).forEach(([k, v]) => dot.setAttribute(k, v));
      const ring = document.createElementNS(NS, "circle");
      Object.entries({ cx: it.lx, cy: it.ly, r: 10, class: "af-co-ring" }).forEach(([k, v]) => ring.setAttribute(k, v));
      const text = document.createElementNS(NS, "text");
      Object.entries({ x: it.lx, y: it.ly + 3.6, class: "af-co-num" }).forEach(([k, v]) => text.setAttribute(k, v));
      text.textContent = it.n;
      overlay.append(line, dot, ring, text);
    }
    if (legend) legend.innerHTML = [...callouts].sort((a, b) => a.n - b.n).map((c) => `<span><b>${c.n}</b>${c.label}</span>`).join("");
  }
  drawHooks.push(() => {
    if (cutaway.on) {
      cutPlanes.length = 1;
      cutPlanes[0] = cutWorld.copy(cutPlane).applyMatrix4(airframe.matrixWorld);
    } else cutPlanes.length = 0;
  });
  const renderAllBase = renderAll;
  renderAll = (silhouette) => {
    renderAllBase(silhouette);
    placeCallouts();
  };
  Object.assign(window.__arcseq, {
    /** 剖视开关（第一次打开时加载内部模块），返回 Promise。 */
    cutaway: (on = true) => setCutaway(on),
    modules: () => [...cutaway.modules],
  });
