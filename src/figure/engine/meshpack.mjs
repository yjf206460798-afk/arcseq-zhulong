// 网格打包（Node 端，引擎通用）：零件表 → 一段量化二进制（base64）+ 一段 JSON 头，浏览器端 05-glb.js 的 unpackMesh 解回零件。
// 比直接塞 GLB 小约 2.5 倍：每个零件按自己的包围盒把坐标量化成 uint16（7.6 m 长的零件精度约 0.12 mm）、法线 int8、
// uv uint16（按 uv 包围盒）、AO uint8、索引 uint16（顶点 < 65536 时）；母版硬边（两端点 + 两侧面法线）同样量化：端点 uint16、法线 int8。
// 每段数组按 4 字节对齐。头里每个零件：{ name, props, n 顶点数, t 三角形数, e 硬边数, lo, ext, uvLo, uvExt, has }。
const align = (n) => (n + 3) & ~3;

export function packMesh(parts, edgesOf = () => null) {
  const head = [];
  const chunks = [];
  let size = 0;
  const push = (typed) => {
    const bytes = new Uint8Array(typed.buffer, typed.byteOffset, typed.byteLength);
    chunks.push(bytes);
    const pad = align(bytes.length) - bytes.length;
    if (pad) chunks.push(new Uint8Array(pad));
    size += align(bytes.length);
  };
  for (const part of parts) {
    const { name, kind, v, f, n: nrm, uv, ao, ...props } = part;
    const count = v.length / 3;
    const lo = [Infinity, Infinity, Infinity];
    const hi = [-Infinity, -Infinity, -Infinity];
    for (let i = 0; i < v.length; i++) {
      lo[i % 3] = Math.min(lo[i % 3], v[i]);
      hi[i % 3] = Math.max(hi[i % 3], v[i]);
    }
    // 多材质对象导出成几个图元（名#0、#1…）：硬边只挂在第一个上，否则线画几遍
    const E = /#[1-9]\d*$/.test(name) ? null : edgesOf(name.split("#")[0]);
    if (E) for (let i = 0; i + 11 < E.length; i += 12) for (const o of [0, 3]) for (let c = 0; c < 3; c++) {
      lo[c] = Math.min(lo[c], E[i + o + c]);
      hi[c] = Math.max(hi[c], E[i + o + c]);
    }
    const ext = hi.map((h, c) => Math.max(h - lo[c], 1e-6));
    const q = (x, c) => Math.round(((x - lo[c]) / ext[c]) * 65535);
    const P = new Uint16Array(count * 3);
    for (let i = 0; i < v.length; i++) P[i] = q(v[i], i % 3);
    push(P);
    let has = "p";
    if (nrm) {
      const N = new Int8Array(count * 3);
      for (let i = 0; i < nrm.length; i++) N[i] = Math.round(Math.max(-1, Math.min(1, nrm[i])) * 127);
      push(N);
      has += "n";
    }
    let uvLo = null;
    let uvExt = null;
    if (uv) {
      uvLo = [Infinity, Infinity];
      const uvHi = [-Infinity, -Infinity];
      for (let i = 0; i < uv.length; i++) {
        uvLo[i % 2] = Math.min(uvLo[i % 2], uv[i]);
        uvHi[i % 2] = Math.max(uvHi[i % 2], uv[i]);
      }
      uvExt = uvHi.map((h, c) => Math.max(h - uvLo[c], 1e-6));
      const U = new Uint16Array(count * 2);
      for (let i = 0; i < uv.length; i++) U[i] = Math.round(((uv[i] - uvLo[i % 2]) / uvExt[i % 2]) * 65535);
      push(U);
      has += "u";
    }
    if (ao) {
      const A = new Uint8Array(count);
      for (let i = 0; i < count; i++) A[i] = Math.round(Math.max(0, Math.min(1, ao[i])) * 255);
      push(A);
      has += "a";
    }
    const idx = [];
    for (let at = 0; at < f.length; at += f[at] + 1) for (let k = 2; k < f[at]; k++) idx.push(f[at + 1], f[at + k], f[at + k + 1]);
    push(count < 65536 ? Uint16Array.from(idx) : Uint32Array.from(idx));
    let e = 0;
    if (E) {
      e = Math.floor(E.length / 12);
      const EP = new Uint16Array(e * 6);
      const EN = new Int8Array(e * 6);
      for (let k = 0; k < e; k++) {
        for (let j = 0; j < 6; j++) EP[k * 6 + j] = q(E[k * 12 + j], j % 3);
        for (let j = 0; j < 6; j++) EN[k * 6 + j] = Math.round(Math.max(-1, Math.min(1, E[k * 12 + 6 + j])) * 127);
      }
      push(EP);
      push(EN);
      has += "e";
    }
    const r6 = (x) => Math.round(x * 1e6) / 1e6;
    head.push({ name, props: { kind, ...props }, n: count, t: idx.length / 3, e, lo: lo.map(r6), ext: ext.map(r6), ...(uvLo ? { uvLo: uvLo.map(r6), uvExt: uvExt.map(r6) } : {}), has });
  }
  const bin = new Uint8Array(size);
  let at = 0;
  for (const c of chunks) {
    bin.set(c, at);
    at += c.length;
  }
  return { head, bin: Buffer.from(bin).toString("base64") };
}
