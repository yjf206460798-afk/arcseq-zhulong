"""銜燭 头盔（X1 硬表面重做，DESIGN 9.1.1 ①）：避开“灰色分块盔壳 + 大面积镜面金面罩”的组合。

语言取自机身：盔顶一道前凸的切面**眉骨**（与座舱上方的眉骨同一做法：几块大切面、棱线分明），眉骨下是一条**窄**面罩开口
（像座舱盖那样的一条缝）；盔壳是石墨色的光滑壳，只在眉骨、盔脊、下巴护条、后脑模块上用切面；盔脊嵌一条朱红细线，
沿盔后往下接到服装脊线（人机同时点亮时一条线贯通）。双层面罩：透明面罩（软态落下）+ 暗琥珀遮光面罩（软态收在眉骨下，
闭眼时落下）。颈环两圈（盔侧 / 服装侧）+ 两只锁扣。

做法：
- 盔壳外形 = 超椭球（前后半轴不等、上下半轴不等，指数 2.3 略方）投到立方体球网格上（六面细分，没有极点），
  面罩开口与下沿用平面切（bisect，切口是直的），实体化 7 mm，开口一圈倒小角。
- 面罩 = 同一张外形面在开口外扩 1 cm 的范围里取出来、外推 4 mm、加厚 3 mm；遮光面罩外推 9 mm，绕两侧铰链轴转上去收起。
- 坐标：头部局部标架（原点在头中心，x 前、y 左、z 上），建好后按头骨的姿态摆到世界里（换坐姿时跟头走）。
"""
import math

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

import geo

N_EXP = 2.3
AX = {"front": 0.158, "back": 0.12, "side": 0.125, "top": 0.138, "bottom": 0.13}
SHELL_T = 0.007
# 面罩开口（头部局部坐标的前视 (y, z)，八边形）：窄——宽 ±0.072、上沿眉骨下 z +0.045、下沿下巴护条 z −0.07
OPENING = [(0.0, 0.036), (0.05, 0.04), (0.068, 0.022), (0.068, -0.024), (0.056, -0.05), (0.03, -0.06),
           (-0.03, -0.06), (-0.056, -0.05), (-0.068, -0.024), (-0.068, 0.022), (-0.05, 0.04)]
BOTTOM = -0.113  # 下沿（盔壳收到颈环上）
PIVOT = Vector((0.0, 0.0, 0.012))  # 面罩铰链轴心（两侧 y = ±side）
SLIDE = 0.103  # 遮光面罩收起时在前视里上移的距离
SUN_EXTRA = -0.0115  # 遮光面罩离底壳面（负 = 在盔壳里面）
PROW = 0.03  # 眉骨前缘探出盔面
BROW_MAT = "brow"
VISOR_GROW = 0.012  # 透明面罩比开口外扩


def radius(d):
    ax = AX["front"] if d.x > 0 else AX["back"]
    az = AX["top"] if d.z > 0 else AX["bottom"]
    s = (abs(d.x) / ax) ** N_EXP + (abs(d.y) / AX["side"]) ** N_EXP + (abs(d.z) / az) ** N_EXP
    return 1.0 / s ** (1.0 / N_EXP)


def surface(d, extra=0.0):
    d = Vector(d).normalized()
    return d * (radius(d) + extra)


# 盔壳切面（与机身上表面同一语言：大块精确切面、棱线分明）：方位 az、仰角 el 处一张切平面，削进超椭球 depth 比例
FACETS = [(az * sg, el, depth) for sg in (1, -1) for az, el, depth in ((58, 14, 0.06), (100, 38, 0.05), (95, -6, 0.045), (140, 18, 0.05), (42, -30, 0.05))] + [(180, 40, 0.04)]


def facet_planes(extra=0.0):
    out = []
    for az, el, depth in FACETS:
        a, e = math.radians(az), math.radians(el)
        n = Vector((math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), math.sin(e)))
        out.append((n, radius(n) * (1 - depth) + extra))
    return out


def faceted(p, extra=0.0):
    """超椭球面上的点 → 被切平面削平（依次投影到越界的平面上）。"""
    for n, d in facet_planes(extra):
        h = p.dot(n) - d
        if h > 0:
            p = p - n * h
    return p


def quad_sphere(level=14, extra=0.0, facets=True):
    """立方体球：六个面各 level×level 格，每个顶点沿方向投到超椭球面上，再被切平面削出几块平面。"""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=2.0)
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=level - 1, use_grid_fill=True)
    for v in bm.verts:
        v.co = surface(v.co, extra)
        if facets:
            v.co = faceted(v.co, extra)
    bm.normal_update()
    return bm


def edges_of(poly, centre):
    cy = sum(y for y, _ in poly) / len(poly)
    cz = sum(z for _, z in poly) / len(poly)
    out = []
    for (y0, z0), (y1, z1) in zip(poly, poly[1:] + poly[:1]):
        ny, nz = z1 - z0, -(y1 - y0)
        L = math.hypot(ny, nz)
        ny, nz = ny / L, nz / L
        if (cy - y0) * ny + (cz - z0) * nz > 0:
            ny, nz = -ny, -nz
        out.append((y0, z0, ny, nz))
    return out


def grow(poly, d):
    cy = sum(y for y, _ in poly) / len(poly)
    cz = sum(z for _, z in poly) / len(poly)
    out = []
    for y, z in poly:
        r = math.hypot(y - cy, z - cz)
        out.append((y + (y - cy) / r * d, z + (z - cz) / r * d))
    return out


def inside(p, E, tol=0.0):
    return all((p.y - y0) * ny + (p.z - z0) * nz <= tol for y0, z0, ny, nz in E)


def cut_prism(bm, poly, keep_inside, front_only=True):
    """沿 x 方向的棱柱（前视多边形）切开曲面：切口是直的；keep_inside 决定留里面还是外面。"""
    E = edges_of(poly, None)
    sel = lambda f: (f.calc_center_median().x > 0.0) if front_only else True  # noqa: E731
    for y0, z0, ny, nz in E:
        geom = [f for f in bm.faces if sel(f)]
        bmesh.ops.bisect_plane(bm, geom=geom + list({e for f in geom for e in f.edges}) + list({v for f in geom for v in f.verts}),
                               dist=1e-6, plane_co=Vector((0, y0, z0)), plane_no=Vector((0, ny, nz)))
    dead = [f for f in bm.faces if sel(f) and (inside(f.calc_center_median(), E, 1e-6) != keep_inside)]
    if not front_only:
        dead = [f for f in bm.faces if inside(f.calc_center_median(), E, 1e-6) != keep_inside]
    bmesh.ops.delete(bm, geom=dead, context="FACES")


def solidify(bm, t, rim_bevel=0.0015):
    """向内加厚 t；开口一圈的边倒小角。"""
    bm.normal_update()
    res = bmesh.ops.solidify(bm, geom=bm.faces[:], thickness=t)
    bm.normal_update()
    if rim_bevel > 0:
        rim = [e for e in bm.edges if len(e.link_faces) == 2 and e.link_faces[0].normal.angle(e.link_faces[1].normal, 0) > math.radians(50)]
        if rim:
            bmesh.ops.bevel(bm, geom=rim, offset=rim_bevel, segments=2, profile=0.6, affect="EDGES", clamp_overlap=True)
    return res


def to_world(bm, M):
    bm.transform(M)


def build(body, props, state="soft"):
    """返回 (件列表, 头部标架 M, 铰链轴)。state：soft（透明面罩落下、遮光面罩收起）/ closed（遮光面罩也落下）。"""
    eyeL, eyeR = body.bone_head("eye.L"), body.bone_head("eye.R")
    ec = (eyeL + eyeR) / 2
    top = max(v.co.z for v in bpy.data.objects["xz.body.cap"].data.vertices)
    O = Vector((ec.x - 0.075, 0.0, ec.z + 0.012))
    M = Matrix.Translation(O)
    out = []
    P = dict(props)

    # —— 盔壳 ——
    bm = quad_sphere(30)
    # 下沿：水平面切，盔壳下沿就坐在颈环上
    bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], dist=1e-6, plane_co=Vector((0, 0, BOTTOM)), plane_no=Vector((0, 0, 1)), clear_inner=True)
    rim = [M @ v.co for v in bm.verts if abs(v.co.z - BOTTOM) < 1e-4]
    cut_prism(bm, OPENING, keep_inside=False)
    # 分块缝：前低后高的一道水平环缝（眉骨两端往后绕），后脑一道竖缝
    seams = []
    for co, no in (((0, 0, 0.03), Vector((0.18, 0, 1)).normalized()),):
        res = bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], dist=1e-6, plane_co=Vector(co), plane_no=no)
        for e in res["geom_cut"]:
            if isinstance(e, bmesh.types.BMEdge):
                e.seam = True
    bm.normal_update()
    for v in {v for e in bm.edges if e.seam for v in e.verts}:
        v.co = v.co - v.normal * 0.0005
    solidify(bm, SHELL_T)
    to_world(bm, M)
    shell = geo.obj_from_bm("xz.helmet.shell", bm, "helmet", P)
    geo.mark_sharp(shell, 22)
    out.append(("helmet", shell))

    out += details(M, P, rim, state)
    return out, M


def dir_(az, el):
    a, e = math.radians(az), math.radians(el)
    return Vector((math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), math.sin(e)))


def details(M, P, rim, state="soft", parts=("frame", "brow", "crest", "hinges", "vents", "rear", "visors", "neckring")):
    """盔壳以外的件（头部标架 M、超椭球 AX、面罩开口 OPENING 为准）：面框、眉骨、盔脊 + 朱红线、铰链、下巴通气缝、
    后脑模块、透明面罩、遮光面罩（形态键 down）、颈环（rim：盔壳下沿一圈点，世界坐标）。parts 选要哪些。"""
    out = []
    def S(d, extra=0.0):
        return M @ surface(d, extra)

    # —— 面框：沿开口一圈扫出来的连续框（眉骨 + 两颊 + 下巴护条一体），截面随位置变：上沿是前凸的切面眉骨，
    #    两侧收窄，下沿是下巴护条；面罩缩在框里 ——
    if "frame" in parts:
        out.append(("brow", face_frame(M, P)))
    # 眉骨：面框上沿正中的箭头形切面楔，前缘探出面罩 2.6 cm、往后收进盔脊——与座舱上方的机身眉骨同一语言
    ty = OPENING[0][1] + 0.005
    q = []
    b0, n0 = on_shell(0.0, ty + 0.004)
    q += [M @ (b0 + n0 * PROW + Vector((0.4 * PROW, 0, -0.006))), M @ (b0 + n0 * (PROW + 0.002) + Vector((0.004, 0, 0.004)))]
    for sg in (1, -1):
        b, n_ = on_shell(sg * 0.05, ty - 0.003)
        q += [M @ (b + n_ * 0.013), M @ (b + n_ * 0.006 + Vector((0, 0, -0.006)))]
        b, n_ = on_shell(sg * 0.014, ty + 0.06)
        q += [M @ (b + n_ * 0.010), M @ (b - n_ * 0.004)]
        b, n_ = on_shell(sg * 0.06, ty + 0.012)
        q += [M @ (b - n_ * 0.004)]
    b, n_ = on_shell(0.0, ty + 0.075)
    q += [M @ (b + n_ * 0.0095), M @ (b - n_ * 0.004)]
    q += [M @ (b0 - n0 * 0.004)]
    out.append(("brow", geo.hull("xz.helmet.brow", q, BROW_MAT, P, bevel=0.0012)))
    # —— 盔脊：眉骨后沿 → 盔顶 → 后脑（四段凸体），顶上嵌朱红细线 ——
    ridge = []
    els = [32, 52, 75, 100, 125, 150, 172]
    for k, (e0, e1) in enumerate(zip(els, els[1:])):
        q = []
        for e in (e0, e1):
            for a in (-7, 7):
                q += [S(dir_(0, e) * 1.0 + Vector((0, math.sin(math.radians(a)) * 0.9, 0)), -0.004), S(dir_(0, e) + Vector((0, math.sin(math.radians(a)) * 0.55, 0)), 0.009)]
        out.append(("helmet", geo.hull(f"xz.helmet.ridge{k}", q, "helmet", P, bevel=0.0012)))
        ridge.append(e0)
    line = [S(dir_(0, e), 0.0105) for e in np.linspace(34, 182, 40)]
    line += [S(dir_(180, e), 0.002) for e in np.linspace(-2, -7, 3)][1:]
    normals = [(p - M @ Vector()).normalized() for p in line]
    out.append(("spine", geo.ribbon("xz.helmet.crestline", line, normals, 0.004, 0.0012, "vermilion", P)))
    # —— 两侧铰链：圆盘 + 中心螺栓 ——
    for s, sg in (("l", 1), ("r", -1)):
        c = S(dir_(90 * sg, 4), 0.0)
        ax = Vector((0, sg, 0))
        out.append(("metal", geo.tube(f"xz.helmet.hinge.{s}", [c - ax * 0.004, c + ax * 0.009], 0.021, "brow", P, sides=24)))
        out.append(("metal", geo.tube(f"xz.helmet.hinge.{s}.bolt", [c + ax * 0.008, c + ax * 0.013], 0.007, "chrome", P, sides=6)))
    # —— 下巴护条：开口下沿外一块切面板，三道通气缝 ——
    for k, az in enumerate((-12, 0, 12) if "vents" in parts else ()):
        c = S(dir_(az, -36), 0.0135)
        R = geo.frame_from((c - M @ Vector()).normalized(), Vector((0, 0, 1)))
        out.append(("lens", geo.box(f"xz.helmet.chin.vent{k}", c, (0.004, 0.006, 0.02), R, "lens", P)))
    # —— 后脑模块（通讯 / 供氧接头）：楔形切面块，盔脊朱红线收进它的上沿；两只圆接头 ——
    q = []
    for az in range(152, 209, 8):
        w = 1 - abs(az - 180) / 30
        for e, x in ((-40, -0.004), (-38, 0.010 + 0.006 * w), (-20, 0.012 + 0.006 * w), (-8, 0.002), (-6, -0.004)):
            q.append(S(dir_(az, e), x))
    out.append(("helmet", geo.hull("xz.helmet.rear", q, "brow", P, bevel=0.0015)))
    for k, az in enumerate((170, 190)):
        c = S(dir_(az, -30), 0.019)
        d = (c - M @ Vector()).normalized()
        out.append(("metal", geo.tube(f"xz.helmet.rear.port{k}", [c - d * 0.004, c + d * 0.006], 0.007, "chrome", P, sides=12)))
    # 透明面罩在外（开口外扩 1.2 cm，四周压在面框下）；遮光面罩在盔壳里面（内藏式）。遮光面罩建在“落下”位置，
    # 再算“收起”位置：每个顶点在前视里上移 SLIDE、沿 x 贴回同一层曲面（离盔面的距离不变）——拓扑不变，
    # 所以收起 = 基础形，落下 = 形态键 down（glTF morph target），网页里拖一个权重就是“闭眼”
    for name, extra, thick, mat, glow in (("visor", 0.004, 0.0028, "glass", VISOR_GROW), ("sunvisor", SUN_EXTRA, 0.0022, "sunvisor", 0.008)):
        bm = quad_sphere(26, extra, facets=False)
        cut_prism(bm, grow(OPENING, glow), keep_inside=True, front_only=True)
        dead = [f for f in bm.faces if f.calc_center_median().x <= 0.0]
        bmesh.ops.delete(bm, geom=dead, context="FACES")
        solidify(bm, thick, rim_bevel=0.0008)
        down = None
        if name == "sunvisor":
            down = [v.co.copy() for v in bm.verts]
            for v in bm.verts:
                v.co = slide(v.co, SLIDE)
        bm.transform(M)
        o = geo.obj_from_bm(f"xz.helmet.{name}", bm, mat, {**P, "glass": True} if mat == "glass" else P)
        if down is not None:
            o.shape_key_add(name="Basis")
            k = o.shape_key_add(name="down")
            for i, c in enumerate(down):
                k.data[i].co = M @ c
            k.value = 1.0 if state == "closed" else 0.0
        out.append((name, o))
    # —— 颈环：按盔壳下沿实际一圈拟合圆心与半径；盔侧一圈 + 服装侧一圈（镀铬），两只锁扣 ——
    R_ = np.array([tuple(p) for p in rim])
    cx, cy = R_[:, 0].mean(), R_[:, 1].mean()
    rr = float(np.mean(np.hypot(R_[:, 0] - cx, R_[:, 1] - cy)))
    base = Vector((cx, cy, M.translation.z + BOTTOM - 0.012))
    for k, (z0, z1, r0, r1) in enumerate(((0.0, 0.013, rr + 0.002, rr + 0.004), (-0.017, 0.0, rr - 0.005, rr - 0.002))):
        prof = [(z0, r0 - 0.009), (z0, r0), (z1, r1), (z1, r1 - 0.009)]
        out.append(("chrome", lathe(f"xz.helmet.neckring{k}", base, prof, 48, "chrome", P)))
    for s, sg in (("l", 1), ("r", -1)):
        c = base + Vector((0.0, sg * (rr + 0.006), -0.002))
        out.append(("metal", geo.box(f"xz.helmet.neckring.latch.{s}", c, (0.03, 0.012, 0.022), Matrix.Identity(3), "metal", P, bevel=0.0015)))
    keep = []
    for kind, o in out:
        if "hinges" not in parts and o.name.startswith("xz.helmet.hinge"):
            bpy.data.objects.remove(o)
            continue
        keep.append((kind, o))
    return keep


def on_shell(y, z, extra=0.0):
    """前半盔壳上 (y, z) 处的点（沿 x 方向求交，头部局部坐标）与外法线。"""
    lo, hi = 0.0, 0.3
    for _ in range(40):
        x = (lo + hi) / 2
        p = Vector((x, y, z))
        if p.length < radius(p.normalized()) + extra:
            lo = x
        else:
            hi = x
    p = Vector(((lo + hi) / 2, y, z))
    e = 1e-3
    g = Vector([(surface_f(p + Vector(d) * e) - surface_f(p - Vector(d) * e)) for d in ((1, 0, 0), (0, 1, 0), (0, 0, 1))]).normalized()
    return p, g


def slide(p, dz):
    """头部局部坐标的点 p：保持它离盔面的距离 e，在前视里上移 dz，沿 x 重新贴到同一层曲面上。"""
    e = p.length - radius(p.normalized())
    q, _ = on_shell(p.y, p.z + dz, e)
    return q


def surface_f(p):
    """隐式函数：> 0 在外。"""
    d = p.normalized()
    return p.length - radius(d)


def face_frame(M, P, n=96):
    """沿面罩开口（外扩 5 mm）扫一圈截面：t ∈ [0, 1) 绕开口一周（0 = 上沿正中）。截面在 (外法线 nrm, 背离开口的切向 m) 平面里：
    内唇 → 外凸顶 → 外缘落回盔面；上沿正中的顶最高、最宽（眉骨），往两侧收、下沿再加宽成下巴护条。"""
    poly = grow(OPENING, 0.005)
    # 多边形按弧长重采样 n 点，从上沿正中开始
    pts = [Vector((0, y, z)) for y, z in poly]
    L = [0.0]
    for a, b in zip(pts, pts[1:] + pts[:1]):
        L.append(L[-1] + (b - a).length)
    tot = L[-1]
    samp = []
    for k in range(n):
        d = tot * k / n
        i = max(j for j in range(len(pts)) if L[j] <= d)
        a, b = pts[i], pts[(i + 1) % len(pts)]
        f = (d - L[i]) / max(L[i + 1] - L[i], 1e-9)
        samp.append(a.lerp(b, f))
    cy = sum(p.y for p in pts) / len(pts)
    cz = sum(p.z for p in pts) / len(pts)
    bm = bmesh.new()
    rows = []
    for k, q in enumerate(samp):
        base, nrm = on_shell(q.y, q.z)
        out_ = Vector((0, q.y - cy, q.z - cz))
        m = (out_ - nrm * out_.dot(nrm)).normalized()
        up = max(0.0, (q.z - cz) / 0.05)  # 上沿 → 1
        dn = max(0.0, (cz - q.z) / 0.05)
        mid = max(0.0, 1 - abs(q.y) / 0.07)
        brow = up * (0.35 + 0.65 * mid ** 1.4)
        h = 0.007 + 0.016 * brow + 0.004 * dn   # 高出盔面
        w = 0.016 + 0.02 * brow + 0.012 * dn    # 往外的宽度
        tip = 0.004 + 0.012 * brow              # 眉骨前缘往开口里探出
        prof = [(-tip, -0.003), (-tip, h * 0.55), (0.004, h), (w * 0.55, h * 0.92), (w, h * 0.35), (w + 0.006, 0.0), (w + 0.006, -0.006), (-tip, -0.006)]
        rows.append([bm.verts.new(M @ (base + m * a + nrm * b)) for a, b in prof])
    mlen = len(rows[0])
    for A, B in zip(rows, rows[1:] + rows[:1]):
        for j in range(mlen):
            bm.faces.new((A[j], A[(j + 1) % mlen], B[(j + 1) % mlen], B[j]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    o = geo.obj_from_bm("xz.helmet.frame", bm, "brow", P)
    geo.mark_sharp(o, 28)
    return o


def lathe(name, c, prof, n, mat, props):
    """绕竖直轴的车削体：prof = [(z, r), …]（闭合截面）。"""
    bm = bmesh.new()
    rows = []
    for i in range(n):
        a = 2 * math.pi * i / n
        rows.append([bm.verts.new(c + Vector((r * math.cos(a), r * math.sin(a), z))) for z, r in prof])
    m = len(prof)
    for i in range(n):
        A, B = rows[i], rows[(i + 1) % n]
        for j in range(m):
            bm.faces.new((A[j], A[(j + 1) % m], B[(j + 1) % m], B[j]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    o = geo.obj_from_bm(name, bm, mat, props)
    geo.mark_sharp(o, 50)
    return o
