// GLB → 页面零件（Node 端，无依赖）。Blender 导出的 glTF 是 y 向上（Blender (x, y, z) → glTF (x, z, −y)），这里换回引擎坐标：
// 米，x 向前、y 向左、z 向上。每个带网格的节点一个零件（多个图元时名字加 #序号）；节点的自定义属性（Blender 的 custom properties，
// 导出时 export_extras）原样并进零件：joint、system、material、skin、smooth、glow、lines、shadow……（见 docs/BLENDER.md「命名即接口」）。
// 顶点：POSITION、NORMAL（Blender 里定好的平滑 / 锐边）、TEXCOORD_0（细节贴图）、COLOR_0 的 r（AO，烘焙在顶点色里）。
import { readFileSync } from "node:fs";

const SIZE = { SCALAR: 1, VEC2: 2, VEC3: 3, VEC4: 4, MAT4: 16 };
const READ = { 5126: ["getFloat32", 4], 5125: ["getUint32", 4], 5123: ["getUint16", 2], 5121: ["getUint8", 1], 5122: ["getInt16", 2], 5120: ["getInt8", 1] };
const NORM = { 5123: 65535, 5121: 255, 5122: 32767, 5120: 127 };

function mat4Mul(a, b) {
  const o = new Array(16).fill(0);
  for (let c = 0; c < 4; c++) for (let r = 0; r < 4; r++) for (let k = 0; k < 4; k++) o[c * 4 + r] += a[k * 4 + r] * b[c * 4 + k];
  return o;
}
function trs(node) {
  if (node.matrix) return node.matrix;
  const [tx, ty, tz] = node.translation ?? [0, 0, 0];
  const [x, y, z, w] = node.rotation ?? [0, 0, 0, 1];
  const [sx, sy, sz] = node.scale ?? [1, 1, 1];
  return [
    (1 - 2 * (y * y + z * z)) * sx, 2 * (x * y + z * w) * sx, 2 * (x * z - y * w) * sx, 0,
    2 * (x * y - z * w) * sy, (1 - 2 * (x * x + z * z)) * sy, 2 * (y * z + x * w) * sy, 0,
    2 * (x * z + y * w) * sz, 2 * (y * z - x * w) * sz, (1 - 2 * (x * x + y * y)) * sz, 0,
    tx, ty, tz, 1,
  ];
}

export function readGlb(file) {
  const buf = readFileSync(file);
  const dv = new DataView(buf.buffer, buf.byteOffset, buf.byteLength);
  if (dv.getUint32(0, true) !== 0x46546c67) throw new Error(`${file}: not a GLB`);
  let at = 12;
  let json = null;
  let bin = null;
  while (at < buf.length) {
    const len = dv.getUint32(at, true);
    const type = dv.getUint32(at + 4, true);
    if (type === 0x4e4f534a) json = JSON.parse(buf.subarray(at + 8, at + 8 + len).toString("utf8"));
    else if (type === 0x004e4942) bin = { offset: at + 8, length: len };
    at += 8 + len;
  }
  const accessor = (i) => {
    const a = json.accessors[i];
    const view = json.bufferViews[a.bufferView];
    const n = SIZE[a.type];
    const [fn, bytes] = READ[a.componentType];
    const stride = view.byteStride ?? n * bytes;
    const base = bin.offset + (view.byteOffset ?? 0) + (a.byteOffset ?? 0);
    const out = new Float64Array(a.count * n);
    const norm = a.normalized ? NORM[a.componentType] : 1;
    for (let k = 0; k < a.count; k++) for (let c = 0; c < n; c++) out[k * n + c] = dv[fn](base + k * stride + c * bytes, true) / norm;
    return { data: out, n };
  };
  return { json, accessor };
}

/** 读 GLB 成零件表。round：坐标保留位数（默认 0.1 mm）。 */
export function glbParts(file, { round = 1e4 } = {}) {
  const { json, accessor } = readGlb(file);
  const parts = [];
  const r = (v) => Math.round(v * round) / round;
  const visit = (index, parent) => {
    const node = json.nodes[index];
    const world = mat4Mul(parent, trs(node));
    if (node.mesh !== undefined) {
      const mesh = json.meshes[node.mesh];
      mesh.primitives.forEach((prim, pi) => {
        if ((prim.mode ?? 4) !== 4) return;
        const P = accessor(prim.attributes.POSITION).data;
        const N = prim.attributes.NORMAL !== undefined ? accessor(prim.attributes.NORMAL).data : null;
        const UV = prim.attributes.TEXCOORD_0 !== undefined ? accessor(prim.attributes.TEXCOORD_0).data : null;
        const C = prim.attributes.COLOR_0 !== undefined ? accessor(prim.attributes.COLOR_0) : null;
        const I = prim.indices !== undefined ? accessor(prim.indices).data : Float64Array.from({ length: P.length / 3 }, (_, i) => i);
        const count = P.length / 3;
        const v = new Array(count * 3);
        const nn = N ? new Array(count * 3) : null;
        const m = world;
        for (let k = 0; k < count; k++) {
          const [x, y, z] = [P[k * 3], P[k * 3 + 1], P[k * 3 + 2]];
          const gx = m[0] * x + m[4] * y + m[8] * z + m[12];
          const gy = m[1] * x + m[5] * y + m[9] * z + m[13];
          const gz = m[2] * x + m[6] * y + m[10] * z + m[14];
          // glTF (x, y, z) → 引擎 (x, −z, y)
          v[k * 3] = r(gx);
          v[k * 3 + 1] = r(-gz);
          v[k * 3 + 2] = r(gy);
          if (N) {
            // 节点矩阵只含旋转与均匀缩放（导出时已应用缩放），法线直接用上 3×3 再归一
            const [a, b, c] = [N[k * 3], N[k * 3 + 1], N[k * 3 + 2]];
            const nx = m[0] * a + m[4] * b + m[8] * c;
            const ny = m[1] * a + m[5] * b + m[9] * c;
            const nz = m[2] * a + m[6] * b + m[10] * c;
            const l = Math.hypot(nx, ny, nz) || 1;
            nn[k * 3] = Math.round((nx / l) * 1e4) / 1e4;
            nn[k * 3 + 1] = Math.round((-nz / l) * 1e4) / 1e4;
            nn[k * 3 + 2] = Math.round((ny / l) * 1e4) / 1e4;
          }
        }
        const f = [];
        for (let t = 0; t < I.length; t += 3) f.push(3, I[t], I[t + 1], I[t + 2]);
        // 材质：glTF 材质名就是网页材质表的键（hull / belly / carbon / glass …）；自定义属性里写了 material 的优先
        const matName = prim.material !== undefined ? json.materials[prim.material].name : undefined;
        const part = { name: mesh.primitives.length > 1 ? `${node.name}#${pi}` : node.name, kind: "mesh", ...(matName ? { material: matName } : {}), ...(node.extras ?? {}), v, f };
        if (nn) part.n = nn;
        if (UV) part.uv = Array.from(UV, (x) => Math.round(x * 1e4) / 1e4);
        if (C) part.ao = Array.from({ length: count }, (_, k) => Math.round(C.data[k * C.n] * 1000) / 1000);
        parts.push(part);
      });
    }
    for (const c of node.children ?? []) visit(c, world);
  };
  const identity = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1];
  for (const root of json.scenes[json.scene ?? 0].nodes) visit(root, identity);
  return parts;
}
