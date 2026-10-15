"""銜燭 · 后备路线（mhclo 式服装壳，作者 2026-10-15 起改以 Tripo 起稿为底，见 build.py）：从零生成人体底模、软态服装、头盔，导出网页资源，出审图渲染。

    .venv/bin/python blender/xianzhu/build_mhclo.py --quick            # 只建模 + Workbench 三视图（dist/xianzhu/quick/）
    .venv/bin/python blender/xianzhu/build_mhclo.py                    # 建模 + 导出 assets/xianzhu.glb、xianzhu.json
    .venv/bin/python blender/xianzhu/build_mhclo.py --review <目录>     # 再出交审图（Cycles 三视图 + 平涂三视图 + 头盔特写 + 叠图）

母版是脚本，不是文件（docs/BLENDER.md 规矩 1）；产物 .glb / .json / 渲染图都不手改。
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402

import body as B  # noqa: E402
import helmet  # noqa: E402
import suit  # noqa: E402
from mh import MH  # noqa: E402

PROPS = {"figure": "xianzhu"}


def arg(name, default=None):
    a = sys.argv
    return a[a.index(name) + 1] if name in a else default


def model():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    t0 = time.time()
    mh = MH()
    body = B.Body(mh)
    body.smooth()
    body.rigged()
    rest = body.evaluated()
    B.stand(body)
    posed = body.evaluated()
    parts, seams, ch = suit.build(mh, body, rest, posed, PROPS)
    collar = bpy.data.objects["xz.suit.collar"]
    collar_top = max(v.co.z for v in collar.data.vertices)
    heads, hidden = B.head_parts(body, rest, posed, collar_top, PROPS)
    parts += heads
    hel, _ = helmet.build(body, PROPS, state=arg("--helmet", "soft"))
    parts += hel
    body.obj.hide_render = True
    tag_layers()
    body.stand_V = posed
    body.rest_V = rest
    body.stand_head = body.pb("head").matrix.copy()
    print(f"model {time.time() - t0:.1f}s · {len(parts)} suit parts · {len(seams)} seam lines")
    return mh, body, parts, seams, ch


LAYER_RULES = (("xz.bladder.", "L2"), ("xz.harness.", "L3"), ("xz.suit.", "L3"), ("xz.kneepad.", "L3"), ("xz.glove.", "L3"), ("xz.boot.", "L3"),
               ("xz.helmet.", "L5"), ("xz.body.", "body"))


def tag_layers():
    """每个零件写上所属层（spec.LAYERS），X2 分层爆炸按它分组。"""
    for o in bpy.data.objects:
        for pre, lay in LAYER_RULES:
            if o.name.startswith(pre):
                o["layer"] = lay
                break


def xz_objects():
    return [o for o in bpy.data.objects if o.type == "MESH" and o.name.startswith("xz.") and o.name != "xz.body" and not o.hide_render]


def repose(body, V_new, suffix):
    """全部服装件换到新姿态：服装 / 面部 / 眼睛按 mhclo 式绑定跟身体（绑在站姿身体上）；头盔整体跟头骨刚体走。
    返回新对象列表（原站姿对象不动）。"""
    from bind import Binding

    M = body.rig.matrix_world @ body.pb("head").matrix @ (body.rig.matrix_world @ body.stand_head).inverted()
    out = []
    for o in xz_objects():
        me = o.data.copy()
        if me.shape_keys:
            # 形态键（遮光面罩 down）跟着刚体走：头盔件整体变换，键也一起变
            pass
        V = np.empty(len(me.vertices) * 3)
        me.vertices.foreach_get("co", V)
        V = V.reshape(-1, 3)
        if o.name.startswith("xz.helmet."):
            W = np.array([tuple(M @ Vector(v)) for v in V])
            if me.shape_keys:
                for kb in me.shape_keys.key_blocks:
                    for d in kb.data:
                        d.co = M @ d.co
        else:
            W = Binding(body.stand_V, body.faces, V).apply(V_new)
        me.vertices.foreach_set("co", W.ravel())
        me.update()
        n = bpy.data.objects.new(o.name + suffix, me)
        for k in o.keys():
            n[k] = o[k]
        bpy.context.scene.collection.objects.link(n)
        out.append(n)
    return out


def export(objs, path):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", use_selection=True, export_extras=True, export_apply=True, export_normals=True,
                              export_texcoords=True, export_vertex_color="ACTIVE", export_all_vertex_colors=False, export_materials="EXPORT",
                              export_image_format="NONE", export_yup=True)


def tris(objs):
    n = 0
    for o in objs:
        o.data.calc_loop_triangles()
        n += len(o.data.loop_triangles)
    return n


def review(out, k=3, samples=48):
    """交审图：设定图同画幅三视图（REFERENCE / AFTER / 50% 叠图）、平涂分色叠图与逐类 IoU、头盔特写。"""
    import numpy as np
    from PIL import Image

    import look
    import render

    os.makedirs(out, exist_ok=True)
    tmp = os.path.join(out, "frames")
    os.makedirs(tmp, exist_ok=True)
    src = Image.open(os.path.join(ROOT, "refs", "concept", "X1_衔烛设定图.png")).convert("RGB")
    split = Image.open(os.path.join(ROOT, "refs", "concept", "X1_衔烛设定图_分色.png")).convert("RGB")
    cal0 = render.calib("soft.front")
    x0, y0, x1, y1 = cal0["region"]
    W, H = (x1 - x0) * k, (y1 - y0) * k
    views = (("front", "soft.front"), ("side", "soft.side"), ("back", "soft.back"))
    # —— 水平对位（侧视按躯干、正背视按腿段质心，与设定图标定同一量法）——
    look.flat_colours()
    shifts = {view: render.align(view, fig, render.calib(fig), k, tmp) for view, fig in views}
    print("align shift (m):", {k_: round(v, 4) for k_, v in shifts.items()})
    # —— 画法 B（Cycles + Freestyle）——
    look.cycles_materials()
    render.mark_lines()
    after = Image.new("RGBA", (W, H), tuple(int(c * 255) for c in render.BG) + (255,))
    for view, fig in views:
        cal = render.calib(fig)
        render.place_ortho(view, cal, k, shift=shifts[view])
        _, right, toward = render.VIEWS[view]
        render.studio(target=(0, 0, 1.0), right=right, toward=toward)
        p = os.path.join(tmp, f"{view}.png")
        render.cycles(p, samples=samples, transparent=True, k=k)
        after.alpha_composite(Image.open(p).convert("RGBA"))
    after = after.convert("RGB")
    ref = src.crop((x0, y0, x1, y1)).resize((W, H), Image.LANCZOS)
    ref.save(os.path.join(out, "REFERENCE-soft.png"))
    after.save(os.path.join(out, "AFTER-soft.png"))
    Image.blend(ref, after, 0.5).save(os.path.join(out, "OVERLAY50-soft.png"))
    # —— 平涂（分色 C 表）与分色图比：逐类 IoU（1× 像素，按各人像的面板偏移对齐）——
    look.flat_colours()
    flat = Image.new("RGB", (W, H), (255, 255, 255))
    for view, fig in views:
        cal = render.calib(fig)
        render.place_ortho(view, cal, k, shift=shifts[view])
        p = os.path.join(tmp, f"flat-{view}.png")
        render.workbench(p, flat=True, background=(1, 1, 1), transparent=True)
        im = Image.open(p).convert("RGBA")
        flat.paste(im, (0, 0), im)
    flat.save(os.path.join(out, "AFTER-soft-flat.png"))
    meta = json.load(open(render.REGIONS))
    dx, dy = next(f for f in meta["figures"] if f["name"] == "soft.front")["dx"], next(f for f in meta["figures"] if f["name"] == "soft.front")["dy"]
    sref = split.crop((x0 - dx, y0 - dy, x1 - dx, y1 - dy))
    sref.resize((W, H), Image.NEAREST).save(os.path.join(out, "REFERENCE-soft-split.png"))
    Image.blend(sref.resize((W, H), Image.LANCZOS), flat, 0.5).save(os.path.join(out, "OVERLAY50-soft-split.png"))
    iou = class_iou(np.asarray(sref), np.asarray(flat.resize(sref.size, Image.NEAREST)))
    # —— 头盔特写（4×：设定图全身视图的 4 倍像素/米）——
    look.cycles_materials()
    helmet_closeups(out, k * 4 // 3)
    with open(os.path.join(out, "metrics.json"), "w") as fp:
        json.dump({"iou_soft": iou, "align_shift_m": shifts}, fp, ensure_ascii=False, indent=1)
    print("IoU", iou)


def class_iou(ref, img):
    """分色图 vs 平涂渲染：按 C 表类别的 IoU（面料、气囊、挽具、盔、棕色件、面部）。"""
    sys.path.insert(0, HERE)
    from x0_split import classify
    from PIL import Image

    A = classify(Image.fromarray(ref))
    B_ = classify(Image.fromarray(img))
    out = {}
    fig_a = (A != "white")
    fig_b = (B_ != "white")
    out["figure"] = round(float((fig_a & fig_b).sum() / max(1, (fig_a | fig_b).sum())), 3)
    for c in ("fabric", "bladder", "harness", "helmet", "brown", "skin", "spine"):
        a, b = A == c, B_ == c
        u = (a | b).sum()
        if u:
            out[c] = round(float((a & b).sum() / u), 3)
    return out


def helmet_closeups(out, k):
    import math

    from mathutils import Vector

    import render

    sc = bpy.context.scene
    shell = bpy.data.objects["xz.helmet.shell"]
    import numpy as np

    V = np.array([tuple(shell.matrix_world @ v.co) for v in shell.data.vertices])
    c = Vector(((V.min(0) + V.max(0)) / 2).tolist()) + Vector((0.01, 0, -0.03))
    cal = render.calib("soft.front")
    ppm = cal["ppm"] * k
    cam = render.camera()
    cam.data.type = "ORTHO"
    sc.render.resolution_x = sc.render.resolution_y = int(0.42 * ppm)
    cam.data.ortho_scale = 0.42
    shots = (("helmet-open-34", 32, 8, 0.0), ("helmet-open-front", 0, 2, 0.0), ("helmet-side", 90, 0, 0.0), ("helmet-back", 200, 12, 0.0),
             ("helmet-closed-34", 32, 8, 1.0), ("helmet-closed-front", 0, 2, 1.0))
    sv = bpy.data.objects["xz.helmet.sunvisor"]
    for name, az, el, down in shots:
        sv.data.shape_keys.key_blocks["down"].value = down
        a, e = math.radians(az), math.radians(el)
        d = Vector((math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), math.sin(e)))
        cam.location = c + d * 3
        cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
        right = d.cross(Vector((0, 0, 1))).normalized() * -1
        render.studio(target=c, scale=0.35, right=tuple(right), toward=tuple(d))
        render.cycles(os.path.join(out, f"AFTER-{name}.png"), samples=64, transparent=False, k=k / 3)
    sv.data.shape_keys.key_blocks["down"].value = 0.0
    # 胸前细节（铭文、脐带接口、挽具扣件）：同样 4×
    c2 = Vector((0.12, 0.06, 1.3))
    cam.data.ortho_scale = 0.42
    d = Vector((math.cos(math.radians(8)) * math.cos(math.radians(25)), math.cos(math.radians(8)) * math.sin(math.radians(25)), math.sin(math.radians(8))))
    cam.location = c2 + d * 3
    cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    render.studio(target=c2, scale=0.35, right=tuple(d.cross(Vector((0, 0, 1))).normalized() * -1), toward=tuple(d))
    render.cycles(os.path.join(out, "AFTER-chest-34.png"), samples=64, transparent=False, k=k / 3)
    # 设定图头盔面板（睁眼 / 闭眼），放大到同样的像素/米，便于并排看
    from PIL import Image

    src = Image.open(os.path.join(ROOT, "refs", "concept", "X1_衔烛设定图.png")).convert("RGB")
    x0, y0, x1, y1 = render.calib("soft.front")["region"]
    helm = json.load(open(render.CALIB))["panels"]["helmet"]["region"]
    crop = src.crop(tuple(helm))
    crop.resize((crop.width * 3, crop.height * 3), Image.LANCZOS).save(os.path.join(out, "REFERENCE-helmet.png"))


def main():
    mh, body, parts, seams, ch = model()  # noqa（后备路线；导出会覆盖 assets/xianzhu*.glb）
    if "--review" in sys.argv:
        review(os.path.join(ROOT, arg("--review")), k=int(arg("--k", 3)), samples=int(arg("--samples", 48)))
        return
    if "--export" in sys.argv or "--quick" not in sys.argv:
        from seat import SEAT

        assets = os.path.join(ROOT, "assets")
        os.makedirs(assets, exist_ok=True)
        stand = xz_objects()
        export(stand, os.path.join(assets, "xianzhu.glb"))
        V_seat = B.sit(body, SEAT)
        seated = repose(body, V_seat, ".seated")
        # 两份 GLB 零件同名：站姿件改名让位，坐姿件用原名导出，再换回来
        names = [o.name for o in stand]
        for o in stand:
            o.name = o.name + ".stand"
            o.hide_render = True
        for o, n in zip(seated, names):
            o.name = n
        export(seated, os.path.join(assets, "xianzhu-seated.glb"))
        for o, n in zip(seated, names):
            o.name = n + ".seated"
        for o, n in zip(stand, names):
            o.name = n
        from bind import Binding

        seams_seated = []
        for q in seams:
            P = np.array(q["points"])
            W = Binding(body.stand_V, body.faces, P).apply(V_seat)
            seams_seated.append({**q, "points": W.round(4).tolist()})
        meta = {
            "figure": "xianzhu", "units": "m", "frame": "x 前、y 左、z 上；站姿原点在两脚之间地面，坐姿原点 = 座椅参考点 SRP（blender/xianzhu/seat.py）",
            "state": "soft", "layers": {k: v for k, v in [(o.name, o.get("layer")) for o in stand]},
            "seams": [{**q, "points": np.round(q["points"], 4).tolist()} for q in seams], "seams_seated": seams_seated,
            "seat": {k: (v.tolist() if hasattr(v, "tolist") else ({kk: vv.tolist() for kk, vv in v.items()} if isinstance(v, dict) else v)) for k, v in SEAT.items()},
            "tris": {"stand": tris(stand), "seated": tris(seated)},
        }
        with open(os.path.join(assets, "xianzhu.json"), "w") as fp:
            json.dump(meta, fp, ensure_ascii=False, separators=(",", ":"))
        print(f"export · stand {meta['tris']['stand']} tris · seated {meta['tris']['seated']} tris · {len(stand)} objects")
        if "--seated-review" in sys.argv:
            seated_review(os.path.join(ROOT, arg("--seated-review")), seated)
        return
    if "--quick" in sys.argv:
        import render
        import look

        look.flat_colours()
        out = os.path.join(ROOT, "dist", "xianzhu", "quick")
        os.makedirs(out, exist_ok=True)
        for view, fig in (("front", "soft.front"), ("side", "soft.side"), ("back", "soft.back")):
            cal = render.calib(fig)
            render.place_ortho(view, cal, 2)
            render.workbench(os.path.join(out, f"{view}.png"))
        return


main()
