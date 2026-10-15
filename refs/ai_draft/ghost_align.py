"""把 Tripo 生成的整机外形对齐到几何母版的坐标，作“体积参照幽灵”（不是最终模型）。

用法（Blender 5.2 无界面）：
    python ghost_align.py -- <输入.glb> <输出.glb> [<出图目录>]

坐标与 blender/zl/util.py 相同：米，x 向前、y 向左、z 向上；机头尖在 (XN, 0, Z_TIP)，全长 L_TOTAL（机头尖 → 塞锥尖）。
只做刚体旋转 + 等比缩放 + 平移，不改网格（PATTERNS「外部模型的导入、检查与保法线」），法线原样保留。
出图目录给了就出俯 / 侧 / 前三张正交图和一份 measure.json（最厚处占全长的比例、翼展），方便和 DESIGN 8.1 #15 对数。
"""
import json
import math
import sys

import bpy
from mathutils import Matrix, Vector

XN, Z_TIP, L_TOTAL = 9.5, 1.65, 19.14

args = sys.argv[sys.argv.index("--") + 1:]
src, dst = args[0], args[1]
outdir = args[2] if len(args) > 2 else None

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)
objs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
for o in bpy.context.scene.objects:
    o.select_set(o in objs)


def world_verts():
    for o in objs:
        M = o.matrix_world
        for v in o.data.vertices:
            yield M @ v.co


def apply_world(T):
    """对整组对象施加世界变换（改对象变换，不碰网格）。"""
    roots = [o for o in bpy.context.scene.objects if o.parent is None]
    for o in roots:
        o.matrix_world = T @ o.matrix_world
    bpy.context.view_layer.update()


# 1. 长轴转到 x：在水平面内找最长的方向（glTF 导入后 z 已朝上）
V = list(world_verts())
best = None
for deg in range(0, 180, 1):
    a = math.radians(deg)
    d = Vector((math.cos(a), math.sin(a), 0))
    ps = [v.dot(d) for v in V]
    span = max(ps) - min(ps)
    if best is None or span > best[0]:
        best = (span, a)
apply_world(Matrix.Rotation(-best[1], 4, "Z"))

# 2. 机头朝 +x：两端各取全长 4% 的切片，横截面更小的一端是机头
V = list(world_verts())
xs = [v.x for v in V]
x0, x1 = min(xs), max(xs)
L = x1 - x0


def spread(lo, hi):
    pts = [v for v in V if lo <= v.x <= hi]
    if not pts:
        return 1e9
    return (max(p.y for p in pts) - min(p.y for p in pts)) + (max(p.z for p in pts) - min(p.z for p in pts))


if spread(x0, x0 + 0.04 * L) < spread(x1 - 0.04 * L, x1):
    apply_world(Matrix.Rotation(math.pi, 4, "Z"))

# 3. 等比缩放到全长，机头尖平移到 (XN, 0, Z_TIP)，横向按包围盒居中
V = list(world_verts())
xs = [v.x for v in V]
k = L_TOTAL / (max(xs) - min(xs))
apply_world(Matrix.Scale(k, 4))
V = list(world_verts())
tip = max(V, key=lambda v: v.x)
ys = [v.y for v in V]
apply_world(Matrix.Translation(Vector((XN - tip.x, -(min(ys) + max(ys)) / 2, Z_TIP - tip.z))))

for o in objs:
    o.name = "ref.ghost" if len(objs) == 1 else f"ref.ghost.{o.name}"
    o["ghost"] = True
bpy.ops.export_scene.gltf(filepath=dst, use_selection=False, export_apply=False)

if outdir:
    V = list(world_verts())
    depth = []
    for i in range(1, 40):
        s = L_TOTAL * i / 40
        x = XN - s
        pts = [v for v in V if abs(v.x - x) < L_TOTAL / 80 and abs(v.y) < 0.9]  # 只量机身中段，不量翼
        if pts:
            depth.append((round(s, 2), round(max(p.z for p in pts) - min(p.z for p in pts), 3)))
    span = max(v.y for v in V) - min(v.y for v in V)
    mx = max(depth, key=lambda d: d[1]) if depth else (0, 0)
    meas = {"scale": k, "max_depth_m": mx[1], "at_s": mx[0], "depth_over_length": round(mx[1] / L_TOTAL, 4),
            "span_m": round(span, 3), "depth_by_station": depth}
    with open(f"{outdir}/measure.json", "w") as f:
        json.dump(meas, f, ensure_ascii=False, indent=1)
    print("MEASURE", json.dumps({k2: meas[k2] for k2 in ("max_depth_m", "at_s", "depth_over_length", "span_m")}))
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sh = sc.display.shading
    sh.light, sh.color_type, sh.single_color, sh.show_cavity = "STUDIO", "SINGLE", (0.62, 0.64, 0.67), True
    sc.render.resolution_x, sc.render.resolution_y = 2000, 1100
    cam = bpy.data.cameras.new("c")
    cam.type, cam.ortho_scale = "ORTHO", 21.0
    co = bpy.data.objects.new("cam", cam)
    sc.collection.objects.link(co)
    sc.camera = co
    for name, loc, look in (("top", (0, 0, 40), (0, 0, 0)), ("side", (0, -40, 1.6), (0, 0, 1.6)), ("front", (40, 0, 1.6), (0, 0, 1.6))):
        co.location = loc
        co.rotation_euler = (Vector(look) - Vector(loc)).to_track_quat("-Z", "Y" if name != "top" else "X").to_euler()
        sc.render.filepath = f"{outdir}/ghost_{name}.png"
        bpy.ops.render.render(write_still=True)
