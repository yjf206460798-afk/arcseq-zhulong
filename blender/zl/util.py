"""烛龙 Blender 建模脚本的公共工具：场景复位、网格、材质占位、自定义属性。

坐标与网页引擎相同：米，x 向前、y 向左、z 向上，原点在地面转台轴心；站位 s 自机头尖向后，x = XN - s。
命名即接口（docs/BLENDER.md）：对象名就是网页里的零件名；对象的自定义属性随 glTF extras 导出，网页按它们取材质、蒙皮组、关节。
"""
import math

import bmesh
import bpy
from mathutils import Vector

XN = 9.5  # 机头尖的 x（全长 19 m，转台轴心在机身中点）


def at(s, y, z):
    return Vector((XN - s, y, z))


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = "METRIC"
    return sc


def material(name):
    """网页材质名（hull / belly / carbon / glass / interior / sensor / void …）；Cycles 渲染用的节点在 render.py 里另配。"""
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name)
        m.use_nodes = True
    return m


def mesh_object(name, bm, mats=("hull",), props=None, collection=None):
    me = bpy.data.meshes.new(name)
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(name, me)
    for m in mats:
        obj.data.materials.append(material(m))
    (collection or bpy.context.scene.collection).objects.link(obj)
    for k, v in (props or {}).items():
        obj[k] = v
    return obj


def hull_object(name, points, mats=("hull",), props=None):
    """点集的凸包（平面零件、眉骨、座舱盖）：共面三角形并成多边形，平面着色。"""
    bm = bmesh.new()
    vs = [bm.verts.new(p) for p in points]
    bmesh.ops.convex_hull(bm, input=vs)
    bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(0.5), verts=bm.verts, edges=bm.edges)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    for f in bm.faces:
        f.smooth = False
    return mesh_object(name, bm, mats, props)


def lerp(a, b, t):
    return a + (b - a) * t


def piecewise(table, s):
    """按站位分段线性插值：table = [(s, value), …]，value 可以是数或元组。"""
    if s <= table[0][0]:
        return table[0][1]
    for (s0, v0), (s1, v1) in zip(table, table[1:]):
        if s <= s1 + 1e-9:
            t = (s - s0) / (s1 - s0)
            if isinstance(v0, tuple):
                return tuple(lerp(a, b, t) for a, b in zip(v0, v1))
            return lerp(v0, v1, t)
    return table[-1][1]


def boolean(target, cutter, operation="UNION"):
    mod = target.modifiers.new(f"bool.{cutter.name}", "BOOLEAN")
    mod.operation = operation
    mod.solver = "EXACT"
    mod.object = cutter
    bpy.context.view_layer.objects.active = target
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(cutter, do_unlink=True)


def mirror_object(obj, name):
    """左侧件镜像出右侧件（y 取反），自定义属性照抄，名字 .l → .r。"""
    me = obj.data.copy()
    me.transform(__import__("mathutils").Matrix.Scale(-1, 4, (0, 1, 0)))
    me.flip_normals()
    new = bpy.data.objects.new(name, me)
    for k in obj.keys():
        new[k] = obj[k]
    bpy.context.scene.collection.objects.link(new)
    return new
