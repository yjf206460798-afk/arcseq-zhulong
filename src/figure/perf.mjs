// 性能测量（ROADMAP G2 的预算）：无头 Chrome 打开页面，在 requestAnimationFrame 里逐帧转动转台 240 帧（每帧 1.1°），
// 读主线程任务、脚本时间与帧间隔，取 3 次的中位数。
//   export CHROME_PATH="$PWD/scripts/chrome.sh"
//   node src/figure/perf.mjs [dist/index.html] --width 1440            （DPR 2）
//   node src/figure/perf.mjs [dist/index.html] --width 390 --throttle 4 （DPR 3、4 倍 CPU 节流）
//   node src/figure/perf.mjs [dist/index.html] --width 390 --throttle 4 --show takeoff
//   node src/figure/perf.mjs [dist/index.html] --width 390 --throttle 4 --show reset --origin forward
//                                       （G4：实时跑完整场演出再悬停 hold 秒，按帧平均；另报页面自记的每帧推进 + 绘制耗时）
//   每条命令都有上限：--timeout 秒（默认 240）内跑不完就杀掉 Chrome、报错退出（exit 2）；单个 CDP 调用 90 s 无回应也报错；
//   演出在页面里另有上限（--show-limit 秒，默认 120），演出走不完直接报错，不会一直等一个不会到来的帧。
//   --runs 1：只做一组快速采样；--height 844：按手机实际视口高度采样。
//   --reduced 模拟“减少动态效果”（prefers-reduced-motion: reduce），用来查这个模式下的停绘逻辑。
// 预算：1440 × DPR 2 每帧主线程 ≤ 13 ms；390 × DPR 3、4× 节流 ≤ 33 ms。云端 Chrome 用软件 GL（SwiftShader），
// GPU 光栅也在 CPU 上做，所以帧间隔偏慢；G4.5 用脚本 ≤ 5 ms 作参考，主线程仅记录。

import { spawn } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { chromePort } from "../../.claude/skills/anatomy/scripts/chrome-port.mjs";

const argv = process.argv.slice(2);
const value = (name, fallback) => (argv.includes(name) ? argv[argv.indexOf(name) + 1] : fallback);
const pageArg = argv.find((a, i) => !a.startsWith("--") && !argv[i - 1]?.startsWith("--")) ?? "dist/index.html";
const page = /^https?:/.test(pageArg) ? pageArg : pathToFileURL(resolve(pageArg)).href;
const width = Number(value("--width", 1440));
const scale = Number(value("--scale", width < 600 ? 3 : 2));
const throttle = Number(value("--throttle", 1));
const mode = value("--mode", "lines");

const limit = Number(value("--timeout", 240));
const profile = mkdtempSync(join(tmpdir(), "arcseq-perf-"));
let chrome = null;
const cleanup = () => {
  // Chrome 单独成进程组（detached），整组杀掉，连 zygote / GPU / 渲染子进程一起
  try {
    if (chrome?.pid) process.kill(-chrome.pid, "SIGKILL");
  } catch {}
  try {
    chrome?.kill("SIGKILL");
  } catch {}
  try {
    rmSync(profile, { recursive: true, force: true });
  } catch {}
};
const fail = (message, code = 2) => {
  console.error(`perf: ${message}`);
  cleanup();
  process.exit(code);
};
// 总看门狗与外部 timeout / Ctrl-C：都先杀 Chrome 再退出，不留孤儿进程
setTimeout(() => fail(`timed out after ${limit} s`), limit * 1000).unref();
for (const sig of ["SIGTERM", "SIGINT", "SIGHUP"]) process.on(sig, () => fail(`killed by ${sig}`, 3));
process.on("unhandledRejection", (cause) => fail(cause?.stack ?? String(cause), 1));
process.on("uncaughtException", (cause) => fail(cause?.stack ?? String(cause), 1));
process.on("exit", cleanup); // 顶层 await 抛错退出时也收拾
chrome = spawn(process.env.CHROME_PATH, ["--headless=new", "--remote-debugging-port=0", `--user-data-dir=${profile}`, "--no-first-run", "--hide-scrollbars", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist", "about:blank"], { detached: true });
const port = await chromePort(chrome, profile);
const target = await (await fetch(`http://127.0.0.1:${port}/json/new?about:blank`, { method: "PUT" })).json();
const socket = new WebSocket(target.webSocketDebuggerUrl);
let id = 0;
const pending = new Map();
const problems = [];
socket.onmessage = (message) => {
  const data = JSON.parse(message.data);
  if (data.id && pending.has(data.id)) {
    pending.get(data.id)(data);
    pending.delete(data.id);
  } else if (data.method === "Runtime.exceptionThrown") problems.push(data.params.exceptionDetails.exception?.description ?? data.params.exceptionDetails.text);
};
await new Promise((done) => (socket.onopen = done));
socket.onclose = () => fail("DevTools socket closed");
const send = (method, params = {}, ms = 90000) =>
  new Promise((done, reject) => {
    const call = ++id;
    const timer = setTimeout(() => reject(new Error(`CDP ${method} got no reply within ${ms / 1000} s`)), ms);
    pending.set(call, (data) => {
      clearTimeout(timer);
      done(data);
    });
    socket.send(JSON.stringify({ id: call, method, params }));
  });
const evaluate = async (expression, ms) => {
  const reply = await send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true }, ms);
  if (reply.result?.exceptionDetails) throw new Error(reply.result.exceptionDetails.exception?.description ?? reply.result.exceptionDetails.text);
  return reply.result?.result?.value;
};

await send("Runtime.enable");
await send("Page.enable");
await send("Emulation.setDeviceMetricsOverride", { width, height: Number(value("--height", Math.round(width * 0.9))), deviceScaleFactor: scale, mobile: width < 600 });
if (argv.includes("--reduced")) await send("Emulation.setEmulatedMedia", { features: [{ name: "prefers-reduced-motion", value: "reduce" }] });
if (throttle > 1) await send("Emulation.setCPUThrottlingRate", { rate: throttle });
await send("Page.navigate", { url: page });
const t0 = Date.now();
while (!(await evaluate("!!window.__arcseq"))) {
  if (Date.now() - t0 > 60000) throw new Error(`page did not expose __arcseq within 60 s\n${problems.join("\n")}`);
  await new Promise((done) => setTimeout(done, 100));
}
const ready = Date.now() - t0;
await send("Performance.enable");

const qualityMode = value('--quality', null);
if (qualityMode) {
  await evaluate(`__arcseq.quality(${JSON.stringify(qualityMode)})`);
  if (qualityMode === 'auto') {
    const deadline = Date.now()+10000;
    while (!(await evaluate('__arcseq.quality().sampled'))) {
      if (Date.now()>deadline) throw Error('Auto quality sample did not complete');
      await new Promise(done=>setTimeout(done,100));
    }
  }
}
const pre = value("--eval", "");
// --frames：采样帧数（默认 240）；软件 GL 下很重的场景（剖视）用 40 帧，免得一次 CDP 调用超过 90 s
const FRAMES = Number(value("--frames", 240));
const showId = value("--show", null);
const hold = Number(value("--hold", 3));
const origin = value("--origin", "park");
const showLimit = Number(value("--show-limit", 120));
// 演出：在计时窗外准备指定起点，页面自己的 requestAnimationFrame 循环推进；走完后再 hold 秒
const SHOW = `(async () => {
  const A = window.__arcseq;
  ${pre}
  A.view(30, ${JSON.stringify(mode)});
  let frames = 0;
  let counting = true;
  const count = () => { frames++; if (counting) requestAnimationFrame(count); };
  requestAnimationFrame(count);
  const since = A.frames().count;
  const t0 = performance.now();
  const ended = await Promise.race([A.show(${JSON.stringify(showId)}), new Promise((done) => setTimeout(() => done("timeout"), ${showLimit * 1000}))]);
  if (ended === false) throw new Error("show ${showId} could not start");
  if (ended === "timeout") { counting = false; throw new Error("show ${showId} did not finish within ${showLimit} s (page frames " + frames + ")"); }
  const showMs = performance.now() - t0;
  const settled = A.frames().count;
  await new Promise((done) => setTimeout(done, ${hold * 1000}));
  counting = false;
  const f = A.frames(since);
  return { holdFrames: A.frames().count - settled, frames, showMs, drawMedian: f.median, drawP95: f.p95, drawMax: f.max, gapMedian: (performance.now() - t0) / frames, gapP95: 0 };
})()`;
const RUN = showId ? SHOW : `(async () => {
  const A = window.__arcseq;
  A.view(0, ${JSON.stringify(mode)});
  const times = [];
  const ms = [];
  await new Promise((done) => {
    let i = 0;
    const tick = (now) => {
      times.push(now);
      const t0 = performance.now();
      A.view(i * 1.1);
      ms.push(performance.now() - t0);
      if (++i < ${FRAMES}) requestAnimationFrame(tick);
      else done();
    };
    requestAnimationFrame(tick);
  });
  const sorted = (l) => l.slice().sort((a, b) => a - b);
  const gaps = times.slice(1).map((t, i) => t - times[i]);
  return { frames: ${FRAMES}, drawMedian: sorted(ms)[${FRAMES} >> 1], drawP95: sorted(ms)[Math.floor(${FRAMES} * 0.95)], gapMedian: sorted(gaps)[(${FRAMES} - 1) >> 1], gapP95: sorted(gaps)[Math.floor((${FRAMES} - 1) * 0.95)] };
})()`;
const metrics = async () => Object.fromEntries((await send("Performance.getMetrics")).result.metrics.map((m) => [m.name, m.value]));
const runs = [];
// 转台测量的前置（如打开剖视、加载内部模块）放在计时窗外
if (pre && !showId) await evaluate(`(async () => { ${pre} })()`, 240000);
for (let r = 0; r < Number(value("--runs", showId ? 1 : 3)); r++) {
  // 起点准备在计时窗外；不会让悬停 / 前飞的前置演出污染当前动作的脚本时间。
  if (showId) await evaluate(`__arcseq.origin(${JSON.stringify(origin)})`);
  const before = await metrics();
  const result = await evaluate(RUN, showId ? (showLimit + hold + 30) * 1000 : 90000);
  const after = await metrics();
  const per = (key) => ((after[key] - before[key]) * 1000) / result.frames;
  runs.push({ ...result, task: per("TaskDuration"), script: per("ScriptDuration") });
}
const med = (key) => runs.map((r) => r[key]).sort((a, b) => a - b)[runs.length >> 1];
if (showId)
  console.log(
    `perf show "${showId}" from ${origin} ${mode} at ${width} px, DPR ${scale}, ${throttle}× CPU (whole show + ${hold} s hold, ${runs.length} run(s)): ${med("frames")} frames · main-thread task ${med("task").toFixed(2)} ms · script ${med("script").toFixed(2)} ms per frame · page advance+draw median ${med("drawMedian").toFixed(2)} ms (p95 ${med("drawP95").toFixed(2)}, max ${med("drawMax").toFixed(1)}) · show wall ${(med("showMs") / 1000).toFixed(1)} s · mean frame ${med("gapMedian").toFixed(1)} ms · page frames drawn during hold ${med("holdFrames")}${argv.includes("--reduced") ? " (reduced motion)" : ""}`,
  );
else console.log(
  `perf ${mode} at ${width} px, DPR ${scale}, ${throttle}× CPU (median of ${runs.length} × ${FRAMES} frames at 1.1°): main-thread task ${med("task").toFixed(2)} ms · script ${med("script").toFixed(2)} ms · draw() ${med("drawMedian").toFixed(2)} ms (p95 ${med("drawP95").toFixed(2)}) · frame interval ${med("gapMedian").toFixed(1)} ms (p95 ${med("gapP95").toFixed(1)}) · script reference 5 ms → ${med("script") <= 5 ? "within" : "OVER"} (software main-thread recorded only) · page ready ${ready} ms`,
);
console.log('quality: '+JSON.stringify(await evaluate('__arcseq.quality()')));
if (problems.length) throw Error(problems.join('\n'));
socket.onclose = null;
socket.close();
cleanup();
process.exit(0);
