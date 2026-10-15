"""头盔：Tripo Smart Mesh 修正版（refs/ai_draft/X1_头盔闭眼修正_smartmesh.glb，作者 2026-10-15 定为头盔底稿；护颌保留）。

底稿已有眉骨、窄面罩带、烟琥珀面罩、护颌、颈环，四面块面干净，所以这里**不改壳形**，只做四件事：
1. 对位：底稿面朝 −Y → 转到 x 前；等比缩放使“盔顶 → 面罩带中线”= 盔顶 TOP → 眼高 EYE（设定图标定：盔顶 1.80，
   身高 1.74 + 鞋底 0.03 的眼高 ≈ 1.652）；横向居中；前后让颈环圆心落在服装领口圆心上。
2. 拆件（零件按连通块 / 平滑区认，不按编号认，换付费版重生成也找得到）：
   - 面罩带 = 前方、法线朝前的最大一块平滑区（相邻面夹角 < 12° 连成片）→ 暗琥珀遮光面罩 `xz.helmet.sunvisor`（单独可动件：
     静止形 = 收起（绕盔心横轴上转 STOW_DEG、略收进壳里），形态键 `down` = 落下，即底稿位置），同一张面内移 2 mm 复制一份透明
     面罩 `xz.helmet.visor`；壳上挖出面罩窗，窗洞往里接一圈暗色窗框 `xz.helmet.liner`，盔内衬在窗后挖开，睁眼时看得见脸。
   - 颈环 = 底部最大一块 → `xz.helmet.neckring`（镀铬），水平方向放大到套住服装领口（RING_CLEAR）。
   - 盔顶天线 = 顶部的小块 → `xz.helmet.antenna`，保持细杆，不加粗。
3. 保法线：所有改拓扑的操作（拆件、挖窗）之前把每角法线存进属性，之后写回（draft.keep_normals / restore_normals）；
   颈环的非等比放大按逆转置矩阵变换法线。
4. 脸（身体底稿的 face 件）按眼高平移到面罩带中线后方。
"""
import math

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

import draft
import geo

TOP = 1.80  # 盔顶（不含天线）
EYE = 1.652  # 眼高
STOW_DEG = 36.0  # 遮光面罩收起：绕盔心横轴上转的角度
STOW_SHRINK = 0.93  # 收起时往里收（藏进壳与内衬之间）
RING_CLEAR = 0.004  # 颈环内表面离领口外表面
NOSE_CLEAR = 0.022  # 鼻尖离透明面罩内表面
CLEAR_IN = 0.002  # 透明面罩在遮光面罩里面 2 mm
VISOR_GROW_DEG = 30.0  # 面罩带往外长时跨过的相邻面夹角上限（面罩与面框等交界的折棱 > 45°）
DEEP = 0.12  # 面罩窗后这么深以内、从窗口看得见的壳内侧都挖掉


def load(path):
    objs = draft.import_glb(path)
    if len(objs) != 1:
        raise RuntimeError(f"头盔底稿应是一个网格，实际 {len(objs)} 个")
    o = objs[0]
    draft.transform_all([o], Matrix.Rotation(math.pi / 2, 4, "Z"))  # 面朝 −Y → +X
    return o


def components(bm):
    """按共享顶点（GLB 顶点按位置合并过）分连通块：返回 [面列表]，大的在前。"""
    seen = set()
    out = []
    for f in bm.faces:
        if f in seen:
            continue
        st, cur = [f], []
        seen.add(f)
        while st:
            g = st.pop()
            cur.append(g)
            for v in g.verts:
                for h in v.link_faces:
                    if h not in seen:
                        seen.add(h)
                        st.append(h)
        out.append(cur)
    return sorted(out, key=len, reverse=True)


def smooth_regions(faces, angle=12.0):
    """相邻面夹角 < angle 连成片：返回 [面列表]。"""
    thr = math.radians(angle)
    pool = set(faces)
    seen = set()
    out = []
    for f in faces:
        if f in seen:
            continue
        st, cur = [f], []
        seen.add(f)
        while st:
            g = st.pop()
            cur.append(g)
            for e in g.edges:
                for h in e.link_faces:
                    if h in pool and h not in seen and h.normal.angle(g.normal, 0.0) < thr:
                        seen.add(h)
                        st.append(h)
        out.append(cur)
    return out


def area(fs):
    return sum(f.calc_area() for f in fs)


def centre(fs):
    a = area(fs)
    return sum((f.calc_center_median() * f.calc_area() for f in fs), Vector()) / a


def find_parts(bm):
    """返回 dict：shell（主壳那一块的面）、visor（面罩带的面）、ring、antenna，以及其余小块 small。"""
    comps = components(bm)
    shell = comps[0]
    zs = [v.co.z for v in bm.verts]
    z0, z1 = min(zs), max(zs)
    H = z1 - z0
    ring = max((c for c in comps[1:] if centre(c).z < z0 + 0.25 * H), key=area)
    antenna = max((c for c in comps if max(v.co.z for f in c for v in f.verts) > z1 - 1e-6), key=len)
    if antenna is shell:
        raise RuntimeError("天线和主壳连在一起了（重生成后拓扑变了？）")
    visor = visor_band(shell)
    small = [c for c in comps if c is not shell and c is not ring and c is not antenna]
    return {"shell": shell, "visor": visor, "ring": ring, "antenna": antenna, "small": small}


def visor_band(shell, seed_angle=12.0, grow_angle=VISOR_GROW_DEG):
    """面罩带（作者 2026-10-15 指出：只取正中平的一段是错的，两侧向后绕的部分要算进来）：
    种子 = 正前方、法线朝前的最大一块平滑区（相邻面 < 12°）里最靠前的面——就是面罩带正中；从它往外长，跨过相邻面
    夹角 < grow_angle 的边，碰到面罩与面框、眉骨、护颌交界的折棱（底稿里这些交界都 > 45°）就停。不再要求平均法线朝前，
    所以面罩带完整包到两侧，直到面框为止。"""
    regs = smooth_regions(shell, seed_angle)
    fwd = [r for r in regs if centre(r).x > 0 and (sum((f.normal * f.calc_area() for f in r), Vector()) / area(r)).x > 0.8]
    seed = max(max(fwd, key=area), key=lambda f: f.calc_center_median().x)
    pool = set(shell)
    thr = math.radians(grow_angle)
    seen = {seed}
    st = [seed]
    while st:
        g = st.pop()
        for e in g.edges:
            for h in e.link_faces:
                if h in pool and h not in seen and h.normal.angle(g.normal, 0.0) < thr:
                    seen.add(h)
                    st.append(h)
    return list(seen)


def split_object(src, groups, props):
    """src 按面分组拆成几件（各自保住角属性 → 写回法线）。groups：{名字: (面号集合, 材质)}；剩下的面留在 src。"""
    out = {}
    for name, (ids, mat) in groups.items():
        o = draft.extract_faces(src, ids, name)
        o.data.materials.clear()
        o.data.materials.append(geo.material(mat))
        for k, v in props.items():
            o[k] = v
        out[name] = o
    dead = set().union(*[ids for ids, _ in groups.values()])
    bm = bmesh.new()
    bm.from_mesh(src.data)
    bm.faces.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.index in dead], context="FACES")
    bm.to_mesh(src.data)
    bm.free()
    draft.restore_normals(src)
    return out


class VisorFit:
    """面罩面的干净重做：底稿面罩带的边是锯齿、下沿两道 V 形小缺口，所以不直接用它。面罩带从正前方一直绕到两侧面框，
    前视的 x(y, z) 在两侧太陡，改用竖直轴的柱坐标：轴过盔心 (xc, 0)；u = θ·R0（θ = atan2(y, x − xc)，R0 = 面罩平均半径，
    u 是米制弧长，和 z 同单位），r = 到轴的水平距离。轮廓 = 外沿点在 (u, z) 里的凸包；面形 r(u, z) 用多项式（u 到 6 次、
    z 到 2 次）最小二乘拟合底稿面罩的顶点。"""

    def __init__(self, V, boundary, xc):
        from suit import hull2d

        self.xc = xc
        self.R0 = float(np.hypot(V[:, 0] - xc, V[:, 1]).mean())
        u, z, _ = self.cyl(boundary)
        self.hull = hull2d(np.stack([u, z], 1))
        u, z, r = self.cyl(V)
        self.cu, self.cz = u.mean(), z.mean()
        self.terms = [(i, j) for i in range(7) for j in range(3)]
        A = self._A(u, z)
        self.c = np.linalg.lstsq(A, r, rcond=None)[0]
        self.residual = float(np.abs(A @ self.c - r).max())

    def cyl(self, P):
        P = np.atleast_2d(np.asarray(P, float))
        dx, dy = P[:, 0] - self.xc, P[:, 1]
        return np.arctan2(dy, dx) * self.R0, P[:, 2], np.hypot(dx, dy)

    def _A(self, u, z):
        u, z = (np.asarray(u) - self.cu) / 0.1, (np.asarray(z) - self.cz) / 0.1
        return np.stack([u ** i * z ** j for i, j in self.terms], -1)

    def r(self, u, z):
        return self._A(u, z) @ self.c

    def _p(self, u, z):
        r = self.r(u, z)
        th = u / self.R0
        return np.stack([self.xc + r * np.cos(th), r * np.sin(th), z], 1)

    def point(self, u, z, inset=0.0):
        """柱面上 (u, z) 处的点；inset：沿面法线往里（朝盔轴）移。"""
        u, z = np.atleast_1d(u).astype(float), np.atleast_1d(z).astype(float)
        P = self._p(u, z)
        if inset:
            e = 1e-4
            N = np.cross(self._p(u + e, z) - P, self._p(u, z + e) - P)
            N /= np.linalg.norm(N, axis=1, keepdims=True)
            out = np.sign(((P - np.array([self.xc, 0, P[0, 2]])) * N * np.array([1, 1, 0])).sum(1, keepdims=True))
            P = P - N * out * inset
        return P

    def x_front(self, z):
        """正前方（u = 0）的面罩面 x。"""
        return float(self.point(0.0, z)[0, 0])

    def span(self, z):
        """凸包在高度 z 处的左右边界 u。"""
        H = self.hull
        us = []
        for k in range(len(H)):
            (u0, z0), (u1, z1) = H[k], H[(k + 1) % len(H)]
            if (z0 - z) * (z1 - z) <= 0 and z0 != z1:
                us.append(u0 + (u1 - u0) * (z - z0) / (z1 - z0))
        return min(us), max(us)

    def sheet(self, nu=72, nv=10, inset=0.0):
        """网格面：nv+1 行（z 从凸包下沿到上沿，行内 u 在凸包左右边界间等分）。返回 (顶点, 面, 外沿环的顶点号)。"""
        z0, z1 = self.hull[:, 1].min(), self.hull[:, 1].max()
        U, Z = [], []
        for j in range(nv + 1):
            z = z0 + (z1 - z0) * (0.002 + 0.996 * j / nv)
            ua, ub = self.span(z)
            for i in range(nu + 1):
                U.append(ua + (ub - ua) * i / nu)
                Z.append(z)
        V = self.point(np.array(U), np.array(Z), inset)
        W = nu + 1
        F = [(j * W + i, j * W + i + 1, (j + 1) * W + i + 1, (j + 1) * W + i) for j in range(nv) for i in range(nu)]
        ring = list(range(0, W)) + [j * W + nu for j in range(1, nv + 1)] + list(range(nv * W + nu - 1, nv * W - 1, -1)) + \
            [j * W for j in range(nv - 1, 0, -1)]
        return V, F, ring


def inside_poly(q, poly):
    """q (y, z) 在多边形 poly [(y, z)] 内（射线法）。"""
    y, z = q
    n = len(poly)
    ins = False
    for i in range(n):
        y0, z0 = poly[i]
        y1, z1 = poly[(i + 1) % n]
        if (z0 > z) != (z1 > z) and y < (y1 - y0) * (z - z0) / (z1 - z0 + 1e-12) + y0:
            ins = not ins
    return ins


def grow_poly(poly, d):
    c = poly.mean(0)
    v = poly - c
    L = np.linalg.norm(v, axis=1, keepdims=True)
    return c + v * (L + d) / np.maximum(L, 1e-9)


def window(shell, fit, props, depth):
    """面罩窗（柱坐标 (u, z, r)）：凸包轮廓里、面罩面到往里 depth 之间的壳面全挖掉（内衬、底稿面罩缺口里的小尖刺）；
    往里到 DEEP 以内、从窗口看得见的壳内侧（护颊内壁）按略收的轮廓挖。窗框 = 面罩外沿朝盔轴往里拉 depth、略向窗心收
    4% 的一圈暗色筒（单独件，法线朝里）。"""
    V, F, ring = fit.sheet()
    R = [Vector(V[i]) for i in ring]
    poly = fit.hull
    big = grow_poly(poly, 0.0015)
    core = grow_poly(poly, -0.001)
    inner = poly.mean(0) + (poly - poly.mean(0)) * 0.96
    bm = bmesh.new()
    bm.from_mesh(shell.data)
    dead = []
    for f in bm.faces:
        u, z, r = fit.cyl([tuple(f.calc_center_median())])
        rf = float(fit.r(u, z)[0])
        if not r[0] < rf + 0.003:
            continue
        U, Z, _ = fit.cyl([tuple(v.co) for v in f.verts])
        if rf - depth - 0.01 < r[0] and (inside_poly((u[0], z[0]), big) or any(inside_poly(q, core) for q in zip(U, Z))):
            dead.append(f)
        elif rf - DEEP < r[0] and any(inside_poly(q, inner) for q in zip(U, Z)):
            dead.append(f)
    n_dead = len(dead)
    bmesh.ops.delete(bm, geom=dead, context="FACES")
    bm.to_mesh(shell.data)
    bm.free()
    draft.restore_normals(shell)
    cu, cz = poly.mean(0)
    bm = bmesh.new()
    a = [bm.verts.new(p) for p in R]
    b = []
    for p in R:
        u, z, r = (q[0] for q in fit.cyl([tuple(p)]))
        u2, z2, r2 = cu + (u - cu) * 0.96, cz + (z - cz) * 0.96, r - depth
        th = u2 / fit.R0
        b.append(bm.verts.new(Vector((fit.xc + r2 * math.cos(th), r2 * math.sin(th), z2))))
    for i in range(len(R)):
        j = (i + 1) % len(R)
        bm.faces.new((a[i], a[j], b[j], b[i]))
    bm.normal_update()
    mid = Vector(tuple(fit.point(cu, cz, inset=depth * 0.5)[0]))
    for f in bm.faces:  # 法线朝窗心（里面）
        if f.normal.dot(mid - f.calc_center_median()) < 0:
            f.normal_flip()
    liner = geo.obj_from_bm("xz.helmet.liner", bm, "cap", props)
    return liner, n_dead


def sunvisor_keys(o, pivot, deg=STOW_DEG, shrink=STOW_SHRINK):
    """遮光面罩：静止形 = 收起（绕 pivot 的横轴 y 上转 deg、向盔心收 shrink），形态键 down = 落下（底稿原位）。"""
    me = o.data
    V = np.array([tuple(v.co) for v in me.vertices])
    o.shape_key_add(name="Basis")
    down = o.shape_key_add(name="down")
    down.data.foreach_set("co", V.ravel())
    down.value = 0.0  # Blender 5.2 新建形态键默认值是 1
    R = Matrix.Rotation(math.radians(deg), 3, "Y")  # 绕 +y 转正角：前方的点往上走（x → z）
    R = R.transposed() if (R @ Vector((1, 0, 0))).z < 0 else R
    P = Vector(pivot)
    U = np.array([tuple(P + (R @ (Vector(v) - P)) * shrink) for v in V])
    o.data.shape_keys.key_blocks["Basis"].data.foreach_set("co", U.ravel())
    me.vertices.foreach_set("co", U.ravel())
    me.update()
    return R


def collar(torso):
    """服装领口：躯干顶端往下找第一个“整圈”的水平截面（前后都有点、y 方向够宽），返回 (圆心 (x, y), 外半径, 截面高)。
    领口是斜的（前低后高），只截顶端几厘米会只截到后半圈。"""
    T = draft.verts(torso)
    zt = T[:, 2].max()
    for z in np.arange(zt - 0.01, zt - 0.12, -0.004):
        sl = T[np.abs(T[:, 2] - z) < 0.003]
        if len(sl) < 50:
            continue
        x0, x1 = sl[:, 0].min(), sl[:, 0].max()
        c = np.array([(x0 + x1) / 2, 0.0])
        # 整圈：前半、后半都有点，且宽深比像个圈
        if (x1 - x0) > 0.14 and (sl[:, 1].max() - sl[:, 1].min()) > 0.14:
            r = float(np.percentile(np.linalg.norm(sl[:, :2] - c, axis=1), 98))
            return c, r, float(z)
    raise RuntimeError("找不到服装领口")


def neck_seal(torso, ring_bottom, props):
    """颈封：服装领口里面一圈暗色软封（领口前低后高，头盔颈环盖不住的前侧会露出领口里的空洞）。
    圆筒：领口内半径 − 2 mm，从领口截面往下 6 cm 到颈环下沿往上 1.5 cm，上端收口。"""
    T = draft.verts(torso)
    c, r_out, z = collar(torso)
    sl = T[np.abs(T[:, 2] - z) < 0.003]
    r_in = float(np.percentile(np.linalg.norm(sl[:, :2] - c, axis=1), 3)) - 0.002
    pts = [Vector((c[0], c[1], z - 0.06)), Vector((c[0], c[1], ring_bottom + 0.015))]
    o = geo.tube("xz.suit.neckseal", pts, r_in, "collar", props, sides=40, caps=True)
    for p in o.data.polygons:
        p.use_smooth = abs(p.normal.z) < 0.5
    return o


def trim_face(face, eye_z, ry=0.046, rz=0.07):
    """身体底稿的脸是一张面具，四周一圈参差、往前翻折的薄边（原来接着底稿头盔的护颊），在面罩窗两侧会露出来：
    只留前视椭圆（半宽 ry、半高 rz、中心在眼下 2.5 cm）的外切 16 边形里的部分，取最大连通块。返回剩下的面数。"""
    bm = bmesh.new()
    bm.from_mesh(face.data)
    zc = eye_z - 0.025
    # 16 个平行于 x 轴的平面围成椭圆的外切多边形，逐个切掉外侧：开口边是直的
    for k in range(16):
        a = 2 * math.pi * (k + 0.5) / 16
        p = Vector((0, ry * math.cos(a), zc + rz * math.sin(a)))
        n = Vector((0, math.cos(a) / ry, math.sin(a) / rz)).normalized()
        bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], dist=1e-6, plane_co=p, plane_no=n, clear_outer=True)
    keep = set(max(components(bm), key=len)) if bm.faces else set()
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f not in keep], context="FACES")
    bm.to_mesh(face.data)
    bm.free()
    draft.restore_normals(face)
    return len(face.data.polygons)


def comms_cap(face, eye_z, props):
    """通讯帽的面部开口：从脸的外沿一圈往外、往后拉出暗色帽兜（三圈：外沿后 0.5 mm → 外扩 1.2 cm、后退 0.8 cm →
    外扩 3.5 cm、后退 5 cm），脸像从帽兜开口里露出来；帽兜外面被头盔的窗框挡住。"""
    bm = bmesh.new()
    bm.from_mesh(face.data)
    B = np.array([tuple(v.co) for v in bm.verts if v.is_boundary])
    bm.free()
    zc = eye_z - 0.025
    ang = np.arctan2(B[:, 2] - zc, B[:, 1])
    B = B[np.argsort(ang)]
    # 沿角度重采样 64 点（外沿点不均匀）
    ang = np.sort(ang)
    tgt = np.linspace(-math.pi, math.pi, 64, endpoint=False)
    R0 = np.array([B[np.argmin(np.abs(np.angle(np.exp(1j * (ang - t)))))] for t in tgt])
    rad = np.stack([np.zeros(len(R0)), R0[:, 1], R0[:, 2] - zc], 1)
    rad /= np.linalg.norm(rad, axis=1, keepdims=True)
    back = np.array([1.0, 0, 0])
    rings = [R0 - back * 0.0005, R0 + rad * 0.012 - back * 0.008, R0 + rad * 0.035 - back * 0.05]
    bm = bmesh.new()
    vs = [[bm.verts.new(Vector(p)) for p in r] for r in rings]
    n = len(R0)
    for A, Bv in zip(vs, vs[1:]):
        for i in range(n):
            bm.faces.new((A[i], A[(i + 1) % n], Bv[(i + 1) % n], Bv[i]))
    bm.normal_update()
    for f in bm.faces:  # 法线朝前（朝外）
        if f.normal.x < 0:
            f.normal_flip()
    return geo.obj_from_bm("xz.body.cap", bm, "cap", props)


def nose_tip(face):
    V = draft.verts(face)
    c = V[np.abs(V[:, 1]) < 0.012]
    return Vector(c[np.argmax(c[:, 0])])


def build(parts, props, path=draft.DRAFT_HELMET, state="soft"):
    """parts：身体零件（要 torso、face）。返回 (头盔零件 {名字: 对象}, 日志)。state：soft 睁眼（遮光面罩收起） / closed 闭眼。"""
    log = {"source": path.split("refs/")[-1]}
    o = load(path)
    o.name = "xz.helmet.shell"
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bm.normal_update()
    P = find_parts(bm)
    shell_top = max(v.co.z for f in P["shell"] for v in f.verts)
    vz = centre(P["visor"]).z
    s = (TOP - EYE) / (shell_top - vz)
    bm.free()
    # 等比缩放 + 盔顶到 TOP；横向居中到 y = 0（底稿基本对称）
    V = draft.verts(o)
    cy = (V[:, 1].min() + V[:, 1].max()) / 2
    draft.transform_all([o], Matrix.Translation(Vector((0, -cy * s, TOP - shell_top * s))) @ Matrix.Diagonal((s, s, s, 1)))
    log["scale"] = round(s, 5)
    # 前后：颈环圆心对领口圆心（领口 = 躯干顶端 3 cm 的一圈）
    collar_c, collar_r, collar_z = collar(parts["torso"])
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bm.normal_update()
    P = find_parts(bm)
    RV = np.array([tuple(v.co) for f in P["ring"] for v in f.verts])
    ring_c = np.array([(RV[:, 0].min() + RV[:, 0].max()) / 2, (RV[:, 1].min() + RV[:, 1].max()) / 2])
    bm.free()
    dx = collar_c[0] - ring_c[0]
    draft.transform_all([o], Matrix.Translation(Vector((dx, 0, 0))))
    draft.keep_normals(o)
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bm.normal_update()
    P = find_parts(bm)
    ids = {k: {f.index for f in P[k]} for k in ("visor", "ring", "antenna")}
    bm.free()
    out = split_object(o, {"xz.helmet.sunvisor": (ids["visor"], "sunvisor"), "xz.helmet.neckring": (ids["ring"], "chrome"),
                           "xz.helmet.antenna": (ids["antenna"], "metal")}, props)
    o.data.materials.clear()
    o.data.materials.append(geo.material("helmet"))
    for k, v in props.items():
        o[k] = v
    out["xz.helmet.shell"] = o
    # 颈环：水平放大到套住领口（法线按逆转置）
    ring = out["xz.helmet.neckring"]
    RV = draft.verts(ring)
    rc = np.array([(RV[:, 0].min() + RV[:, 0].max()) / 2, (RV[:, 1].min() + RV[:, 1].max()) / 2])
    r_out = float(np.percentile(np.linalg.norm(RV[:, :2] - rc, axis=1), 99))
    k = max(1.0, (collar_r + RING_CLEAR) / r_out)
    S = Matrix.Translation(Vector((rc[0], rc[1], 0))) @ Matrix.Diagonal((k, k, 1, 1)) @ Matrix.Translation(Vector((-rc[0], -rc[1], 0)))
    ring.data.transform(S)
    at = ring.data.attributes[draft.NORMAL_ATTR]
    N = np.empty(len(ring.data.loops) * 3)
    at.data.foreach_get("vector", N)
    N = N.reshape(-1, 3) * np.array([1 / k, 1 / k, 1])
    at.data.foreach_set("vector", N.ravel())
    draft.restore_normals(ring)
    log["ring"] = {"collar_r": round(collar_r, 4), "collar_top_front": round(collar_z, 4), "ring_r_out": round(r_out, 4), "scale_xy": round(k, 3),
                   "ring_bottom": round(float(RV[:, 2].min()), 4)}
    # 面罩：底稿面罩带拟合成干净曲面（VisorFit），遮光面罩 / 透明面罩都用它重铺
    raw = out.pop("xz.helmet.sunvisor")
    me = raw.data
    bmr = bmesh.new()
    bmr.from_mesh(me)
    bnd = np.array([tuple(v.co) for v in bmr.verts if v.is_boundary])
    bmr.free()
    VS = draft.verts(raw)
    W0 = draft.verts(o)
    fit = VisorFit(VS, bnd, xc=float((W0[:, 0].min() + W0[:, 0].max()) / 2))
    log["visor_fit_residual_mm"] = round(fit.residual * 1000, 2)
    bpy.data.objects.remove(raw)
    Vs, Fs, _ = fit.sheet()
    sun = geo.obj_from_arrays("xz.helmet.sunvisor", Vs, Fs, "sunvisor", props)
    Vc, Fc, _ = fit.sheet(inset=CLEAR_IN)
    clear = geo.obj_from_arrays("xz.helmet.visor", Vc, Fc, "glass", props)
    out["xz.helmet.sunvisor"] = sun
    out["xz.helmet.visor"] = clear
    W = draft.verts(o)
    vz = Vs[:, 2]
    # 内衬在面罩后多深：从面罩面上几点往后（−x）打射线，打到的第一层就是内衬（面罩已拆走，壳上是个洞）
    tree = geo.bvh_of(o)
    hits = []
    for t in (-0.6, -0.3, 0.0, 0.3, 0.6):
        for w in (-0.3, 0.0, 0.3):
            z = vz.mean() + w * (vz.max() - vz.min()) / 2
            ua, ub = fit.span(z)
            u = (ua + ub) / 2 + t * (ub - ua) / 2
            p = Vector(tuple(fit.point(u, z)[0]))
            inward = Vector((fit.xc - p.x, -p.y, 0)).normalized()
            loc, n, _, dist = tree.ray_cast(p - inward * 0.001, inward, 0.1)
            if loc is not None:
                hits.append(dist - 0.001)
    depth = float(max(hits) + 0.004) if hits else 0.03
    liner, n_dead = window(o, fit, props, depth)
    out["xz.helmet.liner"] = liner
    log["window"] = {"depth": round(depth, 4), "shell_faces_cut": n_dead}
    # 遮光面罩：收起 / 落下
    pivot = Vector(((W[:, 0].min() + W[:, 0].max()) / 2, 0.0, float(vz.mean()) + 0.02))
    sunvisor_keys(sun, pivot)
    sun["morph"] = "down: 遮光面罩落下（闭眼）"
    if state == "closed":
        sun.data.shape_keys.key_blocks["down"].value = 1.0
    # 脸：眼高到面罩带中线（底稿脸的鼻尖 + 3.5 cm ≈ 眼高），鼻尖离透明面罩内表面 NOSE_CLEAR
    face = parts.get("face")
    if face is not None:
        nt = nose_tip(face)
        eye = nt.z + 0.035
        vc = float(vz.mean())
        xin = fit.x_front(vc - 0.035) - CLEAR_IN
        d = Vector((xin - NOSE_CLEAR - nt.x, 0, vc - eye))
        face.data.transform(Matrix.Translation(d))
        log["face_move"] = [round(x, 4) for x in d]
        log["face_trim"] = trim_face(face, vc)
        out["xz.body.cap"] = comms_cap(face, vc, props)
    out["xz.suit.neckseal"] = neck_seal(parts["torso"], float(RV[:, 2].min()), props)
    for k_, ob in out.items():
        for kk, v in props.items():
            ob[kk] = v
        ob["layer"] = "L5"
    log["parts"] = {k_: len(ob.data.polygons) for k_, ob in out.items()}
    return out, log
