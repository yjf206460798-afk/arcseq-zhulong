"""mhclo 式绑定（RESOURCES：MakeClothes2 的做法，自己实现，不拷 GPL 代码——MakeClothes2 是 MIT，但这里只取思路）。

服装的每个顶点记在身体最近的一个三角形上：三个顶点号 + 重心坐标 + 偏移。偏移不像 mhclo 那样存世界坐标，
而是存在该三角形的局部标架（边方向 t1、法线 n、t2 = n × t1）里——身体摆姿时三角形转到哪里，偏移跟着转，
所以同一件衣服既能跟着体型走，也能跟着姿态走（站姿 ↔ 坐姿）。权重继承：衣服顶点的蒙皮权重 = 三个顶点权重按重心插值。
"""
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree


def triangles(faces):
    T = []
    for f in faces:
        for k in range(1, len(f) - 1):
            T.append((f[0], f[k], f[k + 1]))
    return np.array(T, int)


def frames(V, T):
    a, b, c = V[T[:, 0]], V[T[:, 1]], V[T[:, 2]]
    t1 = b - a
    t1 /= np.maximum(np.linalg.norm(t1, axis=1), 1e-12)[:, None]
    n = np.cross(b - a, c - a)
    n /= np.maximum(np.linalg.norm(n, axis=1), 1e-12)[:, None]
    t2 = np.cross(n, t1)
    return t1, t2, n


class Binding:
    """把点集 pts 绑在身体网格 (V, faces) 上。mask：只在这些身体三角形里找（例如手套只绑手）。"""

    def __init__(self, V, faces, pts, tri_mask=None):
        self.T = triangles(faces) if not isinstance(faces, np.ndarray) else faces
        T = self.T
        use = np.arange(len(T)) if tri_mask is None else np.nonzero(tri_mask)[0]
        tree = BVHTree.FromPolygons([Vector(v) for v in V], [tuple(t) for t in T[use]], all_triangles=True)
        idx = np.empty(len(pts), int)
        loc = np.empty((len(pts), 3))
        for k, p in enumerate(pts):
            lo, _, i, _ = tree.find_nearest(Vector(p))
            idx[k] = use[i]
            loc[k] = lo
        self.tri = idx
        a, b, c = V[T[idx, 0]], V[T[idx, 1]], V[T[idx, 2]]
        self.w = bary(loc, a, b, c)
        t1, t2, n = frames(V, T[idx])
        d = np.asarray(pts) - loc
        self.off = np.stack([(d * t1).sum(1), (d * t2).sum(1), (d * n).sum(1)], 1)

    def apply(self, V):
        T = self.T[self.tri]
        base = (V[T] * self.w[:, :, None]).sum(1)
        t1, t2, n = frames(V, T)
        o = self.off
        return base + t1 * o[:, :1] + t2 * o[:, 1:2] + n * o[:, 2:3]

    def weights(self, W):
        """W：身体每个顶点的属性（N × k）→ 按重心插值到每个绑定点。"""
        return (W[self.T[self.tri]] * self.w[:, :, None]).sum(1)


def bary(p, a, b, c):
    v0, v1, v2 = b - a, c - a, p - a
    d00 = (v0 * v0).sum(1)
    d01 = (v0 * v1).sum(1)
    d11 = (v1 * v1).sum(1)
    d20 = (v2 * v0).sum(1)
    d21 = (v2 * v1).sum(1)
    den = np.maximum(d00 * d11 - d01 * d01, 1e-18)
    v = (d11 * d20 - d01 * d21) / den
    w = (d00 * d21 - d01 * d20) / den
    return np.stack([1 - v - w, v, w], 1)
