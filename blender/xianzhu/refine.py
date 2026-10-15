"""Tripo 底稿精修（WORKFLOW「AI 起稿」第 5 步）：硬件锐化、单侧件、靴底、脊线。

起稿网格里的扣具、护膝、靴底是“软”的（边是圆的、面不平）。看得出的硬件按位置表 HARDWARE 一件件重做：
在锚点附近取起稿表面拟合一张局部平面 → 量出这件东西在平面里的外形尺寸 → 放一件棱角干净的新件（略大一圈罩住旧的）。
锚点是设定图标定坐标（站姿，米；正视 / 背视的 (y, z)），重生成后形状漂一点也找得到（就近取面）。
"""
import math

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

import geo

# 位置表：id、视向（front 从前往后打 / back 从后往前打）、(y, z)、外形（宽 = 沿 u、高 = 沿 v，米）、样式、u 方向（屏幕里的角度，度，0 = 水平）、镜像
HARDWARE = [
    ("adjuster.upper", "front", (0.12, 1.40), (0.064, 0.05), "ladder", 0, True),
    ("adjuster.lower", "front", (0.12, 1.29), (0.06, 0.05), "ladder", 0, True),
    ("belt.buckle", "front", (0.0, 1.105), (0.086, 0.054), "release", 0, False),
    ("belt.hip", "front", (0.13, 1.06), (0.034, 0.052), "frame", 90, True),
    ("leg.buckle", "front", (0.088, 0.875), (0.056, 0.046), "ladder", -32, True),
    ("back.adjuster", "back", (0.10, 1.335), (0.056, 0.064), "ladder", 0, True),
    ("back.buckle", "back", (0.0, 1.105), (0.076, 0.052), "frame", 0, False),
    ("back.hip", "back", (0.135, 1.055), (0.034, 0.05), "frame", 90, True),
]
KNEEPADS = [("kneepad", (0.14, 0.565), (0.094, 0.118))]


def tree_of(objs):
    bm = bmesh.new()
    for o in objs:
        tmp = bmesh.new()
        tmp.from_mesh(o.data)
        tmp.transform(o.matrix_world)
        me = bpy.data.meshes.new("tmp")
        tmp.to_mesh(me)
        tmp.free()
        bm.from_mesh(me)
        bpy.data.meshes.remove(me)
    t = BVHTree.FromBMesh(bm)
    pts = np.array([tuple(v.co) for v in bm.verts])
    bm.free()
    return t, pts


def hit(tree, view, y, z):
    sx = 1 if view == "front" else -1
    loc, n, _, _ = tree.ray_cast(Vector((0.7 * sx, y, z)), Vector((-sx, 0, 0)), 2.0)
    return loc, n


def local_frame(pts, c, n0, r):
    """c 附近 r 内的表面点：法线取 PCA 最小方差方向（朝外与 n0 同侧），返回 (面上原点, 法线, 局部点)。"""
    P = pts[np.linalg.norm(pts - np.array(c), axis=1) < r]
    m = P.mean(0)
    w, U = np.linalg.eigh(np.cov((P - m).T))
    n = Vector(U[:, 0])
    if n.dot(n0) < 0:
        n = -n
    return Vector(m), n, P


def build_hardware(parts, props):
    """返回新件列表。parts：{名字: 起稿对象}（已对称）。"""
    objs = [o for k, o in parts.items() if k in ("torso", "thigh.l", "thigh.r")]
    tree, pts = tree_of(objs)
    out = []
    for hid, view, (y, z), (w, h), style, ang, mirror in HARDWARE:
        for sg in ((1, -1) if mirror else (1,)):
            loc, n0 = hit(tree, view, y * sg, z)
            if loc is None:
                print(f"  ! 硬件 {hid} 打空")
                continue
            o_, n, P = local_frame(pts, loc, n0, 0.6 * max(w, h))
            # u 轴：从中线朝外的水平方向转 ang（左右镜像对称）；中线上的件 u = +y
            a = math.radians(ang)
            u = Vector((0, sg * math.cos(a), math.sin(a)))
            u = (u - n * u.dot(n)).normalized()
            v = n.cross(u)
            # 罩住旧件：局部点在法向上的最高处 + 1.5 mm
            rel = P - np.array(o_)
            inb = (np.abs(rel @ np.array(u)) < w / 2) & (np.abs(rel @ np.array(v)) < h / 2)
            top = float((rel[inb] @ np.array(n)).max()) if inb.any() else 0.006
            base = loc - n * 0.004
            R = Matrix((u, v, n)).transposed()
            name = f"xz.hw.{hid}.{'l' if sg > 0 else 'r'}" if mirror else f"xz.hw.{hid}"
            height = min(0.011, max(0.006, (Vector(o_) + n * top - base).dot(n) + 0.0015))
            out += [(style, o) for o in hardware_piece(name, style, base, R, (w + 0.004, h + 0.004, height), props)]
    return out


def hardware_piece(name, style, base, R, size, props):
    """扣件：ladder（梯扣：外框 + 两道横梁）、release（快卸扣：倒角盒 + 中间按钮 + 两侧导槽）、frame（方框扣）。"""
    w, h, t = size
    c = base + R.col[2] * (t / 2)
    out = []
    if style == "release":
        out.append(geo.box(name + ".body", c, (w, h, t), R, "buckle", props, bevel=0.0025))
        out.append(geo.box(name + ".button", c + R.col[2] * (t / 2 + 0.0015), (w * 0.34, h * 0.5, 0.004), R, "metal", props, bevel=0.001))
        for s in (-1, 1):
            out.append(geo.box(name + f".rail{'lr'[s > 0]}", c + R.col[0] * (s * w * 0.36) + R.col[2] * (t / 2), (0.004, h * 0.8, 0.0016), R, "lens", props))
        return [merge(name, out, "buckle", props)]
    # 方框：四根边条（带倒角），ladder 再加两道横梁
    bw = min(w, h) * 0.16
    for k, (du, dv, sw, sh) in enumerate(((0, (h - bw) / 2, w, bw), (0, -(h - bw) / 2, w, bw), ((w - bw) / 2, 0, bw, h), (-(w - bw) / 2, 0, bw, h))):
        out.append(geo.box(f"{name}.e{k}", c + R.col[0] * du + R.col[1] * dv, (sw, sh, t), R, "buckle", props, bevel=0.001))
    # 框里穿过的织带（罩住起稿那团软的旧扣）
    out.append(geo.box(f"{name}.web", c + R.col[2] * (-t * 0.15), (w - 1.6 * bw, h - 1.6 * bw, t * 0.7), R, "strap", props, bevel=0.0008))
    if style == "ladder":
        for k, dv in enumerate((-h * 0.12, h * 0.14)):
            out.append(geo.box(f"{name}.bar{k}", c + R.col[1] * dv + R.col[2] * (-t * 0.1), (w - 2 * bw, bw * 0.8, t * 0.8), R, "buckle", props, bevel=0.0008))
    o = merge(name, out, "buckle", props)
    return [o]


def merge(name, objs, mat, props):
    """几件合成一个对象（零件名 = name），材质按各自的保留。"""
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    o = bpy.context.view_layer.objects.active
    o.name = name
    for k, v in props.items():
        o[k] = v
    return o


def kneepads(parts, props):
    """护膝：起稿的护膝区域拟合平面 + 外形 → 干净的切面硬壳（正面一块大平面、四周倒角、上沿一道折、下沿一道暗槽）。"""
    out = []
    for kid, (y, z), (w, h) in KNEEPADS:
        for sg, side in ((1, "l"), (-1, "r")):
            objs = [parts[f"thigh.{side}"], parts[f"shin.{side}"]]
            tree, pts = tree_of(objs)
            loc, n0 = hit(tree, "front", y * sg, z)
            o_, n, P = local_frame(pts, loc, n0, 0.05)
            up = Vector((0, 0, 1))
            v = (up - n * up.dot(n)).normalized()
            u = v.cross(n)
            rel = P - np.array(o_)
            top = float((rel @ np.array(n)).max())
            base = Vector(o_) + n * (top - 0.01)
            R = Matrix((u, v, n)).transposed()
            # 两片：上片（膝上，宽）+ 下片（膝盖骨，窄），中间 4 mm 缝；每片 = 底面梯形 + 内缩的正面（四周大倒角）
            for k, (b0, b1, wt, wb, lift) in enumerate(((h * 0.12, h / 2, w, w * 0.92, 0.014), (-h / 2, h * 0.08, w * 0.9, w * 0.72, 0.017))):
                q = []
                for bb, ww in ((b0, wb), (b1, wt)):
                    q += [base + u * (-ww / 2) + v * bb, base + u * (ww / 2) + v * bb]
                    q += [base + u * (-ww / 2 + 0.013) + v * (bb + (0.009 if bb == b0 else -0.009)) + n * lift,
                          base + u * (ww / 2 - 0.013) + v * (bb + (0.009 if bb == b0 else -0.009)) + n * lift]
                q += [p - n * 0.012 for p in q[:2]] + [p - n * 0.012 for p in q[4:6]]
                out.append(("kneepad", geo.hull(f"xz.kneepad.{side}.{'upper' if k == 0 else 'lower'}", q, "kneepad", props, bevel=0.0012)))
            slot = base + v * (-h / 2 + 0.016) + n * 0.0145
            out.append(("kneepad", geo.box(f"xz.kneepad.{side}.slot", slot, (w * 0.42, 0.005, 0.004), R, "lens", props)))
    return out


def soles(parts, props, top=0.034):
    """靴底：起稿靴子 z < top 的部分（软的齿纹底）切掉，换一块干净的底：脚印轮廓外扩 3 mm，0～top 厚，上沿倒角，
    侧面一道 1.2 cm 高的分层线（中底 / 大底）。"""
    from suit import hull2d, offset2d

    out = []
    for side in ("l", "r"):
        o = parts[f"boot.{side}"]
        V = np.array([tuple(v.co) for v in o.data.vertices])
        band = V[(V[:, 2] > top - 0.004) & (V[:, 2] < top + 0.012)]
        H = offset2d(hull2d(band[:, :2]), 0.004)
        bm = bmesh.new()
        bm.from_mesh(o.data)
        bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], dist=1e-6, plane_co=(0, 0, top - 0.002), plane_no=(0, 0, 1), clear_inner=True)
        bm.to_mesh(o.data)
        bm.free()
        for k, (z0, z1, grow_) in enumerate(((0.0, 0.012, 0.004), (0.012, top, 0.0))):
            pts = [(x + (x - H[:, 0].mean()) * 0.0, y_, zz) for x, y_ in offset2d(H, grow_) for zz in (z0, z1)]
            out.append(("sole", geo.hull(f"xz.boot.{side}.sole{k}", pts, "sole", props, bevel=0.002)))
    return out


def connector(att_objs, props):
    """脐带接口：起稿里软管连着的圆盘接头（软的）换成干净的件：圆座 + 斜面圈 + 四芯插座（氧 / 冷 / 电 / 数），
    轴向取圆盘的法向（PCA 最小方差方向）。软管保留起稿的盘绕管。返回 (新件, 被替换掉的面数)。"""
    out = []
    for o in att_objs:
        V = np.array([tuple(v.co) for v in o.data.vertices])
        # 圆盘：软管里最“胖”的一团——取离胸前最远的点附近 4 cm
        tip = V[np.argmax(V[:, 0] + 0.3 * V[:, 2])]
        near = np.linalg.norm(V - tip, axis=1) < 0.045
        P = V[near]
        m = P.mean(0)
        w, U = np.linalg.eigh(np.cov((P - m).T))
        ax = Vector(U[:, 0])
        if ax.dot(Vector((0.3, 1.0, 0.0))) < 0:
            ax = -ax
        c = Vector(m)
        rad = float(np.percentile(np.linalg.norm((P - m) - np.outer((P - m) @ np.array(ax), np.array(ax)), axis=1), 90))
        # 删掉起稿圆盘的面
        bm = bmesh.new()
        bm.from_mesh(o.data)
        dead = [f for f in bm.faces if (f.calc_center_median() - c).length < rad * 1.05]
        bmesh.ops.delete(bm, geom=dead, context="FACES")
        bm.to_mesh(o.data)
        bm.free()
        R = geo.frame_from(ax, Vector((0, 0, 1)))
        out.append(("umbilical", geo.tube("xz.suit.umbilical", [c - ax * 0.012, c + ax * 0.01], rad * 0.95, "umbilical", props, sides=32)))
        out.append(("umbilical", geo.tube("xz.suit.umbilical.bezel", [c + ax * 0.008, c + ax * 0.016], rad * 0.78, "metal", props, sides=32)))
        for k in range(4):
            a = math.pi / 4 + k * math.pi / 2
            p = c + ax * 0.016 + (R.col[1] * math.cos(a) + R.col[2] * math.sin(a)) * rad * 0.4
            out.append(("umbilical", geo.tube(f"xz.suit.umbilical.port{k}", [p, p + ax * 0.007], rad * 0.17, "chrome", props, sides=12)))
        o.name = "xz.suit.hose"
        o.data.materials.clear()
        o.data.materials.append(geo.material("hose"))
        for k, v in props.items():
            o[k] = v
    return out


def spine_line(parts, props, z0=1.13, z1=1.5):
    """脊背暗朱红嵌条（软态未点亮，DESIGN 9.1.1 ③）：背中线、腰带上沿 → 立领下，宽 8 mm、高出 1.2 mm。"""
    tree, _ = tree_of([parts["torso"]])
    pts, nrm = [], []
    for z in np.linspace(z0, z1, 40):
        loc, n = hit(tree, "back", 0.0, z)
        if loc is not None:
            pts.append(loc)
            nrm.append(n)
    P, N = geo.drape(tree, pts, 0.0006, step=0.01)
    return [("spine", geo.ribbon("xz.suit.spine", P, N, 0.008, 0.0012, "vermilion", props))]


FONT = "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"


def inscription_texture(path, text="銜燭", px=256, colour=(201, 211, 214, 255)):
    """「銜燭」贴图：浅灰字、透明底（文泉驿正黑），横排两字。"""
    from PIL import Image, ImageDraw, ImageFont

    font = ImageFont.truetype(FONT, px)
    W, H = int(px * (len(text) + 0.4)), int(px * 1.25)
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    bb = d.textbbox((0, 0), text, font=font)
    d.text(((W - (bb[2] - bb[0])) / 2 - bb[0], (H - (bb[3] - bb[1])) / 2 - bb[1]), text, font=font, fill=colour)
    im.save(path)
    return W / H


def inscription(parts, props, tex_path, centre=(0.052, 1.405), char_h=0.022):
    """胸前「銜燭」贴花：左胸、拉链与左肩带之间（y 0.028～0.076，不压在肩带下）；贴花网格 16×6 格，每点投到躯干表面外 0.8 mm。"""
    aspect = inscription_texture(tex_path)
    h = char_h * 1.25
    w = h * aspect
    tree, _ = tree_of([parts["torso"]])
    loc, n = hit(tree, "front", centre[0], centre[1])
    up = Vector((0, 0, 1))
    v_ = (up - n * up.dot(n)).normalized()
    u_ = v_.cross(n)  # 从正面看向右
    if u_.y < 0:
        u_ = -u_
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    nu, nv = 16, 6
    grid = []
    for j in range(nv + 1):
        row = []
        for i in range(nu + 1):
            p = loc + u_ * (w * (i / nu - 0.5)) + v_ * (h * (j / nv - 0.5))
            q, nn, _, _ = tree.find_nearest(p)
            row.append(bm.verts.new(q + nn * 0.0008))
        grid.append(row)
    for j in range(nv):
        for i in range(nu):
            f = bm.faces.new((grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]))
            for lp, (a, b) in zip(f.loops, ((i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1))):
                lp[uv].uv = (a / nu, b / nv)
    o = geo.obj_from_bm("xz.suit.inscription", bm, "inscription", props)
    img = bpy.data.images.load(tex_path, check_existing=True)
    img.name = "xz.inscription"
    return [("inscription", o)]
