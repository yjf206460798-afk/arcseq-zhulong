"""⑧ 驾驶员「銜燭」软态（DESIGN 9.1.1、refs/concept/X1）：开源人体基础网格摆坐姿 + 服装（WORKFLOW：人体不用基本形拼）。

1. 读 blender/assets/makehuman/（CC0，见 THIRD_PARTY_NOTICES）：base.obj 只取 body 组；骨架关节 = 关节辅助体顶点的平均；权重按骨骼名。
   MakeHuman 坐标（x 左、y 上、z 前，分米）→ 机体（x 前、y 左、z 上，米），身高缩放到 HEIGHT。
2. 摆姿：肢体分段（躯干、颈头、大腿、小腿、脚、上臂、前臂、手），每段的旋转 = 静止标架 → 目标标架（段轴 + 铰链轴）；
   大腿 / 小腿、上臂 / 前臂共用一根铰链轴，膝、肘处不拧麻花。膝、肘位置用两段 IK 求（膝朝上，肘朝外下）。手指按节弯曲握拳。
   其余骨骼跟父骨走。线性蒙皮 v' = Σ w·(G v + t)。
3. 定位：躯干后仰 BACK；臀部贴坐垫、背贴椅背（按接触平移后重解 IK，迭代三次）。
4. 服装（软态）：整身外移 5 mm 成服装，按部位分片（左右前襟、上臂、前臂、大腿、小腿、手套、靴）——分片边界就是接缝线；
   腿腹分块气囊、护膝是外层贴片；脊背一条未点亮的暗朱红细线；挽具（肩带、胸扣、腰带、腿带）沿体表走，腰带两端扣在座椅侧板上；
   胸侧脐带接口。头部不建（头盔整个罩住）：头盔按 DESIGN 重做——盔顶前凸的眉骨、窄面罩、收起的暗琥珀遮光面罩、盔脊、面罩铰链、颈环。
"""
import json
import math
import os

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

from kit.finish import finish
from kit.parts import box, cylinder, ellipsoid, hull, lathe, merge, new_object, pipe

HERE = os.path.dirname(os.path.abspath(__file__))
MH = os.path.join(os.path.dirname(HERE), "assets", "makehuman")
HEIGHT = 1.74  # 第 50 百分位左右的成年人
SUIT = 0.005  # 服装离体表
X, Y, Z = np.array([1.0, 0, 0]), np.array([0, 1.0, 0]), np.array([0, 0, 1.0])


# —— 读入 ——————————————————————————————————————————————————————————————
def load():
    V, faces, g = [], [], None
    with open(os.path.join(MH, "base.obj")) as f:
        for line in f:
            if line.startswith("v "):
                V.append([float(t) for t in line.split()[1:4]])
            elif line.startswith("g "):
                g = line.split()[1]
            elif line.startswith("f ") and g == "body":
                faces.append([int(t.split("/")[0]) - 1 for t in line.split()[1:]])
    V = np.array(V)
    sk = json.load(open(os.path.join(MH, "default.mhskel")))
    wt = json.load(open(os.path.join(MH, "default_weights.mhw")))["weights"]
    used = np.unique(np.concatenate([np.array(f) for f in faces]))
    S = HEIGHT / (V[used, 1].max() - V[used, 1].min())
    P = np.stack([V[:, 2], V[:, 0], V[:, 1]], 1) * S
    P[:, 2] -= P[used, 2].min()  # 脚底 z = 0（静止站姿）
    return P, faces, used, sk, wt


def norm(v):
    n = np.linalg.norm(v)
    return v / n if n > 1e-12 else v


def frame(axis, hinge):
    a = norm(np.asarray(axis, float))
    h = np.asarray(hinge, float)
    h = norm(h - a * h.dot(a))
    return np.stack([a, h, np.cross(a, h)], 1)


def rot(axis, ang):
    k = norm(np.asarray(axis, float))
    K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return np.eye(3) + math.sin(ang) * K + (1 - math.cos(ang)) * K @ K


def ik(a, t, l1, l2, pole):
    """两段 IK：根 a、末端目标 t、两段长、极向 pole → 中间关节位置（够不着时伸直）。"""
    d = t - a
    L = min(np.linalg.norm(d), l1 + l2 - 1e-4)
    u = norm(d)
    w = norm(pole - u * pole.dot(u))
    ca = (l1 * l1 + L * L - l2 * l2) / (2 * l1 * L)
    ang = math.acos(max(-1.0, min(1.0, ca)))
    return a + l1 * (math.cos(ang) * u + math.sin(ang) * w)


# —— 骨架 ——————————————————————————————————————————————————————————————
class Rig:
    def __init__(self, P, sk, wt):
        self.P = P
        self.bones = sk["bones"]
        self.J = {k: P[v].mean(0) for k, v in sk["joints"].items()}
        self.W = {b: (np.array([i for i, _ in L], int), np.array([w for _, w in L])) for b, L in wt.items()}
        # 每个骨骼归哪一段：沿父链找到第一个列在 SEG 里的
        self.seg_of = {}
        for b in self.bones:
            c = b
            while c and c not in SEG_BONES:
                c = self.bones[c]["parent"]
            self.seg_of[b] = SEG_BONES.get(c, "torso")

    def h(self, b):
        return self.J[self.bones[b]["head"]]

    def t(self, b):
        return self.J[self.bones[b]["tail"]]


SEG = {
    "torso": ["root", "spine05", "spine04", "spine03", "spine02", "spine01", "pelvis.L", "pelvis.R", "clavicle.L", "clavicle.R", "shoulder01.L", "shoulder01.R"],
    "head": ["neck01", "neck02", "neck03", "head"],
}
for s in "LR":
    SEG.update({f"thigh.{s}": [f"upperleg01.{s}", f"upperleg02.{s}"], f"shin.{s}": [f"lowerleg01.{s}", f"lowerleg02.{s}"], f"foot.{s}": [f"foot.{s}"],
                f"uarm.{s}": [f"upperarm01.{s}", f"upperarm02.{s}"], f"farm.{s}": [f"lowerarm01.{s}", f"lowerarm02.{s}"], f"hand.{s}": [f"wrist.{s}"]})
SEG_BONES = {b: s for s, L in SEG.items() for b in L}


def pose(rig, seat, root):
    """root：躯干根（MakeHuman root 骨头部）的摆放位置。返回 {骨: (G, t)} 与关节位置。"""
    sb, cb = math.sin(seat["back"]), math.cos(seat["back"])
    T = {}
    # 躯干：后仰
    Gt = frame([-sb, 0, cb], Y) @ frame(rig.h("neck01") - rig.h("root"), Y).T
    Mt = (Gt, root - Gt @ rig.h("root"))
    T["torso"] = Mt
    ap = lambda M, p: M[0] @ p + M[1]  # noqa: E731
    # 颈、头：比躯干立起约 18°（看前方）
    hb = seat["back"] - math.radians(18)
    Gh = frame([-math.sin(hb), 0, math.cos(hb)], Y) @ frame(rig.t("head") - rig.h("neck01"), Y).T
    neck = ap(Mt, rig.h("neck01"))
    T["head"] = (Gh, neck - Gh @ rig.h("neck01"))
    joints = {"neck": neck}
    for s, sg in (("L", 1), ("R", -1)):
        # 腿：髋 → 脚踝目标（膝内角 KNEE），膝朝上
        hip = ap(Mt, rig.h(f"upperleg01.{s}"))
        l1 = np.linalg.norm(rig.h(f"lowerleg01.{s}") - rig.h(f"upperleg01.{s}"))
        l2 = np.linalg.norm(rig.h(f"foot.{s}") - rig.h(f"lowerleg01.{s}"))
        d = math.sqrt(l1 * l1 + l2 * l2 - 2 * l1 * l2 * math.cos(seat["knee"]))
        ankle = hip + norm(seat["feet"][s] - hip) * d
        knee = ik(hip, ankle, l1, l2, Z + X * 0.3)
        hinge = norm(np.cross(knee - hip, ankle - knee))
        G = frame(knee - hip, hinge) @ frame(rig.h(f"lowerleg01.{s}") - rig.h(f"upperleg01.{s}"), Y).T
        T[f"thigh.{s}"] = (G, hip - G @ rig.h(f"upperleg01.{s}"))
        G = frame(ankle - knee, hinge) @ frame(rig.h(f"foot.{s}") - rig.h(f"lowerleg01.{s}"), Y).T
        T[f"shin.{s}"] = (G, knee - G @ rig.h(f"lowerleg01.{s}"))
        toe = rig.h(f"toe3-1.{s}")
        G = frame(seat["foot_dir"], Y) @ frame(toe - rig.h(f"foot.{s}"), Y).T
        T[f"foot.{s}"] = (G, ankle - G @ rig.h(f"foot.{s}"))
        # 臂：肩 → 腕目标（握把后 7 cm），肘朝外下
        sh = ap(Mt, rig.h(f"upperarm01.{s}"))
        el_r, wr_r = rig.h(f"lowerarm01.{s}"), rig.h(f"wrist.{s}")
        l1, l2 = np.linalg.norm(el_r - rig.h(f"upperarm01.{s}")), np.linalg.norm(wr_r - el_r)
        hd = norm(seat["hand_dir"][s])
        wrist = seat["grips"][s] - hd * 0.075 - norm(seat["palm"][s]) * 0.025
        elbow = ik(sh, wrist, l1, l2, sg * Y * 0.55 - Z * 0.8 - X * 0.25)
        hinge_r = norm(np.cross(el_r - rig.h(f"upperarm01.{s}"), wr_r - el_r))
        hinge = norm(np.cross(elbow - sh, wrist - elbow))
        G = frame(elbow - sh, hinge) @ frame(el_r - rig.h(f"upperarm01.{s}"), hinge_r).T
        T[f"uarm.{s}"] = (G, sh - G @ rig.h(f"upperarm01.{s}"))
        G = frame(wrist - elbow, hinge) @ frame(wr_r - el_r, hinge_r).T
        T[f"farm.{s}"] = (G, elbow - G @ el_r)
        ax_r = rig.h(f"finger3-1.{s}") - wr_r
        side_r = rig.h(f"finger5-1.{s}") - rig.h(f"finger2-1.{s}")
        G = frame(hd, seat["knuckles"][s]) @ frame(ax_r, side_r).T
        T[f"hand.{s}"] = (G, wrist - G @ wr_r)
        joints.update({f"hip.{s}": hip, f"knee.{s}": knee, f"ankle.{s}": ankle, f"shoulder.{s}": sh, f"elbow.{s}": elbow, f"wrist.{s}": wrist})
    # 每根骨的变换：段的变换；手指再按节弯曲（绕“食指 → 小指”轴，弯向掌心）
    B = {}
    for b in rig.bones:
        B[b] = T[rig.seg_of[b]]
    for s in "LR":
        Gh_, th = T[f"hand.{s}"]
        side = norm(rig.h(f"finger5-1.{s}") - rig.h(f"finger2-1.{s}"))
        for n, curl in ((1, 0.35), (2, 1.05), (3, 1.1), (4, 1.15), (5, 1.2)):
            M = np.eye(4)
            for j in (1, 2, 3):
                b = f"finger{n}-{j}.{s}"
                if b not in rig.bones:
                    continue
                base = rig.h(b)
                fd = norm(rig.t(b) - base)
                palm = palm_dir(rig, s)
                k = norm(np.cross(fd, palm)) if n > 1 else norm(np.cross(fd, palm) + side * 0.3)
                R = rot(k, curl * (0.55 if j == 1 else 0.5))
                step = np.eye(4)
                step[:3, :3] = R
                step[:3, 3] = base - R @ base
                M = M @ step
                G = Gh_ @ M[:3, :3]
                B[b] = (G, Gh_ @ M[:3, 3] + th)
                for c in rig.bones:
                    if c.startswith(f"finger{n}-") and c.endswith(f".{s}") and int(c.split("-")[1][0]) > j:
                        B[c] = B[b]
    return B, joints


def palm_dir(rig, s):
    """掌心朝向（静止姿态）：中指三节的弯曲方向——指节凸向手背，所以掌心在凸出的反方向。"""
    a, m, t = rig.h(f"finger3-1.{s}"), rig.h(f"finger3-2.{s}"), rig.t(f"finger3-3.{s}")
    u = norm(t - a)
    off = (m - a) - u * (m - a).dot(u)
    if np.linalg.norm(off) > 1e-4:
        return -norm(off)
    ax = norm(rig.h(f"finger3-1.{s}") - rig.h(f"wrist.{s}"))
    side = norm(rig.h(f"finger5-1.{s}") - rig.h(f"finger2-1.{s}"))
    return norm(np.cross(side, ax)) * (1 if s == "L" else -1)


def skin(rig, B, idx):
    P = rig.P
    out = np.zeros((len(P), 3))
    tot = np.zeros(len(P))
    for b, (vi, w) in rig.W.items():
        if b not in B:
            continue
        G, t = B[b]
        out[vi] += w[:, None] * (P[vi] @ G.T + t)
        tot[vi] += w
    ok = tot > 1e-6
    out[ok] /= tot[ok, None]
    G, t = B["root"]
    out[~ok] = P[~ok] @ G.T + t
    return out


def solve(rig, seat):
    """摆姿 + 接触：臀贴坐垫、背贴椅背。"""
    sb, cb = math.sin(seat["back"]), math.cos(seat["back"])
    O = seat["srp"]
    nb = np.array([cb, 0, sb])  # 椅背法向（朝前上）
    t8 = math.tan(math.radians(8))
    dom = dominant(rig)
    torso = np.array([rig.seg_of.get(dom[i], "torso") == "torso" for i in range(len(rig.P))])
    root = O + nb * 0.12 + np.array([0, 0, 0.05])
    for _ in range(4):
        B, J = pose(rig, seat, root)
        Q = skin(rig, B, None)
        rel = Q - O
        along = rel @ np.array([-sb, 0, cb])
        n = rel @ nb
        back = torso & (along > 0.12) & (along < 0.62) & (np.abs(Q[:, 1]) < 0.16)
        fwd = (O[0] - Q[:, 0]) * -1 / math.cos(math.radians(8))  # 沿椅面向前（机体 +x）
        hgt = (Q[:, 2] - O[2]) - fwd * t8 * 0 - (Q[:, 0] - O[0]) * t8
        seatv = (fwd > 0.0) & (fwd < 0.4) & (np.abs(Q[:, 1]) < 0.17) & (along < 0.12)
        dn = (seat["back_n"] + 0.004) - n[back].min()
        dh = (seat["pan_h"] + 0.004) - hgt[seatv].min()
        A = np.array([[cb, sb], [-t8, 1.0]])
        dx, dz = np.linalg.solve(A, [dn, dh])
        root = root + np.array([dx, 0, dz])
        if abs(dx) < 5e-4 and abs(dz) < 5e-4:
            break
    B, J = pose(rig, seat, root)
    return skin(rig, B, None), B, J


def dominant(rig):
    best = np.full(len(rig.P), -1.0)
    who = [None] * len(rig.P)
    for b, (vi, w) in rig.W.items():
        m = w > best[vi]
        for i in vi[m]:
            who[i] = b
        best[vi[m]] = w[m]
    return who


# —— 服装 ——————————————————————————————————————————————————————————————
MATERIAL = {"torso": "suit", "shin": "suit", "sleeve": "suit", "forearm": "suit", "glove": "rubber", "boot": "rubber"}


def vertex_normals(Q, faces):
    N = np.zeros_like(Q)
    for f in faces:
        a, b, c = Q[f[0]], Q[f[1]], Q[f[2]]
        n = np.cross(b - a, c - a)
        if len(f) == 4:
            n = n + np.cross(c - a, Q[f[3]] - a)
        N[f] += n
    L = np.linalg.norm(N, axis=1)
    L[L < 1e-12] = 1
    return N / L[:, None]


def smooth_labels(faces, labels, keep=(), rounds=3):
    """面标签按相邻面（共边）多数决平滑几轮：分片边界不锯齿。keep 里的类别不动（领口、靴口是平面切的，本来就直）。"""
    edge_faces = {}
    for fi, f in enumerate(faces):
        for a, b in zip(f, f[1:] + f[:1]):
            edge_faces.setdefault((min(a, b), max(a, b)), []).append(fi)
    nb = [[] for _ in faces]
    for fs in edge_faces.values():
        for a in fs:
            nb[a] += [b for b in fs if b != a]
    lab = list(labels)
    for _ in range(rounds):
        new = list(lab)
        for fi, ns in enumerate(nb):
            if lab[fi][0] in keep or not ns:
                continue
            votes = [lab[j] for j in ns if lab[j][0] not in keep] + [lab[fi]]
            best = max(set(votes), key=votes.count)
            if votes.count(best) > len(votes) / 2:
                new[fi] = best
        lab = new
    return lab


def ribbon(name, pts, normals, width, thick, material, props):
    """织带：沿 pts 的扁带（宽 width、厚 thick），带面贴着各点的体表法线。"""
    bm = bmesh.new()
    rows = []
    for k, (p, n) in enumerate(zip(pts, normals)):
        t = (pts[min(k + 1, len(pts) - 1)] - pts[max(k - 1, 0)]).normalized()
        b = t.cross(n).normalized()
        n2 = b.cross(t).normalized()
        rows.append([bm.verts.new(p + b * sx * width / 2 + n2 * sz * thick) for sx, sz in ((-1, 0), (1, 0), (1, 1), (-1, 1))])
    for A, B in zip(rows, rows[1:]):
        for k in range(4):
            bm.faces.new((A[k], B[k], B[(k + 1) % 4], A[(k + 1) % 4]))
    bm.faces.new(list(reversed(rows[0])))
    bm.faces.new(rows[-1])
    o = new_object(name, bm, material, props)
    return o, finish(o, bevel=0.0, angle=40)


def mesh_object(name, verts, faces, material, props):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], [tuple(f) for f in faces])
    me.update()
    o = bpy.data.objects.new(name, me)
    o.data.materials.append(bpy.data.materials.get(material) or bpy.data.materials.new(material))
    bpy.context.scene.collection.objects.link(o)
    for k, v in props.items():
        o[k] = v
    return o, finish(o, bevel=0.0, curved=True)


def piece(name, Q, faces, keep, material, props):
    """faces 里被 keep 选中的面 → 一个对象（顶点重新编号）。"""
    F = [f for f, k in zip(faces, keep) if k]
    if not F:
        return None
    ids = sorted({i for f in F for i in f})
    remap = {v: k for k, v in enumerate(ids)}
    return mesh_object(name, Q[ids], [[remap[i] for i in f] for f in F], material, props)


def build(seat, props):
    """seat：srp、back、back_n、pan_h、knee、feet、foot_dir、grips、hand_dir、knuckles、palm、seat_side（腰带扣点）。返回 (零件列表, 关节)。"""
    P, faces, used, sk, wt = load()
    rig = Rig(P, sk, wt)
    Q, B, J = solve(rig, seat)
    dom = dominant(rig)
    seg = [rig.seg_of.get(dom[i], "torso") if dom[i] else "torso" for i in range(len(P))]
    # 分片按静止姿态里的平面切（接缝是直的，不跟着权重边界锯齿）：袖根、肘、腕、膝、靴口、领口；躯干与大腿一片（连体服），左右在中线分开（拉链）
    ankle_z = max(rig.h("foot.L")[2], rig.h("foot.R")[2])
    neck_z = rig.h("neck02")[2]
    arm_seg = {"uarm", "farm", "hand"}
    leg_seg = {"thigh", "shin", "foot"}

    def classify(c, sg):
        """c：静止姿态的点；sg：该点的骨段。"""
        if c[2] > neck_z:
            return "head"
        if c[2] < ankle_z + 0.16:
            return "boot"
        s_ = "L" if c[1] >= 0 else "R"
        if sg.split(".")[0] in arm_seg:
            sh, el, wr = rig.h(f"upperarm01.{s_}"), rig.h(f"lowerarm01.{s_}"), rig.h(f"wrist.{s_}")
            if (c - wr).dot(norm(wr - el)) > 0.0:
                return "glove"
            if (c - el).dot(norm(wr - el)) > -0.01:
                return "forearm"
            if (c - sh).dot(norm(el - sh)) > 0.035:
                return "sleeve"
            return "torso"
        if sg.split(".")[0] in leg_seg:
            kn = rig.h(f"lowerleg01.{s_}")
            return "shin" if c[2] < kn[2] - 0.04 else "torso"
        return "torso"

    kind = [classify(P[i], seg[i]) for i in range(len(P))]
    N = vertex_normals(Q, faces)
    Nr = vertex_normals(P, faces)
    off = np.array([{"glove": 0.003, "boot": 0.009}.get(k, SUIT) for k in kind])
    S = Q + N * off[:, None]
    out = []
    fk = []
    for f in faces:
        c = P[f].mean(0)
        ss = [seg[i] for i in f]
        sg = max(set(ss), key=ss.count)
        # 腋下：躯干骨段的面落在袖根平面外、且贴着上臂轴（8 cm 内）的，归袖子——接缝沿平面走
        s_ = "L" if c[1] >= 0 else "R"
        sh, el = rig.h(f"upperarm01.{s_}"), rig.h(f"lowerarm01.{s_}")
        u = norm(el - sh)
        t_ = (c - sh).dot(u)
        if sg.split(".")[0] == "torso" and t_ > 0.035 and np.linalg.norm((c - sh) - u * t_) < 0.08 and c[2] < sh[2]:
            sg = f"uarm.{s_}"
        k = classify(c, sg)
        fk.append((k, s_))
    fk = smooth_labels(faces, fk, keep={"head", "boot"})
    for k in ("torso", "shin", "sleeve", "forearm", "glove", "boot"):
        for sd in "LR":
            keep = [x == (k, sd) for x in fk]
            if k == "boot":
                # 靴筒用网格（踝上 4 cm 起），靴头用脚的凸包（不出脚趾），再垫一块鞋底
                keep = [kk and P[f].mean(0)[2] > ankle_z + 0.04 for kk, f in zip(keep, faces)]
            it = piece(f"int.pilot.{k}.{sd.lower()}", S, faces, keep, MATERIAL[k], props)
            if it:
                out.append(it)
    for sd in "LR":
        ids = np.array([i for i in used if P[i, 2] < ankle_z + 0.06 and (P[i, 1] >= 0) == (sd == "L")])
        shoe = Q[ids] + N[ids] * 0.012
        out.append(hull(f"int.pilot.boot.{sd.lower()}.shoe", [Vector(v.tolist()) for v in shoe[:: max(1, len(shoe) // 300)]], "rubber", props, bevel=0.006))
        # 鞋底：脚掌最低的一圈点沿脚底法向再垫 1.5 cm
        fd = Vector(seat["foot_dir"].tolist()).normalized()
        down = Vector((fd.z, 0.0, -fd.x))
        d = shoe @ np.array(down)
        low = shoe[d > np.percentile(d, 82)]
        sole = [Vector(v.tolist()) + down * dd for v in low[:: max(1, len(low) // 60)] for dd in (0.0, 0.015)]
        out.append(hull(f"int.pilot.boot.{sd.lower()}.sole", sole, "strap", props, bevel=0.004))
    # —— 外层贴片：护膝、大腿 / 小腿 / 腹部分块气囊（比服装再高 8～16 mm）——
    face_c = np.array([P[f].mean(0) for f in faces])
    face_n = np.array([norm(Nr[f].sum(0)) for f in faces])

    def along(i, a, b):
        d = b - a
        return float((face_c[i] - a).dot(d) / d.dot(d))

    pads = []
    for sd in "LR":
        knee = rig.h(f"lowerleg01.{sd}")
        hip, ank = rig.h(f"upperleg01.{sd}"), rig.h(f"foot.{sd}")
        pads.append((f"kneepad.{sd}", 0.02, lambda i, knee=knee: np.linalg.norm(face_c[i] - knee) < 0.065 and face_n[i][0] > 0.2))
        for k, (t0, t1) in enumerate(((0.22, 0.47), (0.5, 0.78))):
            pads.append((f"bladder.thigh{k}.{sd}", 0.012, lambda i, t0=t0, t1=t1, hip=hip, knee=knee, sd=sd: fk[i] == ("torso", sd) and face_n[i][0] > 0.35 and t0 < along(i, hip, knee) < t1 and np.linalg.norm(np.cross(face_c[i] - hip, norm(knee - hip))) < 0.11))
        pads.append((f"bladder.shin.{sd}", 0.011, lambda i, knee=knee, ank=ank, sd=sd: fk[i] == ("shin", sd) and face_n[i][0] > 0.3 and 0.22 < along(i, knee, ank) < 0.7))
        w0, w1 = rig.h("spine05")[2] + 0.02, rig.h("spine03")[2] - 0.01
        pads.append((f"bladder.abdomen.{sd}", 0.012, lambda i, w0=w0, w1=w1, sd=sd: fk[i][0] == "torso" and fk[i][1] == sd and face_n[i][0] > 0.55 and w0 < face_c[i][2] < w1 and abs(face_c[i][1]) > 0.012))
    for name, extra, pred in pads:
        keep = [pred(i) for i in range(len(faces))]
        it = piece(f"int.pilot.{name.lower()}", Q + N * (SUIT + extra), faces, keep, "pad" if name.startswith("bladder") else "rubber", props)
        if it:
            out.append(it)
    # 脊背暗朱红细线（未点亮）
    keep = [fk[i][0] == "torso" and face_n[i][0] < -0.5 and abs(face_c[i][1]) < 0.011 and rig.h("spine05")[2] < face_c[i][2] < rig.h("neck01")[2] for i in range(len(faces))]
    it = piece("int.pilot.spine", Q + N * (SUIT + 0.003), faces, keep, "vermilion", props)
    if it:
        out.append(it)

    # —— 挽具：沿体表的带子（锚点在静止姿态里找体表顶点，摆姿后沿法线外移）——
    torso_ids = np.array([i for i in used if kind[i] == "torso"])
    thigh_ids = np.array([i for i in used if kind[i] == "torso" and seg[i].startswith("thigh")])

    def vid(y, z, front=True, ids=torso_ids):
        """静止姿态里 (y, z) 处躯干前（后）表面的顶点号。"""
        c = ids[(np.abs(P[ids, 2] - z) < 0.02) & (np.abs(P[ids, 1] - y) < 0.02)]
        if not len(c):
            c = ids[np.argsort(np.abs(P[ids, 2] - z) + np.abs(P[ids, 1] - y))[:5]]
        return c[np.argmax(P[c, 0])] if front else c[np.argmin(P[c, 0])]

    def surf(y, z, front=True, ids=torso_ids, out_=0.004):
        i = vid(y, z, front, ids)
        return Vector((Q[i] + N[i] * (SUIT + out_)).tolist())

    def top(y, z0):
        c = torso_ids[(np.abs(P[torso_ids, 1] - y) < 0.02) & (P[torso_ids, 2] > z0)]
        i = c[np.argmax(P[c, 2])]
        return Vector((Q[i] + N[i] * (SUIT + 0.004)).tolist())

    def drape(pts, ids=torso_ids, step=0.025):
        """折线加密后每点投到最近的几个体表顶点（只在躯干 / 大腿上找，不吸到手臂上），沿平均法线外移，再平滑几轮：
        带子贴着身体走、不打折。返回 (点, 法线)。"""
        dense = []
        for a, b in zip(pts, pts[1:]):
            n = max(1, int((b - a).length / step))
            dense += [a.lerp(b, k / n) for k in range(n)]
        dense.append(pts[-1])
        base = Q[ids]
        P_, N_ = [], []
        for p in dense:
            d = np.linalg.norm(base - np.array(p), axis=1)
            near = np.argsort(d)[:6]
            w = 1.0 / (d[near] + 1e-3)
            q = (base[near] * w[:, None]).sum(0) / w.sum()
            n = norm((N[ids[near]] * w[:, None]).sum(0))
            P_.append(q + n * (SUIT + 0.01))  # 离服装 1 cm：平滑后的折线在胸前凸面上也不陷进去
            N_.append(n)
        P_, N_ = np.array(P_), np.array(N_)
        for _ in range(2):
            P_[1:-1] = 0.5 * P_[1:-1] + 0.25 * (P_[:-2] + P_[2:])
            N_[1:-1] = 0.5 * N_[1:-1] + 0.25 * (N_[:-2] + N_[2:])
        return [Vector(v.tolist()) for v in P_], [Vector(norm(v).tolist()) for v in N_]

    sh_z = rig.h("clavicle.L")[2]
    chest = rig.h("spine02")[2]
    belly = rig.h("spine04")[2]
    hipz = rig.h("spine05")[2] - 0.02
    buckle = surf(0.0, chest - 0.06)
    lap = surf(0.0, hipz)
    for sd, sg in (("l", 1), ("r", -1)):
        # 肩带：背后 → 肩顶 → 胸前 → 胸扣
        pts, ns = drape([surf(sg * 0.08, sh_z - 0.14, False), top(sg * 0.1, sh_z - 0.05), surf(sg * 0.09, chest + 0.06), surf(sg * 0.05, chest - 0.03), buckle])
        out.append(ribbon(f"int.pilot.strap.shoulder.{sd}", pts, ns, 0.045, 0.005, "strap", props))
        # 腰带：腰扣 → 胯侧 → 扣在座椅侧板上
        side_pt = Vector(seat["seat_side"][sd.upper()])
        pts, ns = drape([lap, surf(sg * 0.1, hipz + 0.01), surf(sg * 0.16, hipz + 0.02)])
        pts.append(side_pt)
        ns.append(ns[-1])
        out.append(ribbon(f"int.pilot.strap.lap.{sd}", pts, ns, 0.05, 0.005, "strap", props))
        # 腿带：腰扣 → 绕大腿根前侧 → 外侧
        tz = rig.h(f"upperleg01.{sd.upper()}")[2] - 0.12
        pts, ns = drape([lap] + [surf(sg * a, tz, True, thigh_ids) for a in (0.04, 0.09, 0.14)] + [surf(sg * 0.17, tz + 0.05)], ids=np.concatenate([torso_ids, thigh_ids]))
        out.append(ribbon(f"int.pilot.strap.leg.{sd}", pts, ns, 0.04, 0.005, "strap", props))
    # 胸扣、腰扣（扣面朝外）
    for nm, p, w in (("buckle.chest", buckle, 0.07), ("buckle.lap", lap, 0.08)):
        n = Vector(N[used[np.argmin(np.linalg.norm(Q[used] - np.array(p), axis=1))]].tolist()).normalized()
        xa = n
        za = (Vector((0, 0, 1)) - n * n.z).normalized()
        R = Matrix((xa, za.cross(xa), za)).transposed()
        out.append(box(f"int.pilot.{nm}", p + n * 0.006, (0.016, w, 0.045), rot=R, material="metal", face="+x", panel=False, handles=False, plugs=0, ears=False, corner_bolts=True, props=props))
    # 脐带接口（左胸侧，氧 / 冷 / 电 / 数）：小盒 + 四个插头，软管接到座椅左侧
    port = surf(0.13, chest - 0.02, out_=0.03)
    out.append(box("int.pilot.umbilical", port, (0.06, 0.04, 0.07), material="avionics", face="+y", panel=False, handles=False, plugs=0, ears=False, corner_bolts=True, props=props))
    out.append(pipe("int.pilot.hose", [port + Vector((0, 0.02, -0.03)), port + Vector((-0.08, 0.08, -0.12)), Vector(seat["seat_side"]["L"]) + Vector((0.12, 0.0, 0.05))], 0.014, bend=0.06, sides=10, material="cable", props=props))

    # —— 头盔 ——————————————————————————————————————————————————————————
    head_ids = np.array([i for i in used if kind[i] == "head"])
    G, t = B["head"]
    f, l, u = (Vector(G @ v) for v in (X, Y, Z))
    c = Vector(Q[head_ids].mean(0)) + u * 0.02 - f * 0.005
    R = (0.134, 0.124, 0.144)
    axes = (f, l, u)
    out.append(ellipsoid("int.pilot.helmet", c, R, axes, u=40, v=20, material="helmet", props=props))

    def on(az, el, k=1.0):
        a, e = math.radians(az), math.radians(el)
        return c + f * (R[0] * k * math.cos(e) * math.cos(a)) + l * (R[1] * k * math.cos(e) * math.sin(a)) + u * (R[2] * k * math.sin(e))

    # 窄面罩（透明，睁眼态）：方位 ±48°、俯仰 −36°～+10°
    vis = [on(a, e, 1.035) for a in range(-48, 49, 8) for e in range(-36, 11, 6)] + [on(a, e, 0.97) for a in (-48, 0, 48) for e in (-36, 10)]
    out.append(hull("int.pilot.visor", vis, "glass", {**props, "glass": True}, bevel=0.002))
    # 收起的暗琥珀遮光面罩：面罩上沿、眉骨下的一条
    sun = [on(a, e, 1.05) for a in range(-44, 45, 8) for e in (11, 17)] + [on(a, e, 0.98) for a in (-44, 0, 44) for e in (11, 17)]
    out.append(hull("int.pilot.sunvisor", sun, "visor", props, bevel=0.002))
    # 眉骨：盔顶前沿一道前凸的棱（与机身眉骨同一语言），中间最凸
    brow = []
    for a in range(-42, 43, 6):
        k = 1.06 + 0.05 * math.cos(math.radians(a) * 2.1)
        brow += [on(a, 19, k), on(a, 26, 1.04), on(a, 19, 0.98)]
    out.append(hull("int.pilot.helmet.brow", brow, "helmet", props, bevel=0.004))
    # 盔脊：眉骨后沿顶中线到后脑，一条微凸的窄脊（分三段凸体）
    for k, (e0, e1) in enumerate(((28, 70), (70, 115), (115, 150))):
        pts = []
        for e in (e0, e1):
            for a in (-7, 7):
                ang = math.radians(e)
                base = c + f * (R[0] * math.cos(ang)) + u * (R[2] * math.sin(ang))
                n = (base - c).normalized()
                pts += [base + l * (R[1] * math.sin(math.radians(a))) + n * d for d in (-0.004, 0.007)]
        out.append(hull(f"int.pilot.helmet.ridge{k}", pts, "helmet", props, bevel=0.002))
    # 面罩铰链（两侧）、颈环
    for sd, sg in (("l", 1), ("r", -1)):
        p = on(90 * sg, 2, 1.0)
        out.append(cylinder(f"int.pilot.helmet.hinge.{sd}", p - l * sg * 0.004, p + l * sg * 0.012, 0.028, 18, "metal", props, bevel=0.002))
    neck = Vector(J["neck"])
    ax = Vector(G @ Z)
    out.append(lathe("int.pilot.neckring", neck - ax * 0.01, neck + ax * 0.035, [(0, 0.082), (0.4, 0.09), (1, 0.086)], 28, "metal", props))
    return out, {k: Vector(v) for k, v in J.items()} | {"head": c, "helmet_top": c + u * R[2]}
