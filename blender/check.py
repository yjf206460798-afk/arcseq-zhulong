"""化剑逐姿态检查（DESIGN 8.8、10；对应 FIG.01 的 check.mjs）：

    .venv/bin/python blender/check.py [--poses 41] [--out review/<…>/CHECK.json]

不烘焙，只建外形（机头段 + 整机，不建剖视内部：可动件都在蒙皮外）。按页面同一套关节与化剑步骤（各步 smoothstep，
见 engine/50-state.js 的 apply）摆出 N 个姿态（控件值 0 → 1 等分），每个姿态查：
  ① 穿模：不同刚体组（关节链不同）的零件两两 BVHTree.overlap，先用包围盒筛；同一刚体组的零件相对不动，不查；
  ② 不凭空消失：每个姿态零件数、顶点数不变；相邻姿态的顶点位移逐步渐变（一步比前后两步大出 60% 以上算跳变）；
     剑形态里可动件的顶点有九成以上落进机身闭合网格 → 记“藏进机身”；
  ③ 最小间隙：每个可动件全程离别组零件最近的距离（顶点到表面，双向取小，近似到网格精度）。
有穿模、跳变或藏进机身时退出码 1。
"""
import json
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import bpy  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402

from zl import airframe, nose, util  # noqa: E402


def arg(name, default=None):
    a = sys.argv
    return a[a.index(name) + 1] if name in a else default


def smooth(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


def joint_matrix(j, value):
    if j["type"] == "slide":
        return Matrix.Translation(Vector(j["axis"]) * value)
    p = Vector(j["point"])
    return Matrix.Translation(p) @ Matrix.Rotation(math.radians(value), 4, Vector(j["axis"]).normalized()) @ Matrix.Translation(-p)


def main():
    t0 = time.time()
    util.reset()
    ext, meta = nose.build()
    af, _, af_meta = airframe.build()
    ext += af
    joints = {j["name"]: j for j in meta["joints"] + af_meta["joints"]}
    steps = af_meta["controls"][0]["steps"]
    n_pose = int(arg("--poses", 41))
    # 每个零件：静止顶点、面、关节链（自根向下）
    parts = []
    for o in ext:
        me = o.data
        verts = [o.matrix_world @ v.co for v in me.vertices]
        polys = [tuple(p.vertices) for p in me.polygons]
        chain = []
        j = o.get("joint") or ""
        while j and j in joints:
            chain.insert(0, j)
            j = joints[j].get("parent")
        parts.append({"name": o.name, "verts": verts, "polys": polys, "chain": tuple(chain)})
    moving = [p for p in parts if p["chain"]]
    bodies = {p["name"] for p in parts if p["name"] in ("nose.body", "aft.body")}
    print(f"build {time.time() - t0:.1f}s · {len(parts)} parts · {len(moving)} movable · {len(joints)} joints · {len(steps)} steps")

    def pose(v):
        val = {st["joint"]: st["to"] * smooth((v - st["span"][0]) / (st["span"][1] - st["span"][0])) for st in steps}
        mats = {}
        for p in parts:
            M = Matrix.Identity(4)
            for j in p["chain"]:
                M = M @ joint_matrix(joints[j], val.get(j, 0.0))
            mats[p["name"]] = M
        return mats

    def aabb(vs, pad=0.0):
        xs, ys, zs = zip(*vs)
        return (min(xs) - pad, min(ys) - pad, min(zs) - pad, max(xs) + pad, max(ys) + pad, max(zs) + pad)

    def hit(a, b):
        return all(a[i] <= b[i + 3] and b[i] <= a[i + 3] for i in range(3))

    report = {"poses": [], "overlaps": [], "jumps": [], "hidden": [], "clearance": {}}
    prev = None
    step = {p["name"]: [] for p in moving}  # 相邻姿态之间的最大顶点位移
    clear = {p["name"]: (9.0, "", 0.0) for p in moving}
    static_trees = {}
    for k in range(n_pose):
        v = k / (n_pose - 1)
        mats = pose(v)
        cur = {p["name"]: [mats[p["name"]] @ x for x in p["verts"]] for p in parts}
        box = {n: aabb(vs) for n, vs in cur.items()}
        trees = {}

        def tree(name):
            if name not in trees:
                p = next(q for q in parts if q["name"] == name)
                if not p["chain"] and name in static_trees:
                    trees[name] = static_trees[name]
                else:
                    trees[name] = BVHTree.FromPolygons(cur[name], p["polys"])
                    if not p["chain"]:
                        static_trees[name] = trees[name]
            return trees[name]

        found = []
        for m in moving:
            for q in parts:
                if q is m or q["chain"] == m["chain"]:
                    continue
                if q["chain"] and q["name"] < m["name"]:
                    continue  # 两个都可动的对只查一次
                if hit(box[m["name"]], box[q["name"]]):
                    pairs = tree(m["name"]).overlap(tree(q["name"]))
                    if pairs:
                        found.append((m["name"], q["name"], len(pairs)))
                # 间隙：包围盒 0.25 m 内的别组零件，两边顶点到对方表面的最近距离
                if hit(aabb(cur[m["name"]], 0.25), box[q["name"]]):
                    d = 9.0
                    for x in cur[m["name"]]:
                        r = tree(q["name"]).find_nearest(x)
                        if r[0] is not None:
                            d = min(d, r[3])
                    for x in cur[q["name"]]:
                        if hit((x.x, x.y, x.z, x.x, x.y, x.z), aabb(cur[m["name"]], 0.25)):
                            r = tree(m["name"]).find_nearest(x)
                            if r[0] is not None:
                                d = min(d, r[3])
                    if d < clear[m["name"]][0]:
                        clear[m["name"]] = (d, q["name"], v)
        report["poses"].append({"v": round(v, 4), "overlaps": len(found)})
        for a, b, n in found:
            report["overlaps"].append({"v": round(v, 4), "a": a, "b": b, "tris": n})
        if prev is not None:
            for p in moving:
                step[p["name"]].append(max((a - b).length for a, b in zip(cur[p["name"]], prev[p["name"]])))
        prev = cur
    # 跳变：一步的位移比前后两步都大出 60% 以上（且超过 5 cm）——平滑的转动步长是渐变的，凭空跳一下才会这样
    for n, d in step.items():
        for i in range(1, len(d) - 1):
            if d[i] > 0.05 and d[i] > 1.6 * max(d[i - 1], d[i + 1]) + 0.02:
                report["jumps"].append({"v": round((i + 1) / (n_pose - 1), 4), "part": n, "d": round(d[i], 3)})
    report["max_step_m"] = {n: round(max(d), 3) for n, d in step.items()}
    # 剑形态：可动件是否整件藏进机身（顶点向 +z 打射线，与机身相交次数为奇 = 在里面）
    mats = pose(1.0)
    final = {p["name"]: [mats[p["name"]] @ x for x in p["verts"]] for p in parts}
    body_trees = [BVHTree.FromPolygons(final[n], next(q for q in parts if q["name"] == n)["polys"]) for n in bodies]

    def inside(x):
        for t in body_trees:
            n, o = 0, x.copy()
            while True:
                r = t.ray_cast(o, Vector((0, 0, 1)))
                if r[0] is None:
                    break
                n += 1
                o = r[0] + Vector((0, 0, 1e-4))
            if n % 2:
                return True
        return False

    for p in moving:
        vs = final[p["name"]]
        f = sum(inside(x) for x in vs) / len(vs)
        if f > 0.9:
            report["hidden"].append({"part": p["name"], "inside": round(f, 3)})
    report["clearance"] = {n: {"min_m": round(d, 4), "with": w, "at": round(v, 4)} for n, (d, w, v) in sorted(clear.items())}
    report["summary"] = {"poses": n_pose, "parts": len(parts), "movable": len(moving), "overlap_events": len(report["overlaps"]), "jumps": len(report["jumps"]), "hidden": len(report["hidden"]), "min_clearance_m": round(min(d for d, _, _ in clear.values()), 4)}
    out = arg("--out")
    if out:
        os.makedirs(os.path.dirname(out), exist_ok=True)
        json.dump(report, open(out, "w"), ensure_ascii=False, indent=1)
    print(json.dumps(report["summary"], ensure_ascii=False))
    seen = set()
    for o in report["overlaps"]:
        key = (o["a"], o["b"])
        if key not in seen:
            seen.add(key)
            span = [x["v"] for x in report["overlaps"] if (x["a"], x["b"]) == key]
            print(f"  穿模 {o['a']} × {o['b']}：v {min(span)}～{max(span)}（{len(span)} 个姿态）")
    for j in report["jumps"][:20]:
        print("  跳变", j)
    for h in report["hidden"]:
        print("  藏进机身", h)
    tight = sorted(report["clearance"].items(), key=lambda kv: kv[1]["min_m"])[:12]
    for n, c in tight:
        print(f"  间隙 {n}: {c['min_m'] * 100:.1f} cm（与 {c['with']}，v {c['at']}）")
    print(f"check {time.time() - t0:.1f}s")
    sys.exit(1 if report["overlaps"] or report["jumps"] or report["hidden"] else 0)


main()
