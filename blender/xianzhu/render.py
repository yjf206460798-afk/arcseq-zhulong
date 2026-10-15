"""审图渲染：与 X1 设定图同画幅、同比例的正交视图（叠图用），以及头盔特写。

- 机位按 refs/concept/X1_衔烛设定图_分色.regions.json 的米制标定放：每个视图渲染成该面板（原图坐标）的 k 倍大小，
  地面线、人像中线、像素/米与设定图一致——渲染图缩回 1× 就能和设定图逐像素叠。
- 两种画法：`look`（Cycles，B 金属质感 + Freestyle 细线：外轮廓 + 接缝 / 分块轮廓）；`flat`（Workbench 平涂，
  按分色 C 表上色，和分色图直接比面积）。
"""
import json
import math
import os

import bpy
import numpy as np
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
REGIONS = os.path.join(ROOT, "refs", "concept", "X1_衔烛设定图_分色.regions.json")
CALIB = os.path.join(ROOT, "refs", "concept", "X1_衔烛设定图_分色.calib.json")

# 视图 → (相机朝向, 屏幕右方向在世界里的单位向量)
VIEWS = {
    "front": ((math.pi / 2, 0, math.pi / 2), (0, 1, 0), (1, 0, 0)),
    "side": ((math.pi / 2, 0, math.pi), (-1, 0, 0), (0, 1, 0)),
    "back": ((math.pi / 2, 0, -math.pi / 2), (0, -1, 0), (-1, 0, 0)),
}


def calib(figure):
    """设定图里某个人像的标定（原图坐标）与所在面板区域。"""
    R = json.load(open(REGIONS))
    C = json.load(open(CALIB))
    M = R["metric"][figure]
    f = next(g for g in R["figures"] if g["name"] == figure)
    region = C["panels"][f["panel"]]["region"]
    return {"axis_x": M["axis_x_split"] + M["dx"], "ground_y": M["ground_y_split"] + M["dy"], "ppm": M["px_per_m"], "region": region}


def camera():
    sc = bpy.context.scene
    cam = bpy.data.objects.get("xz.cam")
    if cam is None:
        cam = bpy.data.objects.new("xz.cam", bpy.data.cameras.new("xz.cam"))
        sc.collection.objects.link(cam)
    sc.camera = cam
    return cam


def place_ortho(view, cal, k, region=None, shift=0.0):
    """正交相机：渲染 region（原图坐标，默认人像所在面板）的 k 倍，人像中线、地面线、比例与设定图一致。"""
    sc = bpy.context.scene
    x0, y0, x1, y1 = region or cal["region"]
    W, H = int((x1 - x0) * k), int((y1 - y0) * k)
    sc.render.resolution_x, sc.render.resolution_y = W, H
    sc.render.resolution_percentage = 100
    ppm = cal["ppm"] * k
    u_axis = (cal["axis_x"] - x0) * k
    v_ground = (cal["ground_y"] - y0) * k
    Lc = (W / 2 - u_axis) / ppm + shift
    zc = (v_ground - H / 2) / ppm
    rot, right, toward = VIEWS[view]
    cam = camera()
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = max(W, H) / ppm
    cam.data.clip_start = 0.01
    cam.data.clip_end = 40
    cam.rotation_euler = rot
    cam.location = (right[0] * Lc + toward[0] * 10, right[1] * Lc + toward[1] * 10, zc)
    return W, H


def workbench(path, flat=False, background=(0.063, 0.082, 0.094), transparent=False):
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sh = sc.display.shading
    sh.light = "FLAT" if flat else "STUDIO"
    sh.color_type = "MATERIAL"
    sh.show_cavity = not flat
    sh.show_object_outline = False
    sh.show_specular_highlight = not flat
    sc.render.film_transparent = transparent
    sc.world = sc.world or bpy.data.worlds.new("w")
    sh.background_type = "VIEWPORT"
    sh.background_color = background
    sc.view_settings.view_transform = "Standard"
    sc.render.dither_intensity = 0
    sc.render.filter_size = 0.0 if flat else 1.5
    sc.render.use_freestyle = False
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)


def align(view, fig, cal, k, tmp):
    """水平对位（与设定图标定同一量法）：先出一张平涂，量人像在同样行段里的质心（正 / 背视取腿段 60～85%、侧视取躯干段
    20～45%，从盔顶往下算），与设定图的人像中线比，返回相机要横移的米数。"""
    from PIL import Image

    place_ortho(view, cal, k)
    p = os.path.join(tmp, f"align-{view}.png")
    workbench(p, flat=True, background=(1, 1, 1), transparent=True)
    a = np.asarray(Image.open(p).convert("RGBA"))[..., 3] > 128
    rows = np.nonzero(a.any(1))[0]
    top, bot = rows.min(), rows.max()
    h = bot - top
    r0, r1 = (0.2, 0.45) if view == "side" else (0.6, 0.85)
    xs = np.nonzero(a[top + int(h * r0):top + int(h * r1)])[1]
    x0 = cal["region"][0]
    u_axis = (cal["axis_x"] - x0) * k
    return (xs.mean() - u_axis) / (cal["ppm"] * k)


BG = (0.0627, 0.0824, 0.0941)  # 品牌背景 #101518
LINE_MAIN = (0.863, 0.914, 0.922)  # 主描边 #DCE9EB
LINE_STRUCT = (0.502, 0.6, 0.639)  # 结构线 #8099A3


def studio(target=(0.0, 0.0, 1.0), scale=1.0, right=(0, 1, 0), toward=(1, 0, 0)):
    """工作室灯：观者左前上主光、右前补光、左后 / 右后两盏轮廓光、顶光（按相机的右 / 朝向摆，三个视图光感一致）；
    世界 = 品牌背景色的暗环境。"""
    sc = bpy.context.scene
    w = sc.world or bpy.data.worlds.new("xz.world")
    sc.world = w
    w.use_nodes = True
    bgn = w.node_tree.nodes.get("Background")
    bgn.inputs[0].default_value = (*BG, 1)
    bgn.inputs[1].default_value = 0.6
    for o in [o for o in bpy.data.objects if o.name.startswith("xz.light")]:
        bpy.data.objects.remove(o)
    t = Vector(target)
    R, T, U = Vector(right), Vector(toward), Vector((0, 0, 1))
    for name, (a, b, c), power, size, col in (("key", (-0.6, 0.65, 0.75), 70, 1.4, (1.0, 0.97, 0.93)), ("fill", (0.9, 0.1, 0.6), 18, 2.0, (0.85, 0.92, 1.0)),
                                              ("rim.l", (-0.9, 0.5, -0.8), 90, 0.8, (0.8, 0.9, 1.0)), ("rim.r", (0.9, 0.55, -0.8), 80, 0.8, (0.8, 0.9, 1.0)),
                                              ("top", (0.0, 1.0, 0.0), 20, 1.2, (1.0, 1.0, 1.0))):
        d = R * a + U * b + T * c
        L = bpy.data.lights.new(f"xz.light.{name}", "AREA")
        L.energy = power * scale * scale
        L.size = size * scale
        L.color = col
        o = bpy.data.objects.new(f"xz.light.{name}", L)
        sc.collection.objects.link(o)
        dv = d.normalized()
        o.location = t + dv * 3.0 * scale
        o.rotation_euler = (-dv).to_track_quat("-Z", "Y").to_euler()


def freestyle(k=1.0):
    """Freestyle 细线，分三级（VISUAL_TARGET「线条」）：L0 外轮廓 = 主描边色、最亮；L1 件与件的轮廓 / 边界 = 结构线色；
    L2 接缝与分块轮廓（edge mark）= 结构线色、更细更淡。粗细按 1× 设定图像素给，乘渲染倍数 k。"""
    sc = bpy.context.scene
    sc.render.use_freestyle = True
    sc.render.line_thickness_mode = "ABSOLUTE"
    fs = sc.view_layers[0].freestyle_settings
    fs.crease_angle = math.radians(140)
    for ls in list(fs.linesets):
        fs.linesets.remove(ls)
    for name, types, col, alpha, th in (("L0", ("external_contour",), LINE_MAIN, 0.75, 0.75), ("L1", ("silhouette", "border", "crease"), LINE_STRUCT, 0.55, 0.5),
                                        ("L2", ("edge_mark",), LINE_STRUCT, 0.45, 0.38)):
        a = fs.linesets.new(name)
        a.select_by_visibility = True
        a.visibility = "VISIBLE"
        a.select_by_edge_types = True
        for t in ("silhouette", "border", "crease", "edge_mark", "external_contour"):
            setattr(a, f"select_{t}", t in types)
        a.linestyle.color = col
        a.linestyle.alpha = alpha
        a.linestyle.thickness = th * k


def mark_lines():
    """接缝（use_seam）→ Freestyle 边标记。"""
    for o in bpy.data.objects:
        if o.type != "MESH" or not o.name.startswith("xz."):
            continue
        me = o.data
        n = len(me.edges)
        if not n:
            continue
        flags = [False] * n
        me.edges.foreach_get("use_seam", flags)
        if not any(flags):
            continue
        at = me.attributes.get("freestyle_edge") or me.attributes.new("freestyle_edge", "BOOLEAN", "EDGE")
        at.data.foreach_set("value", flags)


def cycles(path, samples=64, transparent=True, lines=True, k=1.0):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.cycles.max_bounces = 6
    sc.cycles.transmission_bounces = 6
    sc.render.film_transparent = transparent
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Base Contrast"
    sc.render.use_freestyle = lines
    if lines:
        freestyle(k)
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
