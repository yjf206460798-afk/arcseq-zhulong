"""收尾：硬边记录 + 两段倒角（PATTERNS「复刻标准」· 倒角与线）。

为什么先记硬边再倒角：倒角后一条硬边变成两三条缓边，按折角取线会出双线；所以线只从倒角前标记的硬边来，
位置挪到倒角圆弧的中点（离原棱 w·(1 − sin(α/2)) / cos(α/2)，α 为两面内角），法线取原来两侧面的法线——
网页按两侧面朝向定级（一前一后是外轮廓，至少一面朝相机是一级结构线）。曲面件（管、球）不记折边，网页按“曲面轮廓”取线。
"""
import math

import bmesh
from mathutils import Vector


def hard_edges(bm, angle=30.0, bevel=0.0):
    """返回 (要倒角的边, 线数据 [ax, ay, az, bx, by, bz, n1x, n1y, n1z, n2x, n2y, n2z, …])。"""
    thr = math.radians(angle)
    beveled = []
    lines = []
    bm.normal_update()
    for e in bm.edges:
        if len(e.link_faces) == 2:
            f1, f2 = e.link_faces
            n1, n2 = f1.normal, f2.normal
            phi = n1.angle(n2, 0.0)
            if phi < thr:
                continue
            a, b = e.verts[0].co.copy(), e.verts[1].co.copy()
            if bevel > 0:
                alpha = math.pi - phi
                inward = -(n1 + n2)
                if inward.length > 1e-9:
                    inward.normalize()
                    # 凸棱才往里挪；凹棱（内角 > 180°）倒角后线留在原处
                    convex = (f2.calc_center_median() - f1.calc_center_median()).dot(n1) < 0
                    if convex:
                        d = bevel * (1 - math.sin(alpha / 2)) / max(math.cos(alpha / 2), 1e-3)
                        a += inward * d
                        b += inward * d
                beveled.append(e)
            lines += [*a, *b, *n1, *n2]
        elif len(e.link_faces) == 1:
            n = e.link_faces[0].normal
            lines += [*e.verts[0].co, *e.verts[1].co, *n, *n]
    return beveled, lines


def finish(obj, bevel=0.02, angle=30.0, curved=False, segments=2, lines=True):
    """记硬边、倒角、写回网格；返回线数据（扁平浮点表，保留 4 位）。curved：曲面件，不记折边（只记端面一圈）。"""
    me = obj.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    beveled, data = hard_edges(bm, angle=60.0 if curved else angle, bevel=bevel)
    if bevel > 0 and beveled:
        bmesh.ops.bevel(bm, geom=beveled, offset=bevel, offset_type="OFFSET", segments=segments, profile=0.5, affect="EDGES", clamp_overlap=True)
    bm.normal_update()
    for f in bm.faces:
        f.smooth = curved
    if curved:
        # 曲面件：端面与侧面之间标锐边（导出时法线在此断开），其余平滑
        for e in bm.edges:
            if len(e.link_faces) == 2 and e.link_faces[0].normal.angle(e.link_faces[1].normal, 0.0) > math.radians(60):
                e.smooth = False
    bm.to_mesh(me)
    bm.free()
    obj["curved"] = bool(curved)
    return [round(v, 4) for v in data] if lines else []
