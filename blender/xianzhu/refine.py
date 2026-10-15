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

import draft
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


def simplify(H, d):
    """凸轮廓抽稀：相邻点间距不小于 d（靴底轮廓点太密，倒角后一块底上千个三角形）。"""
    out = [H[0]]
    for p in H[1:]:
        if np.linalg.norm(p - out[-1]) >= d:
            out.append(p)
    if len(out) > 3 and np.linalg.norm(out[-1] - out[0]) < d:
        out.pop()
    return np.array(out)


def soles(parts, props, top=0.034):
    """靴底：起稿靴子 z < top 的部分（软的齿纹底）切掉，换一块干净的底：脚印轮廓外扩 3 mm，0～top 厚，上沿倒角，
    侧面一道 1.2 cm 高的分层线（中底 / 大底）。"""
    from suit import hull2d, offset2d

    out = []
    for side in ("l", "r"):
        o = parts[f"boot.{side}"]
        V = np.array([tuple(v.co) for v in o.data.vertices])
        band = V[(V[:, 2] > top - 0.004) & (V[:, 2] < top + 0.012)]
        H = simplify(offset2d(hull2d(band[:, :2]), 0.004), 0.006)
        bm = bmesh.new()
        bm.from_mesh(o.data)
        bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], dist=1e-6, plane_co=(0, 0, top - 0.002), plane_no=(0, 0, 1), clear_inner=True)
        bm.to_mesh(o.data)
        bm.free()
        draft.restore_normals(o)
        for k, (z0, z1, grow_) in enumerate(((0.0, 0.012, 0.004), (0.012, top, 0.0))):
            pts = [(x + (x - H[:, 0].mean()) * 0.0, y_, zz) for x, y_ in offset2d(H, grow_) for zz in (z0, z1)]
            out.append(("sole", geo.hull(f"xz.boot.{side}.sole{k}", pts, "sole", props, bevel=0.002)))
    return out


# 脐带接头（Tripo Smart Mesh：refs/ai_draft/X1_脐带接头_smartmesh.glb）：长方体主体，一端四根短管（氧 / 冷 / 电 / 数），
# 另一端提手。底稿坐标里短管朝 −x、提手朝 +x、主体高沿 z、薄的方向沿 y。
PLUG_SCALE = 0.1  # 主体约 6 × 3 × 3.2 cm，连短管长 10 cm
PLUG_BODY = Vector((0.10, 0.0, 0.307))  # 主体中心（底稿坐标）
PLUG_TIP = Vector((-0.50, 0.0, 0.29))  # 四根短管端头的中心
PLUG_HALF_T = 0.161  # 主体半厚（底稿 y）


def plug(name, R, centre, props, path=None):
    """接头放到世界里：R 的三列 = 底稿 x / y / z 轴在世界里的方向（右手系），主体中心落在 centre。只有刚体 + 等比变换，
    Tripo 的自定义法线照样有效。返回 (对象, 短管端头中心, 短管方向, 变换矩阵)。"""
    o = draft.import_glb(path or draft.DRAFT_CONNECTOR)[0]
    o.name = o.data.name = name
    M = Matrix.Translation(centre) @ (R.to_4x4() @ Matrix.Diagonal((PLUG_SCALE,) * 3 + (1.0,))) @ Matrix.Translation(-PLUG_BODY)
    draft.transform_all([o], M)
    o.data.materials.clear()
    o.data.materials.append(geo.material("umbilical"))
    for k, v in props.items():
        o[k] = v
    return o, M @ PLUG_TIP, -(R.col[0]), M


def connector(att_objs, parts, props):
    """左胸脐带接口：起稿里软管连着的圆盘接头（软的）删掉，换成 Tripo 脐带接头：主体平贴胸前（薄面朝外），提手朝上，
    四根短管朝下接进起稿保留的盘绕软管。返回 [(类, 对象)] 和接头信息（坐姿重接软管用）。"""
    o = att_objs[0]
    V = np.array([tuple(v.co) for v in o.data.vertices])
    tip = V[np.argmax(V[:, 0] + 0.3 * V[:, 2])]
    near = np.linalg.norm(V - tip, axis=1) < 0.045
    P = V[near]
    m = P.mean(0)
    w, U = np.linalg.eigh(np.cov((P - m).T))
    ax = Vector(U[:, 0])
    if ax.dot(Vector((1.0, 0.3, 0.0))) < 0:
        ax = -ax
    c = Vector(m)
    rad = float(np.percentile(np.linalg.norm((P - m) - np.outer((P - m) @ np.array(ax), np.array(ax)), axis=1), 90))
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if (f.calc_center_median() - c).length < rad * 1.05], context="FACES")
    bm.to_mesh(o.data)
    bm.free()
    draft.restore_normals(o)
    o.name = o.data.name = "xz.suit.hose"
    # 胸面上的落点与外法线
    tree, _ = tree_of([parts["torso"]])
    q, n, _, _ = tree.find_nearest(c)
    n = Vector(n).normalized()
    down = Vector((0, 0, -1))
    d = (down - n * down.dot(n)).normalized()
    X = -d  # 底稿 +x（提手）朝上
    Y = n  # 底稿 +y 朝外
    R = Matrix((X, Y, X.cross(Y))).transposed()
    centre = Vector(q) + n * (PLUG_HALF_T * PLUG_SCALE + 0.004)
    obj, tip_w, tip_d, M = plug("xz.suit.umbilical", R, centre, props)
    info = {"chest_tip": tuple(tip_w), "chest_dir": tuple(tip_d), "disc_r": round(rad, 4), "M": draft.flat(M)}
    return [("umbilical", obj)], info


def seat_plug(port):
    """座椅侧接头（坐姿版）：同一件，主体贴在座椅左侧板外侧（薄面朝 +y），短管朝上（接胸前来的软管），提手朝下。
    port：座椅局部坐标的插座点（seat.SEAT["umbilical_port"]）。返回 (变换矩阵, 短管端头中心, 短管方向)——坐姿版直接把
    胸前那件（已减面、已烘法线）按 M_座椅 · M_胸前⁻¹ 复制过去，两处共用 UV 与贴图。"""
    X = Vector((0, 0, -1))
    Y = Vector((0, 1, 0))
    R = Matrix((X, Y, X.cross(Y))).transposed()
    centre = Vector(port) + Y * (PLUG_HALF_T * PLUG_SCALE)
    M = Matrix.Translation(centre) @ (R.to_4x4() @ Matrix.Diagonal((PLUG_SCALE,) * 3 + (1.0,))) @ Matrix.Translation(-PLUG_BODY)
    return M, M @ PLUG_TIP, -(R.col[0])


def seated_hose(a, da, b, db, props, radius=0.011):
    """坐姿软管：胸前接头的短管端头 a（方向 da）→ 座椅侧接头端头 b（方向 db），三次贝塞尔，两端顺着短管方向出。"""
    a, b, da, db = Vector(a), Vector(b), Vector(da).normalized(), Vector(db).normalized()
    L = (b - a).length
    p1, p2 = a + da * L * 0.4, b + db * L * 0.4
    pts = []
    for k in range(25):
        t = k / 24
        u = 1 - t
        pts.append(a * u ** 3 + p1 * 3 * u * u * t + p2 * 3 * u * t * t + b * t ** 3)
    return geo.tube("xz.suit.hose.seated", pts, radius, "cable", props, sides=16)


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
