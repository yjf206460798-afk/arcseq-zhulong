"""銜燭 软态服装（X1）：独立的干净服装低模 + mhclo 式绑定 + delete group（RESOURCES「銜燭 · 服装」）。

服装壳 = MakeHuman 基础网格里自带的 `helper-tights` 组（CC0；MakeHuman 自己给紧身衣贴合用的干净四边形壳：肢体一圈圈边环、
没有胸肌腹肌、领口 / 腕口 / 脚都已是开口或封好）。做法：
1. 静止姿态把 tights 绑到平滑后的身体（bind.Binding），身体摆到设定图站姿，tights 跟着到位——这就是“作者姿态”；
2. 在作者姿态里细分一级，按 spec.py 的区域表用平面切出接缝边环（bisect：切口是直的，不锯齿）、切出气囊分块的轮廓，
   气囊 / 护膝做成独立的外层贴片；挽具、手套、靴、脐带、脊线、铭文都在作者姿态里建；
3. 全部服装件再绑到作者姿态的身体上（同一套 Binding），换姿态（坐姿）时跟着身体走；
4. delete group：身体被服装盖住的面（颈部以下、手、脚）删掉，只留头面部。
"""
import math

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

import geo
from bind import Binding
from spec import PARTS

SPEC = {p["id"]: p for p in PARTS}
D = math.radians


class Charts:
    """作者姿态（站姿）里的部位坐标：躯干绕竖直轴、四肢绕肢体轴的 (方位 az, 高度 z)。"""

    def __init__(self, body, BV):
        self.BV = BV
        self.seg = body.seg
        b = body.bone_head
        self.J = {}
        for s in "LR":
            self.J.update({f"hip.{s}": b(f"upperleg01.{s}"), f"knee.{s}": b(f"lowerleg01.{s}"), f"ankle.{s}": b(f"foot.{s}"),
                           f"shoulder.{s}": b(f"upperarm01.{s}"), f"elbow.{s}": b(f"lowerarm01.{s}"), f"wrist.{s}": b(f"wrist.{s}")})
        self.J["neck"] = b("neck01")
        self.J["head"] = b("head")
        tor = np.array([s_ == "torso" for s_ in self.seg])
        T = BV[tor]
        self.zs = np.arange(0.7, 1.62, 0.01)
        xc, wd = [], []
        for z in self.zs:
            m = (np.abs(T[:, 2] - z) < 0.01) & (np.abs(T[:, 1]) < 0.12)
            xc.append((T[m, 0].max() + T[m, 0].min()) / 2 if m.sum() > 3 else 0.0)
            m2 = np.abs(T[:, 2] - z) < 0.01
            wd.append(T[m2, 1].max() - T[m2, 1].min() if m2.sum() > 3 else 0.0)
        self.xc = np.array(xc)
        mid = np.abs(BV[:, 1]) < 0.012
        self.crotch = float(BV[mid & (BV[:, 2] > 0.6) & (BV[:, 2] < 1.0) & tor, 2].min()) if (mid & tor).any() else 0.83
        band = (self.zs > 1.0) & (self.zs < 1.25)
        self.waist = float(self.zs[band][np.argmin(np.array(wd)[band])])
        self.knee = float((self.J["knee.L"].z + self.J["knee.R"].z) / 2)
        self.neckz = float(self.J["neck"].z)
        # 设定图高度 → 本模型高度（分段线性；锚点：地、靴口、护膝中心、胯、腰带、领口、盔顶）
        self.anchors = [(0.0, 0.0), (0.25, 0.25), (0.56, self.knee + 0.045), (0.82, self.crotch), (1.12, self.waist + 0.01), (1.47, self.neckz - 0.01), (1.80, 1.80)]

    def zmap(self, zc):
        a = self.anchors
        for (x0, y0), (x1, y1) in zip(a, a[1:]):
            if zc <= x1:
                return y0 + (y1 - y0) * (zc - x0) / (x1 - x0)
        return zc

    def torso_x(self, z):
        return float(np.interp(z, self.zs, self.xc))

    def axis(self, seg):
        part, s = seg.split(".")
        a, b = {"thigh": ("hip", "knee"), "shin": ("knee", "ankle"), "uarm": ("shoulder", "elbow"), "farm": ("elbow", "wrist")}[part]
        return self.J[f"{a}.{s}"], self.J[f"{b}.{s}"], (1 if s == "L" else -1)

    def frame(self, seg, z):
        """(轴上点 C, 轴向 u, 前 f, 外侧 l)。"""
        if seg == "torso":
            return Vector((self.torso_x(z), 0, z)), Vector((0, 0, 1)), Vector((1, 0, 0)), Vector((0, 1, 0))
        A, B, sg = self.axis(seg)
        u = (B - A).normalized()
        t = (z - A.z) / (B.z - A.z)
        C = A + (B - A) * t
        f = Vector((1, 0, 0))
        f = (f - u * f.dot(u)).normalized()
        l = Vector((0, sg, 0))
        l = (l - u * l.dot(u) - f * l.dot(f)).normalized()
        return C, u, f, l

    def coords(self, seg, p):
        C, u, f, l = self.frame(seg, p.z)
        r = p - C
        return math.degrees(math.atan2(r.dot(l), r.dot(f))), p.z, (r - u * r.dot(u)).length

    def point(self, seg, az, z, r=0.1):
        C, u, f, l = self.frame(seg, z)
        d = f * math.cos(D(az)) + l * math.sin(D(az))
        return C + d * r, d, u


class Shell:
    """服装壳的 bmesh 与接缝记录。"""

    def __init__(self, V, F, body_kd, seg):
        o = geo.obj_from_arrays("xz.tmp", V, F, "suit")
        m = o.modifiers.new("sub", "SUBSURF")
        m.levels = 1
        m.render_levels = 1
        bpy.context.view_layer.objects.active = o
        bpy.ops.object.modifier_apply(modifier="sub")
        self.bm = bmesh.new()
        self.bm.from_mesh(o.data)
        bpy.data.objects.remove(o)
        self.kd = body_kd
        self.bseg = seg
        self.seams = []
        self.lay = self.bm.faces.layers.int.new("panel")

    def seg_of(self, p):
        _, i, _ = self.kd.find(p)
        return self.bseg[i]

    def faces(self, pred):
        return [f for f in self.bm.faces if pred(f.calc_center_median(), f)]

    def cut(self, co, no, pred, sid=None, level="secondary"):
        F = self.faces(pred)
        if not F:
            return []
        E = list({e for f in F for e in f.edges})
        Vs = list({v for f in F for v in f.verts})
        res = bmesh.ops.bisect_plane(self.bm, geom=F + E + Vs, dist=1e-5, plane_co=Vector(co), plane_no=Vector(no).normalized())
        cut = [e for e in res["geom_cut"] if isinstance(e, bmesh.types.BMEdge)]
        # 平面恰好压在已有边环上（tights 左右对称，前后中线本来就有一圈边）时会切出零面积的细条：并掉
        bmesh.ops.dissolve_degenerate(self.bm, dist=1e-5, edges=self.bm.edges[:])
        cut = [e for e in cut if e.is_valid]
        if sid:
            self.record(cut, sid, level)
        return cut

    def record(self, edges, sid, level):
        for e in edges:
            e.seam = True
        for chain in chains(edges):
            self.seams.append({"id": sid, "points": [list(map(float, v.co)) for v in chain], "level": level})

    def delete(self, pred):
        F = self.faces(pred)
        bmesh.ops.delete(self.bm, geom=F, context="FACES")


def chains(edges):
    """边集 → 首尾相接的顶点链。"""
    adj = {}
    for e in edges:
        a, b = e.verts
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)
    seen = set()
    out = []
    for start in list(adj):
        if start in seen:
            continue
        # 从端点（度 1）开始；闭环任取一点
        comp, stack = [], [start]
        while stack:
            v = stack.pop()
            if v in seen:
                continue
            seen.add(v)
            comp.append(v)
            stack += [w for w in adj[v] if w not in seen]
        ends = [v for v in comp if len(adj[v]) == 1]
        v0 = ends[0] if ends else comp[0]
        chain, prev, cur = [v0], None, v0
        while True:
            nxt = [w for w in adj[cur] if w is not prev and w not in chain[-2:]]
            if not nxt or (nxt[0] is v0):
                if nxt and nxt[0] is v0:
                    chain.append(v0)
                break
            prev, cur = cur, nxt[0]
            chain.append(cur)
            if len(chain) > len(comp) + 1:
                break
        out.append(chain)
    return out


# —— 区域多边形 → 切面 ——————————————————————————————————————————————
def chamfer_rect(az0, az1, z0, z1, caz, cz):
    """倒角矩形（图表坐标，逆时针）：设定图里的分块都是切角多边形（与机身的切面语言一致）。"""
    return [(az0 + caz, z0), (az1 - caz, z0), (az1, z0 + cz), (az1, z1 - cz), (az1 - caz, z1), (az0 + caz, z1), (az0, z1 - cz), (az0, z0 + cz)]


def poly_planes(ch, seg, poly, r):
    """多边形每条边 → 一张平面（含边的两个表面点与中点的径向）：内侧 = 法向的负侧。"""
    pts = [ch.point(seg, a, z, r) for a, z in poly]
    cen = sum((p for p, _, _ in pts), Vector()) / len(pts)
    planes = []
    for (A, dA, _), (B, dB, _) in zip(pts, pts[1:] + pts[:1]):
        radial = (dA + dB).normalized()
        n = (B - A).cross(radial)
        if n.length < 1e-9:
            continue
        n.normalize()
        if (cen - A).dot(n) > 0:
            n = -n
        planes.append((A, n))
    return planes


def panel(shell, ch, seg, poly, sid, segs_ok, rmax, r=0.1, cut_only=False):
    """在服装壳上切出多边形分块的轮廓（接缝），返回分块里的面。"""
    az = [a for a, _ in poly]
    zz = [z for _, z in poly]
    lo, hi = min(az) - 14, max(az) + 14
    zl, zh = min(zz) - 0.04, max(zz) + 0.04
    side = seg.split(".")[1] if "." in seg else None

    def near(c, f):
        if not (zl < c.z < zh):
            return False
        s_ = shell.seg_of(c)
        if s_.split(".")[0] not in segs_ok:
            return False
        if side and "." in s_ and s_.split(".")[1] != side:
            return False
        a, _, rr = ch.coords(seg, c)
        return lo < a < hi and rr < rmax

    planes = poly_planes(ch, seg, poly, r)
    for co, no in planes:
        shell.cut(co, no, near)

    def inside(c, f):
        return near(c, f) and all((c - co).dot(no) <= 1e-6 for co, no in planes)

    F = shell.faces(inside)
    # 轮廓 = 分块面与外面的交界边
    Fs = set(F)
    edges = [e for f in F for e in f.edges if any(g not in Fs for g in e.link_faces)]
    shell.record(list(set(edges)), sid, "secondary")
    return F


def pillow(name, faces, relief, ramp, mat, props, lip=0.0015):
    """分块面 → 外层贴片：中间鼓起 relief、离边 ramp 内渐降到 lip，四周一圈裙边垂回服装面（掠射角不露缝）。"""
    bm = bmesh.new()
    vmap = {}
    for f in faces:
        for v in f.verts:
            if v not in vmap:
                vmap[v] = bm.verts.new(v.co.copy())
    for f in faces:
        bm.faces.new([vmap[v] for v in f.verts])
    bm.normal_update()
    bnd = [v for v in bm.verts if v.is_boundary]
    B = np.array([tuple(v.co) for v in bnd])
    for v in bm.verts:
        d = np.min(np.linalg.norm(B - np.array(v.co), axis=1)) if len(B) else 1.0
        t = min(1.0, d / ramp)
        t = t * t * (3 - 2 * t)
        v.co = v.co + v.normal * (lip + (relief - lip) * t)
    # 裙边
    edges = [e for e in bm.edges if e.is_boundary]
    ext = bmesh.ops.extrude_edge_only(bm, edges=edges)
    for v in [g for g in ext["geom"] if isinstance(g, bmesh.types.BMVert)]:
        v.co = v.co - v.normal * (lip + 0.002)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return geo.obj_from_bm(name, bm, mat, props, smooth=True)


def groove(bm, depth=0.0008):
    """接缝边环往里压一点：Cycles 里读得出一道细缝。"""
    bm.normal_update()
    vs = {v for e in bm.edges if e.seam for v in e.verts}
    for v in vs:
        v.co = v.co - v.normal * depth


# —— 主流程 ——————————————————————————————————————————————————————————————
def build(mh, body, rest_V, posed_V, props):
    """返回 (服装件列表, 接缝线, 地标)。全部在作者姿态（站姿）里建。"""
    ch = Charts(body, posed_V)
    kd = KDTree(len(posed_V))
    for i, v in enumerate(posed_V):
        kd.insert(Vector(v), i)
    kd.balance()
    T, tf, _ = mh.piece("helper-tights")
    bt = Binding(rest_V, body.faces, T)
    Tp = bt.apply(posed_V)
    sh = Shell(Tp, tf, kd, body.seg)
    z = ch.zmap
    parts = []

    # 靴里的部分删掉（靴口 0.25 往下 4 cm 以下）
    boot_top = z(SPEC["suit.boot"]["z"][1])
    sh.delete(lambda c, f: c.z < boot_top - 0.04)

    def on(segs, side=None):
        def p(c, f):
            s_ = sh.seg_of(c)
            if s_.split(".")[0] not in segs:
                return False
            return side is None or ("." in s_ and s_.split(".")[1] == side)
        return p

    # —— 环缝 ——
    wz = z(1.10)
    sh.cut((0, 0, wz), (0, 0, 1), lambda c, f: on(["torso"])(c, f) and abs(c.z - wz) < 0.03, "seam.waist")
    yf = z(1.345)
    sh.cut((0, 0, yf), (0, 0.0, 1), lambda c, f: on(["torso"])(c, f) and abs(c.z - yf) < 0.03 and abs(ch.coords("torso", c)[0]) < 80, "seam.yoke.front")
    yb = z(1.42)
    sh.cut((0, 0, yb), (0, 0, 1), lambda c, f: on(["torso"])(c, f) and abs(c.z - yb) < 0.03 and abs(ch.coords("torso", c)[0]) > 105, "seam.yoke.back")
    for s in "LR":
        S_, E_, W_ = ch.J[f"shoulder.{s}"], ch.J[f"elbow.{s}"], ch.J[f"wrist.{s}"]
        u = (E_ - S_).normalized()
        pc = S_ + u * 0.035
        sh.cut(pc, u, lambda c, f, pc=pc, u=u: (c - pc).length < 0.12 and ((c - pc) - u * (c - pc).dot(u)).length < 0.08, "seam.armhole")
        u2 = (W_ - E_).normalized()
        for k, (pt, ax) in enumerate(((E_ - u * 0.03, u), (E_ + u2 * 0.04, u2))):
            sh.cut(pt, ax, lambda c, f, pt=pt, ax=ax: (c - pt).length < 0.09 and on(["uarm", "farm"], s)(c, f), "seam.elbow")
        K_, H_, A_ = ch.J[f"knee.{s}"], ch.J[f"hip.{s}"], ch.J[f"ankle.{s}"]
        ut = (K_ - H_).normalized()
        us = (A_ - K_).normalized()
        for pt, ax in ((K_ - ut * 0.075, ut), (K_ + us * 0.045, us)):
            sh.cut(pt, ax, lambda c, f, pt=pt: (c - pt).length < 0.11 and on(["thigh", "shin"], s)(c, f), "seam.knee")
    # —— 纵缝 ——
    cz = ch.crotch
    sh.cut((0, 0, 0), (0, 1, 0), lambda c, f: on(["torso"])(c, f) and cz + 0.01 < c.z < ch.neckz + 0.06 and c.x > ch.torso_x(c.z), "seam.zipper", "primary")
    for sg in (1, -1):
        a = D(95) * sg
        n = Vector((math.cos(a + math.pi / 2), math.sin(a + math.pi / 2), 0))
        sh.cut((ch.torso_x(1.1), 0, 0), n, lambda c, f, sg=sg: on(["torso"])(c, f) and wz - 0.16 < c.z < z(1.30) and abs(ch.coords("torso", c)[0] - 95 * sg) < 20, "seam.side")
    for s in "LR":
        for seg, z0, z1, azs in ((f"thigh.{s}", ch.knee + 0.08, cz - 0.015, (-90,)), (f"shin.{s}", boot_top - 0.04, ch.knee - 0.05, (-90, -25, 25))):
            for a0 in azs:
                C, d, u = ch.point(seg, a0, (z0 + z1) / 2)
                n = d.cross(u).normalized()
                sh.cut(C, n, lambda c, f, seg=seg, a0=a0, z0=z0, z1=z1: z0 < c.z < z1 and on([seg.split(".")[0]], s)(c, f) and abs(ch.coords(seg, c)[0] - a0) < 30 and ch.coords(seg, c)[2] < 0.13, "seam.inseam" if a0 == -90 else "seam.shin")
    # —— 分块：气囊（外层鼓起的贴片）与背部面板（只有接缝）——
    zp = lambda key: (z(SPEC[key]["z"][0]), z(SPEC[key]["z"][1]))  # noqa: E731
    for s, sg in (("L", 1), ("R", -1)):
        a0, a1 = SPEC["bladder.abdomen"]["az"]
        z0, z1 = zp("bladder.abdomen")
        poly = chamfer_rect(a0, a1, z0, z1, 8, 0.035)
        if sg < 0:
            poly = [(-a, zz) for a, zz in reversed(poly)]
        F = panel(sh, ch, "torso", poly, "bladder.abdomen", ["torso"], 0.3, r=0.13)
        parts.append(("bladder", pillow(f"xz.bladder.abdomen.{s.lower()}", F, 0.011, 0.025, "bladder", props)))
        a0, a1 = SPEC["bladder.thigh"]["az"]
        z0, z1 = zp("bladder.thigh")
        F = panel(sh, ch, f"thigh.{s}", chamfer_rect(a0, a1, z0, z1, 14, 0.05), "bladder.thigh", ["thigh", "torso"], 0.2, r=0.09)
        parts.append(("bladder", pillow(f"xz.bladder.thigh.{s.lower()}", F, 0.012, 0.03, "bladder", props)))
        a0, a1 = SPEC["bladder.calf"]["az"]
        z0, z1 = zp("bladder.calf")
        F = panel(sh, ch, f"shin.{s}", chamfer_rect(a0, a1, z0, z1, 12, 0.04), "bladder.calf", ["shin"], 0.15, r=0.06)
        parts.append(("bladder", pillow(f"xz.bladder.calf.{s.lower()}", F, 0.009, 0.022, "bladder", props)))
        a0, a1 = SPEC["panel.back"]["az"]
        z0, z1 = zp("panel.back")
        poly = chamfer_rect(a0, a1, z0, z1, 8, 0.04)
        if sg < 0:
            poly = [(-a, zz) for a, zz in reversed(poly)]
        panel(sh, ch, "torso", poly, "panel.back", ["torso"], 0.3, r=0.12)
    # 护膝：膝前切出倒角块（轮廓也是接缝），做成硬壳贴片
    pads = []
    for s in "LR":
        a0, a1 = SPEC["suit.kneepad"]["az"]
        kz = ch.knee + 0.045
        F = panel(sh, ch, f"thigh.{s}", chamfer_rect(a0, a1, kz - 0.066, kz + 0.07, 10, 0.028), "suit.kneepad", ["thigh", "shin"], 0.16, r=0.06)
        pads.append((s, F))
    for s, F in pads:
        parts.append(("kneepad", pillow(f"xz.kneepad.{s.lower()}", F, 0.017, 0.009, "kneepad", props, lip=0.004)))
    groove(sh.bm)
    # 领口开口一圈（立领从这里长出来）、两只袖口（手套翻边套在外面）
    neck_loop = boundary_loop(sh.bm, lambda v: v.co.z > ch.neckz - 0.05)
    for s in "LR":
        Wj = ch.J[f"wrist.{s}"]
        sleeve_ends[s] = boundary_loop(sh.bm, lambda v, Wj=Wj: (v.co - Wj).length < 0.09)
    shell = geo.obj_from_bm("xz.suit.shell", sh.bm, "suit", props)
    parts.insert(0, ("shell", shell))
    surf = Surf(shell, ch)
    parts += collar(neck_loop, ch, props)
    parts += harness(surf, ch, props)
    parts += trims(surf, ch, props)
    parts += gloves(body, posed_V, ch, props)
    parts += boots(body, posed_V, ch, props)
    return parts, sh.seams, ch


def faces_where(body, pred_v, all_=True):
    F = []
    for f in body.faces:
        ok = [pred_v(i) for i in f]
        if (all(ok) if all_ else any(ok)):
            F.append(f)
    return F


def sub_mesh(V, F):
    ids = sorted({i for f in F for i in f})
    remap = {v: k for k, v in enumerate(ids)}
    return V[ids], [[remap[i] for i in f] for f in F], np.array(ids)


def laplace(V, F, iters, lam=0.5, fixed=None):
    E = set()
    for f in F:
        for a, b in zip(f, f[1:] + f[:1]):
            E.add((min(a, b), max(a, b)))
    E = np.array(sorted(E))
    cnt = np.zeros(len(V))
    np.add.at(cnt, E[:, 0], 1)
    np.add.at(cnt, E[:, 1], 1)
    cnt = np.maximum(cnt, 1)[:, None]
    for _ in range(iters):
        acc = np.zeros_like(V)
        np.add.at(acc, E[:, 0], V[E[:, 1]])
        np.add.at(acc, E[:, 1], V[E[:, 0]])
        d = acc / cnt - V
        if fixed is not None:
            d[fixed] = 0
        V = V + lam * d
    return V


sleeve_ends = {}


def gloves(body, BV, ch, props):
    """手套：手 + 腕上 7 cm 的身体网格外扩 3 mm、抹掉指甲与指节褶，腕口用平面切直；外加一圈 3.5 cm 的翻边袖口压在袖口外。"""
    import body as B_
    out = []
    N = B_.normals(BV, body.faces)
    for s in "LR":
        E_, W_ = np.array(ch.J[f"elbow.{s}"]), np.array(ch.J[f"wrist.{s}"])
        ax = (W_ - E_) / np.linalg.norm(W_ - E_)
        cut = W_ - ax * 0.07

        def inv(i, s=s):
            sg = body.seg[i]
            return sg == f"hand.{s}" or (sg == f"farm.{s}" and (BV[i] - cut).dot(ax) > -0.02)

        F = faces_where(body, inv)
        V, F2, ids = sub_mesh(BV + N * 0.003, F)
        V = laplace(V, F2, 6, 0.4)
        bm = bmesh.new()
        vs = [bm.verts.new(Vector(v)) for v in V]
        for f in F2:
            try:
                bm.faces.new([vs[i] for i in f])
            except ValueError:
                pass
        res = bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], dist=1e-6, plane_co=Vector(cut), plane_no=Vector(ax), clear_inner=True)
        loop = [e for e in res["geom_cut"] if isinstance(e, bmesh.types.BMEdge)]
        ring = [v.co.copy() for v in {v for e in loop for v in e.verts}]
        o = geo.obj_from_bm(f"xz.glove.{s.lower()}", bm, "glove", props)
        out.append(("glove", o))
        sleeve = sleeve_ends.get(s)
        if sleeve:
            c = sum(sleeve, Vector()) / len(sleeve)
            # 翻边袖口：盖住袖口，往手腕方向 1.2 cm、往肘方向 3.6 cm（ax 指向手，所以沿 −ax 往上）
            out.append(("glove", cuff(f"xz.glove.{s.lower()}.cuff", sleeve, c, -Vector(ax), 0.036, props, grow=0.005, thick=0.004, below=0.012)))
    return out


def cuff(name, ring, c, ax, height, props, grow=0.006, thick=0.004, mat="glove", below=0.006):
    """开口一圈 → 翻边环：从开口往手（-ax 反向）伸 below，沿 ax 方向长 height；外扩 grow、厚 thick。"""
    ax = ax.normalized()
    u = ax.orthogonal().normalized()
    v = ax.cross(u)
    rad = []
    for p in ring:
        r = (p - c) - ax * (p - c).dot(ax)
        rad.append((math.atan2(r.dot(v), r.dot(u)), r))
    rad.sort(key=lambda t: t[0])
    rad = [r for _, r in rad]
    n = len(rad)
    bm = bmesh.new()
    rows = []
    for h, g in ((below, grow), (-height * 0.3, grow + 0.001), (-height, grow), (-height, grow - thick), (below, grow - thick)):
        rows.append([bm.verts.new(c + r + r.normalized() * g - ax * h) for r in rad])
    for A, B_ in zip(rows, rows[1:] + rows[:1]):
        for i in range(n):
            bm.faces.new((A[i], A[(i + 1) % n], B_[(i + 1) % n], B_[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return geo.obj_from_bm(name, bm, mat, props)


def boots(body, BV, ch, props):
    """靴：脚与小腿下段的横截面逐层取凸包、外扩、按角度重采样 → 一圈圈放样（四边形干净拓扑）；鞋底另做一块；
    靴口翻边、脚踝一道扣带。"""
    out = []
    top = ch.zmap(0.25)
    n = 40
    for s in "LR":
        idx = np.array([i for i, sg in enumerate(body.seg) if sg in (f"foot.{s}", f"shin.{s}")])
        P = BV[idx]
        P = P[P[:, 2] < top + 0.02]
        zmin = P[:, 2].min()
        levels = [zmin + 0.004, zmin + 0.015, zmin + 0.03, zmin + 0.045, zmin + 0.06, zmin + 0.08, zmin + 0.105, zmin + 0.135, zmin + 0.17, top - 0.03, top]
        rings = []
        for k, zl in enumerate(levels):
            band = P[np.abs(P[:, 2] - zl) < 0.012]
            if k <= 2:  # 脚底几层：取整只脚的轮廓（鞋头不随脚趾收窄）
                band = P[P[:, 2] < zmin + 0.05]
            pts = hull2d(band[:, :2])
            thick = 0.021 if zl < zmin + 0.05 else (0.016 if zl < zmin + 0.09 else 0.011)
            pts = offset2d(pts, thick)
            rings.append(resample(pts, n, zl))
        # 鞋头：底下两层往前多伸 1 cm，略上翘
        bm = bmesh.new()
        R = [[bm.verts.new(Vector(p)) for p in r] for r in rings]
        for A, B_ in zip(R, R[1:]):
            for i in range(n):
                bm.faces.new((A[i], A[(i + 1) % n], B_[(i + 1) % n], B_[i]))
        bm.faces.new(list(reversed(R[0])))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        out.append(("boot", geo.obj_from_bm(f"xz.boot.{s.lower()}", bm, "boot", props)))
        # 鞋底：底层轮廓外扩 5 mm，厚 = 地面到底层
        base = offset2d(hull2d(np.array([p[:2] for p in rings[0]])), 0.007)
        sole = [(x, y, zz) for x, y in base for zz in (0.0, zmin + 0.006)]
        out.append(("sole", geo.hull(f"xz.boot.{s.lower()}.sole", sole, "sole", props, bevel=0.003)))
        # 靴口翻边、脚踝扣带
        c = Vector((float(np.mean([p[0] for p in rings[-1]])), float(np.mean([p[1] for p in rings[-1]])), top))
        out.append(("boot", cuff(f"xz.boot.{s.lower()}.cuff", [Vector(p) for p in rings[-1]], c, Vector((0, 0, -1)), 0.03, props, grow=0.004, thick=0.005, mat="boot")))
        zb = zmin + 0.12
        rb = resample(offset2d(hull2d(P[np.abs(P[:, 2] - zb) < 0.012][:, :2]), 0.013), n, zb)
        cb = Vector((float(np.mean([p[0] for p in rb])), float(np.mean([p[1] for p in rb])), zb))
        out.append(("strap", cuff(f"xz.boot.{s.lower()}.strap", [Vector(p) for p in rb], cb, Vector((0, 0, -1)), 0.022, props, grow=0.002, thick=0.003, mat="strap")))
    return out


def hull2d(P):
    P = np.unique(np.round(P, 5), axis=0)
    P = P[np.lexsort((P[:, 1], P[:, 0]))]

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lo, up = [], []
    for p in P:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(tuple(p))
    for p in P[::-1]:
        while len(up) >= 2 and cross(up[-2], up[-1], p) <= 0:
            up.pop()
        up.append(tuple(p))
    return np.array(lo[:-1] + up[:-1])


def offset2d(H, d):
    """凸多边形外扩 d（顶点沿两邻边法线的角平分线外推）。"""
    out = []
    n = len(H)
    c = H.mean(0)
    for i in range(n):
        p = H[i]
        r = p - c
        out.append(p + r / max(np.linalg.norm(r), 1e-9) * d)
    return np.array(out)


def resample(H, n, z):
    """凸轮廓按绕质心的角度重采样 n 点（逆时针，从 +x 起）。"""
    c = H.mean(0)
    ang = np.arctan2(H[:, 1] - c[1], H[:, 0] - c[0])
    o = np.argsort(ang)
    H, ang = H[o], ang[o]
    out = []
    for k in range(n):
        a = -math.pi + 2 * math.pi * k / n
        d = np.array([math.cos(a), math.sin(a)])
        best = None
        for i in range(len(H)):
            p, q = H[i], H[(i + 1) % len(H)]
            # 射线 c + t d 与边 pq 求交
            M = np.array([d, p - q]).T
            if abs(np.linalg.det(M)) < 1e-12:
                continue
            t, u = np.linalg.solve(M, p - c)
            if t > 0 and -1e-9 <= u <= 1 + 1e-9:
                if best is None or t < best:
                    best = t
        r = c + d * (best if best is not None else 0.05)
        out.append((float(r[0]), float(r[1]), float(z)))
    return out


def boundary_loop(bm, pred):
    """满足 pred 的开口边界顶点，按绕中心的角度排好。"""
    vs = [v for v in bm.verts if v.is_boundary and pred(v)]
    if not vs:
        return []
    c = sum((v.co for v in vs), Vector()) / len(vs)
    vs.sort(key=lambda v: math.atan2(v.co.y - c.y, v.co.x - c.x))
    return [v.co.copy() for v in vs]


class Surf:
    """服装壳表面上的取点：躯干 / 四肢从轴向外打射线（第一次碰到的就是本段表面），肩顶从上往下打。"""

    def __init__(self, obj, ch):
        self.tree = geo.bvh_of(obj)
        self.ch = ch

    def ray(self, o, d):
        loc, n, _, _ = self.tree.ray_cast(Vector(o), Vector(d).normalized(), 1.0)
        return loc, n

    def at(self, seg, az, z, lift=0.0):
        C, d, _ = self.ch.point(seg, az, z, 0.0)
        loc, n = self.ray(C, d)
        if loc is None:
            loc, n = geo.project(self.tree, C + d * 0.12)
        return loc + n * lift

    def top(self, x, y, lift=0.0):
        loc, n = self.ray((x, y, 2.2), (0, 0, -1))
        return loc + n * lift

    def front(self, y, z, lift=0.0):
        """前表面：从身前水平往后打（打空了就取离该点最近的表面点）。"""
        return self._hz(1, y, z, lift)

    def back(self, y, z, lift=0.0):
        return self._hz(-1, y, z, lift)

    def _hz(self, sx, y, z, lift):
        loc, n = self.ray((0.7 * sx, y, z), (-sx, 0, 0))
        if loc is None:
            loc, n = geo.project(self.tree, (self.ch.torso_x(z) + 0.1 * sx, y, z))
        return loc + n * lift


def collar(loop, ch, props):
    """立领：领口开口一圈往上长 3.6 cm（略收），4 mm 厚、上沿圆边；颈封一圈细条。"""
    if not loop:
        return []
    c = sum(loop, Vector()) / len(loop)
    n = len(loop)
    up = Vector((0, 0, 1))
    rings = []
    for h, k in ((-0.004, 1.035), (0.012, 1.03), (0.026, 1.0), (0.036, 0.975)):
        rings.append([c + (p - c) * k + up * h + Vector((0.004, 0, 0)) * (h > 0) for p in loop])
    inner = [[c + (p - c) * (k - 0.06) + up * h for p in loop] for h, k in ((0.036, 0.975), (-0.004, 1.035))]
    allr = rings + inner
    bm = bmesh.new()
    R = [[bm.verts.new(p) for p in r] for r in allr]
    for A, B_ in zip(R, R[1:]):
        for i in range(n):
            bm.faces.new((A[i], A[(i + 1) % n], B_[(i + 1) % n], B_[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return [("collar", geo.obj_from_bm("xz.suit.collar", bm, "collar", props))]


def harness(sf, ch, props):
    """挽具（约束层）：扁织带贴着服装壳走（离面 2.5 mm、厚 3.5 mm），金属扣件。路径点用部位坐标给。"""
    out = []
    z = ch.zmap
    belt = z(1.12)
    W, TH, LIFT = 0.045, 0.0035, 0.0025

    def strap(name, pts, width=W):
        P_, N_ = geo.drape(sf.tree, pts, LIFT, step=0.015)
        out.append(("strap", geo.ribbon(name, P_, N_, width, TH, "strap", props)))
        return P_, N_

    # 腰带：一圈
    ring = [sf.at("torso", a, belt) for a in range(-180, 180, 8)]
    P_, N_ = geo.drape(sf.tree, ring, LIFT, step=0.015, smooth=0)
    out.append(("strap", geo.ribbon("xz.harness.belt", P_, N_, 0.05, TH, "strap", props, closed=True)))
    plates = []
    for s, sg in (("l", 1), ("r", -1)):
        S_ = "L" if s == "l" else "R"
        xs = ch.torso_x(1.40)
        # 肩带：腰后三角扣板 → 背上斜向外 → 竖直上肩 → 过肩顶 → 胸前竖直 → 腰带（设定图正视 x ±0.12、背视 ±0.10）
        back = [sf.back(sg * 0.03, belt + 0.045), sf.back(sg * 0.06, z(1.20)), sf.back(sg * 0.088, z(1.26)), sf.back(sg * 0.10, z(1.36)), sf.back(sg * 0.105, z(1.44))]
        over = [sf.top(xs - 0.05, sg * 0.108), sf.top(xs - 0.01, sg * 0.108), sf.top(xs + 0.03, sg * 0.11)]
        front = [sf.front(sg * 0.112, z(1.45)), sf.front(sg * 0.118, z(1.36)), sf.front(sg * 0.12, z(1.24)), sf.front(sg * 0.122, belt)]
        strap(f"xz.harness.shoulder.{s}", back + over + front)
        for k, p in enumerate((sf.front(sg * 0.115, z(1.44)), sf.front(sg * 0.12, z(1.29)), sf.back(sg * 0.103, z(1.43)), sf.back(sg * 0.07, z(1.215)))):
            plates.append((f"xz.harness.adjuster.{s}{k}", p, (0.009, 0.052, 0.034)))
        # 腿带：腰带胯前 → 斜向内下到大腿内侧 → 绕到臀下 → 斜向外上回到胯后腰带（正视 V 字、背视倒 V）
        leg = [sf.front(sg * 0.135, belt - 0.03), sf.front(sg * 0.115, z(1.02)), sf.front(sg * 0.085, z(0.94)), sf.at(f"thigh.{S_}", -45, ch.crotch - 0.01),
               sf.at(f"thigh.{S_}", -95, ch.crotch - 0.04), sf.at(f"thigh.{S_}", -140, ch.crotch - 0.045),
               sf.back(sg * 0.075, ch.crotch + 0.01), sf.back(sg * 0.105, ch.crotch + 0.06), sf.back(sg * 0.135, z(0.98)), sf.back(sg * 0.12, belt - 0.035)]
        strap(f"xz.harness.leg.{s}", leg, 0.04)
        plates.append((f"xz.harness.legbuckle.{s}0", sf.front(sg * 0.098, z(0.97)), (0.009, 0.046, 0.04)))
        plates.append((f"xz.harness.legbuckle.{s}1", sf.back(sg * 0.112, ch.crotch + 0.085), (0.009, 0.046, 0.04)))
    plates.append(("xz.harness.buckle", sf.at("torso", 0, belt), (0.016, 0.085, 0.056)))
    for name, p, size in plates:
        q, n = geo.project(sf.tree, p, LIFT + TH + size[0] / 2)
        R = geo.frame_from(n, Vector((0, 0, 1)))
        out.append(("buckle", geo.box(name, q, size, R, "buckle", props, bevel=0.002)))
    # 腰后三角扣板：肩带、脊线汇合处（尖朝下）
    c = sf.at("torso", 180, belt + 0.01)
    _, n = geo.project(sf.tree, c)
    R = geo.frame_from(n, Vector((0, 0, 1)))
    tri = []
    for d in (0.0, 0.012):
        for yy, zz in ((-0.04, 0.03), (0.04, 0.03), (0.0, -0.045)):
            tri.append(c + n * (LIFT + TH + d) + R.col[1] * yy + R.col[2] * zz)
    out.append(("buckle", geo.hull("xz.harness.backplate", tri, "buckle", props, bevel=0.003)))
    return out


def trims(sf, ch, props):
    """前中拉链条、脊背暗朱红嵌条、脐带接口与盘绕软管、胸前「銜燭」。"""
    out = []
    z = ch.zmap
    # 拉链：前中，胯上 → 领口
    pts = [sf.at("torso", 0, zz) for zz in np.linspace(ch.crotch + 0.03, ch.neckz + 0.025, 24)]
    P_, N_ = geo.drape(sf.tree, pts, 0.0008, step=0.012)
    out.append(("strap", geo.ribbon("xz.suit.zipper", P_, N_, 0.012, 0.0015, "strap", props)))
    # 脊线：后中 z 1.15 → 1.55（软态未点亮的暗朱红）
    z0, z1 = z(SPEC["suit.spine"]["z"][0]), min(z(SPEC["suit.spine"]["z"][1]), ch.neckz - 0.012)
    pts = [sf.at("torso", 180, zz) for zz in np.linspace(z0, z1, 24)]
    P_, N_ = geo.drape(sf.tree, pts, 0.0008, step=0.012)
    out.append(("spine", geo.ribbon("xz.suit.spine", P_, N_, 0.008, 0.0016, "vermilion", props)))
    # 脐带接口：装在左肩带上（设定图正视 x ≈ 0.12、z ≈ 1.22），氧 / 冷 / 电 / 数四个插座
    c = sf.front(0.12, z(1.22), 0.0025 + 0.0035)
    _, n = geo.project(sf.tree, c)
    R = geo.frame_from(n, Vector((0, 0, 1)))
    body_c = c + n * 0.016
    out.append(("umbilical", geo.box("xz.suit.umbilical", body_c, (0.026, 0.05, 0.062), R, "umbilical", props, bevel=0.003)))
    for k, (dy, dz) in enumerate(((-0.012, 0.014), (0.012, 0.014), (-0.012, -0.014), (0.012, -0.014))):
        p0 = body_c + R.col[0] * 0.013 + R.col[1] * dy + R.col[2] * dz
        out.append(("umbilical", geo.tube(f"xz.suit.umbilical.port{k}", [p0, p0 + R.col[0] * 0.008], 0.0075, "metal", props, sides=10)))
    # 软管：接口底下出，盘绕着垂到腰带左侧挂扣
    top = body_c - R.col[2] * 0.031
    clip = sf.front(0.155, z(1.12) + 0.03)
    _, nc = geo.project(sf.tree, clip)
    clip = clip + nc * 0.02
    pts = []
    for k in range(90):
        t = k / 89
        base = top.lerp(clip, t) + R.col[0] * (0.045 * math.sin(math.pi * t))  # 软管垂成向前的 U 形
        a = t * 2 * math.pi * 9
        r = 0.009 * math.sin(math.pi * min(1.0, t * 1.2))
        pts.append(base + R.col[1] * (r * math.cos(a)) + R.col[0] * (r * math.sin(a)))
    out.append(("hose", geo.tube("xz.suit.hose", pts, 0.0055, "hose", props, sides=8)))
    # 铭文：左胸，拉链左侧，字高 2.4 cm
    a = SPEC["suit.inscription"]
    zc = z(sum(a["z"]) / 2)
    p = sf.at("torso", sum(a["az"]) / 2, zc)
    _, n = geo.project(sf.tree, p)
    out.append(("inscription", inscription("xz.suit.inscription", "銜燭", p + n * 0.0012, n, 0.024, props)))
    return out


FONT = "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"


def inscription(name, text, centre, normal, height, props):
    cu = bpy.data.curves.new(name, "FONT")
    cu.body = text
    cu.font = bpy.data.fonts.load(FONT, check_existing=True)
    cu.size = height / 0.72
    cu.align_x = "CENTER"
    cu.align_y = "CENTER"
    cu.extrude = 0.0005
    tmp = bpy.data.objects.new(name + ".tmp", cu)
    bpy.context.scene.collection.objects.link(tmp)
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(tmp.evaluated_get(dg))
    bpy.data.objects.remove(tmp)
    bpy.data.curves.remove(cu)
    zd = Vector(normal).normalized()
    up = Vector((0, 0, 1))
    xd = up.cross(zd).normalized()  # 字行方向：从正面看向右（着装者的右手方向）
    yd = zd.cross(xd).normalized()
    M = Matrix((xd, yd, zd)).transposed()
    for v in me.vertices:
        v.co = Vector(centre) + M @ v.co
    o = bpy.data.objects.new(name, me)
    o.data.materials.append(geo.material("inscription"))
    bpy.context.scene.collection.objects.link(o)
    for k, v in props.items():
        o[k] = v
    return o
