"""机身蒙皮细节贴图（numpy，程序生成，可重跑）。输入每个纹素的世界坐标 P、法线 N、贴图 AO，输出两张图：

  skin.png      r 明度乘子（0.5 = 不变：刻线 / 铆钉压暗，面板之间 ±3% 错拼，棱边极淡的磨损提亮）、g 涂装、b AO
  skin-pbr.png  rgb 物体空间法线（刻线成浅槽、铆钉成小圆顶、鳞片缝成细槽），a 粗糙度（B 画法用）

细节疏密（CLAUDE.md）：集中在机头光窗、座舱与眉骨、化剑转轴处；大面积蒙皮保持安静——
  · 铆钉行只沿几何母版的分割线 / 口盖线（seams），不在空白蒙皮上撒；
  · 安静区不留空白：面板之间 ±3% 明度错拼（看得出拼板，看不出花纹）；
  · 鳞片缝只画在平腹底（下切面上是几何样片，不重复），按结构框分区，区与区之间留一道分区缝；
  · 涂装只有三处：上外切面机号「02」、座舱下方一行「燭龍 ZHULONG」（铭文一律繁体，DESIGN 8.5）、姿控喷口前的警示三角。
"""
import numpy as np

from .nose import APEX_S, HEX_H, HEX_W, K, S_END, S_FLAT, Z_TIP, ZONES
from .util import XN

FONT = "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"


def ring_np(s):
    """nose.ring 的向量版：{R0…R3: (y, z)}，每项是与 s 同形的数组（背脊在 S_FLAT 后放平）。"""
    t = s - APEX_S
    out = {k: (a * t, Z_TIP + b * t) for k, (a, b) in K.items()}
    out["R0"] = (np.zeros_like(s), Z_TIP + K["R0"][1] * np.minimum(t, S_FLAT - APEX_S))
    return out


def hash01(*keys):
    """整数键 → [0, 1) 的确定性伪随机（面板编号用）。"""
    h = np.zeros(np.broadcast(*keys).shape, np.uint64)
    for k in keys:
        h = (h ^ (np.asarray(k).astype(np.int64).astype(np.uint64) + np.uint64(0x9E3779B97F4A7C15) + (h << np.uint64(6)) + (h >> np.uint64(2))))
        h = h * np.uint64(0xBF58476D1CE4E5B9)
        h ^= h >> np.uint64(31)
    return (h % np.uint64(1 << 24)).astype(np.float32) / float(1 << 24)


def value_noise(P, scale, seed=0):
    """三维值噪声（磨损的不规则边）：格点哈希 + 三线性插值。"""
    q = P[..., :3] / scale
    i = np.floor(q).astype(np.int64)
    f = q - i
    f = f * f * (3 - 2 * f)
    out = np.zeros(q.shape[:-1], np.float32)
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                w = (f[..., 0] if dx else 1 - f[..., 0]) * (f[..., 1] if dy else 1 - f[..., 1]) * (f[..., 2] if dz else 1 - f[..., 2])
                out += w * hash01(i[..., 0] + dx, i[..., 1] + dy, i[..., 2] + dz, seed)
    return out


class Field:
    """纹素的 3D 位置按 x 排好序：给线段 / 点只查附近一段纹素。"""

    def __init__(self, P, valid):
        self.flat = np.where(valid.ravel())[0]
        self.pts = P[..., :3].reshape(-1, 3)
        xs = self.pts[self.flat, 0]
        order = np.argsort(xs)
        self.xs = xs[order]
        self.ids = self.flat[order]

    def near(self, x0, x1):
        lo = np.searchsorted(self.xs, x0)
        hi = np.searchsorted(self.xs, x1)
        return self.ids[lo:hi]


def segment_field(F, segs, reach):
    """到一组 3D 线段的最近距离与“离线方向”（单位向量），只算 reach 以内；返回 (d, dir) 拉平数组。"""
    n = F.pts.shape[0]
    d = np.full(n, np.inf, np.float32)
    away = np.zeros((n, 3), np.float32)
    for a, b in segs:
        a, b = np.asarray(a, np.float32), np.asarray(b, np.float32)
        ids = F.near(min(a[0], b[0]) - reach, max(a[0], b[0]) + reach)
        if len(ids) == 0:
            continue
        p = F.pts[ids]
        ab = b - a
        L2 = float(ab @ ab) or 1e-12
        t = np.clip(((p - a) @ ab) / L2, 0, 1)
        q = a + t[:, None] * ab
        v = p - q
        dd = np.linalg.norm(v, axis=1)
        better = dd < d[ids]
        sel = ids[better]
        d[sel] = dd[better]
        away[sel] = v[better] / np.maximum(dd[better], 1e-6)[:, None]
    return d, away


def seam_segments(seams, levels=(None, "secondary", "structure")):
    out = []
    for sm in seams:
        if sm.get("level") not in levels:
            continue
        pts = [np.array(p) for p in sm["points"]]
        loop = pts + ([pts[0]] if sm.get("closed") else [])
        out += list(zip(loop, loop[1:]))
    return out


def rivets_along(seams, pitch=0.035, offset=0.018):
    """沿每条分割线两侧各一行铆钉：偏离 offset，间距 pitch。"""
    out = []
    for sm in seams:
        if sm.get("level") not in (None, "secondary", "structure"):
            continue
        pts = [np.array(p) for p in sm["points"]]
        nrm = [np.array(n) for n in sm["normals"]]
        loop = pts + ([pts[0]] if sm.get("closed") else [])
        nl = nrm + ([nrm[0]] if sm.get("closed") else [])
        for a, b, na in zip(loop, loop[1:], nl):
            L = np.linalg.norm(b - a)
            if L < 1e-6:
                continue
            dvec = (b - a) / L
            side = np.cross(na, dvec)
            side /= np.linalg.norm(side) or 1
            for k in range(1, int(L / pitch)):
                p = a + dvec * k * pitch
                for sgn in (1, -1):
                    out.append(p + side * offset * sgn - na * 0.002)
    return out


def text_mask(text, height_px=96, pad=8):
    from PIL import Image, ImageDraw, ImageFont

    font = ImageFont.truetype(FONT, height_px)
    box = font.getbbox(text)
    w, h = box[2] - box[0] + 2 * pad, box[3] - box[1] + 2 * pad
    img = Image.new("L", (w, h), 0)
    ImageDraw.Draw(img).text((pad - box[0], pad - box[1]), text, fill=255, font=font)
    return np.asarray(img, dtype=np.float32) / 255.0


def decal(g, sel, u, v, mask, u0, v0, width, flip=False):
    """把 mask（图像，宽 width 米）贴到 (u, v) 平面坐标上：u0, v0 为左上角；flip 为右侧机身（读向反过来）。"""
    H, W = mask.shape
    height = width * H / W
    uu = (u - u0) / width
    vv = (v - v0) / height
    if flip:
        uu = 1 - uu
    inside = sel & (uu >= 0) & (uu < 1) & (vv >= 0) & (vv < 1)
    ix = np.clip((uu * W).astype(int), 0, W - 1)
    iy = np.clip((vv * H).astype(int), 0, H - 1)
    g[inside] = np.maximum(g[inside], mask[iy[inside], ix[inside]])
    return g


def facet_of(y, z, s, R, nz):
    """纹素在哪个切面：0 屋面、1 外上、2 下切面、3 腹底。"""
    ya = np.abs(y)
    f = np.full(y.shape, 2, np.int64)
    f = np.where(z >= R["R1"][1] - 0.003, 0, f)
    f = np.where((z < R["R1"][1] - 0.003) & (z >= R["R2"][1] - 0.003), 1, f)
    f = np.where(nz < -0.97, 3, f)
    return f


def paint(P, N, A, meta):
    """返回 (skin rgb, pbr rgba, valid)。"""
    valid = np.linalg.norm(N[..., :3], axis=-1) > 0.5  # 浮点图 alpha 不可靠：用烘出来的法线长度判断
    shape = valid.shape
    x, y, z = P[..., 0], P[..., 1], P[..., 2]
    s = XN - x
    n = N[..., :3] / np.maximum(np.linalg.norm(N[..., :3], axis=-1, keepdims=True), 1e-6)
    nz = n[..., 2]
    R = ring_np(np.clip(s, 0.3, S_END))
    F = Field(P, valid)
    r = np.full(shape, 0.5, np.float32)
    g = np.zeros(shape, np.float32)
    b = np.where(valid, A[..., 0], 1.0).astype(np.float32)
    rough = np.full(shape, 0.55, np.float32)
    bump = np.zeros(shape + (3,), np.float32)  # 法线扰动（加到 n 上再归一）

    # —— 面板错拼：按分割线环（seams 的 ring 站位）+ 切面 + 左右编号，每块 ±3% 明度、±0.05 粗糙度 ——
    cuts = np.array(sorted(meta.get("panel_cuts", [0.62, 1.07, 2.05, 3.1, 4.06, 4.8, 5.85, 6.95])))
    idx = np.searchsorted(cuts, s)
    fac = facet_of(y, z, s, R, nz)
    h = hash01(idx, fac, (y > 0).astype(np.int64), 7)
    r += np.where(valid, (h - 0.5) * 0.06 * 0.5, 0)  # r 是 0.5 中性：±3% → ±0.015
    rough += np.where(valid, (h - 0.5) * 0.1, 0)

    # —— 腹底鳞片（平腹底，与下切面的几何瓦同一套蜂窝：W × H、奇数列错开半行，按 ZONES 分区；下切面是几何瓦，不画）——
    belly = valid & (fac == 3) & (s > ZONES[0][0])
    vb = R["R3"][0] - np.abs(y)  # 到腹缘的距离
    W, H = HEX_W, HEX_H
    best = np.full(shape, 9.0, np.float32)
    zone_edge = np.full(shape, 9.0, np.float32)
    for (s0, s1) in ZONES:
        inz = belly & (s >= s0) & (s < s1)
        if not inz.any():
            continue
        zone_edge = np.where(inz, np.minimum(s - s0, s1 - s), zone_edge)
        c0 = np.round((s - s0 - W / 2) / (0.75 * W))
        for dc in (-1, 0, 1):
            c = c0 + dc
            sc = s0 + W / 2 + c * 0.75 * W
            off = np.where(np.mod(c, 2) == 1, H / 2, 0.0)
            j0 = np.round((vb - off) / H)
            for dj in (-1, 0, 1):
                vc = off + (j0 + dj) * H
                du, dv = np.abs(s - sc), np.abs(vb - vc)
                hn = np.maximum(dv / (H / 2), du / (W / 2) + dv / H)  # 六边形“范数”：边上为 1
                best = np.where(inz, np.minimum(best, hn), best)
    edge = np.clip((best - 0.88) / 0.12, 0, 1)
    gap = np.clip(1 - zone_edge / 0.008, 0, 1)  # 分区缝 1.5 cm
    r = np.where(belly, r - 0.12 * edge - 0.2 * gap, r)
    rough = np.where(belly, rough + 0.08 * edge, rough)

    # —— 刻线（分割线、口盖线：浅槽 0.5 mm、宽 4 mm）——
    segs = seam_segments(meta["seams"])
    d, away = segment_field(F, segs, 0.01)
    d = d.reshape(shape)
    away = away.reshape(shape + (3,))
    groove = np.exp(-(d / 0.0022) ** 2)
    r -= 0.13 * groove
    rough += 0.15 * groove
    slope = np.where(np.isfinite(d), 0.25 * (d / 0.0022) * np.exp(-(d / 0.0022) ** 2), 0)
    bump -= away * slope[..., None]

    # —— 铆钉：沿分割线两侧（小圆顶，压暗一圈）——
    rv = np.array(rivets_along(meta["seams"]), np.float32)
    if len(rv):
        dr, awr = segment_field(F, [(c, c) for c in rv], 0.006)
        dr = dr.reshape(shape)
        awr = awr.reshape(shape + (3,))
        dome = np.clip(1 - (dr / 0.0035) ** 2, 0, 1)
        ringk = np.exp(-((dr - 0.0035) / 0.0008) ** 2)
        r -= 0.05 * ringk - 0.02 * dome
        bump += awr * np.where(dr < 0.0035, 0.6 * dr / 0.0035, 0)[..., None]

    # —— 棱边磨损：几何母版的硬边附近，极淡地提亮一点（噪声控制成断续的磨痕），粗糙度略降 ——
    hard = []
    for name, data in meta.get("edges", {}).items():
        if name != "nose.body":
            continue
        a = np.array(data, np.float32).reshape(-1, 12)
        for e in a:
            n1, n2 = e[6:9], e[9:12]
            if float(n1 @ n2) < 0.85:  # 只要真折边
                hard.append((e[0:3], e[3:6]))
    if hard:
        de, _ = segment_field(F, hard, 0.03)
        de = de.reshape(shape)
        noise = value_noise(P, 0.025, 3)
        wear = np.clip((noise - 0.55) / 0.2, 0, 1) * np.exp(-(de / 0.012) ** 2)
        r += 0.03 * wear
        rough -= 0.12 * wear

    # —— 涂装：机号、名字、警示三角（上外切面，左右各一）——
    upper_outer = valid & (fac == 1) & (nz > 0.05)
    v_up = np.hypot(np.abs(y) - R["R1"][0], z - R["R1"][1])
    for side, flip in ((1, False), (-1, True)):
        sel = upper_outer & (np.sign(y) == side)
        g = decal(g, sel, s, v_up, text_mask("02", 140), 4.12, 0.1, 0.25, flip)
        g = decal(g, sel, s, v_up, text_mask("燭龍 ZHULONG", 80), 5.45, 0.06, 0.6, flip)
        tri = np.zeros((64, 72), np.float32)
        yy, xx = np.mgrid[0:64, 0:72]
        inside = (yy > 6) & (yy < 58) & (np.abs(xx - 36) < (yy - 6) * 0.62)
        inner = (yy > 18) & (yy < 50) & (np.abs(xx - 36) < (yy - 18) * 0.62 - 4)
        tri[inside & ~inner] = 1
        g = decal(g, sel, s, v_up, tri, 1.2, 0.09, 0.08, flip)
    g *= 0.85
    rough = np.where(g > 0.3, rough - 0.08, rough)

    skin = np.stack([np.clip(r, 0, 1), g, b], -1)
    nn = n + bump
    nn /= np.maximum(np.linalg.norm(nn, axis=-1, keepdims=True), 1e-6)
    pbr = np.concatenate([nn * 0.5 + 0.5, np.clip(rough, 0.05, 1)[..., None]], -1)
    return skin, pbr, valid


def dilate(img, valid, n, fill):
    """未覆盖的纹素取邻居均值，往外扩 n 圈（防止 mip 与双线性采样在接缝处漏进底色）；再外面填 fill。"""
    out = img.copy()
    mask = valid.copy()
    for _ in range(n):
        acc = np.zeros_like(out)
        cnt = np.zeros(mask.shape, np.float32)
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            m = np.roll(mask, (dy, dx), (0, 1))
            acc += np.roll(out, (dy, dx), (0, 1)) * m[..., None]
            cnt += m
        grow = ~mask & (cnt > 0)
        out[grow] = acc[grow] / cnt[grow][:, None]
        mask = mask | grow
    out[~mask] = fill
    return out
