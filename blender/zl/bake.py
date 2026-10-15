"""烘焙与导出：顶点 AO（Cycles，存进颜色属性 ao → glTF COLOR_0）、细节贴图（机身蒙皮：刻线 / 铆钉 / 鳞片缝、涂装字样、贴图 AO）、GLB 导出。

细节贴图的做法（写进 PATTERNS「烘焙细节与贴花」）：
  1. 机身蒙皮按角度展 UV（smart project），在 Cycles 里把每个纹素的世界坐标与法线烘成两张浮点图（发光着色器输出 Position / Normal）；
  2. 回到 numpy，按坐标“画”细节：铆钉行、鳞片缝（机腹与下切面）、涂装字样（PIL 画好再按切面平面投影贴上），全部是程序生成、可重跑；
  3. 再烘一张贴图 AO；三者打包成一张 RGB（r 刻线压暗、g 涂装、b AO），边缘向外扩几圈防止接缝漏色。
"""
import math
import os

import bmesh
import bpy
import numpy as np

from .util import XN


def _cycles(samples):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_denoising = False
    if sc.world is None:
        sc.world = bpy.data.worlds.new("bake")
    sc.world.light_settings.distance = 0.45  # AO 只看 45 cm 以内：缝隙、内角、眉骨与座舱盖下沿
    return sc


def _select(objs, active):
    for o in bpy.context.view_layer.objects:
        if o is not None:  # 布尔后删掉的切割体在视图层缓存里可能留成 None
            o.select_set(False)
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = active


def _voids(objs):
    """空腔薄片（姿态推进器口……）只是“开口”的着色，不是实体：烘 AO 时藏起来，否则贴着蒙皮 3 mm 的薄片会在周围烘出一圈黑斑。"""
    return [o for o in objs if o.get("system") == "void"]


def _loose(objs):
    """不当遮挡物的贴面件（鳞片瓦样片：aoOccluder = False）——它们盖住的蒙皮本来看不见，周围却会被烘出一圈脏黑。"""
    return [o for o in objs if o.get("aoOccluder") is False]


def vertex_ao(objs, samples=64, hide=()):
    """顶点 AO：hide 里的对象（另一套模块，如剖视内部）烘焙时藏起来，不当遮挡物。"""
    sc = _cycles(samples)
    voids = _voids(objs)
    loose = _loose(objs)
    meshes = [o for o in objs if o.type == "MESH" and o not in voids and o not in loose]
    for o in hide:
        o.hide_render = True
    for o in meshes + voids:
        attr = o.data.color_attributes.get("ao") or o.data.color_attributes.new("ao", "FLOAT_COLOR", "POINT")
        o.data.color_attributes.active_color = attr
        o.data.attributes.active_color = attr
    for o in voids:
        o.data.color_attributes["ao"].data.foreach_set("color", [1.0] * (4 * len(o.data.vertices)))
        o.hide_render = True
    sc.render.bake.target = "VERTEX_COLORS"
    # 两遍：先藏起贴面件烘其余零件，再把贴面件自己烘一遍（它们仍然被机身遮挡）
    for o in loose:
        o.hide_render = True
        attr = o.data.color_attributes.get("ao") or o.data.color_attributes.new("ao", "FLOAT_COLOR", "POINT")
        o.data.color_attributes.active_color = attr
        o.data.attributes.active_color = attr
    _select(meshes, meshes[0])
    bpy.ops.object.bake(type="AO")
    for o in loose:
        o.hide_render = False
    if loose:
        _select(loose, loose[0])
        bpy.ops.object.bake(type="AO")
    sc.render.bake.target = "IMAGE_TEXTURES"
    for o in voids:
        o.hide_render = False
    for o in hide:
        o.hide_render = False


def _bake_float(obj, image, socket_fn):
    """把发光着色器（输出由 socket_fn(nodes, links, emission) 接好）烘进 image。"""
    saved = [m for m in obj.data.materials]
    mat = bpy.data.materials.new("__bake")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(em.outputs[0], out.inputs[0])
    socket_fn(nt.nodes, nt.links, em)
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = image
    nt.nodes.active = tex
    for i in range(len(obj.data.materials)):
        obj.data.materials[i] = mat
    _select([obj], obj)
    bpy.ops.object.bake(type="EMIT", margin=0)
    for i, m in enumerate(saved):
        obj.data.materials[i] = m
    bpy.data.materials.remove(mat)


def _pixels(image):
    a = np.empty(image.size[0] * image.size[1] * 4, dtype=np.float32)
    image.pixels.foreach_get(a)
    return a.reshape(image.size[1], image.size[0], 4)


def detail_texture(objs, meta, assets, size=2048, hide=()):
    """机身蒙皮的两张细节贴图（见 detail.py）：zhulong-skin.png（A/B 共用）与 zhulong-skin-pbr.png（B 画法）。返回 meta["detail"]。"""
    body = next(o for o in objs if o.name == "nose.body")
    _cycles(1)
    # UV：按角度展开（切面是平面，岛就是切面），岛间留 2.5 个纹素
    _select([body], body)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(40), island_margin=2.5 / size, area_weight=0.0, scale_to_bounds=True)
    bpy.ops.object.mode_set(mode="OBJECT")
    imgs = {}
    for name in ("pos", "nor", "ao"):
        img = bpy.data.images.new(f"__{name}", size, size, float_buffer=True, alpha=True)
        img.generated_color = (0, 0, 0, 0)
        imgs[name] = img

    def pos(nodes, links, em):
        g = nodes.new("ShaderNodeNewGeometry")
        links.new(g.outputs["Position"], em.inputs["Color"])

    def nor(nodes, links, em):
        g = nodes.new("ShaderNodeNewGeometry")
        links.new(g.outputs["Normal"], em.inputs["Color"])

    _bake_float(body, imgs["pos"], pos)
    _bake_float(body, imgs["nor"], nor)
    # 贴图 AO：同一 UV 再烘一张（比顶点 AO 细，缝隙里能到厘米级）
    _cycles(48)
    saved = [m for m in body.data.materials]
    mat = bpy.data.materials.new("__aobake")
    mat.use_nodes = True
    tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
    tex.image = imgs["ao"]
    mat.node_tree.nodes.active = tex
    for i in range(len(body.data.materials)):
        body.data.materials[i] = mat
    hidden = _voids(objs) + _loose(objs) + list(hide)
    for o in hidden:
        o.hide_render = True
    _select([body], body)
    bpy.ops.object.bake(type="AO", margin=0)
    for o in hidden:
        o.hide_render = False
    for i, m in enumerate(saved):
        body.data.materials[i] = m
    bpy.data.materials.remove(mat)

    P = _pixels(imgs["pos"])
    N = _pixels(imgs["nor"])
    A = _pixels(imgs["ao"])
    from PIL import Image

    from . import detail

    skin, pbr, valid = detail.paint(P, N, A, meta)
    skin = detail.dilate(skin, valid, 6, (0.5, 0.0, 1.0))
    pbr = detail.dilate(pbr, valid, 6, (0.5, 0.5, 1.0, 0.55))
    # Blender 图像第 0 行在底部；glTF UV 的 v 向下（导出器已翻转 v），PNG 第 0 行在顶部：上下翻转后写出
    Image.fromarray(np.flipud(np.clip(skin * 255 + 0.5, 0, 255).astype(np.uint8)), "RGB").save(os.path.join(assets, "zhulong-skin.png"), optimize=True)
    Image.fromarray(np.flipud(np.clip(pbr * 255 + 0.5, 0, 255).astype(np.uint8)), "RGBA").save(os.path.join(assets, "zhulong-skin-pbr.png"), optimize=True)
    for img in imgs.values():
        bpy.data.images.remove(img)
    return {
        "skin": {"file": "zhulong-skin.png", "k": [1.0, 0.38, 0.6], "paint": "#8a9296", "mid": True},
        "skinPbr": {"file": "zhulong-skin-pbr.png", "look": "metal"},
    }


def export(objs, path):
    _select([o for o in objs if o.type == "MESH"], objs[0])
    for o in objs:
        if o.type == "MESH" and o.data.color_attributes.get("ao"):
            o.data.color_attributes.active_color = o.data.color_attributes["ao"]
    bpy.ops.export_scene.gltf(
        filepath=path,
        export_format="GLB",
        use_selection=True,
        export_extras=True,
        export_apply=True,
        export_normals=True,
        export_texcoords=True,
        export_vertex_color="ACTIVE",
        export_all_vertex_colors=False,
        export_materials="EXPORT",
        export_image_format="NONE",
        export_yup=True,
    )
