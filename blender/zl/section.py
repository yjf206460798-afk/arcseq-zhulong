"""剖视用的剖面带与内部件自检。

剖面带：剖切面 y = 0 上，蒙皮（厚 SKIN）与座舱盖玻璃被切开的那一圈实心带（K1 里机身外壳那条亮边）。按几何母版的解析外形直接生成
（背线含眉骨与背部整流、龙骨线），只在剖视时显示（随内部模块一起按需加载）。
自检：内部件的每个顶点都要在外形截面里（或座舱盖下），否则报“穿出蒙皮”。
"""
import bmesh
from mathutils import Vector

from kit.finish import finish
from kit.parts import new_object

from .interior import SKIN
from .nose import BROW, CANOPY, S_END, S_FRONT, Z_TIP, at, ring, spine_z
from .util import XN, lerp


def top_profile(s):
    z = spine_z(s)
    s0, s1, s2 = BROW
    if s0 <= s <= s2:
        z = max(z, lerp(spine_z(s0), spine_z(s1) + 0.1, min(1.0, (s - s0) / (s1 - s0))))
    if s >= 6.85:
        z = max(z, Z_TIP + lerp(1.27, 1.285, (s - 6.85) / (S_END - 6.85)))
    return z


def band(name, outer, inner, props):
    """outer / inner：剖切面上的两条折线 [(s, z)…]（等长），之间成带，沿 y 厚 3 mm。"""
    bm = bmesh.new()
    rows = []
    for (s, zo), (_, zi) in zip(outer, inner):
        rows.append([bm.verts.new(at(s, y, z)) for y, z in ((0.0015, zo), (0.0015, zi), (-0.0015, zi), (-0.0015, zo))])
    for A, B in zip(rows, rows[1:]):
        for k in range(4):
            bm.faces.new((A[k], B[k], B[(k + 1) % 4], A[(k + 1) % 4]))
    bm.faces.new(list(reversed(rows[0])))
    bm.faces.new(rows[-1])
    o = new_object(name, bm, "section", props)
    return o, finish(o, bevel=0.0, angle=20)


def bands():
    P = {"module": "interior", "show": "cutaway", "skin": "section", "shadow": False}
    ss = [S_FRONT + 0.05] + [x / 20 for x in range(2, int(S_END * 20) + 1)]
    ss = [s for s in ss if s <= S_END]
    out = []
    top = [(s, top_profile(s)) for s in ss]
    out.append(band("section.top", top, [(s, z - SKIN) for s, z in top], P))
    keel = [(s, ring(s)["R3"][1]) for s in ss]
    out.append(band("section.keel", keel, [(s, z + SKIN) for s, z in keel], P))
    glass = [(s, Z_TIP + top) for s, top, _, _ in CANOPY]
    out.append(band("section.canopy", glass, [(s, z - 0.012) for s, z in glass], {**P, "skin": "section.canopy"}))
    return out


def inside(p, margin=0.004):
    s = XN - p.x
    if s < S_FRONT or s > S_END:
        return False
    if 4.8 <= s <= 7.0 and abs(p.y) < 0.42 and p.z < Z_TIP + 1.27:
        return True
    R = ring(s)
    poly = [R["R0"], R["R1"], R["R2"], R["R3"], (-R["R3"][0], R["R3"][1]), (-R["R2"][0], R["R2"][1]), (-R["R1"][0], R["R1"][1])]
    # 凸多边形（y 向右、z 向上看是顺时针）：内侧在每条边行进方向的右边
    q = Vector((p.y, p.z))
    n = len(poly)
    for k in range(n):
        a, b = Vector(poly[k]), Vector(poly[(k + 1) % n])
        e = b - a
        if e.length < 1e-9:
            continue
        nrm = Vector((e.y, -e.x)).normalized()
        if (q - a).dot(nrm) < margin:
            return False
    return True


def containment(objs):
    bad = []
    for o in objs:
        if o.get("show") == "cutaway":
            continue
        worst = 0
        for v in o.data.vertices:
            if not inside(v.co):
                worst += 1
        if worst:
            bad.append(f"{o.name}: {worst}/{len(o.data.vertices)} 顶点")
    return bad
