"""烛龙几何母版（Blender 建模脚本）：从零生成模型，烘焙，导出网页资源，按需出 Cycles 渲染。

    .venv/bin/python blender/build.py                 # 建模 + 顶点 AO + 细节贴图 + 导出 assets/zhulong.glb / .json / zhulong-skin.png
    .venv/bin/python blender/build.py --fast          # 不烘焙（快速看形，写到 dist/fast/）
    .venv/bin/python blender/build.py --render out.png [--shot hero|nose] [--samples 64]
    .venv/bin/python blender/build.py --blend         # 另存 dist/zhulong.blend（产物，不手改）

母版是脚本，不是文件（docs/BLENDER.md 规矩 1）：.blend / .glb 都是产物；作者手调的地方由 Claude 写回脚本。
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import bpy  # noqa: E402

from zl import bake, nose, util  # noqa: E402


def arg(name, default=None):
    a = sys.argv
    return a[a.index(name) + 1] if name in a else default


def main():
    t0 = time.time()
    util.reset()
    objs, meta = nose.build()
    t1 = time.time()
    fast = "--fast" in sys.argv
    if "--render-only" in sys.argv:
        # 只出渲染：不烘焙、不导出（用 assets/ 里现有的细节贴图）
        from zl import render

        render.cycles(objs, meta, arg("--render-only"), shot=arg("--shot", "hero"), samples=int(arg("--samples", 64)), size=arg("--size", "1600x1072"), power=float(arg("--power", 1.0)))
        print(f"render {time.time() - t1:.1f}s → {arg('--render-only')}")
        return
    # --fast 只看形：写到 dist/fast/，不覆盖 assets/ 里烘焙过的产物
    assets = os.path.join(ROOT, "dist", "fast") if fast else os.path.join(ROOT, "assets")
    os.makedirs(assets, exist_ok=True)
    if not fast:
        bake.vertex_ao(objs, samples=int(arg("--ao-samples", 64)))
        meta["detail"] = {"skin": bake.detail_texture(objs, meta, os.path.join(assets, "zhulong-skin.png"), size=int(arg("--tex", 2048)))}
    t2 = time.time()
    bake.export(objs, os.path.join(assets, "zhulong.glb"))
    with open(os.path.join(assets, "zhulong.json"), "w") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    t3 = time.time()
    tris = sum(len(o.data.loop_triangles) for o in objs if o.type == "MESH" and not o.data.calc_loop_triangles())
    print(f"build {t1 - t0:.1f}s · bake {t2 - t1:.1f}s · export {t3 - t2:.1f}s · {len(objs)} objects · {tris} triangles · {meta.get('tiles')} scale tiles/side")
    if "--blend" in sys.argv:
        os.makedirs(os.path.join(ROOT, "dist"), exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOT, "dist", "zhulong.blend"))
    if "--render" in sys.argv:
        from zl import render

        render.cycles(objs, meta, arg("--render"), shot=arg("--shot", "hero"), samples=int(arg("--samples", 64)), size=arg("--size", "1600x1072"))
        print(f"render {time.time() - t3:.1f}s → {arg('--render')}")


main()
