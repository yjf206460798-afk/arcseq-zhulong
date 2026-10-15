// ARCSEQ 引擎（Node 端）：取景、零件打包、页面拼装。与作品无关——作品的 build.mjs 给出几何、色板与文字，这里负责变成单文件页面。
// 浏览器端引擎是同目录的 NN-*.js，按文件名顺序拼进同一个闭包（共享作用域），DATA 由作品注入。
import { readFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import * as k from "../../../.claude/skills/anatomy/kit/iso-kit.mjs";
import { dropContactFaces, weldTJunctions } from "../weld.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
export const r4 = (v) => Math.round(v * 1e4) / 1e4;
export const r3 = (v) => Math.round(v * 1e3) / 1e3;

/** 零件的所有顶点（取景、投影范围用）。 */
export function pointsOf(parts) {
  const pts = [];
  for (const p of parts) {
    if (p.v) for (let i = 0; i < p.v.length; i += 3) pts.push([p.v[i], p.v[i + 1], p.v[i + 2]]);
    else if (p.o) for (const t of [p.s0, p.s1]) pts.push(p.o.map((c, i) => c + p.a[i] * t));
  }
  return pts;
}

/**
 * 取景（FIG.01 G2 定）：机体绕转台转一圈，在画面上的平均宽度占画幅宽的 share；同时转到任何角度，机体加转台都落在画幅高度内（留边 pad）。
 * 转台半径只比机体平面外接圆大 margin。返回每米多少画幅单位 K、原点（地面转台轴心）在画幅中的位置与转台尺寸。
 * offset：模型整体平移（look-dev 只有一段时把它挪到转台中心）；rise：演出中升起的最高高度（米），算进最高点。
 */
export function fitView(points, { view, elevation, share = 0.7, pad = 8, rise = 0, offset = [0, 0, 0], margin = 0.35, minR = 2 } = {}) {
  const se = Math.sin((elevation * Math.PI) / 180);
  const ce = Math.cos((elevation * Math.PI) / 180);
  const pts = points.length ? points.map(([x, y, z]) => [x + offset[0], y + offset[1], z + offset[2]]) : [[minR, 0, 0], [-minR, 0, 0], [0, minR, 0], [0, -minR, 0], [0, 0, 0]];
  const reach = Math.max(...pts.map(([x, y]) => Math.hypot(x, y)));
  const deck = { r: Math.max(minR, Math.ceil((reach + margin) * 10) / 10), h: 0.35, baseH: 0.5 };
  deck.base = deck.r + 0.4;
  let widths = 0;
  let top = Infinity;
  const turns = 72;
  for (let i = 0; i < turns; i++) {
    const a = (i / turns) * 2 * Math.PI;
    const xs = pts.map(([x, y]) => -x * Math.sin(a) + y * Math.cos(a));
    widths += Math.max(...xs) - Math.min(...xs);
    top = Math.min(top, ...pts.map(([x, y, z]) => (x * Math.cos(a) + y * Math.sin(a)) * se - (z + rise) * ce));
  }
  top = Math.min(top, -deck.base * se);
  const bottom = deck.base * se + (deck.h + deck.baseH) * ce;
  const K = Math.min((share * view.width) / (widths / turns), (view.height - 2 * pad) / (bottom - top), (view.width - 2 * pad) / (2 * deck.base));
  return { K, origin: [view.width / 2, view.height / 2 - ((top + bottom) / 2) * K], deck, meanWidth: widths / turns };
}

/**
 * 凸包零件（FIG.01 几何母版格式 { name, kind: "hull", hull: { verts, faces }, joint, … }）→ 页面零件：
 * 补 T 形接缝、去掉同一刚体组里的接触面（跨组的标为 x，往后推着画），面环打平成 [n, i0…]。
 */
export function packHulls(list, { meta = () => ({}) } = {}) {
  const hulls = list.map((p) => ({ verts: p.hull.verts.map((q) => q.map(r4)), faces: p.hull.faces.map((f) => f.slice()) }));
  const welded = weldTJunctions(hulls);
  const { dropped, contact, cross } = dropContactFaces(hulls, list.map((p) => p.joint ?? ""));
  const parts = list.map((p, i) => ({ name: p.name, kind: "hull", system: p.system, glass: p.glass ?? false, joint: p.joint, ...meta(p), c: contact[i], x: cross[i], v: hulls[i].verts.flat(), f: hulls[i].faces.flatMap((face) => [face.length, ...face]) }));
  return { parts, welded, dropped };
}

/** three.module.min.js 只有末尾一条 export：改成全局 THREE，作为普通脚本内联，页面从本地文件打开也能运行。 */
export function threeClassic() {
  const src = readFileSync(join(HERE, "..", "vendor", "three.module.min.js"), "utf8");
  const at = src.lastIndexOf("export{");
  const list = src.slice(at + 7, src.indexOf("}", at)).split(",").map((item) => item.trim().split(/\s+as\s+/));
  const map = list.map(([local, name]) => `${name ?? local}:${local}`).join(",");
  return `(function(){"use strict";${src.slice(0, at)};window.THREE={${map}};})();`;
}

/** 浏览器端引擎：NN-*.js 按文件名顺序拼进一个闭包，注入 DATA；extra 为作品自己的脚本片段（同一闭包、在引擎之后）。 */
export function engineScript(data, extra = "") {
  const files = readdirSync(HERE).filter((f) => /^\d\d-.*\.js$/.test(f)).sort();
  const body = files.map((f) => `// ——— engine/${f} ———\n${readFileSync(join(HERE, f), "utf8")}`).join("\n");
  return `(() => {\n${body.replace("const DATA = __DATA__;", () => `const DATA = ${JSON.stringify(data)};`)}\n${extra}\n})();`;
}

/** 单文件页面：Anatomy kit 的卡片外壳 + 舞台 + 内联 three 与引擎。 */
export function pageHtml({ title, fig, plateTitle, hint, caption, css, stage, console: consoleHtml = "", script }) {
  const body = k.plateHtml({ fig, title: plateTitle, hint, readout: "机位 30°", caption, body: `<style>${css}</style>${stage}${consoleHtml}` });
  return k.pageHtml({ title, theme: "dark", body, width: 1080 }).replace("</body>", () => `<script>${threeClassic()}</script><script>${script.replace(/<\/(script)/gi, "<\\/$1")}</script></body>`);
}
