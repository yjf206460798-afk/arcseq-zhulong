"""MakeHuman CC0 资产：基础网格 base.obj（含 body 与 helper-tights 等辅助组）、默认骨架、默认权重。

查找顺序：`blender/assets/makehuman/`（烛龙分支已入库的同一份，合入 main 后直接用）→ `dist/cache/makehuman/`（没有就从
上游 makehuman 仓库下载，sha1 校验与烛龙分支入库的那份逐字节相同）。许可见 THIRD_PARTY_NOTICES（CC0 1.0，只用资产，不用程序代码）。

坐标：MakeHuman（x 左、y 上、z 前，分米）→ 本作（x 前、y 左、z 上，米），身高缩放到 HEIGHT，脚底 z = 0。
"""
import collections
import hashlib
import json
import os
import urllib.request

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
HEIGHT = 1.74
SOLE = 0.03  # 靴底厚：人整体抬高 3 cm，地面 z = 0 是靴底（与设定图米制标定“盔顶 → 鞋底 1.80 m”一致）
UPSTREAM = "https://raw.githubusercontent.com/makehumancommunity/makehuman/master/makehuman/data/"
FILES = {  # 文件 → (上游路径, sha1)
    "base.obj": ("3dobjs/base.obj", "5690bbb7e53f4762e329043e1462cb6b57ccd41a"),
    "default.mhskel": ("rigs/default.mhskel", "a6e41fdb4a3a3b62c1d08ce6c5c6984c38fc2e88"),
    "default_weights.mhw": ("rigs/default_weights.mhw", "dfe562ca6b181daf42328912969bf4b9556b3f7f"),
}


def asset_dir():
    shared = os.path.join(ROOT, "blender", "assets", "makehuman")
    if all(os.path.exists(os.path.join(shared, f)) for f in FILES):
        return shared
    cache = os.path.join(ROOT, "dist", "cache", "makehuman")
    os.makedirs(cache, exist_ok=True)
    for f, (path, sha) in FILES.items():
        p = os.path.join(cache, f)
        if not os.path.exists(p):
            data = urllib.request.urlopen(UPSTREAM + path, timeout=60).read()
            if hashlib.sha1(data).hexdigest() != sha:
                raise RuntimeError(f"{f}: sha1 不符（上游改了？）")
            with open(p, "wb") as fp:
                fp.write(data)
    return cache


class MH:
    """读入后的 MakeHuman：P（全部顶点，本作坐标）、groups（组名 → 面表，全局顶点号）、骨架、权重。"""

    def __init__(self):
        d = asset_dir()
        V, groups, g = [], collections.defaultdict(list), None
        with open(os.path.join(d, "base.obj")) as fp:
            for line in fp:
                if line.startswith("v "):
                    V.append([float(t) for t in line.split()[1:4]])
                elif line.startswith("g "):
                    g = line.split()[1]
                elif line.startswith("f "):
                    groups[g].append([int(t.split("/")[0]) - 1 for t in line.split()[1:]])
        V = np.array(V)
        body = np.unique(np.concatenate([np.array(f) for f in groups["body"]]))
        self.scale = HEIGHT / (V[body, 1].max() - V[body, 1].min())
        P = np.stack([V[:, 2], V[:, 0], V[:, 1]], 1) * self.scale
        P[:, 2] -= P[body, 2].min() - SOLE
        self.P = P
        self.groups = dict(groups)
        self.skel = json.load(open(os.path.join(d, "default.mhskel")))
        self.weights = json.load(open(os.path.join(d, "default_weights.mhw")))["weights"]
        self.J = {k: P[v].mean(0) for k, v in self.skel["joints"].items()}

    def head(self, bone):
        return self.J[self.skel["bones"][bone]["head"]]

    def tail(self, bone):
        return self.J[self.skel["bones"][bone]["tail"]]

    def piece(self, group):
        """组 → (顶点坐标, 面表（局部编号）, 全局顶点号)。"""
        F = self.groups[group]
        ids = np.unique(np.concatenate([np.array(f) for f in F]))
        remap = {v: k for k, v in enumerate(ids)}
        return self.P[ids].copy(), [[remap[i] for i in f] for f in F], ids
