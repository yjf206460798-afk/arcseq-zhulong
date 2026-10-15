"""起稿身体的材质与明暗（不用 Tripo 的贴图，换成我们的配色）。

X1 试过把 X0 分色图按标定投到网格上逐面定材质（织带 / 气囊 / 面料），边界跟着分色图走，糊、碎，比起稿浮雕的边差
一两厘米，渲染出来是一块块污斑——不用。现在的做法：
- 材质按件整件定：躯干与四肢 = 服装面料（suit）、手 = 手套、靴 = 靴、脸 = 皮肤；扣件、护膝、靴底、脐带、脊线是另建的干净件。
- 起伏读出来靠一层连续的顶点明暗（颜色属性 `ao`，导出为 COLOR_0，网页与 Cycles 都乘进底色）：比局部平滑面高的地方
  （织带、扣具、分块面板）亮一点，低的地方（缝、褶）暗一点——没有硬边界，不会碎；和设定图那种近单色的石墨服一致。
  正式烘焙的 AO 以后乘进同一个属性。
"""
import numpy as np

import geo

WHOLE = {"hand": "glove", "boot": "boot", "face": "skin"}


def protrusion(V, F, iters):
    E = set()
    for f in F:
        for a, b in zip(f, f[1:] + f[:1]):
            E.add((min(a, b), max(a, b)))
    E = np.array(sorted(E))
    cnt = np.zeros(len(V))
    np.add.at(cnt, E[:, 0], 1)
    np.add.at(cnt, E[:, 1], 1)
    cnt = np.maximum(cnt, 1)[:, None]
    Q = V.copy()
    out = {}
    for k in range(1, max(iters) + 1):
        acc = np.zeros_like(Q)
        np.add.at(acc, E[:, 0], Q[E[:, 1]])
        np.add.at(acc, E[:, 1], Q[E[:, 0]])
        Q = Q + 0.5 * (acc / cnt - Q)
        if k in iters:
            from body import normals
            N = normals(Q, F)
            out[k] = ((V - Q) * N).sum(1)
    return out


def shade(o, fine=30, coarse=160, gain=(18.0, 9.0), floor=0.55):
    """顶点明暗：0.84 + 细尺度起伏 × gain0 + 粗尺度起伏 × gain1，夹在 [floor, 1]。"""
    me = o.data
    V = np.array([tuple(v.co) for v in me.vertices])
    F = [list(p.vertices) for p in me.polygons]
    d = protrusion(V, F, (fine, coarse))
    v = np.clip(0.84 + gain[0] * d[fine] + gain[1] * d[coarse], floor, 1.0)
    at = me.color_attributes.get("ao") or me.color_attributes.new("ao", "FLOAT_COLOR", "POINT")
    at.data.foreach_set("color", np.stack([v, v, v, np.ones_like(v)], 1).ravel())
    me.color_attributes.active_color = at
    return v


def paint(parts):
    """parts：{部位名: 对象}。返回 {材质: 件数}。"""
    stats = {}
    for k, o in parts.items():
        mat = WHOLE.get(k.split(".")[0], "suit")
        o.data.materials.clear()
        o.data.materials.append(geo.material(mat))
        stats[mat] = stats.get(mat, 0) + 1
        if mat in ("suit", "glove", "boot"):
            shade(o)
    return stats


def ensure_ao(objs):
    """没算过明暗的件（干净的重做件、头盔小件）写 ao = 1：所有件都带 COLOR_0，材质节点统一乘 ao。"""
    for o in objs:
        me = o.data
        if me.color_attributes.get("ao") is None:
            at = me.color_attributes.new("ao", "FLOAT_COLOR", "POINT")
            at.data.foreach_set("color", np.ones(len(me.vertices) * 4))
            me.color_attributes.active_color = at
