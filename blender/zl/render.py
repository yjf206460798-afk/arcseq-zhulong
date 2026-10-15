"""Cycles 渲染（海报、封面、特写镜头）：与网页同一套配色卡与机位约定（方位角相对机头逆时针、俯仰 30°），线条用 Freestyle 画发丝线。

不追求“照片级”，追求与网页同一张脸：哑光石墨、低对比、深色舞台、极细分级线条、克制的发光。差别只在真实的光照、软影与 AO。
"""
import math

import bpy
from mathutils import Vector

from .util import XN

PALETTE = {
    # 与 src/figure/build.mjs 的 PALETTE 最亮一档对应（sRGB），Cycles 里换成线性：
    # 实际光照下哑光面只有约一半的光照到，按第 5 档给才与网页的明度对得上（机身比台面亮）
    "hull": "#484d50", "belly": "#343a40", "carbon": "#232527", "glass": "#12161a", "interior": "#24282a", "sensor": "#281c12",
    "void": "#0c0e10", "deck": "#0b0f11", "frame": "#323538", "metal": "#41464a", "chrome": "#5c646a", "rubber": "#1b1c1e",
    "iris": "#1f2124", "vermilion": "#8f3224", "stand": "#1c2023", "structure": "#494e51", "avionics": "#46463f", "panel": "#323330",
    "pipe": "#424c50", "cable": "#272a2b", "tank": "#555d61", "screen": "#1a2a2f", "seat": "#333537", "suit": "#47494b", "pad": "#4c5053", "strap": "#28292b", "visor": "#52391b",
    "helmet": "#626768", "section": "#727c7b", "label": "#737875", "hazard": "#6a4c23", "backwall": "#1f2326",
}
# 金属度、粗糙度（与网页 B 画法同一张表，src/figure/build.mjs 的 PBR）
PBR = {
    "hull": (0.55, 0.38), "belly": (0.4, 0.5), "carbon": (0.2, 0.35), "glass": (0.0, 0.05), "interior": (0.3, 0.6), "sensor": (0.0, 0.08),
    "frame": (0.7, 0.35), "metal": (0.9, 0.3), "chrome": (1.0, 0.12), "rubber": (0.0, 0.85), "iris": (0.6, 0.35), "vermilion": (0.2, 0.4),
    "stand": (0.5, 0.5), "structure": (0.75, 0.38), "avionics": (0.45, 0.45), "panel": (0.4, 0.5), "pipe": (0.85, 0.3), "cable": (0.1, 0.7),
    "tank": (0.85, 0.28), "screen": (0.0, 0.1), "seat": (0.2, 0.7), "suit": (0.15, 0.65), "pad": (0.15, 0.55), "strap": (0.05, 0.75), "visor": (0.6, 0.15), "helmet": (0.4, 0.25), "section": (0.6, 0.4),
    "label": (0.1, 0.5), "hazard": (0.2, 0.5), "backwall": (0.3, 0.7),
}
GLOW = {"sensor": ("#ffb060", 6.0), "screen": ("#7bdbec", 5.0)}


def lin(hex_):
    c = [int(hex_[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    return tuple(((v + 0.055) / 1.055) ** 2.4 if v > 0.04045 else v / 12.92 for v in c) + (1.0,)


def setup_materials(objs, skin_png, power=0.0):
    skin = bpy.data.images.load(skin_png) if skin_png else None
    if skin:
        skin.colorspace_settings.name = "Non-Color"
    for name, hex_ in PALETTE.items():
        m = bpy.data.materials.get(name)
        if m is None:
            continue
        m.use_nodes = True
        nt = m.node_tree
        nt.nodes.clear()
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
        nt.links.new(bsdf.outputs[0], out.inputs[0])
        base = lin(hex_)
        bsdf.inputs["Base Color"].default_value = base
        metal, rough = PBR.get(name, (0.15, 0.62))
        bsdf.inputs["Roughness"].default_value = rough
        bsdf.inputs["Metallic"].default_value = metal
        if name in GLOW:
            col, k = GLOW[name]
            bsdf.inputs["Emission Color"].default_value = lin(col)
            bsdf.inputs["Emission Strength"].default_value = k * power
        if skin and name in ("hull", "belly"):
            # 细节贴图：r 是 0.5 中性的明度乘子（×2 后乘到基色上），g 涂装（混向浅灰）
            tex = nt.nodes.new("ShaderNodeTexImage")
            tex.image = skin
            sep = nt.nodes.new("ShaderNodeSeparateColor")
            nt.links.new(tex.outputs["Color"], sep.inputs[0])
            two = nt.nodes.new("ShaderNodeMath")
            two.operation = "MULTIPLY"
            two.inputs[1].default_value = 2.0
            nt.links.new(sep.outputs["Red"], two.inputs[0])
            mul = nt.nodes.new("ShaderNodeMix")
            mul.data_type = "RGBA"
            mul.blend_type = "MULTIPLY"
            mul.inputs["Factor"].default_value = 1.0
            mul.inputs["A"].default_value = base
            nt.links.new(two.outputs[0], mul.inputs["B"])
            paint = nt.nodes.new("ShaderNodeMix")
            paint.data_type = "RGBA"
            nt.links.new(sep.outputs["Green"], paint.inputs["Factor"])
            nt.links.new(mul.outputs["Result"], paint.inputs["A"])
            paint.inputs["B"].default_value = lin("#8a9296")
            nt.links.new(paint.outputs["Result"], bsdf.inputs["Base Color"])


def cutaway(objs):
    """剖视（与网页同一剖切面 y = 0，从 +y 一侧看）：整件在一侧的外部件藏起来，跨中线的件（cut）用布尔差切掉 y > 0 一半。"""
    import bmesh

    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * 40, (v.co.y + 0.5) * 6, v.co.z * 20))
    me = bpy.data.meshes.new("cutbox")
    bm.to_mesh(me)
    box = bpy.data.objects.new("cutbox", me)
    bpy.context.scene.collection.objects.link(box)
    for o in objs:
        if o.get("show") == "!cutaway":
            o.hide_render = True
        elif o.get("cut"):
            mod = o.modifiers.new("cut", "BOOLEAN")
            mod.operation = "DIFFERENCE"
            mod.solver = "EXACT"
            mod.object = box
    box.hide_render = True


def chine_tube(meta, power, near=True):
    """朱红棱线：沿棱线的一根 3 mm 发光细管（未通电只是暗朱红漆线）。near=False：剖视时不要近侧（y > 0）那根。"""
    out = []
    for seam in meta["seams"]:
        if seam.get("level") != "accent":
            continue
        if not near and seam["points"][0][1] > 0:
            continue
        cu = bpy.data.curves.new("chine", "CURVE")
        cu.dimensions = "3D"
        cu.bevel_depth = 0.004
        sp = cu.splines.new("POLY")
        sp.points.add(len(seam["points"]) - 1)
        for p, q in zip(sp.points, seam["points"]):
            p.co = (*q, 1)
        ob = bpy.data.objects.new("chine.tube", cu)
        bpy.context.scene.collection.objects.link(ob)
        m = bpy.data.materials.new("chine")
        m.use_nodes = True
        b = m.node_tree.nodes["Principled BSDF"]
        b.inputs["Base Color"].default_value = lin("#7a2a1e")
        b.inputs["Emission Color"].default_value = lin("#ff5a32")
        b.inputs["Emission Strength"].default_value = 0.4 + 9 * power
        ob.data.materials.append(m)
        out.append(ob)
    return out


def stage(meta, env="hangar"):
    sc = bpy.context.scene
    off = Vector(meta["offset"])
    # 转台：圆盘 + 台侧，台面中心在模型中心下方（网页里模型平移到转台中心，这里反过来把转台放到模型下面）
    bpy.ops.mesh.primitive_cylinder_add(vertices=160, radius=4.2, depth=0.35, location=(-off.x, 0, -0.175))
    deck = bpy.context.object
    m = bpy.data.materials.new("deckm")
    m.use_nodes = True
    m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = lin(PALETTE["deck"])
    m.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.85
    deck.data.materials.append(m)
    w = bpy.data.worlds.new("w")
    sc.world = w
    w.use_nodes = True
    bg = {"hangar": "#111518", "space": "#090d14"}[env]
    w.node_tree.nodes["Background"].inputs[0].default_value = lin(bg)
    w.node_tree.nodes["Background"].inputs[1].default_value = 1.0
    # 主光：随相机，从画面左上方来（与网页的 n·L 光同向）；补光：右后方冷色大面光；地面反光靠世界色
    return deck


def camera(meta, az, el, shot):
    sc = bpy.context.scene
    off = Vector(meta["offset"])
    centre = Vector((-off.x, 0, 1.25))
    a, e = math.radians(az), math.radians(el)
    d = Vector((math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), math.sin(e)))
    cam_data = bpy.data.cameras.new("cam")
    cam = bpy.data.objects.new("cam", cam_data)
    sc.collection.objects.link(cam)
    if shot == "cutaway":
        aim = Vector((XN - 3.8, 0, 1.75))
        cam_data.type = "ORTHO"
        cam_data.ortho_scale = 8.4
        cam.location = aim + Vector((0, 60, 0))
        cam_data.clip_end = 200
    elif shot == "nose":
        aim = Vector(meta["focus"]["nose"]) + Vector((-0.9, 0, 0.05))
        cam_data.type = "PERSP"
        cam_data.lens = 85
        cam.location = aim + d * 6.5
        cam_data.dof.use_dof = True
        cam_data.dof.focus_distance = (Vector(meta["focus"]["nose"]) - cam.location).length
        cam_data.dof.aperture_fstop = 2.8
    else:
        aim = centre
        cam_data.type = "ORTHO"
        cam_data.ortho_scale = 10.8
        cam.location = aim + d * 60
        cam_data.clip_end = 200
    cam.rotation_euler = (aim - cam.location).to_track_quat("-Z", "Y").to_euler()
    sc.camera = cam
    # 主光：相机右向为 r，上向为 u；光从 −r（画面左）、上方来
    r = d.cross(Vector((0, 0, 1))).normalized() * -1  # 相机右向
    u = d.cross(r).normalized()  # 相机上向
    key_dir = (-r * 1.0 + u * 1.2 + d * 0.6).normalized()
    for name, direction, energy, size, color in (("key", key_dir, 6.0, 22.0, "#fff4ea"), ("fill", (r * 1.0 + u * 0.3 - d * 0.5).normalized(), 2.0, 30.0, "#cfe0ff")):
        L = bpy.data.lights.new(name, "SUN")
        L.energy = energy
        L.angle = math.radians(size)
        L.color = lin(color)[:3]
        ob = bpy.data.objects.new(name, L)
        sc.collection.objects.link(ob)
        ob.rotation_euler = (-direction).to_track_quat("-Z", "Y").to_euler()
    return cam


def freestyle(width=1.0):
    """发丝线：轮廓 + 折边（与网页 L0 / L1 同色），线宽按 1600 宽画幅给。"""
    sc = bpy.context.scene
    sc.render.use_freestyle = True
    sc.render.line_thickness_mode = "ABSOLUTE"
    sc.render.line_thickness = width
    vl = bpy.context.view_layer
    vl.use_freestyle = True
    fs = vl.freestyle_settings
    fs.crease_angle = math.radians(146)
    for ls in list(fs.linesets):
        fs.linesets.remove(ls)
    for name, sel, color, alpha, thick in (("contour", ("silhouette", "border"), "#b9c7cb", 0.6, 0.9), ("crease", ("crease",), "#7d939c", 0.5, 0.6)):
        ls = fs.linesets.new(name)
        ls.select_by_visibility = True
        # 转台不出线（网页里台面只有极淡的刻度环）：只取 model 集合里的边
        ls.select_by_collection = False
        ls.collection = bpy.data.collections["model"]
        ls.collection_negation = "INCLUSIVE"
        ls.select_by_edge_types = True
        for t in ("silhouette", "border", "crease", "contour", "external_contour", "material_boundary", "edge_mark"):
            setattr(ls, f"select_{t}", t in sel)
        st = ls.linestyle
        st.color = lin(color)[:3]
        st.alpha = alpha
        st.thickness = thick
        st.chaining = "PLAIN"


def cycles(objs, meta, path, shot="hero", samples=64, size="1600x1072", power=1.0, az=30, el=30, env="hangar"):
    import os

    sc = bpy.context.scene
    col = bpy.data.collections.new("model")
    sc.collection.children.link(col)
    for o in objs:
        col.objects.link(o)
    skin = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "assets", "zhulong-skin.png")
    setup_materials(objs, skin if os.path.exists(skin) else None, power=power)
    if shot == "cutaway":
        cutaway(objs)
    else:
        for o in objs:
            if o.get("module") == "interior" or o.get("show") == "cutaway":
                o.hide_render = True
    chine_tube(meta, power, near=shot != "cutaway")
    stage(meta, env)
    camera(meta, az if shot == "hero" else 35, el if shot == "hero" else 12, shot)
    freestyle()
    w, h = map(int, size.split("x"))
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Medium Low Contrast"
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
