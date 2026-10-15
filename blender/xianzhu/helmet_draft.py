"""銜燭 头盔：以 Tripo Smart Mesh 起稿（refs/ai_draft/X1_头盔闭眼_smartmesh.glb）为底（作者 2026-10-15 定）。

1. 导入、三角面并回四边面，按连通块拆：盔壳（含被并在一起的头颈）、面罩（光滑的大圆罩）、领口 / 肩部、天线等。
2. 定朝向：面罩质心相对盔壳质心的水平方向 = 正前，转到 +x；等比缩放到身体起稿原头盔的外形尺寸（宽 0.25 m）、对到脸上。
3. 只留盔壳；盔壳按左右对称补齐（设定图那张是 3/4 侧视，看清的是着装者左半边，镜像左 → 右）。
4. 后脑与侧后方是猜的、块面歪扭：在耳后一刀切掉，按前半的块面逻辑补齐——同一套超椭球底壳（拟合前半盔壳）+
   大切面（helmet.py 的 FACETS）+ 后脑盖板、盔脊、后模块；接缝处一道环形肋盖住。
5. 按 DESIGN 9.1.1 改：丢掉起稿的大圆面罩，前脸用面板补成窄面罩开口（helmet.py 的面框 + 眉骨），暗琥珀遮光面罩做成
   单独可动件（形态键 down），加颈环。
"""
import math

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

import draft
import geo


def components(bm):
    seen = set()
    out = []
    for f in bm.faces:
        if f in seen:
            continue
        stack, comp = [f], []
        while stack:
            g = stack.pop()
            if g in seen:
                continue
            seen.add(g)
            comp.append(g)
            for e in g.edges:
                for h in e.link_faces:
                    if h not in seen:
                        stack.append(h)
        out.append(comp)
    return sorted(out, key=len, reverse=True)


def centroid(faces):
    P = np.array([tuple(v.co) for f in faces for v in f.verts])
    return P.mean(0), P.min(0), P.max(0)


def load(path=draft.DRAFT_HELMET):
    """返回 (bm, 面罩面集合, 盔壳面集合, 日志)：已转到本作坐标（正前 +x）但未缩放。"""
    o = draft.import_glb(path)[0]
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bpy.data.objects.remove(o)
    bmesh.ops.join_triangles(bm, faces=bm.faces[:], angle_face_threshold=math.radians(10), angle_shape_threshold=math.radians(40))
    comps = components(bm)
    shell = comps[0]
    c_shell, lo, hi = centroid(shell)
    # 面罩：盔壳以外、在盔壳高度范围里、面最少但面积最大的光滑块——取“面积 / 面数”最大的块
    best, score = None, 0
    for c in comps[1:]:
        cc, l2, h2 = centroid(c)
        if h2[2] < c_shell[2]:
            continue
        area = sum(f.calc_area() for f in c)
        s = area / len(c)
        if s > score:
            best, score = c, s
    visor = best
    cv, _, _ = centroid(visor)
    d = cv - c_shell
    yaw = math.atan2(d[1], d[0])
    bmesh.ops.rotate(bm, verts=bm.verts[:], cent=Vector(c_shell), matrix=Matrix.Rotation(-yaw, 3, "Z"))
    log = {"components": [len(c) for c in comps], "yaw_deg": round(math.degrees(yaw), 2), "visor_faces": len(visor)}
    return bm, set(visor), set(shell), log


WIDTH = 0.25  # 盔宽（spec LANDMARKS helmet_width 0.257 量自设定图，取整）
TOP = 1.80  # 盔顶（设定图米制标定）


def place(bm, face):
    """等比缩放到盔宽 WIDTH，盔顶 TOP，左右居中，前缘（下巴护条最前）在脸最前点前 4.5 cm。"""
    V = np.array([tuple(v.co) for v in bm.verts])
    s = WIDTH / (V[:, 1].max() - V[:, 1].min())
    bmesh.ops.scale(bm, vec=Vector((s, s, s)), verts=bm.verts[:])
    V = V * s
    F = np.array([tuple(v.co) for v in face.data.vertices])
    t = Vector((F[:, 0].max() + 0.045 - V[:, 0].max(), -(V[:, 1].max() + V[:, 1].min()) / 2, TOP - V[:, 2].max()))
    bmesh.ops.translate(bm, vec=t, verts=bm.verts[:])
    return s


def straighten(bm):
    """盔壳按对称面转正（绕 z），再镜像：留着装者左半（设定图那张看清的一侧），补出右半。"""
    for _ in range(6):
        V = np.array([tuple(v.co) for v in bm.verts])
        a, b, m = draft.symmetry_plane(V, sample=6000)
        c = Vector((V[:, 0].mean(), 0, 0))
        bmesh.ops.rotate(bm, verts=bm.verts[:], cent=c, matrix=Matrix.Rotation(-math.atan(b), 3, "Z"))
        bmesh.ops.translate(bm, vec=Vector((0, -a, 0)), verts=bm.verts[:])
        if abs(b) < 1e-3 and abs(a) < 2e-4:
            break
    bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], dist=1e-6, plane_co=(0, 0, 0), plane_no=(0, 1, 0), clear_inner=True)
    bmesh.ops.mirror(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], axis="Y", merge_dist=2e-5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return m


def fit_ellipsoid(P):
    """超椭球（helmet.radius 的形式）拟合：中心 (x, z)（y = 0）+ 前 / 后 / 侧 / 上 / 下半轴。"""
    from scipy.optimize import least_squares

    import helmet

    def res(q):
        cx, cz, f, b, s, t, d = q
        helmet.AX.update(front=f, back=b, side=s, top=t, bottom=d)
        out = np.empty(len(P))
        for i, p in enumerate(P):
            r = Vector((p[0] - cx, p[1], p[2] - cz))
            out[i] = r.length - helmet.radius(r.normalized())
        return out

    c = P.mean(0)
    q0 = [c[0], c[2], 0.15, 0.13, 0.125, 0.14, 0.13]
    sol = least_squares(res, q0, loss="soft_l1", f_scale=0.004)
    cx, cz, f, b, s, t, d = sol.x
    helmet.AX.update(front=f, back=b, side=s, top=t, bottom=d)
    return Vector((cx, 0.0, cz)), dict(helmet.AX), float(np.median(np.abs(sol.fun)))


def build(face, props, state="soft", path=draft.DRAFT_HELMET, eye_z=None, collar_top=1.53):
    """返回 (件列表, 头部标架 M, 日志)。face：身体起稿的脸（定前后位置）。"""
    import helmet

    P = dict(props)
    bm, visor, shell, log = load(path)
    # 起稿大圆面罩的轮廓（前视 y, z）：之后用面板把它补成窄开口
    vis_pts = [v.co.copy() for f in visor for v in f.verts]
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f not in shell], context="FACES")
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    # 面罩点跟着一起缩放、平移、转正：放进同一个 bmesh 当孤点，最后删掉
    tmp = [bm.verts.new(p) for p in vis_pts]
    log["scale"] = round(place(bm, face), 5)
    vis_pts = [v.co.copy() for v in tmp]
    for v in tmp:
        bm.verts.remove(v)
    log["sym_residual_m"] = round(straighten(bm), 4)
    V = np.array([tuple(v.co) for v in bm.verts])
    # —— 拟合底壳：盔壳点（去掉下巴护条以下的点）——
    keep = V[V[:, 2] > V[:, 2].min() + 0.04]
    O, AX, err = fit_ellipsoid(keep[:: max(1, len(keep) // 1500)])
    log["fit"] = {"O": [round(x, 4) for x in O], "AX": {k: round(v, 4) for k, v in AX.items()}, "median_err_m": round(err, 4)}
    M = Matrix.Translation(O)
    # —— 后半切掉：耳后一刀（中心往后 1.5 cm），切口直 ——
    x_cut = O.x - 0.015
    bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], dist=1e-6, plane_co=(x_cut, 0, 0), plane_no=(1, 0, 0), clear_inner=True)
    # 下沿：起稿盔壳后半的最低处往上 1 cm；不低于底壳的 0.85 倍下半轴（否则后半切不出下沿）
    zb = V[V[:, 0] < O.x, 2].min()
    helmet.BOTTOM = max((zb + 0.01) - O.z, -0.85 * AX["bottom"])
    log["bottom_z"] = round(O.z + helmet.BOTTOM, 4)
    shell_o = geo.obj_from_bm("xz.helmet.shell.front", bm, "helmet", P)
    geo.mark_sharp(shell_o, 30)
    out = [("helmet", shell_o)]
    # —— 后半：同一底壳 + 大切面，切到 x_cut 以后，下沿与前半同高 ——
    bk = helmet.quad_sphere(30)
    bmesh.ops.bisect_plane(bk, geom=bk.verts[:] + bk.edges[:] + bk.faces[:], dist=1e-6, plane_co=(x_cut - O.x + 0.006, 0, 0), plane_no=(1, 0, 0), clear_outer=True)
    bmesh.ops.bisect_plane(bk, geom=bk.verts[:] + bk.edges[:] + bk.faces[:], dist=1e-6, plane_co=(0, 0, helmet.BOTTOM), plane_no=(0, 0, 1), clear_inner=True)
    rim = [M @ v.co for v in bk.verts if abs(v.co.z - helmet.BOTTOM) < 1e-4]
    plates(bk)
    helmet.solidify(bk, helmet.SHELL_T)
    bk.transform(M)
    back_o = geo.obj_from_bm("xz.helmet.shell.back", bk, "helmet", P)
    geo.mark_sharp(back_o, 22)
    out.append(("helmet", back_o))
    out.append(("helmet", rib(M, x_cut - O.x, P)))
    # —— 前脸：起稿大面罩的洞用面板补上，只留窄开口 ——
    if eye_z is not None:
        dz = (eye_z + 0.048) - (O.z + helmet.OPENING[0][1])
        helmet.OPENING[:] = [(y, z + dz) for y, z in helmet.OPENING]
    big = [((p - O).y, (p - O).z) for p in vis_pts]
    out.append(("helmet", mask_plate(M, big, P)))
    helmet.SUN_EXTRA = -0.02  # 起稿前半的板之间有缝：遮光面罩收得更深，收起时不从缝里露出来
    helmet.PROW = 0.02  # 起稿已有一道眉带：眉骨楔收小，骑在眉带上、往后接盔脊
    helmet.BROW_MAT = "helmet"
    helmet.VISOR_GROW = 0.005
    out += helmet.details(M, P, rim, state, parts=("brow", "crest", "rear", "visors", "neckring"))
    out += neck_seal(rim, collar_top, P)
    log["parts"] = len(out)
    return out, M, log


# 后半分块的种子方向（头部局部的方位、仰角）：与前半起稿的块面一样大小不一、错开排
SEEDS = [(180, 58), (180, 20), (180, -12), (152, 38), (-152, 38), (138, 6), (-138, 6), (122, 34), (-122, 34), (160, -20), (-160, -20), (112, -4), (-112, -4)]


def plates(bm, groove=0.0015, lift=0.001):
    """后半底壳分块（与前半起稿的块面同一逻辑）：按种子方向分区——按夹角最近的种子分，分界是过球心、法线为 Sᵢ − Sⱼ
    的平面（大圆），所以先沿这些平面切（切口是直的），再把分界边压成一道缝、块面略抬起。"""
    import helmet

    S = [helmet.dir_(a, e) for a, e in SEEDS]

    def owner(p):
        d = p.normalized()
        return max(range(len(S)), key=lambda i: d.dot(S[i]))

    def top2(p):
        d = p.normalized()
        o = sorted(range(len(S)), key=lambda i: -d.dot(S[i]))
        return frozenset(o[:2])

    pairs = {}
    for f in bm.faces:
        for v in f.verts:
            pairs.setdefault(top2(v.co), set()).add(f)
    for key, fs in pairs.items():
        i, j = sorted(key)
        n = (S[i] - S[j]).normalized()
        geom = [f for f in fs if f.is_valid]
        # 只切真跨过这条分界的面（顶点在平面两侧）
        geom = [f for f in geom if min(v.co.dot(n) for v in f.verts) < -1e-7 < 1e-7 < max(v.co.dot(n) for v in f.verts)]
        if not geom:
            continue
        bmesh.ops.bisect_plane(bm, geom=geom + list({e for f in geom for e in f.edges}) + list({v for f in geom for v in f.verts}),
                               dist=1e-6, plane_co=(0, 0, 0), plane_no=n)
    bmesh.ops.dissolve_degenerate(bm, dist=2e-5, edges=bm.edges[:])
    own = {f: owner(f.calc_center_median()) for f in bm.faces}
    for e in bm.edges:
        if len(e.link_faces) == 2 and own[e.link_faces[0]] != own[e.link_faces[1]]:
            e.seam = True
    # 缝的截面按“到分界平面的真实距离”给（不按网格），缝边才不出锯齿：距离 0 处压下 groove，宽 w 以外抬起 lift
    bm.normal_update()
    w = 0.0045
    for v in bm.verts:
        d = v.co.normalized()
        i = owner(v.co)
        dist = min(((d.dot(S[i]) - d.dot(S[j])) / (S[i] - S[j]).length for j in range(len(S)) if j != i), default=1.0) * v.co.length
        t = min(1.0, max(0.0, dist / w))
        t = t * t * (3 - 2 * t)
        v.co = v.co + v.normal * (-groove + (groove + lift) * t)


def neck_seal(rim, collar_top, P):
    """颈封：服装立领上沿 → 盔下沿颈环，中间一段暗色波纹密封（三道褶），上下各一圈环。"""
    import helmet

    R_ = np.array([tuple(p) for p in rim])
    cx, cy = R_[:, 0].mean(), R_[:, 1].mean()
    rr = float(np.mean(np.hypot(R_[:, 0] - cx, R_[:, 1] - cy)))
    z1 = float(R_[:, 2].mean()) - 0.012
    z0 = collar_top - 0.006
    base = Vector((cx, cy, 0.0))
    prof = [(z0, rr - 0.012)]
    n = 3
    for k in range(n):
        za = z0 + (z1 - z0) * (k + 0.25) / n
        zb = z0 + (z1 - z0) * (k + 0.75) / n
        prof += [(za, rr - 0.004), (zb, rr - 0.011)]
    prof += [(z1, rr - 0.012), (z1, rr - 0.02), (z0, rr - 0.02)]
    out = [("rubber", helmet.lathe("xz.helmet.neckseal", base, prof, 48, "rubber", P))]
    prof2 = [(z0 - 0.004, rr - 0.016), (z0 - 0.004, rr - 0.003), (z0 + 0.008, rr - 0.002), (z0 + 0.008, rr - 0.016)]
    out.append(("chrome", helmet.lathe("xz.helmet.neckring.suit", base, prof2, 48, "chrome", P)))
    return out


def back_plates(M, P):
    """后半的分块：按前半的块面逻辑——大切面上各贴一块内缩 6 mm、高 3 mm、四周倒角的板（后上、左右后侧、左右后下）。"""
    import helmet

    out = []
    for k, (az, el, w, h) in enumerate(((180, 42, 50, 26), (142, 20, 26, 30), (-142, 20, 26, 30), (150, -12, 24, 18), (-150, -12, 24, 18))):
        q = []
        for da in (-w / 2, w / 2):
            for de in (-h / 2, h / 2):
                d = helmet.dir_(az + da, el + de)
                q += [M @ helmet.faceted(helmet.surface(d, -0.003)), M @ helmet.faceted(helmet.surface(d, 0.0))]
                d2 = helmet.dir_(az + da * 0.82, el + de * 0.78)
                q.append(M @ helmet.faceted(helmet.surface(d2, 0.0035), 0.0035))
        out.append(("helmet", geo.hull(f"xz.helmet.plate.back{k}", q, "helmet", P, bevel=0.001)))
    return out


def rib(M, xr, P, w=0.012, t=0.004):
    """前后两半的接缝上压一道环形肋（盔壳与 x = xr 平面的交线，绕 x 轴一圈，下沿以上）。"""
    import helmet

    pts, nrm = [], []
    for a in np.linspace(-110, 110, 80):
        r = math.radians(a)
        # 平面 x = xr 上、方向 (0, sin, cos) 的点：沿射线找到底壳面
        lo, hi = 0.0, 0.3
        for _ in range(40):
            m_ = (lo + hi) / 2
            p = Vector((xr, m_ * math.sin(r), m_ * math.cos(r)))
            if p.length < helmet.radius(p.normalized()):
                lo = m_
            else:
                hi = m_
        p = Vector((xr, lo * math.sin(r), lo * math.cos(r)))
        if p.z < helmet.BOTTOM + 0.004:
            continue
        pts.append(M @ p)
        nrm.append(p.normalized())
    return geo.ribbon("xz.helmet.rib", pts, nrm, w, t, "helmet", P)


def mask_plate(M, big, P, t=0.005):
    """起稿大面罩洞（big：前视 (y, z) 点）补成面板：底壳在大洞凸包（外扩 6 mm）以内、窄开口 OPENING 以外的部分，加厚 t。"""
    import helmet
    from suit import hull2d

    H = hull2d(np.array(big))
    poly = helmet.grow([tuple(p) for p in H], 0.006)
    bm = helmet.quad_sphere(32, 0.0015, facets=False)
    helmet.cut_prism(bm, poly, keep_inside=True, front_only=True)
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.calc_center_median().x <= 0.0], context="FACES")
    helmet.cut_prism(bm, helmet.OPENING, keep_inside=False, front_only=True)
    helmet.solidify(bm, t, rim_bevel=0.001)
    bm.transform(M)
    o = geo.obj_from_bm("xz.helmet.mask", bm, "helmet", P)
    geo.mark_sharp(o, 30)
    return o
