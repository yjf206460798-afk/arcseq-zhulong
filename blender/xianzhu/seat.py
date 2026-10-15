"""坐姿接口：烛龙弹射座椅的 `seat` 表（以 `blender/zl/interior.py` 的 seat_and_pilot() / `blender/zl/pilot.py` 为准，两边改动都要同步）。

座椅局部坐标：原点 = 座椅参考点 SRP（椅面与椅背交线中点），x 向前（机头方向）、y 向左、z 向上，米。
烛龙那边 SRP = at(6.15, 0, Z_TIP + 0.25)，下面的数由它的 at() / pan() 换算到 SRP 为原点（2026-10-15 烛龙分支 R4）：
- 脚：at(5.32, ±0.14, Z_TIP + 0.2) → (+0.83, ±0.14, −0.05)
- 握把：右侧杆 at(5.98, −0.33, Z_TIP + 0.68) → (+0.17, −0.33, +0.43)；左油门 at(6.0, 0.33, Z_TIP + 0.65) → (+0.15, +0.33, +0.40)
- 腰带扣点：pan(0.12, 0.08, ±0.235) → (+0.119, ±0.235, +0.097)
"""
import math

import numpy as np

SEAT = {
    "back": math.radians(30),  # 椅背后倾
    "back_n": 0.07,  # 椅背垫厚（背贴在这张面上）
    "pan_h": 0.06,  # 坐垫高（臀贴在这张面上；坐垫前沿上翘 8°）
    "pan_tilt": math.radians(8),
    "knee": math.radians(112),  # 膝内角
    "feet": {"L": np.array([0.83, 0.14, -0.05]), "R": np.array([0.83, -0.14, -0.05])},
    "foot_dir": np.array([0.75, 0.0, 0.66]),
    "grips": {"R": np.array([0.17, -0.33, 0.43]), "L": np.array([0.15, 0.33, 0.40])},
    "hand_dir": {"R": np.array([0.92, 0.18, -0.3]), "L": np.array([0.92, -0.18, -0.25])},
    "knuckles": {"R": np.array([0.0, 0.0, -1.0]), "L": np.array([0.0, 0.0, -1.0])},
    "palm": {"R": np.array([0.0, 1.0, 0.0]), "L": np.array([0.0, -1.0, 0.0])},
    "seat_side": {"L": np.array([0.119, 0.235, 0.097]), "R": np.array([0.119, -0.235, 0.097])},
    "umbilical_port": np.array([0.239, 0.235, 0.147]),  # 座椅左侧板上的脐带插座（烛龙：int.pilot.hose 接到 seat_side L + (0.12, 0, 0.05)）
}
