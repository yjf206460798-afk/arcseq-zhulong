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
from .nose import CANOPY, S_END, S_FRONT, Z_TIP, at, ring, top_profile
from .util import XN, lerp


def band(name, outer, inner, props, material="section", half=0.02):
    """outer / inner：剖切面上的两条折线 [(s, z)…]（等长），之间成带，沿 y 从 −half 到 +half（剖视时 y > 0 一半被切掉，
    切口画成实心剖面：比本体亮一档 + 极淡斜线，见 10-materials.js 的 cap）。"""
    bm = bmesh.new()
    rows = []
    for (s, zo), (_, zi) in zip(outer, inner):
        rows.append([bm.verts.new(at(s, y, z)) for y, z in ((half, zo), (half, zi), (-half, zi), (-half, zo))])
    for A, B in zip(rows, rows[1:]):
        for k in range(4):
            bm.faces.new((A[k], B[k], B[(k + 1) % 4], A[(k + 1) % 4]))
    bm.faces.new(list(reversed(rows[0])))
    bm.faces.new(rows[-1])
    o = new_object(name, bm, material, props)
    return o, finish(o, bevel=0.0, angle=20)


def quad(name, s0, s1, z0, z1, props, material="section", half=0.02):
    """剖切面上的一块矩形实心（眉骨后壁、槽衬板……）。"""
    return band(name, [(s0, z1), (s1, z1)], [(s0, z0), (s1, z0)], props, material, half)


def bands():
    """蒙皮剖面（厚 SKIN = 4 cm）：背线（机头到座舱盖前缘，眉骨下面照样是机身蒙皮）、眉骨外壳、眉骨后壁（中间开遮光盾槽，
    槽上下各一块衬板，盾收在中间）、座舱盖玻璃（青色剖面）、座舱后背部整流、龙骨线。"""
    from .nose import BROW, SLOT_DZ, roof_z, spine_z

    P = {"module": "interior", "show": "cutaway", "skin": "section", "shadow": False, "cut": True, "section": "cap"}
    out = []

    def run(s0, s1, f, step=0.05):
        n = max(2, int((s1 - s0) / step) + 1)
        return [(s0 + (s1 - s0) * k / (n - 1), f(s0 + (s1 - s0) * k / (n - 1))) for k in range(n)]

    c0 = CANOPY[0][0]
    top = run(S_FRONT + 0.03, c0, spine_z)
    out.append(band("section.top", top, [(s, z - SKIN) for s, z in top], P))
    b0, b1, b2 = BROW
    brow = run(b0, b2, top_profile, 0.04)
    out.append(band("section.brow", brow, [(s, max(z - SKIN, spine_z(s))) for s, z in brow], P))
    zs = roof_z(b2, 0.0) + SLOT_DZ
    out.append(quad("section.brow.rear.0", b2 - SKIN, b2, zs + 0.0125, top_profile(b2) - 0.005, P))
    out.append(quad("section.brow.rear.1", b2 - SKIN, b2, spine_z(b2), zs - 0.0125, P))
    for k, (z0, z1) in enumerate(((zs + 0.0125, zs + 0.0175), (zs - 0.0175, zs - 0.0125))):
        out.append(quad(f"section.slot.{k}", b2 - 0.3, b2 - SKIN, z0, z1, P, material="metal"))
    glass = [(s, Z_TIP + t) for s, t, _, _ in CANOPY]
    out.append(band("section.canopy", glass, [(s, z - 0.012) for s, z in glass], {**P, "skin": "section.canopy", "glass": True}, material="glass"))
    aft = run(CANOPY[-1][0], S_END, top_profile)
    out.append(band("section.aft", aft, [(s, z - SKIN) for s, z in aft], P))
    keel = run(S_FRONT + 0.05, S_END, lambda s: ring(s)["R3"][1])
    out.append(band("section.keel", keel, [(s, z + SKIN) for s, z in keel], P))
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
