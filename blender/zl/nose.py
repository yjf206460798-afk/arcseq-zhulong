"""烛龙机头段 · 复刻样板（s 0～7.6 m）：外形对 refs/concept/C2 叠图，内部见 interior.py（对 refs/layout/K1）。

外形（C2 实测，见 review/20261015-Z1-replica/SUMMARY.md 的量图表）：
  前机身是**一个棱锥**：背脊、朱红脊线、棱线（最宽）、腹缘、龙骨五条棱都是汇向机头前方 0.35 m 那一点（APEX）的直线，
  所以每张切面严格是平面；机头尖在 s 0.02 处截平，截面上开眼窝放烛光窗眼珠。背脊在 s 6.4 之后放平（C2 座舱后背线水平）。
  截面（半边，从背脊顺时针）：R0 背脊 → 屋面（约 41°）→ R1 朱红脊线 → 外上切面（约 63°，C2 里那条暗带）→ R2 棱线（最宽）
  → 下切面（约 62°，鳞片瓦）→ R3 腹缘 → 平腹底。
  每单位 t = s + 0.35：R0 z +0.182t；R1 (0.135t, +0.065t)；R2 (0.150t, +0.035t)；R3 (0.070t, −0.118t)；z 相对机头尖 Z_TIP。
"""
import math

import bmesh
import bpy
from mathutils import Matrix, Vector

from kit.finish import finish
from kit.parts import connector, cylinder, hull, new_object, pipe

from .util import XN, at, boolean, lerp, mirror_object

Z_TIP = 1.65
APEX_S = -0.35
S_FRONT = 0.36  # 机身前端面（眼窝所在）；前面是眼珠与虹膜尖盖
S_END = 7.6
S_FLAT = 6.4  # 背脊在此之后放平
K = {"R0": (0.0, 0.182), "R1": (0.135, 0.065), "R2": (0.150, 0.035), "R3": (0.070, -0.118)}
EYE = {"s": 0.33, "r": 0.086, "z": 0.01}  # C2 三视图实测：眼心 s≈0.32、半径约 0.09，略高于机头尖线
IRIS_CLOSED = False  # 停机是睁眼：虹膜六瓣收起，看得见角膜后的光圈与瞳孔（作者 R4）
CAP_S, CAP_R = 0.264, 0.055  # 虹膜尖盖：长到 s 0.25（眼珠前极稍后），底半径 = 眼珠在该站位的截面半径
FRAMES = [0.67, 1.25, 2.05, 3.1, 3.9, 4.75, 6.95]  # 结构框站位（K1 的舱壁）
EDGES = {}  # 对象名 → 线数据（finish 的输出），build() 写进 meta


def ring(s):
    t = s - APEX_S
    out = {k: (a * t, Z_TIP + b * t) for k, (a, b) in K.items()}
    if s > S_FLAT:
        out["R0"] = (0.0, Z_TIP + K["R0"][1] * (S_FLAT - APEX_S))
    return out


def spine_z(s):
    return ring(s)["R0"][1]


def top_profile(s):
    """剖切面（y = 0）上的外形顶线：背脊，加上眉骨（s 3.9～4.78 隆起）与座舱后的背部整流。"""
    z = spine_z(s)
    s0, s1, s2 = BROW
    if s0 <= s <= s2:
        z = max(z, lerp(spine_z(s0), spine_z(s1) + 0.1, min(1.0, (s - s0) / (s1 - s0))))
    if s >= 6.85:
        z = max(z, Z_TIP + lerp(1.27, 1.285, (s - 6.85) / (S_END - 6.85)))
    return z


FACETS = {"roof": ("R0", "R1"), "outer": ("R1", "R2"), "lower": ("R2", "R3")}


def surface(s, facet, t, side=1, lift=0.0):
    """切面上的点与外法线：facet 为 "roof" / "outer" / "lower" / "belly"；t 为两棱之间的比例（belly：0 腹缘 → 1 中线）。"""
    R = ring(s)
    if facet == "belly":
        y = R["R3"][0] * (1 - t) * side
        return at(s, y, R["R3"][1]) + Vector((0, 0, -lift)), Vector((0, 0, -1))
    a, b = FACETS[facet]
    p = at(s, lerp(R[a][0], R[b][0], t) * side, lerp(R[a][1], R[b][1], t))
    n = facet_normal(s, facet, side)
    return p + n * lift, n


def facet_normal(s, facet, side=1):
    if facet == "belly":
        return Vector((0, 0, -1))
    a, b = FACETS[facet]
    s0, s1 = max(s - 0.05, S_FRONT), min(s + 0.05, S_END)
    R0, R1 = ring(s0), ring(s1)
    p00 = at(s0, R0[a][0] * side, R0[a][1])
    p01 = at(s0, R0[b][0] * side, R0[b][1])
    p10 = at(s1, R1[a][0] * side, R1[a][1])
    n = (p01 - p00).cross(p10 - p00).normalized()
    mid = (p00 + p01) / 2
    if n.dot(mid - Vector((mid.x, 0, Z_TIP - 0.1))) < 0:
        n = -n
    return n


def roof_z(s, y):
    """屋面（背脊到朱红脊线）在 |y| 处的高度；超出脊线按外上切面。"""
    R = ring(s)
    y = abs(y)
    if y <= R["R1"][0]:
        return lerp(R["R0"][1], R["R1"][1], y / R["R1"][0])
    return lerp(R["R1"][1], R["R2"][1], min(1.0, (y - R["R1"][0]) / (R["R2"][0] - R["R1"][0])))


# —— 机身蒙皮 ————————————————————————————————————————————————
COLS = {"roof": 4, "outer": 2, "lower": 4}


def section_points(s):
    """整圈截面点（左：R0→R1→R2→R3，腹底 6 格，右：R3'→…→R1'），每点带它所在切面的材质。"""
    R = ring(s)
    left = []
    for name, (a, b) in FACETS.items():
        n = COLS[name]
        for i in range(n):
            t = i / n
            left.append(((lerp(R[a][0], R[b][0], t), lerp(R[a][1], R[b][1], t)), name))
    left.append((R["R3"], "belly"))
    belly = [((lerp(R["R3"][0], -R["R3"][0], i / 6), R["R3"][1]), "belly") for i in range(1, 6)]
    right = [((-y, z), m) for (y, z), m in reversed(left[1:])]
    return left + belly + right


def stations():
    s = [S_FRONT]
    x = 0.4
    while x < S_END - 1e-6:
        s.append(round(x, 3))
        x += 0.1
    return sorted(set([round(v, 4) for v in s + [S_FLAT, S_END] + FRAMES]))


def body():
    bm = bmesh.new()
    rings = []
    for s in stations():
        rings.append([bm.verts.new(at(s, y, z)) for (y, z), _ in section_points(s)])
    n = len(rings[0])
    for A, B in zip(rings, rings[1:]):
        for i in range(n):
            bm.faces.new((A[i], A[(i + 1) % n], B[(i + 1) % n], B[i]))
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    obj = new_object("nose.body", bm, "hull", {"skin": "skin", "cut": True})
    for m in ("belly", "interior"):
        obj.data.materials.append(bpy.data.materials.get(m) or bpy.data.materials.new(m))
    return obj


def assign_body_materials(obj):
    """上表面 hull、棱线以下 belly（鳞片瓦区）、前后端面 interior。"""
    for f in obj.data.polygons:
        c = f.center
        s = XN - c.x
        if abs(f.normal.x) > 0.95 and (s < S_FRONT + 0.03 or s > S_END - 0.03):
            f.material_index = 2
            continue
        R = ring(min(max(s, S_FRONT), S_END))
        f.material_index = 1 if c.z < R["R2"][1] - 2e-3 else 0


# —— 烛光窗眼珠：夹在虹膜尖盖与机身眼窝之间（C2 三视图都画成一个整圆，见 DESIGN 8.6） ——————————————
def eye_centre():
    return at(EYE["s"], 0, Z_TIP + EYE["z"])


def cap_radius(s):
    """虹膜尖盖（六瓣合拢）的母线：s 0 处尖、s CAP_S 处半径 CAP_R、底部切线水平（正切卵形）。"""
    f = min(max(s / CAP_S, 0.0), 1.0)
    return CAP_R * math.sin(f * math.pi / 2) ** 0.55


def eye():
    c = eye_centre()
    r = EYE["r"]
    out = []

    def torus(name, centre_s, radius, minor, mat, props, sides=8, segs=72, squash=1.0):
        bm = bmesh.new()
        grid = []
        for i in range(segs):
            phi = 2 * math.pi * i / segs
            radial = Vector((0, math.cos(phi), math.sin(phi)))
            row = []
            for k in range(sides):
                th = 2 * math.pi * k / sides
                p = Vector((XN - centre_s + minor * math.sin(th) * squash, 0, c.z)) + radial * (radius + minor * math.cos(th))
                row.append(bm.verts.new(p))
            grid.append(row)
        for i in range(segs):
            A, B = grid[i], grid[(i + 1) % segs]
            for k in range(sides):
                bm.faces.new((A[k], B[k], B[(k + 1) % sides], A[(k + 1) % sides]))
        o = new_object(name, bm, mat, props)
        EDGES[o.name] = finish(o, bevel=0, curved=True)
        return o

    # 眼珠：深色烟晶玻璃球，分两件——前极“角膜”（根环以内，透明，看得见里面的虹膜与瞳孔）+ 其余眼球（暗烟晶，通电只透出暗琥珀）。
    # 停机（大气内）是睁眼：六瓣虹膜收进眼眶（DESIGN 8.6：合拢成尖盖是高超音速 / 再入的闭眼态，开合机构 Z4 做）
    def ball(front):
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=64, v_segments=40, radius=r)
        bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, "Y"))
        bmesh.ops.translate(bm, verts=bm.verts, vec=c)
        # 只留机身前端面以前的部分（断口藏在密封圈与内圈台阶环后面）
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if XN - v.co.x > S_FRONT - 0.002], context="VERTS")
        cut = [f for f in bm.faces if ((XN - f.calc_center_median().x) < CAP_S) != front]
        bmesh.ops.delete(bm, geom=cut, context="FACES")
        return bm

    o = new_object("sensor.ball", ball(False), "sensor", {"skin": "sensor.ball"})  # 眼球不发光（不要“发光环”），只有瞳孔是“烛”
    EDGES[o.name] = finish(o, bevel=0, curved=True)
    out.append(o)
    o = new_object("sensor.cornea", ball(True), "glass", {"skin": "sensor.cornea", "glass": True, "opacity": 0.22})
    EDGES[o.name] = finish(o, bevel=0, curved=True)
    out.append(o)
    # 角膜后面：虹膜光圈（六片 1.2 mm 叶片，内缘拼成六边形瞳孔、外缘一段圆弧，片间错叠）→ 瞳孔透镜（通电是“烛”的亮点）
    s_i = CAP_S + 0.017
    ra, ro = 0.03, 0.062
    for k in range(6):
        th = math.radians(60 * k)
        pts = []
        for a_ in (-30, 30):
            ang = th + math.radians(a_)
            rr = ra / math.cos(math.radians(30))
            pts.append((math.cos(ang) * rr, math.sin(ang) * rr))
        for a_ in range(-40, 41, 10):
            ang = th + math.radians(a_)
            pts.append((math.cos(ang) * ro, math.sin(ang) * ro))
        ds = 0.0009 * k
        P = [at(s_i + ds + d, y, c.z + z) for y, z in pts for d in (0.0, 0.0012)]
        o, l = hull(f"sensor.iris.blade{k}", P, "chrome", {"skin": f"sensor.iris.blade{k}", "lineLevel": "secondary", "aoFlat": True}, bevel=0.0)
        EDGES[o.name] = l
        out.append(o)
    out.append(torus("sensor.iris.housing", s_i + 0.003, ro + 0.004, 0.0045, "carbon", {"skin": "sensor.iris.housing", "lineLevel": "secondary", "aoFlat": True}))
    # 瞳孔里一片圆镜片（R4 作者：要看得到圆形镜片——镜片在叶片前，半径 2.4 cm 小于六边形瞳孔的内切圆 2.6 cm，读成圆），
    # 镜片中心一粒暗色内镜（像眼睛的瞳仁）；通电时琥珀色镜片是“烛”。叶片与座圈在眼球腔里，顶点 AO 会把它们压成一片黑，不烘（aoFlat）
    def dome(name, s_, rad, depth, mat, props):
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=40, v_segments=12, radius=1.0)
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.x < -1e-6], context="VERTS")
        bmesh.ops.scale(bm, verts=bm.verts, vec=(depth, rad, rad))
        bmesh.ops.translate(bm, verts=bm.verts, vec=at(s_, 0, c.z))
        o_ = new_object(name, bm, mat, props)
        EDGES[o_.name] = finish(o_, bevel=0, curved=True)
        return o_

    out.append(dome("sensor.lens", s_i - 0.001, 0.024, 0.006, "sensor", {"skin": "sensor.lens", "glow": {"key": "sensor", "color": "#ffb060"}, "aoFlat": True}))
    out.append(dome("sensor.pupil", s_i - 0.0055, 0.0085, 0.003, "carbon", {"skin": "sensor.pupil", "lineLevel": "secondary", "aoFlat": True}))
    if IRIS_CLOSED:
        out += iris_cap(c)
    # 根环：角膜边上一圈（虹膜六瓣铰在这一圈上，铰轴是这圈的切线，Z4 做开合）
    out.append(torus("sensor.iris.ring", CAP_S - 0.002, CAP_R + 0.0005, 0.0032, "metal", {"skin": "sensor.iris.ring", "lineLevel": "secondary"}))
    # 多层眼眶：机身前端面上外圈压边环、内圈台阶环，眼珠与眼窝之间一圈橡胶密封圈
    sf = S_FRONT
    # 外圈压边环比机身端面略大（C2 三个视图里眼珠外都有一圈浅色的环），浅金属色
    for name, r0, r1, d0, d1, mat in (("sensor.socket.outer", r * 1.04, r * 1.32, -0.01, 0.004, "metal"), ("sensor.socket.inner", r * 0.985, r * 1.04, -0.004, 0.012, "carbon")):
        bm = bmesh.new()
        n = 72
        rings_ = []
        for rad, ds in ((r0, d0), (r1, d0), (r1, d1), (r0, d1)):
            rings_.append([bm.verts.new(Vector((XN - sf - ds, math.cos(2 * math.pi * k / n) * rad, c.z + math.sin(2 * math.pi * k / n) * rad))) for k in range(n)])
        for A, B in zip(rings_, rings_[1:] + rings_[:1]):
            for k in range(n):
                j = (k + 1) % n
                bm.faces.new((A[k], A[j], B[j], B[k]))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        o = new_object(name, bm, mat, {"skin": name, "lineLevel": "secondary"})
        EDGES[o.name] = finish(o, bevel=0.0015, angle=45)
        out.append(o)
    seal_r = math.sqrt(r * r - (EYE["s"] - sf + 0.006) ** 2) + 0.002
    out.append(torus("sensor.seal", sf - 0.006, seal_r, 0.0026, "rubber", {"skin": "sensor.seal", "lineLevel": "secondary"}))
    return out


def iris_cap(c):
    """闭眼态：六瓣虹膜合拢成机头尖盖（卵形，s 0 → CAP_S，每瓣厚 2.5 mm、瓣间 1 mm 缝）+ 尖端钛针。停机睁眼时不建（IRIS_CLOSED）。"""
    out = []
    n_s, n_az = 14, 10
    for k in range(6):
        gap = 0.0005 / CAP_R
        a0, a1 = k * math.pi / 3 + gap, (k + 1) * math.pi / 3 - gap
        bm = bmesh.new()
        layers = []
        for off in (0.0, -0.0025):
            rows = []
            for i in range(n_s + 1):
                ss = lerp(0.004, CAP_S, (i / n_s) ** 0.8)
                rad = max(cap_radius(ss) + off, 0.0008)
                rows.append([bm.verts.new(at(ss, math.cos(lerp(a0, a1, j / n_az)) * rad, c.z + math.sin(lerp(a0, a1, j / n_az)) * rad)) for j in range(n_az + 1)])
            layers.append(rows)
        outer, inner = layers
        for L, flip in ((outer, False), (inner, True)):
            for A, B in zip(L, L[1:]):
                for j in range(n_az):
                    f = (A[j], B[j], B[j + 1], A[j + 1])
                    bm.faces.new(tuple(reversed(f)) if flip else f)
        for i in range(n_s):
            for j in (0, n_az):
                bm.faces.new((outer[i][j], inner[i][j], inner[i + 1][j], outer[i + 1][j]))
        for i in (0, n_s):
            for j in range(n_az):
                bm.faces.new((outer[i][j], outer[i][j + 1], inner[i][j + 1], inner[i][j]))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        o = new_object(f"sensor.iris.{k}", bm, "hull", {"skin": f"sensor.iris.{k}"})
        EDGES[o.name] = finish(o, bevel=0.0006, curved=True)
        out.append(o)
    # 尖针：六瓣尖端汇合处一根 3 cm 的钛针（盖住汇合点）
    o, l = cylinder("sensor.pin", at(-0.012, 0, c.z), at(0.035, 0, c.z), 0.0012, 10, "chrome", {"skin": "sensor.pin", "lineLevel": "secondary"}, r2=cap_radius(0.035) * 0.8)
    EDGES[o.name] = l
    out.append(o)
    return out


def socket_cutter():
    """眼窝：机身前端面上一个浅圆坑（半径 = 眼珠在端面处的截面 + 3 mm，深 1.5 cm），眼珠的后部藏在里面。"""
    c = eye_centre()
    rad = math.sqrt(EYE["r"] ** 2 - (S_FRONT - EYE["s"]) ** 2) + 0.003
    bm = bmesh.new()
    n = 64
    for ds in (-0.02, 0.015):
        for k in range(n):
            a = 2 * math.pi * k / n
            bm.verts.new(at(S_FRONT + ds, math.cos(a) * rad, c.z + math.sin(a) * rad))
    bmesh.ops.convex_hull(bm, input=list(bm.verts))
    return new_object("cut.socket", bm)


# —— 眉骨、遮光盾、背部整流 ——————————————————————————————————
BROW = (3.9, 4.72, 4.78)  # 前尖、顶峰、后端面


def brow():
    """眉骨：座舱前一道向前的 V 形脊（K1 ⑤，s 3.9～4.78），后端面高出背线约 10 cm，里面是遮光盾的收纳槽。"""
    s0, s1, s2 = BROW
    pts = [at(s0, 0, spine_z(s0) - 0.04)]
    for side in (1, -1):
        for s, y, dz in ((4.3, 0.16, 0.05), (s1, 0.34, 0.08), (s2, 0.34, 0.08), (4.55, 0.3, 0.06)):
            pts.append(at(s, y * side, roof_z(s, y) + dz))
        for s, y in ((s0, 0.0), (4.3, 0.2), (s1, 0.36), (s2, 0.36)):
            pts.append(at(s, y * side, roof_z(s, y) - 0.06))
    pts += [at(s1, 0, spine_z(s1) + 0.1), at(s2, 0, spine_z(s2) + 0.1)]
    bm = bmesh.new()
    vs = [bm.verts.new(p) for p in pts]
    bmesh.ops.convex_hull(bm, input=vs)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    return new_object("brow", bm, "hull")


SLOT_DZ = 0.04  # 收纳槽中心离屋面的高度（眉骨顶比屋面高 8～10 cm）


def slot_cutter():
    """收纳槽：眉骨后端面上一道扁槽（高 2.5 cm、半宽 0.28 m、深 0.3 m），顺着屋面坡度做成帐篷形（左右两半各一块凸体）。"""
    s2 = BROW[2]
    out = []
    for side in (1, -1):
        pts = [at(s, y * side, roof_z(s, y) + SLOT_DZ + dz) for s in (s2 + 0.05, s2 - 0.3) for y in (0.0, 0.28) for dz in (-0.0125, 0.0125)]
        bm = bmesh.new()
        vs = [bm.verts.new(p) for p in pts]
        bmesh.ops.convex_hull(bm, input=vs)
        out.append(new_object(f"cut.slot.{'lr'[side < 0]}", bm))
    return out


def shield():
    """遮光盾（收起）：两片帐篷形钛板（左右各一，中线对接），槽里露出 3 cm 的前缘；Z4 做沿滑轨滑出盖住座舱盖的机构。"""
    s2 = BROW[2]
    out = []
    for side in (1, -1):
        pts = [at(s, y * side, roof_z(s, y) + SLOT_DZ + dz) for s in (s2 - 0.03, s2 - 0.28) for y in (0.0, 0.26) for dz in (-0.006, 0.006)]
        o, l = hull(f"shield.{'lr'[side < 0]}", pts, "metal", {"skin": "shield", "joint": "shield"}, bevel=0.002)
        EDGES[o.name] = l
        out.append(o)
    return out


def fairing():
    """座舱后的背部整流（并进机身）：C2 背线 s 6.95～7.6 平在机头尖以上 1.285 m。"""
    pts = []
    for s, top, (ys, zs), yb in ((6.85, 1.27, (0.13, 1.25), 0.22), (S_END, 1.285, (0.2, 1.255), 0.32)):
        pts.append(at(s, 0, Z_TIP + top))
        for side in (1, -1):
            pts.append(at(s, ys * side, Z_TIP + zs))
            pts.append(at(s, yb * side, roof_z(s, yb) - 0.04))
        pts.append(at(s, 0, spine_z(s) - 0.06))
    bm = bmesh.new()
    vs = [bm.verts.new(p) for p in pts]
    bmesh.ops.convex_hull(bm, input=vs)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    return new_object("fairing", bm, "hull")


# —— 座舱盖：低矮宝石形（C2 俯视 s 4.78～7.0，最宽 ±0.42；侧视顶高 +1.29） ————————————————
CANOPY = [  # (s, 顶高 rel, 肩 (y, z rel), 底宽)
    (4.80, 0.99, (0.10, 0.97), 0.16),
    (5.20, 1.18, (0.20, 1.14), 0.33),
    (5.60, 1.29, (0.25, 1.25), 0.42),
    (6.25, 1.29, (0.25, 1.25), 0.42),
    (7.00, 1.25, (0.10, 1.23), 0.15),
]
BOW_S = 5.85


def canopy():
    out = []

    def pts(rows, grow=0.0, drop=0.03):
        P = []
        for s, top, (ys, zs), yb in rows:
            P.append(at(s, 0, Z_TIP + top + grow))
            for side in (1, -1):
                P.append(at(s, (ys + grow) * side, Z_TIP + zs + grow))
                P.append(at(s, (yb + grow) * side, roof_z(s, yb + grow) + 0.001))
                P.append(at(s, (yb + grow) * side, roof_z(s, yb + grow) - drop))
            P.append(at(s, 0, spine_z(s) - drop))
        return P

    def interp(s):
        for a, b in zip(CANOPY, CANOPY[1:]):
            if a[0] <= s <= b[0]:
                f = (s - a[0]) / (b[0] - a[0])
                return (s, lerp(a[1], b[1], f), (lerp(a[2][0], b[2][0], f), lerp(a[2][1], b[2][1], f)), lerp(a[3], b[3], f))
        return CANOPY[-1]

    front = [r for r in CANOPY if r[0] < BOW_S] + [interp(BOW_S - 0.025)]
    rear = [interp(BOW_S + 0.025)] + [r for r in CANOPY if r[0] > BOW_S]
    for name, rows in (("canopy.glass.front", front), ("canopy.glass.rear", rear)):
        o, l = hull(name, pts(rows), "glass", {"skin": "glass", "glass": True, "cut": True, "section": "shell"}, bevel=0.004)
        EDGES[o.name] = l
        out.append(o)
    # 框：弓形框（有厚度，高出玻璃 1 cm）、两侧窗槛（沿底边的厚条）、前风挡框
    o, l = hull("canopy.bow", pts([interp(BOW_S - 0.03), interp(BOW_S + 0.03)], grow=0.012, drop=0.035), "frame", {"skin": "canopy.frame", "cut": True}, bevel=0.004)
    EDGES[o.name] = l
    out.append(o)
    for side, tag in ((1, "l"), (-1, "r")):
        P = []
        for s, _, _, yb in CANOPY:
            for dy in (-0.02, 0.025):
                y = (yb + dy) * side
                P += [at(s, y, roof_z(s, abs(y)) - 0.02), at(s, y, roof_z(s, abs(y)) + 0.045)]
        # 窗槛按两段凸体拼（前段、后段），中间在最宽处断开
        for k, (i0, i1) in enumerate(((0, 3), (2, 5))):
            sub = [p for j, p in enumerate(P) if i0 * 4 <= j < i1 * 4]
            o, l = hull(f"canopy.sill.{k}.{tag}", sub, "frame", {"skin": "canopy.frame", "cut": True}, bevel=0.005)
            EDGES[o.name] = l
            out.append(o)
        # 密封条：玻璃底边与窗槛之间一圈黑橡胶（管，半径 5 mm）
        line = [at(s, (yb - 0.005) * side, roof_z(s, yb) + 0.046) for s, _, _, yb in CANOPY]
        o, l = pipe(f"canopy.seal.{tag}", line, 0.005, bend=0.2, sides=6, material="rubber", props={"skin": "canopy.seal", "lineLevel": "secondary", "cut": True})
        EDGES[o.name] = l
        out.append(o)
        # 铰链：后端两只铰链座（块 + 销）
        s = 6.93
        y = 0.12 * side
        z = roof_z(s, 0.12) + 0.02
        o, l = hull(f"canopy.hinge.{tag}", [at(s + ds, y + dy, z + dz) for ds in (-0.05, 0.05) for dy in (-0.018, 0.018) for dz in (-0.02, 0.03)], "frame", {"skin": f"canopy.hinge.{tag}", "cut": True}, bevel=0.003)
        EDGES[o.name] = l
        out.append(o)
        o, l = cylinder(f"canopy.hinge.pin.{tag}", at(s, y - 0.03, z + 0.03), at(s, y + 0.03, z + 0.03), 0.009, 12, "metal", {"skin": f"canopy.hinge.pin.{tag}", "cut": True})
        EDGES[o.name] = l
        out.append(o)
    return out


# —— 滑轨与滚轮座、鸭翼、姿控喷口、探头、天线、朱红嵌条 ——————————————————
RAIL_Y = 0.5


def rails():
    out = []
    for side, tag in ((1, "l"), (-1, "r")):
        P = []
        for s in (BROW[2], S_END):
            for dy in (-0.015, 0.015):
                y = RAIL_Y + dy
                z = roof_z(s, y)
                P += [at(s, y * side, z - 0.01), at(s, y * side, z + 0.022)]
        o, l = hull(f"shield.rail.{tag}", P, "frame", {"skin": f"shield.rail.{tag}"}, bevel=0.004)
        EDGES[o.name] = l
        out.append(o)
        # 滚轮座：每 0.45 m 一个（座块 + 滚轮）
        s = BROW[2] + 0.2
        k = 0
        while s < S_END - 0.1:
            z = roof_z(s, RAIL_Y)
            o, l = hull(f"shield.roller.{k}.{tag}", [at(s + ds, (RAIL_Y + dy) * side, z + dz) for ds in (-0.04, 0.04) for dy in (-0.03, 0.03) for dz in (0.0, 0.035)], "metal", {"skin": f"shield.roller.{k}.{tag}", "lineLevel": "secondary"}, bevel=0.003)
            EDGES[o.name] = l
            out.append(o)
            o, l = cylinder(f"shield.roller.wheel.{k}.{tag}", at(s, (RAIL_Y - 0.036) * side, z + 0.035), at(s, (RAIL_Y + 0.036) * side, z + 0.035), 0.016, 14, "rubber", {"skin": f"shield.roller.wheel.{k}.{tag}", "lineLevel": "secondary"})
            EDGES[o.name] = l
            out.append(o)
            s += 0.45
            k += 1
    return out


def mirror_lines(data):
    """线数据 y 取反（点与两侧法线）。"""
    out = list(data)
    for i in range(0, len(out), 12):
        for j in (1, 4, 7, 10):
            out[i + j] = -out[i + j]
    return out


def canards():
    """鸭翼（C2 俯视：根弦 s 5.35～6.5，梢弦 6.2～6.45，展长 0.65 m；侧视在棱线下方）+ 转轴整流包。"""
    out = []
    zc = ring(6.0)["R2"][1] - 0.03

    def yroot(s):
        R = ring(s)
        f = (R["R2"][1] - zc) / (R["R2"][1] - R["R3"][1])
        return lerp(R["R2"][0], R["R3"][0], f) - 0.025

    P = []
    for s_le, s_te, span, th in ((5.35, 6.5, 0.0, 0.05), (6.2, 6.45, 0.65, 0.016)):
        y = yroot(6.0) + span
        m = (s_le + s_te) / 2
        P += [at(s_le, y, zc), at(s_te, y, zc), at(m, y, zc + th / 2), at(m, y, zc - th / 2)]
    left = []
    o, l = hull("canard.l", P, "hull", {"skin": "canard.l", "joint": "canard.l"}, bevel=0.006)
    EDGES[o.name] = l
    left.append(o)
    # 转轴整流：根部中弦下方一只扁梭形包（长 0.42、宽 0.09、高 0.07）
    s = 5.95
    y = yroot(s) + 0.01
    pod = [at(s + ds, y + dy, zc + dz) for ds, dy, dz in ((0.21, 0, -0.01), (-0.21, 0, -0.01), (0, 0.045, -0.02), (0, 0.045, -0.06), (0, -0.04, -0.06), (0.1, 0.035, -0.045), (-0.1, 0.035, -0.045), (0, 0.0, 0.0))]
    o2, l2 = hull("canard.fairing.l", pod, "hull", {"skin": "canard.fairing.l"}, bevel=0.01)
    EDGES[o2.name] = l2
    left.append(o2)
    for o in left:
        out.append(o)
        r = mirror_object(o, o.name.replace(".l", ".r"))
        EDGES[r.name] = mirror_lines(EDGES[o.name])
        r["skin"] = o["skin"].replace(".l", ".r")
        if "joint" in o.keys():
            r["joint"] = o["joint"].replace(".l", ".r")
        out.append(r)
    return out


def rcs():
    """机头姿态推进器（K1 ③，s 1.3～1.6）：外上切面两个、下切面一个带格栅的喷口；口是内凹 2 cm 的空腔，横格栅 4 片。"""
    out = []
    ports = [("outer", 1.38, 0.5, 0.07, 0.05), ("outer", 1.56, 0.5, 0.07, 0.05), ("lower", 1.47, 0.35, 0.08, 0.05)]
    for side, tag in ((1, "l"), (-1, "r")):
        for k, (facet, s, t, ls, ws) in enumerate(ports):
            n = facet_normal(s, facet, side)
            c, _ = surface(s, facet, t, side)
            # 切面内的两条方向：沿机身、沿切面横向
            u = (surface(s + 0.1, facet, t, side)[0] - c).normalized()
            v = n.cross(u).normalized()
            # 空腔（凹 2 cm）：开口薄片 + 四面口壁，空腔着色
            pts = [c + u * a * ls / 2 + v * b * ws / 2 + n * d for a in (-1, 1) for b in (-1, 1) for d in (0.002, -0.02)]
            o, l = hull(f"rcs.{k}.{tag}", pts, "void", {"system": "void", "skin": f"rcs.{k}.{tag}", "shadow": False, "aoOccluder": False}, bevel=0.0)
            EDGES[o.name] = l
            out.append(o)
            # 格栅：4 片横板（宽 3 mm、伸出口面 2 mm）
            for g in range(4):
                gu = (g + 0.5) / 4 - 0.5
                pts = [c + u * (gu * ls + a * 0.0015) + v * b * ws * 0.48 + n * d for a in (-1, 1) for b in (-1, 1) for d in (0.003, -0.015)]
                o, l = hull(f"rcs.{k}.vane{g}.{tag}", pts, "metal", {"skin": f"rcs.{k}.vanes.{tag}", "lineLevel": "secondary"}, bevel=0.0)
                EDGES[o.name] = l
                out.append(o)
            # 口框：一圈 6 mm 宽的凸框
            pts = [c + u * a * (ls / 2 + 0.008) + v * b * (ws / 2 + 0.008) + n * d for a in (-1, 1) for b in (-1, 1) for d in (0.004, -0.003)]
            # 框是环：四条边各一块凸体
            for e, (a0, b0, a1, b1) in enumerate(((-1, -1, 1, -1), (1, -1, 1, 1), (1, 1, -1, 1), (-1, 1, -1, -1))):
                P = []
                for (a, b) in ((a0, b0), (a1, b1)):
                    for inset in (0.0, 0.008):
                        for d in (0.004, -0.003):
                            P.append(c + u * a * (ls / 2 + 0.008 - inset) + v * b * (ws / 2 + 0.008 - inset) + n * d)
                o, l = hull(f"rcs.{k}.rim{e}.{tag}", P, "metal", {"skin": f"rcs.{k}.rim.{tag}", "lineLevel": "secondary"}, bevel=0.0)
                EDGES[o.name] = l
                out.append(o)
    return out


def probes_antennas():
    """大气数据探头（下切面 s 0.9，前伸 0.22 m 的细管 + 底座）、静压孔（下切面 s 2.3 两枚）、刀形天线（腹底 s 3.3、背脊 s 2.6）、贴片天线（屋面 s 1.85、3.5）。"""
    out = []
    for side, tag in ((1, "l"), (-1, "r")):
        base, n = surface(0.95, "lower", 0.25, side)
        o, l = hull(f"probe.base.{tag}", [base + Vector((dx, dy * side, dz)) + n * d for dx in (-0.04, 0.04) for dy in (-0.012, 0.012) for dz in (-0.012, 0.012) for d in (0.0, 0.025) if not (d and dx < 0)], "metal", {"skin": f"probe.base.{tag}", "lineLevel": "secondary"}, bevel=0.002)
        EDGES[o.name] = l
        out.append(o)
        tip = base + n * 0.03 + Vector((0.22, 0, 0))
        o, l = cylinder(f"probe.tube.{tag}", base + n * 0.03 - Vector((0.02, 0, 0)), tip, 0.006, 10, "chrome", {"skin": f"probe.tube.{tag}", "lineLevel": "secondary"}, r2=0.004)
        EDGES[o.name] = l
        out.append(o)
        for k, s in enumerate((2.25, 2.4)):
            p, n = surface(s, "lower", 0.3, side, lift=0.0005)
            o, l = cylinder(f"static.{k}.{tag}", p - n * 0.002, p + n * 0.0015, 0.013, 16, "metal", {"skin": f"static.{k}.{tag}", "lineLevel": "secondary"}, bevel=0.0005)
            EDGES[o.name] = l
            out.append(o)
    # 刀形天线：底座长 0.16，高 0.14 / 0.10，后掠
    for name, s, h, top in (("antenna.belly", 3.3, 0.14, False), ("antenna.spine", 2.6, 0.1, True)):
        if top:
            z0, d = spine_z(s), 1
        else:
            z0, d = ring(s)["R3"][1], -1
        P = [at(s + ds, dy, z0 + d * dz) for ds, dz in ((0.08, -0.01), (-0.08, -0.01), (-0.06, h), (-0.1, h), (0.04, 0.0)) for dy in (-0.006, 0.006)]
        o, l = hull(name, P, "carbon", {"skin": name, "lineLevel": "secondary"}, bevel=0.002)
        EDGES[o.name] = l
        out.append(o)
    for k, (s, y) in enumerate(((1.85, 0.0), (3.5, 0.18))):
        for side in ((1,) if y == 0 else (1, -1)):
            p, n = surface(s, "roof", y / max(ring(s)["R1"][0], 1e-3), side)
            u = Vector((1, 0, 0))
            v = n.cross(u).normalized()
            P = [p + u * a * 0.07 + v * b * 0.045 + n * dd for a in (-1, 1) for b in (-1, 1) for dd in (-0.003, 0.0018)]
            o, l = hull(f"antenna.patch.{k}.{'lr'[side < 0]}", P, "carbon", {"skin": f"antenna.patch.{k}", "lineLevel": "secondary"}, bevel=0.001)
            EDGES[o.name] = l
            out.append(o)
    return out


# 口盖（与 seams() 里的口盖线同一张表）：切面、站位 s0～s1、横向 t0～t1
HATCHES = [("roof", 3.1, 4.06, 0.02, 0.73), ("roof", 0.68, 1.0, 0.25, 0.85), ("outer", 1.28, 1.7, 0.08, 0.92), ("lower", 2.1, 3.0, 0.1, 0.5), ("belly", 4.1, 5.8, 0.1, 1.0)]


def hatches():
    """口盖本体：口盖线以内一块高出蒙皮 0.8 mm 的薄板（板边离口盖线 4 mm——这一圈就是凹缝），板边内 1.5 cm 一圈紧固件（六角头，间距约 6 cm）。
    板只有十几个顶点，顶点 AO 会把眉骨的遮挡、板边贴蒙皮的接触暗拉满整块板（R4 自查：屋面口盖成了一块暗板），所以不烘顶点 AO（aoFlat）。
    腹底的是前起落架舱门（左右两扇）。"""
    from kit.parts import bolts

    out = []
    for side, tag in ((1, "l"), (-1, "r")):
        for k, (facet, s0, s1, t0, t1) in enumerate(HATCHES):
            def corner(s, t, lift):
                return surface(s, facet, t, side, lift)[0]

            # 横向 t 的 4 mm：按当地两棱间距换算
            def dt(s):
                if facet == "belly":
                    return 0.004 / max(ring(s)["R3"][0], 1e-3)
                a, b = FACETS[facet]
                R = ring(s)
                return 0.004 / max((Vector(R[a]) - Vector(R[b])).length, 1e-3)

            g0, g1 = s0 + 0.004, s1 - 0.004
            C = [(g0, t0 + dt(g0)), (g1, t0 + dt(g1)), (g1, t1 - dt(g1)), (g0, t1 - dt(g0))]
            pts = [corner(s, t, lift) for s, t in C for lift in (-0.002, 0.0008)]
            o, l = hull(f"hatch.{k}.{tag}", pts, "belly" if facet in ("lower", "belly") else "hull", {"skin": f"hatch.{k}.{tag}", "lineLevel": "structure", "aoFlat": True}, bevel=0.0015)
            EDGES[o.name] = l
            out.append(o)
            # 紧固件：板边内 1.5 cm 一圈
            n = surface((s0 + s1) / 2, facet, (t0 + t1) / 2, side)[1]
            inset = [(g0 + 0.015, t0 + 3.75 * dt(g0)), (g1 - 0.015, t0 + 3.75 * dt(g1)), (g1 - 0.015, t1 - 3.75 * dt(g1)), (g0 + 0.015, t1 - 3.75 * dt(g0))]
            row = []
            for (sa, ta), (sb, tb) in zip(inset, inset[1:] + inset[:1]):
                a, b = corner(sa, ta, 0.0008), corner(sb, tb, 0.0008)
                m = max(2, int((b - a).length / 0.06))
                row.append(bolts(f"hatch.{k}.{tag}.f{len(row)}", a, b, m, 0.0035, n, ends=False))
            from kit.parts import merge

            o, l = merge(f"hatch.{k}.{tag}.fasteners", row, props={"skin": f"hatch.{k}.{tag}.fasteners", "lineLevel": "secondary"})
            EDGES[o.name] = l
            out.append(o)
    return out


def inlay():
    """朱红嵌条：沿朱红脊线（R1）s 4.0～7.6 的一条有厚度的嵌条（宽 9 mm，凸出 2.5 mm）；通电时沿 u（=uv.x）从前往后点亮。"""
    out = []
    S0 = 4.0
    for side, tag in ((1, "l"), (-1, "r")):
        bm = bmesh.new()
        uv = bm.loops.layers.uv.new("UVMap")
        ss = [S0 + (S_END - S0) * i / 24 for i in range(25)]
        rows = []
        for s in ss:
            R = ring(s)
            p = at(s, R["R1"][0] * side, R["R1"][1])
            nr = facet_normal(s, "roof", side)
            no = facet_normal(s, "outer", side)
            n = (nr + no).normalized()
            w = (nr - no).normalized()  # 横跨脊线、沿屋面向上
            rows.append([bm.verts.new(p + w * a * 0.0045 + n * d) for a, d in ((-1, -0.004), (-1, 0.0025), (1, 0.0025), (1, -0.004))])
        for i, (A, B) in enumerate(zip(rows, rows[1:])):
            for k in range(4):
                f = bm.faces.new((A[k], A[(k + 1) % 4], B[(k + 1) % 4], B[k]))
        bm.faces.new(list(reversed(rows[0])))
        bm.faces.new(rows[-1])
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        for f in bm.faces:
            for loop in f.loops:
                s = XN - loop.vert.co.x
                loop[uv].uv = ((s - S0) / (S_END - S0), 0.5)
        o = new_object(f"chine.inlay.{tag}", bm, "vermilion", {"skin": f"chine.inlay.{tag}", "glow": {"key": "chine", "color": "#ff5a32", "sweep": "chine.sweep"}, "lineLevel": "secondary"})
        EDGES[o.name] = finish(o, bevel=0.0)
        out.append(o)
    return out


# —— 鳞片瓦：下切面上的扁六边形蜂窝（C2 侧视实测：沿机身长 0.24 m、行距 0.15 m），按结构框分区 ——————————————
HEX_W, HEX_H = 0.236, 0.15  # 六边形沿机身的对角长、跨切面的对边距（两头尖、上下平）
ZONES = [(0.65, 1.5), (1.5, 2.2), (2.2, 3.1), (3.1, 3.9), (3.9, 4.84), (4.84, 6.0), (6.0, 6.95), (6.95, S_END)]


def slant(s):
    """下切面在站位 s 的斜宽（棱线 R2 到腹缘 R3）。"""
    R = ring(s)
    return math.hypot(R["R2"][0] - R["R3"][0], R["R2"][1] - R["R3"][1])


def tiles():
    """C2 的鳞片是一张连续的蜂窝：一套全局格子（列沿机身每 0.75·W 一列，奇数列错开半行），从光窗后环缝铺到段尾，
    在棱线、腹缘和段两端处被裁开（裁剩不到三成的不要）。瓦缝 1.2 cm；每片是 5 mm 厚的扁六棱柱（下表面埋进蒙皮 2 mm）。
    分区（ZONES，落在结构框上）只体现在腹底细节贴图里，下切面跟 C2 一样不断开。"""
    out = []
    count = 0
    W, H = HEX_W, HEX_H
    g = 0.006
    hexagon = [(W / 2 - g * 1.15, 0.0), (W / 4 - g * 0.58, H / 2 - g), (-W / 4 + g * 0.58, H / 2 - g), (-W / 2 + g * 1.15, 0.0), (-W / 4 + g * 0.58, -H / 2 + g), (W / 4 - g * 0.58, -H / 2 + g)]
    s_lo, s_hi, edge = ZONES[0][0], S_END - 0.006, 0.012
    for side, tag in ((1, "l"), (-1, "r")):
        bm = bmesh.new()
        c = 0
        while True:
            sc = s_lo + c * 0.75 * W
            if sc - W / 2 > s_hi:
                break
            v = (H / 2 if c % 2 else 0.0)
            while v - H / 2 < slant(min(sc + W / 2, s_hi)):
                pts = []
                for du, dv in hexagon:
                    ss = min(max(sc + du, s_lo), s_hi)
                    sl = slant(ss)
                    vv = min(max(v + dv, edge), sl - edge)
                    pts.append((ss, vv / sl))
                # 裁剩面积（按 (s, v) 平面里的多边形面积估）
                area = 0.0
                for (sa, ta), (sb, tb) in zip(pts, pts[1:] + pts[:1]):
                    area += sa * tb * slant(sb) - sb * ta * slant(sa)
                if abs(area) / 2 > 0.3 * 0.75 * W * H:
                    vs = []
                    for ss, t in pts:
                        for lift in (0.003, -0.002):
                            vs.append(bm.verts.new(surface(ss, "lower", t, side, lift=lift)[0]))
                    bmesh.ops.convex_hull(bm, input=vs)
                    count += 1
                v += H
            c += 1
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
        o = new_object(f"scales.{tag}", bm, "belly", {"skin": "scales", "lineLevel": "secondary", "shadow": False, "aoOccluder": False})
        EDGES[o.name] = finish(o, bevel=0.0, angle=40)
        out.append(o)
    return out, count


def stand():
    s = 4.0
    zb = ring(s)["R3"][1]
    out = []
    o, l = hull("stand.post", [at(s + ds * a, dy * b, z) for ds, dy, z in ((0.1, 0.1, 0.0), (0.05, 0.05, zb - 0.05)) for a in (1, -1) for b in (1, -1)], "stand", {"skin": "stand.post"}, bevel=0.008)
    EDGES[o.name] = l
    out.append(o)
    o, l = hull("stand.cradle", [at(s + ds, dy, z) for ds in (0.24, -0.24) for dy in (0.2, -0.2) for z in (zb - 0.05, zb - 0.002)], "stand", {"skin": "stand.cradle"}, bevel=0.008)
    EDGES[o.name] = l
    out.append(o)
    return out


# —— 分割线、口盖（按结构分）——————————————————————————————————
def seams():
    out = []

    def line(pn, level="secondary", closed=False, **extra):
        out.append({"points": [[round(v, 4) for v in p] for p, _ in pn], "normals": [[round(v, 4) for v in n] for _, n in pn], "level": level, "closed": closed, **extra})

    def around(s, lift=0.0015, facets=("roof", "outer", "lower")):
        pts = []
        for side in (1, -1):
            run = []
            for f in facets:
                for t in ((0.0, 0.5) if f != "lower" else (0.0, 0.5, 1.0)):
                    run.append(surface(s, f, t, side, lift))
            pts.append(run)
        left, right = pts
        belly = [surface(s, "belly", t, 1, lift) for t in (0.5, 1.0)] + [surface(s, "belly", 1 - t, -1, lift) for t in (0.0, 0.5)]
        return list(reversed(left)) + right

    def rect(facet, s0, s1, t0, t1, side, lift=0.0015, level="secondary"):
        line([surface(s, facet, t, side, lift) for s, t in ((s0, t0), (s1, t0), (s1, t1), (s0, t1))], level=level, closed=True)

    # C2 量出来的分缝（俯视 66 px/m、侧视 42.4 px/m）：光窗后一圈环缝 s 0.62；屋面两道向前的 V 形缝（s 1.07→1.27、2.84→3.09，
    # 中线处在前）；屋面口盖 s 3.1～4.06（外沿到 t 0.73）；外上切面竖缝 s 2.62、3.54。其余是 K1 结构框处的低对比环缝（L2）。
    line(around(0.62), level="structure")
    for s0, s1 in ((1.07, 1.27), (2.84, 3.09)):
        for side in (1, -1):
            line([surface(s0, "roof", 0.0, side, 0.0015), surface(s1, "roof", 1.0, side, 0.0015)], level="structure")
            line([surface(s1, f, t, side, 0.0015) for f, t in (("outer", 0.0), ("outer", 1.0), ("lower", 0.5), ("lower", 1.0))])
    for side in (1, -1):
        rect("roof", 3.1, 4.06, 0.0, 0.73, side, level="structure")
        for sx in (2.62, 3.54):
            line([surface(sx, "outer", t, side, 0.0015) for t in (0.0, 1.0)])
    # 结构框处的低对比环缝：左右各一条（背脊 → 下切面），遇到口盖断开——口盖是一整块板，环缝不从板上穿过
    def ring_runs(sx, side, lift=0.0015):
        # 口盖离棱不到 3% 的一边按贴棱算（屋面口盖的口盖线画在背脊上），免得在凹缝里留一截短线
        spans = [(fh, s0, s1, t0 if t0 > 0.03 else 0.0, t1 if t1 < 0.97 else 1.0) for fh, s0, s1, t0, t1 in HATCHES]
        runs, run = [], []
        for f in ("roof", "outer", "lower"):
            cuts = sorted({0.0, 1.0} | {t for fh, s0, s1, t0, t1 in spans if fh == f and s0 - 0.01 <= sx <= s1 + 0.01 for t in (t0, t1)})
            for ta, tb in zip(cuts, cuts[1:]):
                inside = any(fh == f and s0 - 0.01 <= sx <= s1 + 0.01 and t0 <= (ta + tb) / 2 <= t1 for fh, s0, s1, t0, t1 in spans)
                if inside:
                    if len(run) > 1:
                        runs.append(run)
                    run = []
                    continue
                if not run:
                    run.append(surface(sx, f, ta, side, lift))
                run.append(surface(sx, f, tb, side, lift))
        if len(run) > 1:
            runs.append(run)
        return runs

    for sx in (1.5, 2.2, 3.9):
        for side in (1, -1):
            for run in ring_runs(sx, side):
                line(run)
    # 背脊两侧一条窄条（C2 俯视里贯穿到座舱前的两道细线，离中线 ±4.5 cm）
    for side in (1, -1):
        pts = []
        for sx in (0.62, 1.07, 2.0, 2.84, 3.1):
            t = 0.045 / max(ring(sx)["R1"][0], 1e-3)
            pts.append(surface(sx, "roof", t, side, 0.0015))
        line(pts)
    # 口盖：传感器舱门（屋面 s 0.7～1.0）、姿控喷口检修板（外上切面 s 1.28～1.7）、下切面检修口（s 2.1～3.0），前起落架舱门（腹底 s 4.1～5.8，左右两扇，L1）
    for side in (1, -1):
        rect("roof", 0.68, 1.0, 0.25, 0.85, side, level="structure")
        rect("outer", 1.28, 1.7, 0.08, 0.92, side)
        rect("lower", 2.1, 3.0, 0.1, 0.5, side)
    line([surface(s, "belly", t, 1, 0.0015) for s, t in ((4.1, 1.0), (5.8, 1.0), (5.8, 0.1), (4.1, 0.1))], level="structure", closed=True)
    line([surface(s, "belly", t, -1, 0.0015) for s, t in ((4.1, 1.0), (5.8, 1.0), (5.8, 0.1), (4.1, 0.1))], level="structure", closed=True)
    # 朱红线（accent）：沿 R1 脊线 s 4.0～7.6，通电扫亮（与嵌条同一条 u）
    for side in (1, -1):
        def ridge(s, side=side):
            R = ring(s)
            n = (facet_normal(s, "roof", side) + facet_normal(s, "outer", side)).normalized()
            return at(s, R["R1"][0] * side, R["R1"][1]) + n * 0.003, n
        line([ridge(s) for s in (4.0, S_FLAT, S_END)], level="accent", accent="chine", u0=0.0, u1=1.0)
    return out


def ball_mask(c, r):
    planes = []
    k = 1 / math.sqrt(3)
    dirs = [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)] + [(a * k, b * k, d * k) for a in (1, -1) for b in (1, -1) for d in (1, -1)]
    for n in dirs:
        n = Vector(n)
        planes.append([round(n.x, 4), round(n.y, 4), round(n.z, 4), round(n.dot(c) + r, 4)])
    return planes


def build():
    EDGES.clear()
    objs = []
    b = body()
    boolean(b, brow())
    boolean(b, fairing())
    boolean(b, socket_cutter(), "DIFFERENCE")
    for c in slot_cutter():
        boolean(b, c, "DIFFERENCE")
    assign_body_materials(b)
    EDGES[b.name] = finish(b, bevel=0.03, angle=30)
    objs.append(b)
    objs += eye()
    objs += shield()
    objs += canopy()
    objs += rails()
    objs += canards()
    objs += rcs()
    objs += probes_antennas()
    objs += hatches()
    objs += inlay()
    t, n_tiles = tiles()
    objs += t
    objs += stand()
    c = eye_centre()
    meta = {
        "offset": [-(XN - S_END / 2), 0, 0],
        "seams": seams(),
        "edges": dict(EDGES),
        "landmarks": {"sensor": list(c), "canopy": list(at(5.9, 0, Z_TIP + 1.2)), "brow": list(at(4.6, 0, spine_z(4.6) + 0.05)), "rcs.l": list(surface(1.47, "outer", 0.5)[0]), "tip": list(at(0, 0, Z_TIP + EYE["z"])), "keel.end": list(at(S_END, 0, ring(S_END)["R3"][1]))},
        "joints": [],
        "masks": [ball_mask(c, EYE["r"] * 0.75)],
        "focus": {"nose": list(c), "canopy": list(at(5.6, 0, Z_TIP + 1.0))},
        "tiles": n_tiles,
        "panel_cuts": [0.62, 1.07, 1.5, 2.2, 2.84, 3.1, 3.9, 4.06, 4.8, 5.85, 6.95],
        "callouts": [
            {"n": 1, "label": "机头光窗（虹膜）", "at": list(c)},
            {"n": 5, "label": "眉骨", "at": list(at(4.5, 0, spine_z(4.5) + 0.06))},
            {"n": 6, "label": "遮光盾（收起）", "at": list(at(BROW[2] - 0.1, 0, roof_z(BROW[2] - 0.1, 0) + SLOT_DZ))},
            {"n": 7, "label": "座舱盖（低矮）", "at": list(at(6.1, 0, Z_TIP + 1.25))},
        ],
    }
    return objs, meta
