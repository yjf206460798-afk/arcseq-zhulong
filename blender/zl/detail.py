"""机身蒙皮细节贴图（numpy，程序生成，可重跑）：输入每个纹素的世界坐标 P、法线 N、贴图 AO，输出 RGB（r 刻线压暗、g 涂装、b AO）。

细节疏密（CLAUDE.md）：集中在机头光窗、座舱与眉骨、化剑转轴处；大面积蒙皮保持安静。所以：
  · 铆钉行只沿已有的口盖 / 接缝线（几何母版的 seams），不在空白蒙皮上撒；
  · 鳞片缝只在机腹与下切面（棱线以下），菱形错排、与几何样片同一套行距列宽；几何样片覆盖的地方不画（避免双线）；
  · 涂装只有三处：上外切面的机号「02」、座舱下方一行小字「烛龍 ZHULONG」、机头姿态推进器旁的警示三角。
"""
import math
import os

import numpy as np

from .nose import FORE_APEX, NEEDLE, REAR, S_END
from .util import XN

FONT = "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"


def ring_np(s):
    """nose.ring 的向量版：返回 {R0…R3: (y, z)}，每项是与 s 同形的数组。"""
    sa, za = FORE_APEX
    s = np.clip(s, 0.16, S_END)
    kf = (s - sa) / (S_END - sa)
    s0, z0 = NEEDLE[1]
    kn_base = (NEEDLE[0] - sa) / (S_END - sa)
    kn = (s - s0) / (NEEDLE[0] - s0)
    out = {}
    for key, (y, z) in REAR.items():
        yf, zf = y * kf, za + (z - za) * kf
        yb, zb = y * kn_base, za + (z - za) * kn_base
        yn, zn = yb * kn, z0 + (zb - z0) * kn
        needle = s < NEEDLE[0]
        out[key] = (np.where(needle, yn, yf), np.where(needle, zn, zf))
    return out


def stamp_dots(r, valid, P, centres, radius, depth):
    """在 r 上按 3D 点盖圆点（铆钉）：纹素按 x 排序后只查邻近一段。"""
    flat = np.where(valid.ravel())[0]
    xs = P[..., 0].ravel()[flat]
    order = np.argsort(xs)
    xs_sorted = xs[order]
    idx_sorted = flat[order]
    pts = P[..., :3].reshape(-1, 3)
    rr = r.ravel()
    for c in centres:
        lo = np.searchsorted(xs_sorted, c[0] - radius * 1.6)
        hi = np.searchsorted(xs_sorted, c[0] + radius * 1.6)
        if hi <= lo:
            continue
        ids = idx_sorted[lo:hi]
        d = np.sqrt(((pts[ids] - c) ** 2).sum(1)) / radius
        k = np.clip(1.6 - d, 0, 1) ** 1.5  # 实心圆 + 1 圈柔边
        rr[ids] = np.minimum(rr[ids], 1 - depth * k)
    return rr.reshape(r.shape)


def rivets_along(seams, pitch=0.035, offset=0.018):
    """沿每条（次级）接缝两侧各一行铆钉：偏离接缝 offset，间距 pitch。"""
    out = []
    for sm in seams:
        if sm.get("level") not in (None, "secondary"):
            continue
        pts = [np.array(p) for p in sm["points"]]
        nrm = [np.array(n) for n in sm["normals"]]
        loop = pts + ([pts[0]] if sm.get("closed") else [])
        nl = nrm + ([nrm[0]] if sm.get("closed") else [])
        for a, b, na in zip(loop, loop[1:], nl):
            L = np.linalg.norm(b - a)
            if L < 1e-6:
                continue
            d = (b - a) / L
            side = np.cross(na, d)
            side /= np.linalg.norm(side) or 1
            for k in range(1, int(L / pitch)):
                p = a + d * k * pitch
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


def paint(P, N, A, meta):
    # 浮点图的 alpha 不可靠（未烘到的纹素也是 1）：用烘出来的法线长度判断（表面上是单位向量，底色是 0）
    valid = np.linalg.norm(N[..., :3], axis=-1) > 0.5
    x, y, z = P[..., 0], P[..., 1], P[..., 2]
    s = XN - x
    nz = N[..., 2]
    R = ring_np(s)
    r = np.ones(valid.shape, np.float32)
    g = np.zeros(valid.shape, np.float32)
    b = np.where(valid, A[..., 0], 1.0).astype(np.float32)

    # —— 下切面与机腹：鳞片缝（棱线以下）——
    below = valid & (z < R["R2"][1] - 0.004) & (s > 0.5) & (s < S_END - 0.01)
    belly = below & (nz < -0.97)
    lower = below & ~belly
    # 切面坐标：下切面 v = 到棱线的截面内距离；机腹 v = 到腹缘的距离 + 下切面全宽（两块连续排）
    slant = np.hypot(R["R2"][0] - R["R3"][0], R["R2"][1] - R["R3"][1])
    v_lower = np.hypot(np.abs(y) - R["R2"][0], z - R["R2"][1])
    v_belly = slant + (R["R3"][0] - np.abs(y))
    v = np.where(belly, v_belly, v_lower)
    p, w = 0.085, 0.15
    best = np.full(valid.shape, 9.0, np.float32)
    front = np.zeros(valid.shape, np.float32)
    i0 = np.round((s - 3.3) / p)
    for di in (-1, 0, 1):
        i = i0 + di
        sc = 3.3 + i * p
        off = np.where(np.mod(i, 2) == 1, w / 2, 0.0) + 0.10
        j = np.round((v - off) / w)
        for dj in (-1, 0, 1):
            vc = off + (j + dj) * w
            d = np.abs(s - sc) / p + np.abs(v - vc) / (w / 2)
            better = d < best
            front = np.where(better, (sc - s) / p, front)
            best = np.minimum(best, d)
    # 缝：菱形边上一条约 5 mm 的暗线（d 接近 1）；片内由前到后略亮（后缘翘起迎光）
    edge = np.clip((best - 0.93) / 0.07, 0, 1)
    tiles = lower | belly
    patch = lower & (s > 3.25) & (s < 5.35) & (v_lower > 0.06) & (v_lower < slant * 0.9 + 0.05)
    scale_r = 1 - 0.5 * edge - 0.06 * np.clip(front, 0, 1)
    r = np.where(tiles & ~patch, np.minimum(r, scale_r), r)

    # —— 铆钉：只沿口盖 / 接缝线 ——
    centres = rivets_along(meta["seams"])
    r = stamp_dots(r, valid, P, centres, radius=0.0035, depth=0.35)

    # —— 涂装：机号、名字、警示三角（上外切面，左右各一）——
    upper_outer = valid & (z > R["R1"][1] - 0.5) & (z <= R["R1"][1] + 0.002) & (z >= R["R2"][1] - 0.002) & (nz > 0.2) & (nz < 0.9)
    # 上外切面坐标：u = s，v = 到肩线的截面内距离
    v_up = np.hypot(np.abs(y) - R["R1"][0], z - R["R1"][1])
    for side, flip in ((1, False), (-1, True)):
        sel = upper_outer & (np.sign(y) == side)
        g = decal(g, sel, s, v_up, text_mask("02", 140), 4.06, 0.12, 0.27, flip)
        g = decal(g, sel, s, v_up, text_mask("烛龍 ZHULONG", 80), 5.45, 0.06, 0.62, flip)
        # 姿态推进器警示：口前一个空心三角
        tri = np.zeros((64, 72), np.float32)
        yy, xx = np.mgrid[0:64, 0:72]
        inside = (yy > 6) & (yy < 58) & (np.abs(xx - 36) < (yy - 6) * 0.62)
        inner = (yy > 18) & (yy < 50) & (np.abs(xx - 36) < (yy - 18) * 0.62 - 4)
        tri[inside & ~inner] = 1
        g = decal(g, sel, s, v_up, tri, 1.32, 0.10, 0.09, flip)
    g *= 0.85
    rgb = np.stack([r, g, b], -1)
    return rgb, valid


def dilate(rgb, valid, n):
    """未覆盖的纹素取邻居均值，往外扩 n 圈（防止 mip 与双线性采样在接缝处漏进底色）。"""
    out = rgb.copy()
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
    out[~mask] = (1, 0, 1)
    return out
