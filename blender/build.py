"""烛龙几何母版（Blender 建模脚本）：从零生成模型，烘焙，导出网页资源，按需出 Cycles 渲染。

    .venv/bin/python blender/build.py                 # 外形 + 内部 + 烘焙 + 导出 assets/
    .venv/bin/python blender/build.py --fast          # 不烘焙（快速看形，写到 dist/fast/）
    .venv/bin/python blender/build.py --render-only out.png [--shot hero|nose|cutaway] [--power 0|1] [--samples 64]
    .venv/bin/python blender/build.py --blend         # 另存 dist/zhulong.blend（产物，不手改）

产物（assets/）：zhulong.glb（常驻外形）、zhulong-interior.glb（剖视内部，按需加载）、zhulong.json（线、分割线、地标、标注、剖面）、
zhulong-skin.png（细节：刻线 / 涂装 / AO）、zhulong-skin-pbr.png（B 画法：粗糙度 + 法线）。
母版是脚本，不是文件（docs/BLENDER.md 规矩 1）。
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import bpy  # noqa: E402

from zl import bake, interior, nose, section, util  # noqa: E402


def arg(name, default=None):
    a = sys.argv
    return a[a.index(name) + 1] if name in a else default


def tris(objs):
    n = 0
    for o in objs:
        o.data.calc_loop_triangles()
        n += len(o.data.loop_triangles)
    return n


def main():
    t0 = time.time()
    util.reset()
    ext, meta = nose.build()
    # 剖视（剖切面 y = 0，从 +y 一侧看）：整件在近侧或远侧的外部件剖视时不画（近侧的挡住内部，远侧的在蒙皮外、线会透过蒙皮）；
    # 跨中线的（机身、座舱盖、光窗、探头……）被剖切面切开
    spans = []
    for o in ext:
        ys = [v.co.y for v in o.data.vertices]
        if min(ys) > 0.002 or max(ys) < -0.002:
            o["show"] = "!cutaway"
        else:
            o["cut"] = True
            spans.append(o.name)
    print("cut:", " ".join(sorted(spans)))
    pairs, callouts = interior.build()
    inner = [o for o, _ in pairs]
    meta["edges"].update({o.name: l for o, l in pairs})
    meta["callouts"] += callouts
    bands = section.bands()
    meta["edges"].update({o.name: l for o, l in bands})
    inner += [o for o, _ in bands]
    problems = section.containment(inner)
    t1 = time.time()
    print(f"build {t1 - t0:.1f}s · exterior {len(ext)} objects {tris(ext)} tris · interior {len(inner)} objects {tris(inner)} tris · {meta.get('tiles')} scale tiles")
    for p in problems[:40]:
        print("  穿出蒙皮:", p)
    print(f"  穿出蒙皮合计 {len(problems)} 件")
    if "--render-only" in sys.argv:
        from zl import render

        render.cycles(ext + inner, meta, arg("--render-only"), shot=arg("--shot", "hero"), samples=int(arg("--samples", 64)), size=arg("--size", "1600x1072"), power=float(arg("--power", 1.0)))
        print(f"render {time.time() - t1:.1f}s → {arg('--render-only')}")
        return
    fast = "--fast" in sys.argv
    assets = os.path.join(ROOT, "dist", "fast") if fast else os.path.join(ROOT, "assets")
    os.makedirs(assets, exist_ok=True)
    if not fast:
        bake.vertex_ao(ext, samples=int(arg("--ao-samples", 64)), hide=inner)
        bake.vertex_ao(inner, samples=int(arg("--ao-samples", 64)), hide=ext)
        meta["detail"] = bake.detail_texture(ext, meta, assets, size=int(arg("--tex", 2048)), hide=inner)
    t2 = time.time()
    bake.export(ext, os.path.join(assets, "zhulong.glb"))
    bake.export(inner, os.path.join(assets, "zhulong-interior.glb"))
    meta["edges"] = {k: [round(x, 4) for x in v] for k, v in meta["edges"].items()}  # 0.1 mm，够了
    with open(os.path.join(assets, "zhulong.json"), "w") as f:
        json.dump(meta, f, ensure_ascii=False, separators=(",", ":"))
    print(f"bake {t2 - t1:.1f}s · export {time.time() - t2:.1f}s")
    if "--blend" in sys.argv:
        os.makedirs(os.path.join(ROOT, "dist"), exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOT, "dist", "zhulong.blend"))


main()
