"""X1 交审图（CLAUDE.md「每轮工作的规矩」；作者 2026-10-15：每张检查图旁配一张 Tripo 原模型同角度的原样渲染作对照）。

出图（都在 review/<日期>-X1-<轮次>/ 下）：
- 叠图：REFERENCE / AFTER / OVERLAY50（与 X1 设定图正 / 侧 / 背视同画幅、同比例），TRIPO（原样件同机位）。
- 四机位：AFTER-az030 / 120 / 210 / 300（俯仰 10°，正交全身）。
- 头盔特写：睁眼 / 闭眼的 3/4 与正视、侧、背；胸前特写（铭文、脐带接头、扣具）。
- 坐姿：侧 / 3/4（座椅示意块按 seat 表）。
- PAIR-*：左 = 我们的，右 = Tripo 原样（原样件只套物体级变换，网格与自带法线不动，统一中性灰）。
画法 B（Cycles + Freestyle 细线）；线条只取轮廓、边界与我们自己建的硬件的硬棱（Tripo 件不取折痕线：三十万面上满身都是）。
"""
import math
import os

import bpy
import numpy as np
from mathutils import Vector
from PIL import Image

import asis
import draft
import look
import render

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SAMPLES = 48


def _cam_dir(az, el):
    a, e = math.radians(az), math.radians(el)
    return Vector((math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), math.sin(e)))


def shoot(path, target, az, el, size, res, scale=1.0, k=1.0, samples=SAMPLES, lines=True, transparent=False):
    """正交机位：朝 target，方位 az、俯仰 el，画幅 size 米（长边），分辨率 res=(w, h)。"""
    sc = bpy.context.scene
    cam = render.camera()
    cam.data.type = "ORTHO"
    d = _cam_dir(az, el)
    cam.location = Vector(target) + d * 6
    cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    cam.data.ortho_scale = size
    cam.data.clip_end = 20
    sc.render.resolution_x, sc.render.resolution_y = res
    right = -(d.cross(Vector((0, 0, 1))).normalized())
    render.studio(target=target, scale=scale, right=tuple(right), toward=tuple(d))
    render.cycles(path, samples=samples, transparent=transparent, lines=lines, k=k, crease=False)


def pair(a, b, out, labels=("銜燭 X1", "Tripo 原样")):
    A, Bm = Image.open(a).convert("RGB"), Image.open(b).convert("RGB")
    W = Image.new("RGB", (A.width + Bm.width + 8, max(A.height, Bm.height)), (16, 21, 24))
    W.paste(A, (0, 0))
    W.paste(Bm, (A.width + 8, 0))
    try:
        from PIL import ImageDraw, ImageFont

        f = ImageFont.truetype("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc", max(14, A.height // 45))
        d = ImageDraw.Draw(W)
        d.text((12, 8), labels[0], font=f, fill=(220, 233, 235))
        d.text((A.width + 20, 8), labels[1], font=f, fill=(128, 153, 163))
    except OSError:
        pass
    W.save(out)


class Twins:
    """原样件：身体（藏掉起稿自带头盔）、头盔、胸前接头。"""

    def __init__(self, ours, helmet_src):
        self.ours = ours
        body = [o for o in ours if o.get("src_file", "").endswith("hd分件.glb")]
        hel = [o for o in ours if o.name == "xz.helmet.shell"]
        plug = [o for o in ours if o.name == "xz.suit.umbilical"]
        self.body = asis.twin(body[:1], "asis.body")
        self.helmet = asis.twin(hel, "asis.helmet")
        self.plug = asis.twin(plug, "asis.plug")
        self.draft_helmet = [o for o in self.body if o.get("src_name") == helmet_src]
        asis.clay(self.body + self.helmet + self.plug)

    def show(self, raw, with_draft_helmet=False):
        objs = self.body + self.helmet + self.plug
        for o in objs:
            o.hide_render = not raw
        if raw:
            # 原样：身体底稿 + Smart Mesh 头盔 + 接头；起稿自带的头盔藏掉（换掉了的那顶）
            for o in self.draft_helmet:
                o.hide_render = not with_draft_helmet
            for o in self.helmet + self.plug:
                o.hide_render = with_draft_helmet
        for o in self.ours:
            o.hide_render = raw


def lines_setup(objs):
    """线条：我们自己建的件按 40° 锐边出 L2；Tripo 件（对象属性 tripo）不出折痕线。"""
    for o in objs:
        if o.get("tripo"):
            at = o.data.attributes.get("freestyle_edge")
            if at is not None:
                o.data.attributes.remove(at)
        else:
            draft.mark_hard(o)


def overlays(out, tw, k=3):
    src = Image.open(os.path.join(ROOT, "refs", "concept", "X1_衔烛设定图.png")).convert("RGB")
    cal0 = render.calib("soft.front")
    x0, y0, x1, y1 = cal0["region"]
    W, H = (x1 - x0) * k, (y1 - y0) * k
    views = (("front", "soft.front"), ("side", "soft.side"), ("back", "soft.back"))
    tmp = os.path.join(out, "frames")
    os.makedirs(tmp, exist_ok=True)
    look.flat_colours()
    tw.show(False)
    shifts = {view: render.align(view, fig, render.calib(fig), k, tmp) for view, fig in views}
    look.cycles_materials()
    res = {}
    for who, raw in (("AFTER", False), ("TRIPO", True)):
        tw.show(raw, with_draft_helmet=True)
        img = Image.new("RGBA", (W, H), tuple(int(c * 255) for c in render.BG) + (255,))
        for view, fig in views:
            cal = render.calib(fig)
            render.place_ortho(view, cal, k, shift=shifts[view])
            _, right, toward = render.VIEWS[view]
            render.studio(target=(0, 0, 1.0), right=right, toward=toward)
            p = os.path.join(tmp, f"{who}-{view}.png")
            render.cycles(p, samples=SAMPLES, transparent=True, k=k, crease=False)
            img.alpha_composite(Image.open(p).convert("RGBA"))
        img = img.convert("RGB")
        img.save(os.path.join(out, f"{who}-soft.png"))
        res[who] = img
    ref = src.crop((x0, y0, x1, y1)).resize((W, H), Image.LANCZOS)
    ref.save(os.path.join(out, "REFERENCE-soft.png"))
    Image.blend(ref, res["AFTER"], 0.5).save(os.path.join(out, "OVERLAY50-soft.png"))
    Image.blend(ref, res["TRIPO"], 0.5).save(os.path.join(out, "OVERLAY50-soft-tripo.png"))
    pair(os.path.join(out, "AFTER-soft.png"), os.path.join(out, "TRIPO-soft.png"), os.path.join(out, "PAIR-soft.png"))
    return shifts


def four_views(out, tw, state_down=0.0):
    sv = bpy.data.objects.get("xz.helmet.sunvisor")
    if sv is not None:
        sv.data.shape_keys.key_blocks["down"].value = state_down
    for az in (30, 120, 210, 300):
        for who, raw in (("AFTER", False), ("TRIPO", True)):
            tw.show(raw)
            shoot(os.path.join(out, f"{who}-az{az:03d}.png"), (0.0, 0.0, 0.92), az, 10, 2.0, (1000, 1100), k=1.2)
        pair(os.path.join(out, f"AFTER-az{az:03d}.png"), os.path.join(out, f"TRIPO-az{az:03d}.png"), os.path.join(out, f"PAIR-az{az:03d}.png"))


def closeups(out, tw):
    sv = bpy.data.objects["xz.helmet.sunvisor"]
    shell = bpy.data.objects["xz.helmet.shell"]
    V = draft.verts(shell)
    c = Vector(((V.min(0) + V.max(0)) / 2).tolist()) + Vector((0.0, 0, -0.02))
    shots = (("helmet-open-34", 32, 8, 0.0), ("helmet-closed-34", 32, 8, 1.0), ("helmet-open-front", 0, 2, 0.0), ("helmet-closed-front", 0, 2, 1.0),
             ("helmet-side", 90, 0, 0.0), ("helmet-back", 200, 12, 0.0))
    for name, az, el, down in shots:
        sv.data.shape_keys.key_blocks["down"].value = down
        tw.show(False)
        shoot(os.path.join(out, f"AFTER-{name}.png"), c, az, el, 0.42, (900, 900), scale=0.35, k=1.6, samples=64)
        if down or name in ("helmet-side", "helmet-back"):
            # 原样头盔是闭眼稿（面罩带就是落下的遮光面罩），睁眼图配同角度的闭眼原样
            tw.show(True)
            shoot(os.path.join(out, f"TRIPO-{name}.png"), c, az, el, 0.42, (900, 900), scale=0.35, k=1.6, samples=64)
    sv.data.shape_keys.key_blocks["down"].value = 0.0
    for name in ("helmet-open-34", "helmet-open-front"):
        twin = name.replace("open", "closed")
        pair(os.path.join(out, f"AFTER-{name}.png"), os.path.join(out, f"TRIPO-{twin}.png"), os.path.join(out, f"PAIR-{name}.png"),
             labels=("銜燭 X1 · 睁眼", "Tripo 原样（闭眼稿）"))
    for name in ("helmet-closed-34", "helmet-closed-front", "helmet-side", "helmet-back"):
        pair(os.path.join(out, f"AFTER-{name}.png"), os.path.join(out, f"TRIPO-{name}.png"), os.path.join(out, f"PAIR-{name}.png"))
    # 胸前（铭文、脐带接头、扣具）
    c2 = Vector((0.1, 0.05, 1.3))
    for who, raw in (("AFTER", False), ("TRIPO", True)):
        tw.show(raw, with_draft_helmet=True)
        shoot(os.path.join(out, f"{who}-chest-34.png"), c2, 25, 8, 0.45, (900, 900), scale=0.35, k=1.6, samples=64)
    pair(os.path.join(out, "AFTER-chest-34.png"), os.path.join(out, "TRIPO-chest-34.png"), os.path.join(out, "PAIR-chest-34.png"))
    # 设定图头盔面板，便于并排看
    import json

    src = Image.open(os.path.join(ROOT, "refs", "concept", "X1_衔烛设定图.png")).convert("RGB")
    helm = json.load(open(render.CALIB))["panels"]["helmet"]["region"]
    crop = src.crop(tuple(helm))
    crop.resize((crop.width * 3, crop.height * 3), Image.LANCZOS).save(os.path.join(out, "REFERENCE-helmet.png"))


def visor_coverage(out, tw):
    """验收（作者 2026-10-15）：前视和左右 45° 正交，三行 = 底稿原样 / 遮光罩落下 / 收起。落下时要盖满底稿原来的整条
    面罩带，左右两端都抵到面框，不留灰边。拼成一张 CHECK-visor-coverage.png。"""
    sv = bpy.data.objects["xz.helmet.sunvisor"]
    shell = bpy.data.objects["xz.helmet.shell"]
    V = draft.verts(shell)
    c = Vector(((V.min(0) + V.max(0)) / 2).tolist()) + Vector((0.0, 0, -0.02))
    rows = (("底稿原样", True, 1.0), ("遮光罩落下", False, 1.0), ("遮光罩收起", False, 0.0))
    views = (("左 45°", 45), ("前视", 0), ("右 45°", -45))
    tiles = []
    for label, raw, down in rows:
        sv.data.shape_keys.key_blocks["down"].value = down
        tw.show(raw)
        row = []
        for vname, az in views:
            p = os.path.join(out, "frames", f"cov-{int(raw)}-{down:.0f}-{az}.png")
            shoot(p, c, az, 3, 0.36, (640, 640), scale=0.35, k=1.4, samples=48)
            row.append(Image.open(p).convert("RGB"))
        tiles.append((label, row))
    sv.data.shape_keys.key_blocks["down"].value = 0.0
    from PIL import ImageDraw, ImageFont

    W = Image.new("RGB", (120 + 640 * 3, 40 + 640 * 3), (16, 21, 24))
    d = ImageDraw.Draw(W)
    f = ImageFont.truetype("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc", 22)
    for i, (vname, _) in enumerate(views):
        d.text((120 + 640 * i + 280, 8), vname, font=f, fill=(220, 233, 235))
    for j, (label, row) in enumerate(tiles):
        d.text((10, 40 + 640 * j + 300), label, font=f, fill=(220, 233, 235))
        for i, im in enumerate(row):
            W.paste(im, (120 + 640 * i, 40 + 640 * j))
    W.save(os.path.join(out, "CHECK-visor-coverage.png"))


def standing(out, objs, helmet_src):
    os.makedirs(out, exist_ok=True)
    look.cycles_materials()
    lines_setup(objs)
    tw = Twins(objs, helmet_src)
    shifts = overlays(out, tw)
    look.cycles_materials()
    four_views(out, tw)
    closeups(out, tw)
    visor_coverage(out, tw)
    tw.show(False)
    for o in tw.body + tw.helmet + tw.plug:
        o.hide_render = True
    return shifts


def seat_proxy():
    """座椅示意块（seat 表）：坐垫面、椅背面、左侧板，半透明灰。"""
    import geo
    from mathutils import Matrix

    from seat import SEAT

    out = []
    m = "seatproxy"
    t = SEAT["pan_tilt"]
    R = Matrix.Rotation(-t, 3, "Y")
    out.append(geo.box("seatproxy.pan", Vector((0.24, 0, SEAT["pan_h"] - 0.04)), (0.48, 0.42, 0.08), R, m))
    b = SEAT["back"]
    Rb = Matrix.Rotation(-b, 3, "Y")
    along = Vector((-math.sin(b), 0, math.cos(b)))
    nrm = Vector((math.cos(b), 0, math.sin(b)))
    out.append(geo.box("seatproxy.back", along * 0.4 + nrm * (SEAT["back_n"] - 0.04), (0.08, 0.42, 0.8), Rb, m))
    p = Vector(SEAT["seat_side"]["L"].tolist())
    out.append(geo.box("seatproxy.side", p + Vector((0.05, 0.01, -0.02)), (0.4, 0.02, 0.16), Matrix(), m))
    mat = bpy.data.materials.get(m)
    mat.use_nodes = True
    bs = mat.node_tree.nodes.get("Principled BSDF")
    bs.inputs["Base Color"].default_value = (0.08, 0.09, 0.1, 1)
    bs.inputs["Roughness"].default_value = 0.8
    return out


def seated(out, objs):
    os.makedirs(out, exist_ok=True)
    look.cycles_materials()
    lines_setup(objs)
    for o in objs:
        o.hide_render = False
    proxy = seat_proxy()
    for name, az, el in (("seated-side", 90, 0), ("seated-34", 35, 12)):
        shoot(os.path.join(out, f"AFTER-{name}.png"), (0.25, 0.0, 0.45), az, el, 1.7, (1000, 900), k=1.2)
    for o in proxy:
        bpy.data.objects.remove(o)


def before(out, glb):
    """BEFORE：上一版（mhclo 服装壳路线导出的 assets/xianzhu.glb）同机位：四机位 + 头盔 3/4。"""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=glb)
    objs = [o for o in bpy.data.objects if o.type == "MESH"]
    look.cycles_materials()
    os.makedirs(out, exist_ok=True)
    for az in (30, 120, 210, 300):
        shoot(os.path.join(out, f"BEFORE-az{az:03d}.png"), (0.0, 0.0, 0.92), az, 10, 2.0, (1000, 1100), k=1.2)
    shell = next((o for o in objs if o.name.startswith("xz.helmet.shell")), None)
    if shell is not None:
        V = np.array([tuple(shell.matrix_world @ v.co) for v in shell.data.vertices])
        c = Vector(((V.min(0) + V.max(0)) / 2).tolist()) + Vector((0.0, 0, -0.02))
        shoot(os.path.join(out, "BEFORE-helmet-34.png"), c, 32, 8, 0.42, (900, 900), scale=0.35, k=1.6, samples=64)
