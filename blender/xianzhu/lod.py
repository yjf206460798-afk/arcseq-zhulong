"""网页常驻版：减面 + 高模细节烘成法线贴图（PATTERNS「外部模型的导入、检查与保法线」规矩 3）。

- 预算（BLENDER.md「网页面数预算」）：銜燭单独页面常驻约 6 万三角形（TARGET）；座舱里的坐姿版 Tripo 件再减到 40%（LOD1，整件约 3 万，
  对齐 R4 座舱里飞行员 2.9 万的位置），共用同一套 UV 与贴图（塌边减面保 UV）。
- 只减 Tripo 起稿件（三十万面）；自己建的干净件（扣件、护膝、靴底、管、面罩）本来就低，不动。
- 减面改了拓扑，Tripo 的自定义法线作废：低模清掉自定义法线、按 30° 设锐边，块面与硬棱从高模（原样法线）烘成切线空间
  法线贴图。两张图集：body（服装、手套、靴、脸、软管）2048²，hard（头盔壳、颈环、脐带接头）1024²。
- 每件先留一份高模 `hi.<名字>`（烘完删掉）。
"""
import math

import bpy
import numpy as np

import geo

# 每件的目标三角形数（按 Tripo 件的种类，对象属性 `tripo`，build.py 里标）
TARGET = {"torso": 16000, "thigh": 4000, "shin": 2400, "boot": 2600, "uarm": 2000, "farm": 1500, "hand": 1800, "face": 1400,
          "hose": 1600, "shell": 7000, "neckring": 1200, "plug": 1800}
ATLAS = {"body": (("suit", "glove", "boot", "skin", "hose"), 2048), "hard": (("helmet", "chrome", "umbilical"), 1024)}
LOD1 = 0.4


def target(o):
    return TARGET.get(o.get("tripo"))


def tris(o):
    o.data.calc_loop_triangles()
    return len(o.data.loop_triangles)


def decimate(o, n, name="lod"):
    """塌边减面到约 n 个三角形（顶点组、UV、颜色属性跟着插值）。"""
    t0 = tris(o)
    if t0 <= n:
        return t0, t0
    m = o.modifiers.new(name, "DECIMATE")
    m.decimate_type = "COLLAPSE"
    m.ratio = n / t0
    m.use_collapse_triangulate = True
    bpy.context.view_layer.objects.active = o
    while o.modifiers.find(name) > 0:
        bpy.ops.object.modifier_move_up(modifier=name)
    bpy.ops.object.modifier_apply(modifier=name)
    return t0, tris(o)


def sharp_by_angle(o, angle=30.0):
    """清掉自定义法线，所有面平滑、折角 > angle 的边设锐边。"""
    me = o.data
    if me.has_custom_normals:
        bpy.context.view_layer.objects.active = o
        bpy.ops.mesh.customdata_custom_splitnormals_clear()
    geo.mark_sharp(o, angle)


def keep_high(o):
    h = o.copy()
    h.data = o.data.copy()
    h.name = "hi." + o.name
    bpy.context.scene.collection.objects.link(h)
    for m in list(h.modifiers):
        h.modifiers.remove(m)
    h.hide_render = True
    return h


def atlas_of(o):
    mat = o.data.materials[0].name if o.data.materials else ""
    for k, (mats, _) in ATLAS.items():
        if mat in mats:
            return k
    return None


def unwrap(objs, margin=0.003):
    """几件一起展 UV、一起排进一张 0～1 图集（多物体编辑模式下的 Smart UV Project 会把所有件的岛排在一起）。"""
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
        if not o.data.uv_layers:
            o.data.uv_layers.new(name="UVMap")
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=margin, area_weight=0.0, correct_aspect=True, scale_to_bounds=False)
    bpy.ops.object.mode_set(mode="OBJECT")


def image_node(mat, img):
    nt = mat.node_tree
    n = nt.nodes.get("xz.bake")
    if n is None:
        n = nt.nodes.new("ShaderNodeTexImage")
        n.name = "xz.bake"
    n.image = img
    nt.nodes.active = n
    return n


def bake(pairs, img, extrusion=0.012, distance=0.03):
    """pairs：[(高模, 低模)]，低模的材质里放好了图像节点（image_node）。逐件 selected-to-active 烘切线空间法线。"""
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 1
    b = sc.render.bake
    b.use_selected_to_active = True
    b.use_cage = False
    b.cage_extrusion = extrusion
    b.max_ray_distance = distance
    b.margin = 6
    b.normal_space = "TANGENT"
    b.target = "IMAGE_TEXTURES"
    for hi, lo in pairs:
        for o in (hi, lo):
            o.hide_render = False
            o.hide_set(False)
        bpy.ops.object.select_all(action="DESELECT")
        hi.select_set(True)
        lo.select_set(True)
        bpy.context.view_layer.objects.active = lo
        bpy.ops.object.bake(type="NORMAL", use_clear=False, margin=6)


def new_image(name, size):
    img = bpy.data.images.get(name)
    if img is not None:
        bpy.data.images.remove(img)
    img = bpy.data.images.new(name, size, size, alpha=False)
    img.generated_color = (0.5, 0.5, 1.0, 1.0)
    img.colorspace_settings.name = "Non-Color"
    return img


def build(objs, out_dir):
    """objs：全部 xz. / draft. 件（站姿、已上好权重）。就地减面、展 UV、烘法线；返回 (日志, {图集名: 图像})。"""
    import os

    log = {"tris": {}}
    work = [o for o in objs if target(o)]
    highs = {}
    for o in work:
        highs[o.name] = keep_high(o)
        t0, t1 = decimate(o, target(o))
        log["tris"][o.name] = [t0, t1]
        sharp_by_angle(o)
    images = {}
    for k, (mats, size) in ATLAS.items():
        group = [o for o in work if atlas_of(o) == k]
        if not group:
            continue
        unwrap(group)
        img = new_image(f"xianzhu-{k}-nrm", size)
        for m in mats:
            mat = bpy.data.materials.get(m)
            if mat is not None:
                mat.use_nodes = True
                image_node(mat, img)
        bake([(highs[o.name], o) for o in group], img)
        img.filepath_raw = os.path.join(out_dir, f"xianzhu-{k}-nrm.png")
        img.file_format = "PNG"
        img.save()
        images[k] = img
    for h in highs.values():
        bpy.data.objects.remove(h)
    return log, images


def lod1(objs, ratio=LOD1):
    """座舱坐姿版：Tripo 件再减到 ratio（UV 跟着插值，图集共用）。"""
    log = {}
    for o in objs:
        if target(o):
            t0, t1 = decimate(o, int(tris(o) * ratio), "lod1")
            log[o.name] = [t0, t1]
    return log
