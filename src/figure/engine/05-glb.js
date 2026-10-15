  // ———————————————— GLB → 零件（浏览器端，FIG.02 复刻样板起） ————————————————
  // 常驻模型与按需模块都以 base64 的 GLB 进来（单文件页面从本地打开也能用），在这里解成与 build.mjs 相同的零件格式。
  // 坐标换算同 engine/glb.mjs：glTF (x, y, z) → 引擎 (x, −z, y)；节点 extras 并进零件；材质名即材质表键；COLOR_0.r 为 AO。
  // edges：{ 零件名: base64 Float32 }，每 12 个数一条硬边（两端点 + 两侧面法线，见 blender/kit/finish.py）。
  const b64 = (s) => {
    const bin = atob(s);
    const out = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
    return out;
  };
  function parseGlb(bytes, edges = {}) {
    const dv = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    let at = 12;
    let json = null;
    let bin = 0;
    while (at < bytes.length) {
      const len = dv.getUint32(at, true);
      const type = dv.getUint32(at + 4, true);
      if (type === 0x4e4f534a) json = JSON.parse(new TextDecoder().decode(bytes.subarray(at + 8, at + 8 + len)));
      else if (type === 0x004e4942) bin = at + 8;
      at += 8 + len;
    }
    const SIZE = { SCALAR: 1, VEC2: 2, VEC3: 3, VEC4: 4 };
    const READ = { 5126: [4, (o) => dv.getFloat32(o, true)], 5125: [4, (o) => dv.getUint32(o, true)], 5123: [2, (o) => dv.getUint16(o, true)], 5121: [1, (o) => dv.getUint8(o)] };
    const NORM = { 5123: 65535, 5121: 255 };
    const accessor = (i) => {
      const a = json.accessors[i];
      const view = json.bufferViews[a.bufferView];
      const n = SIZE[a.type];
      const [bytesPer, read] = READ[a.componentType];
      const stride = view.byteStride ?? n * bytesPer;
      const base = bin + (view.byteOffset ?? 0) + (a.byteOffset ?? 0);
      const out = new Float32Array(a.count * n);
      const norm = a.normalized ? NORM[a.componentType] : 1;
      for (let k = 0; k < a.count; k++) for (let c = 0; c < n; c++) out[k * n + c] = read(base + k * stride + c * bytesPer) / norm;
      return { data: out, n };
    };
    const parts = [];
    const visit = (index) => {
      const node = json.nodes[index];
      if (node.mesh !== undefined) {
        const mesh = json.meshes[node.mesh];
        const t = node.translation ?? [0, 0, 0];
        mesh.primitives.forEach((prim, pi) => {
          const P = accessor(prim.attributes.POSITION).data;
          const N = prim.attributes.NORMAL !== undefined ? accessor(prim.attributes.NORMAL).data : null;
          const UV = prim.attributes.TEXCOORD_0 !== undefined ? accessor(prim.attributes.TEXCOORD_0).data : null;
          const C = prim.attributes.COLOR_0 !== undefined ? accessor(prim.attributes.COLOR_0) : null;
          const count = P.length / 3;
          const I = prim.indices !== undefined ? accessor(prim.indices).data : Float32Array.from({ length: count }, (_, i) => i);
          const v = new Float32Array(count * 3);
          const nn = N ? new Float32Array(count * 3) : null;
          for (let k = 0; k < count; k++) {
            // 母版对象都是单位变换（世界坐标直接建），只加平移
            v[k * 3] = P[k * 3] + t[0];
            v[k * 3 + 1] = -(P[k * 3 + 2] + t[2]);
            v[k * 3 + 2] = P[k * 3 + 1] + t[1];
            if (nn) {
              nn[k * 3] = N[k * 3];
              nn[k * 3 + 1] = -N[k * 3 + 2];
              nn[k * 3 + 2] = N[k * 3 + 1];
            }
          }
          const f = new Uint32Array((I.length / 3) * 4);
          for (let q = 0, o = 0; q < I.length; q += 3, o += 4) f.set([3, I[q], I[q + 1], I[q + 2]], o);
          const material = prim.material !== undefined ? json.materials[prim.material].name : undefined;
          const name = mesh.primitives.length > 1 ? `${node.name}#${pi}` : node.name;
          const part = { name, kind: "mesh", ...(material ? { material } : {}), ...(node.extras ?? {}), v, f };
          if (nn) part.n = nn;
          if (UV) part.uv = UV;
          if (C) {
            part.ao = new Float32Array(count);
            for (let k = 0; k < count; k++) part.ao[k] = C.data[k * C.n];
          }
          if (edges[node.name]) {
            const e = b64(edges[node.name]);
            part.edges = new Float32Array(e.buffer, e.byteOffset, e.byteLength / 4);
          }
          parts.push(part);
        });
      }
      for (const c of node.children ?? []) visit(c);
    };
    for (const root of json.scenes[json.scene ?? 0].nodes) visit(root);
    return parts;
  }
  if (DATA.mesh) DATA.parts = [...DATA.parts, ...parseGlb(b64(DATA.mesh.glb), DATA.mesh.edges)];
