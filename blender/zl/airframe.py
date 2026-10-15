"""烛龙整机（Z2）：中后机身、折扇主翼、边条、翼尖鳍、垂尾、喷口、塞锥、进气门；化剑的全部转轴与步骤。

这一阶段只做体积与剪影（DESIGN 8.7 实测，C2 三视图对位），不加细节。机头段（s 0～7.6）仍是 nose.py 的复刻样板。

化剑（DESIGN 8.8）：C2 的主翼本身是以翼根前缘为圆心的扇面，所以主翼做成**折扇**——12 片扇骨（羽片）叠在 12 层上，
绕翼根前缘一根竖轴（主翼回转轴）各转各的角度，收拢后叠成一条顺着后机身侧面的窄带（C3 俯视那条暗带）。
扇骨的层：前缘那片在最下（与棱线、边条齐平），翼根那片在最上；前视读成下反。
其余转轴：鸭翼、前边条、后缘边条沿根部铰线下折，贴住棱线下的下切面（鸭翼那一处就是“棱线槽”）；
翼尖鳍沿翼尖弦再下折 25° 到竖直（外翼下折），扇骨收拢后它竖在后机身两侧；垂尾沿根部铰线向外转 65° 成水平的剑格；
进气门（即进气斜板）绕前缘铰线放平，封住腹底进气口。
关节都只写左侧（.l），右侧按 y 镜像：点 y 取反，轴按赝矢量 [-ax, ay, -az]，左右同一组角度就是镜像动作（PATTERNS「关节、机构与状态」）。
"""
import math

import bmesh
import bpy
from mathutils import Matrix, Vector

from kit.finish import finish
from kit.parts import cylinder, hull, lathe, new_object

from . import nose
from .util import XN, at, lerp, mirror_object, piecewise

EDGES = {}
S0 = nose.S_END  # 7.6：接机头段
S_AFT = 17.13  # 后机身端面（二元喷口、塞锥从这里伸出）
L_TOTAL = 19.14  # 机头尖 → 塞锥尖

# —— 中后机身截面（C2 实测，DESIGN 8.7）：R0 背脊、R1 上肩、R2 棱线（最宽）、R3 腹缘；s 7.6 处与机头段棱锥重合 ——————
_R = nose.ring(S0)
R0Z = [(S0, _R["R0"][1]), (15.0, _R["R0"][1]), (S_AFT, 2.72)]
R2 = [(S0, _R["R2"]), (9.66, (1.37, 1.90)), (13.2, (1.44, 1.88)), (15.0, (1.58, 1.86)), (S_AFT, (1.62, 1.85))]
R1Z = [(S0, _R["R1"][1]), (9.66, 2.55), (12.0, 2.62), (15.0, 2.62), (S_AFT, 2.6)]
R3 = [(S0, _R["R3"]), (8.6, (0.95, 0.70)), (9.66, (1.15, 0.70)), (12.0, (1.24, 0.70)), (13.2, (1.27, 0.77)), (14.0, (1.32, 0.87)), (15.0, (1.39, 0.95)), (16.0, (1.41, 1.0)), (S_AFT, (1.43, 1.03))]


SHOULDER = (0.25, 2.38)  # 上肩倒角：R1 在棱线内侧 0.25 m；外上切面在 z 2.38 处折一道（下半竖直，是翼根带，托住扇骨）


def ring(s):
    r2 = piecewise(R2, s)
    # 上肩：机头段的朱红脊线 R1 在 s 9.66 前展到棱线内侧 0.25 m；外上切面中点 M 由直线中点渐变到翼根带上沿 (R2.y, 2.38)
    f = min(1.0, (s - S0) / (9.66 - S0))
    y1 = lerp(_R["R1"][0], r2[0] - SHOULDER[0], f)
    z1 = piecewise(R1Z, s)
    mid = ((y1 + r2[0]) / 2, (z1 + r2[1]) / 2)
    m = (lerp(mid[0], r2[0], f), lerp(mid[1], SHOULDER[1], f))
    return {"R0": (0.0, piecewise(R0Z, s)), "R1": (y1, z1), "M": m, "R2": r2, "R3": piecewise(R3, s)}


def chine_y(s):
    return ring(s)["R2"][0] if s >= S0 else nose.ring(s)["R2"][0]


def chine_z(s):
    return ring(s)["R2"][1] if s >= S0 else nose.ring(s)["R2"][1]


def lower_facet_y(s, z):
    """棱线以下下切面在高度 z 处的 |y|。"""
    R = ring(s) if s >= S0 else nose.ring(s)
    (y2, z2), (y3, z3) = R["R2"], R["R3"]
    return lerp(y2, y3, (z2 - z) / (z2 - z3))


def section_points(s):
    R = ring(s)
    left = []
    for name, (a, b) in nose.FACETS.items():
        n = nose.COLS[name]
        for i in range(n):
            t = i / n
            p = (lerp(R[a][0], R[b][0], t), lerp(R[a][1], R[b][1], t))
            if name == "outer" and i == 1:
                p = R["M"]  # 外上切面中点：上肩倒角与翼根带的折线
            left.append((p, name))
    left.append((R["R3"], "belly"))
    belly = [((lerp(R["R3"][0], -R["R3"][0], i / 6), R["R3"][1]), "belly") for i in range(1, 6)]
    right = [((-y, z), m) for (y, z), m in reversed(left[1:])]
    return left + belly + right


def stations():
    s, x = [], S0
    while x < S_AFT - 1e-6:
        s.append(round(x, 3))
        x += 0.25
    keys = [t for t, _ in R2 + R1Z + R3 + R0Z]
    return sorted(set([round(v, 4) for v in s + keys + [S_AFT] if S0 <= v <= S_AFT]))


INTAKE = {"lip": 9.9, "ramp": 9.25, "end": 11.2, "w": 1.0, "h": 0.27}  # 腹底扁口：唇口 s 9.9、宽 ±1.0、口高 0.27（DESIGN 8.7：斜板起点处腹底只有 ±1.08 宽）


def _boolean(target, cutter, op="DIFFERENCE"):
    mod = target.modifiers.new("cut", "BOOLEAN")
    mod.operation = op
    mod.solver = "EXACT"
    mod.object = cutter
    if hasattr(mod, "material_mode"):
        mod.material_mode = "TRANSFER"
    bpy.context.view_layer.objects.active = target
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(cutter, do_unlink=True)


def _box(name, pts, material):
    o, _ = hull(name, pts, material, bevel=0.0)
    return o


def aft_body():
    bm = bmesh.new()
    rings = []
    for s in stations():
        rings.append([bm.verts.new(at(s, y, z)) for (y, z), _ in section_points(s)])
    n = len(rings[0])
    for A, B in zip(rings, rings[1:]):
        for i in range(n):
            bm.faces.new((A[i], A[(i + 1) % n], B[(i + 1) % n], B[i]))
    front = bm.faces.new(list(reversed(rings[0])))
    front.material_index = 0
    bm.faces.new(rings[-1])
    obj = new_object("aft.body", bm, "hull", {"aoFlat": True, "show": "!cutaway"})
    for m in ("belly", "interior", "void"):
        obj.data.materials.append(bpy.data.materials.get(m) or bpy.data.materials.new(m))
    # 进气口：前面一段斜板槽（s 8.95 → 9.6 由 0 加深到口高，向下敞开），后面一段进气道（唇口以后留 2 cm 腹底蒙皮）
    I = INTAKE
    zb = ring(I["lip"])["R3"][1]
    w, h = I["w"], I["h"]
    ramp = [at(I["ramp"], y, z) for y in (w, -w) for z in (zb - 0.05, zb + 0.004)] + [at(I["lip"], y, z) for y in (w, -w) for z in (zb - 0.05, zb + h)]
    _boolean(obj, _box("intake.ramp", ramp, "void"))
    duct = [at(s, y, z) for s in (I["lip"] - 0.05, I["end"]) for y in (w, -w) for z in (zb + 0.02, zb + h)]
    _boolean(obj, _box("intake.duct", duct, "void"))
    # 材质：前后端面 interior，棱线以下 belly，进气道里 void
    for f in obj.data.polygons:
        c = f.center
        s = XN - c.x
        R = ring(min(max(s, S0), S_AFT))
        name = obj.data.materials[f.material_index].name if f.material_index < len(obj.data.materials) else ""
        if name == "void":
            f.material_index = obj.data.materials.find("void")
        elif abs(f.normal.x) > 0.95 and (s < S0 + 0.03 or s > S_AFT - 0.03):
            f.material_index = obj.data.materials.find("interior")
        else:
            f.material_index = obj.data.materials.find("belly") if c.z < R["R2"][1] - 2e-3 else 0
    lines = finish(obj, bevel=0.0, angle=25)
    # 接机头段的那一圈：删掉前端面（藏在机头段后端面里），它的线也不要（机头段那一圈已有）
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    x0 = XN - S0
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if abs(f.calc_center_median().x - x0) < 1e-4 and abs(f.normal.x) > 0.99], context="FACES")
    bm.to_mesh(obj.data)
    bm.free()
    EDGES[obj.name] = [v for i in range(0, len(lines), 12) if not (abs(lines[i] - x0) < 1e-3 and abs(lines[i + 3] - x0) < 1e-3) for v in lines[i:i + 12]]
    return obj


def intake_door():
    """进气斜板 = 进气门：大气形态贴在斜板槽顶（斜板），化剑时绕前缘铰线放平、与腹底齐平封住进气口。"""
    I = INTAKE
    zb = ring(I["lip"])["R3"][1]
    s0 = I["ramp"] + 0.09
    s1 = s0 + (I["lip"] - 0.008 - s0) * math.cos(math.atan2(I["h"], I["lip"] - I["ramp"]))  # 放平后的长度不超过唇口
    slope = I["h"] / (I["lip"] - I["ramp"])
    zt = lambda s: zb + 0.004 + slope * (s - I["ramp"])  # 斜板槽顶
    w = I["w"] - 0.01
    pts = [at(s, y, zt(s) - dz) for s in (s0, s1) for y in (w, -w) for dz in (0.012, 0.032)]
    o, l = hull("intake.door", pts, "belly", {"joint": "intake.door", "aoFlat": True, "show": "!cutaway"}, bevel=0.0)
    EDGES[o.name] = l
    hinge = at(s0, 0, zt(s0) - 0.032)
    ang = math.degrees(math.atan2(zt(s1) - zt(s0), s1 - s0))
    return [o], [{"name": "intake.door", "type": "hinge", "point": list(hinge), "axis": [0, -1, 0], "range": [0, round(ang, 2)], "note": "进气门：斜板绕前缘铰线放平，封住腹底进气口"}], round(ang, 2)


# —— 主翼：折扇（DESIGN 8.8） ————————————————————————————————————————————————
PIVOT = (9.66, 1.40)  # 翼根前缘：扇子的圆心（主翼回转轴）
TILT = 3.0  # 扇面下反（外侧低），轴垂直于扇面
N_FEATHER = 12
T_LEVEL = 0.04  # 每层 4 cm；羽片厚 3.6 cm，层间 4 mm
T_FEATHER = 0.036
Z_BOTTOM = 1.86  # 最下一层（前缘羽片）在圆心处的底面高：与棱线、边条齐平
THETA0, THETA_LE, THETA_C, THETA_C_LE = 1.2, 37.5, 2.3, 3.0  # 翼根羽片内沿、前缘羽片内沿、收拢后各羽片的内沿、前缘羽片收拢后的内沿（度）
R_IN = 0.17  # 羽片根部让开轮毂（半径 0.15）
STRAKE_FOLD, FILLET_FOLD = 96.0, 100.0  # 前边条、后缘边条的下折角（度）
OVERLAP = 0.5  # 相邻羽片在下面那片上多盖 0.5°
# C2 俯视左舷平面形（s, y）：边条外沿 → 前缘外沿 → 翼尖 → 后缘（含襟副翼）→ 根部后缘缺口 → 机身侧（DESIGN 8.7）
PLANFORM = [(7.40, 1.17), (9.90, 2.20), (13.33, 4.76), (13.45, 4.82), (14.30, 4.82), (14.55, 4.00), (14.70, 3.20), (14.80, 2.80),
            (14.88, 2.40), (14.90, 2.20), (14.55, 2.02), (13.20, 1.455), (9.66, 1.39), (8.5, 1.29)]
FIN = {"root": (13.45, 14.08), "tip": (13.92, 14.42), "span": 1.0, "droop": 65.0, "t": 0.03}  # 翼尖鳍：根弦在前缘羽片的翼尖上（前缘羽片内沿 37.5° 的射线在翼尖处 s 14.12）


def feather_angles():
    d = (THETA_LE - THETA0) / (N_FEATHER - 1)
    return [THETA0 + i * d for i in range(N_FEATHER)], d


def level_z(i, s, y):
    """第 i 片羽片底面在 (s, y) 处的高度：层（前缘羽片 i = 11 在最下）+ 扇面下反。"""
    return Z_BOTTOM + (N_FEATHER - 1 - i) * T_LEVEL - (y - PIVOT[1]) * math.tan(math.radians(TILT))


def axis_vec(side=1):
    t = math.radians(TILT)
    return Vector((0.0, math.sin(t) * side, math.cos(t)))


def _clip(poly, keep):
    """Sutherland–Hodgman：保留 keep(p) ≥ 0 的一侧（keep 为线性函数）。"""
    out = []
    for i in range(len(poly)):
        a, b = poly[i - 1], poly[i]
        fa, fb = keep(a), keep(b)
        if fa >= 0:
            out.append(a)
        if (fa >= 0) != (fb >= 0):
            t = fa / (fa - fb)
            out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    return out


def _wedge(poly, a, b):
    ps, py = PIVOT
    ca, sa, cb, sb = math.cos(math.radians(a)), math.sin(math.radians(a)), math.cos(math.radians(b)), math.sin(math.radians(b))
    poly = _clip(poly, lambda p: ca * (p[1] - py) - sa * (p[0] - ps))  # 在射线 a 的逆时针一侧
    poly = _clip(poly, lambda p: -(cb * (p[1] - py) - sb * (p[0] - ps)))  # 在射线 b 的顺时针一侧
    # 根部让开轮毂：沿角平分线在 R_IN 处切一刀（弦），扇骨根部离轮毂至少 R_IN − 0.15
    m = math.radians((a + b) / 2)
    cm, sm = math.cos(m), math.sin(m)
    return _clip(poly, lambda p: cm * (p[0] - ps) + sm * (p[1] - py) - R_IN)


def _slab(name, poly, zfun, t, material="hull", props=None):
    """平面多边形（s, y）按 zfun(s, y) 给底面高度，向上加厚 t（竖直方向）。"""
    bm = bmesh.new()
    bot = [bm.verts.new(at(s, y, zfun(s, y))) for s, y in poly]
    top = [bm.verts.new(at(s, y, zfun(s, y) + t)) for s, y in poly]
    bm.faces.new(list(reversed(bot)))
    bm.faces.new(top)
    n = len(poly)
    for i in range(n):
        bm.faces.new((bot[i], bot[(i + 1) % n], top[(i + 1) % n], top[i]))
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    o = new_object(name, bm, material, {"aoFlat": True, "show": "!cutaway", **(props or {})})
    EDGES[o.name] = finish(o, bevel=0.004, angle=30)
    return o


def wing():
    """左舷主翼：12 片羽片 + 轮毂 + 前边条 + 翼尖鳍；返回 (零件, 关节, 化剑步骤用的收拢角)。"""
    out, joints, close = [], [], {}
    angles, d = feather_angles()
    piv3 = at(PIVOT[0], PIVOT[1], Z_BOTTOM)
    for i, a in enumerate(angles):
        b = 95.0 if i == N_FEATHER - 1 else a + d + OVERLAP
        poly = _wedge(PLANFORM, a, b)
        poly = _clip(poly, lambda p: p[0] - 9.50)  # 前边条（s ≤ 9.46）与前缘羽片之间留 4 cm
        name = f"wing.f{i:02d}.l"
        o = _slab(name, poly, lambda s, y, i=i: level_z(i, s, y), T_FEATHER, "hull", {"joint": name if i else ""})
        out.append(o)
        if i:
            close[name] = round(a - (THETA_C_LE if i == N_FEATHER - 1 else THETA_C), 3)
            joints.append({"name": name, "type": "hinge", "point": list(piv3), "axis": list(axis_vec()), "range": [0, close[name]], "note": f"主翼回转（折扇羽片 {i}）"})
    # 轮毂：沿回转轴的一根短圆柱，半嵌在机身侧面（化剑关节特写的位置）
    ax = axis_vec()
    h0, h1 = piv3 - ax * 0.02, piv3 + ax * (N_FEATHER * T_LEVEL + 0.03)
    o, l = cylinder("wing.hub.l", h0, h1, 0.15, sides=24, material="metal", props={"show": "!cutaway", "aoFlat": True})
    EDGES[o.name] = l
    out.append(o)
    # 前边条：棱线外的一片三角板，与前缘羽片同层；化剑时沿根部铰线下折，贴住下切面
    zle = lambda s, y: level_z(N_FEATHER - 1, s, y)
    sp = [(7.40, chine_y(7.40) + 0.01), (9.46, 2.10), (9.46, chine_y(9.46) + 0.01)]
    o = _slab("strake.l", sp, zle, T_FEATHER, "hull", {"joint": "strake.l"})
    out.append(o)
    a3, b3 = at(sp[0][0], sp[0][1], zle(*sp[0])), at(sp[2][0], sp[2][1], zle(*sp[2]))
    joints.append({"name": "strake.l", "type": "hinge", "point": list(a3), "axis": list((b3 - a3).normalized()), "range": [0, STRAKE_FOLD], "note": "前边条下折，贴住棱线下的下切面"})
    close["strake.l"] = STRAKE_FOLD
    # 翼尖鳍：根弦铰在前缘羽片翼尖的底面外沿，向下外撇 65°；化剑先再下折 25° 到竖直（外翼下折），随前缘羽片收进后机身两侧
    y0 = PLANFORM[4][1]
    z0 = level_z(N_FEATHER - 1, FIN["root"][0], y0) - 0.005
    dr = math.radians(FIN["droop"])
    down = Vector((0, math.cos(dr), -math.sin(dr)))
    nrm = Vector((0, math.sin(dr), math.cos(dr)))
    t = FIN["t"] / 2
    pts = []
    for (s_le, s_te), off in ((FIN["root"], 0.0), (FIN["tip"], FIN["span"])):
        for s in (s_le, s_te):
            p = at(s, y0, z0) + down * off
            pts += [p + nrm * (t * 0.3), p - nrm * (t * 0.3)]
        m = at((s_le + s_te) / 2, y0, z0) + down * off
        pts += [m + nrm * t, m - nrm * t]
    o, l = hull("fin.l", pts, "hull", {"joint": "fin.l", "show": "!cutaway", "aoFlat": True}, bevel=0.003)
    EDGES[o.name] = l
    out.append(o)
    joints.append({"name": "fin.l", "type": "hinge", "point": list(at(FIN["root"][0], y0, z0)), "axis": [-1.0, 0.0, 0.0], "range": [0, 25], "parent": f"wing.f{N_FEATHER - 1:02d}.l", "note": "翼尖鳍（外翼）再下折 25° 到竖直"})
    close["fin.l"] = 25.0
    return out, joints, close


def fillet():
    """后缘边条：垂尾根前方的一块三角板（C2 俯视），化剑时沿根部铰线下折。"""
    z = chine_z(15.4) - 0.14  # 比前缘羽片低 10 cm：收拢后的扇骨从它上面过
    poly = [(14.92, chine_y(14.92) + 0.012), (15.6, 2.56), (15.85, 2.32), (15.9, chine_y(15.9) + 0.012)]
    o = _slab("fillet.l", poly, lambda s, y: z, T_FEATHER, "hull", {"joint": "fillet.l"})
    a, b = at(poly[0][0], poly[0][1], z), at(poly[3][0], poly[3][1], z)
    return [o], [{"name": "fillet.l", "type": "hinge", "point": list(a), "axis": list((b - a).normalized()), "range": [0, FILLET_FOLD], "note": "后缘边条下折"}]


TAIL = {"root": (15.70, 17.60), "tip": (16.92, 18.22), "span": 2.3, "cant": 30.0, "y": 1.45, "z": 2.57, "t": (0.10, 0.04)}  # 根在上肩倒角上（8.1 #3：y≈1.4）


def tail():
    """垂尾：外倾 25°（DESIGN 8.1 #3），根部铰线在机身上肩外沿；化剑时向外转 65° 成水平的剑格。"""
    c = math.radians(TAIL["cant"])
    up = Vector((0, math.sin(c), math.cos(c)))
    w = Vector((0, math.cos(c), -math.sin(c)))  # 外侧面法线
    pts = []
    for (s_le, s_te), off, th in ((TAIL["root"], 0.0, TAIL["t"][0]), (TAIL["tip"], TAIL["span"], TAIL["t"][1])):
        base = Vector((0, TAIL["y"], TAIL["z"])) + up * off
        for s in (s_le, s_te):
            pts.append(at(s, base.y, base.z))
        m = (s_le + s_te) / 2
        pts += [at(m, base.y, base.z) + w * (th / 2), at(m, base.y, base.z) - w * (th / 2)]
    o, l = hull("tail.l", pts, "hull", {"joint": "tail.l", "show": "!cutaway", "aoFlat": True}, bevel=0.004)
    EDGES[o.name] = l
    hinge = Vector((0, TAIL["y"], TAIL["z"])) + w * (TAIL["t"][0] / 2 + 0.005)
    return [o], [{"name": "tail.l", "type": "hinge", "point": list(at(TAIL["root"][0], hinge.y, hinge.z)), "axis": [-1.0, 0.0, 0.0], "range": [0, 90 - TAIL["cant"]], "note": "垂尾向外转平成剑格"}]


def nozzle():
    """左侧二元喷口（DESIGN 8.7：s 17.13～18.17、|y| 0.64～1.62、z 1.3～2.45），出口内缩成暗色腔。"""
    s0, s1, y0, y1, z0, z1 = S_AFT - 0.05, 18.17, 0.64, 1.60, 1.30, 2.45
    o = _box("nozzle.l", [at(s, y, z) for s in (s0, s1) for y in (y0, y1) for z in (z0, z1)], "hull")
    o["show"] = "!cutaway"
    o["aoFlat"] = True
    e = 0.06
    cav = _box("nozzle.cav", [at(s, y, z) for s in (s1 - 0.45, s1 + 0.1) for y in (y0 + e, y1 - e) for z in (z0 + e, z1 - e)], "void")
    _boolean(o, cav)
    EDGES[o.name] = finish(o, bevel=0.0, angle=30)
    return [o]


def plug():
    """中央塞锥（火箭磁喷管）：s 17.13 起的短圆柱，s 17.95 起收成锥尖到 19.14。"""
    zc = 1.88
    a, b = at(S_AFT - 0.05, 0, zc), at(L_TOTAL, 0, zc)
    L = L_TOTAL - S_AFT + 0.05
    f = (17.95 - S_AFT + 0.05) / L
    o, l = lathe("plug", a, b, [(0, 0.29), (f, 0.29), (f + 0.02, 0.275), (1, 0.0)], sides=24, material="metal", props={"show": "!cutaway", "aoFlat": True})
    EDGES[o.name] = l
    return [o]


def mirror_joint(j):
    p, a = j["point"], j["axis"]
    out = {**j, "name": j["name"].replace(".l", ".r"), "point": [p[0], -p[1], p[2]], "axis": [-a[0], a[1], -a[2]]}
    if j.get("parent"):
        out["parent"] = j["parent"].replace(".l", ".r")
    return out


def mirror_part(o):
    r = mirror_object(o, o.name.replace(".l", ".r"))
    EDGES[r.name] = nose.mirror_lines(EDGES[o.name])
    if o.get("joint"):
        r["joint"] = o["joint"].replace(".l", ".r")
    if o.get("skin"):
        r["skin"] = o["skin"].replace(".l", ".r")
    return r


def canard_joint():
    """鸭翼沿根部铰线（顺着下切面那条线，离面 4 cm 的“棱线槽”）下折，贴住下切面。铰线与零件见 nose.canards()。"""
    a, b = nose.CANARD_HINGE
    ang = nose.CANARD_FOLD
    return {"name": "canard.l", "type": "hinge", "point": list(a), "axis": list((b - a).normalized()), "range": [0, ang], "note": "鸭翼下折进棱线槽"}, ang


# 化剑步骤（控件值 0 → 1，约 14 s；DESIGN 5、10）：解锁与锁销在 Z4 做，这里只排主运动的先后与重叠
def sword_steps(close, door):
    steps = []
    for side in ("l", "r"):
        steps.append({"joint": f"canard.{side}", "to": close["canard"], "span": [0.0, 0.14]})
        steps.append({"joint": f"strake.{side}", "to": close["strake.l"], "span": [0.08, 0.22]})
        steps.append({"joint": f"fin.{side}", "to": close["fin.l"], "span": [0.14, 0.26]})
        steps.append({"joint": f"fillet.{side}", "to": FILLET_FOLD, "span": [0.2, 0.32]})
        for i in range(1, N_FEATHER):
            steps.append({"joint": f"wing.f{i:02d}.{side}", "to": close[f"wing.f{i:02d}.l"], "span": [0.3, 0.66]})
        steps.append({"joint": f"tail.{side}", "to": 90 - TAIL["cant"], "span": [0.66, 0.86]})
    steps.append({"joint": "intake.door", "to": door, "span": [0.84, 0.96]})
    return steps


def build():
    EDGES.clear()
    objs, joints = [], []
    objs.append(aft_body())
    o, j, door = intake_door()
    objs += o
    joints += j
    left, lj = [], []
    w, wj, close = wing()
    left += w
    lj += wj
    for fn in (fillet, tail):
        o, j = fn()
        left += o
        lj += j
    left += nozzle()
    cj, cang = canard_joint()
    close["canard"] = cang
    lj.append(cj)
    for o in left:
        objs.append(o)
        objs.append(mirror_part(o))
    joints += lj + [mirror_joint(j) for j in lj]
    objs += plug()
    for o in nose.stand(11.8, ring(11.8)["R3"][1]):
        o["show"] = "!cutaway"
        EDGES[o.name] = nose.EDGES[o.name]
        objs.append(o)
    meta = {
        "joints": joints,
        "controls": [{"id": "sword", "label": "化剑", "range": [0, 1], "rest": 0, "time": 14, "ends": ["大气形态", "剑形态"], "steps": sword_steps(close, door)}],
        "landmarks": {"wing.pivot.l": list(at(PIVOT[0], PIVOT[1], Z_BOTTOM + 0.25)), "tail.l": list(at(16.2, TAIL["y"], TAIL["z"] + 0.8)), "plug.tip": list(at(L_TOTAL, 0, 1.88)), "intake": list(at(INTAKE["lip"], 0, 0.8))},
        "focus": {"wing": list(at(12.0, 2.6, 1.9)), "tail": list(at(16.5, 1.6, 2.6)), "sword": list(at(9.6, 0, 1.9))},
        "close": close,
    }
    return objs, dict(EDGES), meta
