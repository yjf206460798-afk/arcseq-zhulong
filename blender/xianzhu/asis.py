"""原样对照（PATTERNS「外部模型的导入、检查与保法线」规矩 1、2）：Tripo 原文件原样导入，不动网格，只在物体上套与管线
相同的累计变换（draft.import_glb 记在每件的 `xform` 里：转向、缩放、站正都是刚体 + 等比，所以原样件和精修件同位置），
同一机位各出一张，并排对照。原样件放在集合 `asis` 里，平时 hide_render。
"""
import os

import bpy

import draft

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))


def twin(objs, name="asis"):
    """objs：管线里来自同一个源文件的件（取其中一件的 xform；同一文件各件变换相同）。返回原样件列表。"""
    src = [o for o in objs if "xform" in o]
    if not src:
        return []
    path = os.path.join(ROOT, src[0]["src_file"])
    M = draft.unflat(list(src[0]["xform"]))
    col = bpy.data.collections.get(name) or bpy.data.collections.new(name)
    if col.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(col)
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    out = []
    for o in new:
        for c in list(o.users_collection):
            c.objects.unlink(o)
        col.objects.link(o)
        if o.type == "MESH":
            o.parent = None
            o.matrix_world = M  # xform 已含原文件里的父级变换；网格（含自定义法线）原封不动
            o["src_name"] = o.name
            o.name = "asis." + o.name
            o.hide_render = True
            out.append(o)
    for o in new:
        if o.type != "MESH":
            bpy.data.objects.remove(o)
    return out


def show(asis_on, objs_asis, objs_ours):
    for o in objs_asis:
        o.hide_render = not asis_on
    for o in objs_ours:
        o.hide_render = asis_on


def clay(objs):
    """原样件统一一种中性灰（Tripo 没带颜色，测试稿也不带贴图）；网格与法线不动。"""
    m = bpy.data.materials.get("tripo.clay") or bpy.data.materials.new("tripo.clay")
    m.use_nodes = True
    b = m.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = (0.2, 0.21, 0.22, 1.0)
    b.inputs["Roughness"].default_value = 0.5
    m.diffuse_color = (0.55, 0.56, 0.58, 1.0)
    for o in objs:
        o.data.materials.clear()
        o.data.materials.append(m)
