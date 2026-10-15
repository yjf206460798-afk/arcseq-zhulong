"""銜燭 分层与区域表（X0 拆图的结论，X1 建模直接读这里；改设定先改这里）。

坐标（与烛龙引擎一致）：米；人站立、面朝 +x；+y 是着装者的左手边；z 离地。
- 站姿高度 z：按 X1 设定图米制标定（refs/concept/X1_衔烛设定图_分色.calib.json「metric」，盔顶 → 鞋底 = 1.80 m）量得。
- 方位角 az（度）：躯干绕竖直轴，0 = 正前，+90 = 着装者左侧，180 = 正后；
  四肢绕肢体轴，0 = 前，+90 = 外侧（左腿 / 左臂的外侧是 +y），−90 = 内侧，180 = 后；右侧件按左侧镜像。

量取依据：x0_split.py 从分色图自动提取的连通块（regions.json）；views 一栏是各视图里的匹配框（米，视图坐标：
正视 x 为观者右 = 着装者左；背视 x 为观者右 = 着装者右；侧视人像朝左（看到左侧），x 为观者右 = 身后）。
"""

# —— 五层（DESIGN 9.1.1 由内到外）+ 软态可见的外层连体服 ——
LAYERS = [
    ("L1", "液冷管网内衣", "贴身内衣上的管网；只取走向，设定图画出的肌肉不采信（calib color_errors）"),
    ("L2", "抗荷气囊层", "腿腹分块气囊：腹部左右两块、大腿外侧包裹、小腿外后侧；软态在外层上显出鼓起的分块"),
    ("L3", "约束层（外层连体服 + 挽具）", "软态看到的就是这一层：连体服壳、领口、拉链、接缝、护膝、手套、靴、挽具、脐带接口、暗朱红脊线、胸前「銜燭」"),
    ("L4", "鳞甲外层", "披甲态（X2）才出现：肩、上臂、前臂、脊背 + 大腿外侧、小腿前侧成片甲板；躯干正面中线与关节内侧保持软态"),
    ("L5", "双层面罩头盔", "盔壳（盔顶前凸眉骨）、窄透明面罩、暗琥珀遮光面罩、颈环；X1 按硬表面重做"),
]

# —— 区域表：id、层、名称、类别（分色 C 表）、部位、站姿 z 范围、方位范围、做法、采信、把握度、各视图匹配框 ——
# views: {人像: (类别, x0, x1, z0, z1)}，x0_split.py 用它把自动连通块认成零件（块中心落在框内即匹配）
PARTS = [
    # L3 外层
    dict(id="suit.shell", layer="L3", name="连体服壳", cls="fabric", seg="全身", z=(0.25, 1.50), az=None,
         how="独立低模（mhclo 式绑定）；头、手、脚不覆盖", adopt="采信", conf="高", views={}),
    dict(id="suit.collar", layer="L3", name="立领 / 颈封", cls="fabric", seg="颈", z=(1.46, 1.53), az=None,
         how="立领一圈，上沿接头盔颈环；分色图涂成绿色是错的（calib color_errors ①）", adopt="改判", conf="高",
         views={"soft.side": ("brown", -0.05, 0.16, 1.44, 1.54), "armored.front": ("brown", -0.05, 0.05, 1.44, 1.53)}),
    dict(id="suit.glove", layer="L3", name="手套", cls="brown", seg="手", z=(0.78, 1.0), az=None,
         how="手形外扩 2 mm；腕口 4 cm 翻边压在袖口外", adopt="改判（分色涂成棕 = 手套件）", conf="高",
         views={"soft.front": ("brown", 0.2, 0.35, 0.75, 1.0), "soft.back": ("brown", 0.2, 0.35, 0.75, 1.0), "soft.side": ("brown", -0.12, 0.02, 0.75, 1.0)}),
    dict(id="suit.boot", layer="L3", name="靴", cls="brown", seg="脚", z=(0.0, 0.25), az=None,
         how="鞋底 3 cm + 靴筒到小腿中段（z 0.25）；前掌、脚背、后跟分块", adopt="采信", conf="高",
         views={"soft.front": ("brown", 0.08, 0.32, 0.0, 0.3), "soft.back": ("brown", 0.08, 0.32, 0.0, 0.3), "soft.side": ("brown", -0.25, 0.2, 0.0, 0.3)}),
    dict(id="suit.kneepad", layer="L3", name="护膝", cls="brown", seg="膝", z=(0.495, 0.62), az=(-28, 28),
         how="外层贴片，高出服装 1.5～2 cm；宽 0.09、高 0.125；外侧一点朱红（设定图护膝外侧有红点）", adopt="改判（分色涂成棕 = 护膝件）", conf="高",
         views={"soft.front": ("brown", 0.05, 0.22, 0.45, 0.65), "soft.side": ("brown", -0.12, 0.0, 0.45, 0.65)}),
    dict(id="suit.zipper", layer="L3", name="前中拉链", cls="fabric", seg="躯干前中", z=(0.84, 1.50), az=(0, 0),
         how="接缝边环 + 拉链条（宽 1.2 cm、高出 1.5 mm）", adopt="采信", conf="高", views={}),
    dict(id="suit.spine", layer="L3", name="脊背暗朱红细线", cls="spine", seg="躯干后中", z=(1.15, 1.55), az=(180, 180),
         how="宽 8 mm 的嵌条，软态未点亮（暗朱红）；下端没入腰后三角扣板", adopt="采信（软态改为未点亮，DESIGN 9.1.1 ③）", conf="高",
         views={"soft.back": ("spine", -0.03, 0.03, 1.1, 1.6), "armored.side": ("spine", 0.05, 0.2, 1.1, 1.6)}),
    dict(id="suit.umbilical", layer="L3", name="脐带接口 + 软管", cls="brown", seg="左胸侧", z=(1.07, 1.30), az=(55, 75),
         how="左胸侧接口盒（氧 / 冷 / 电 / 数四芯）+ 盘绕软管垂到腰带左侧挂扣", adopt="采信", conf="中",
         views={"soft.front": ("brown", 0.05, 0.2, 1.05, 1.25), "armored.front": ("brown", 0.05, 0.2, 1.05, 1.25)}),
    dict(id="suit.inscription", layer="L3", name="胸前「銜燭」", cls="—", seg="左胸", z=(1.385, 1.415), az=(12, 26),
         how="繁体两字横排，字高 2.4 cm，左胸（拉链左侧 6 cm）", adopt="采信", conf="高", views={}),
    # L3 挽具
    dict(id="harness.shoulder", layer="L3", name="肩带（前段）", cls="harness", seg="躯干前", z=(1.12, 1.50), az=(28, 40),
         how="宽 4.5 cm 扁织带：肩顶 → 胸前竖直 → 腰带；两只调节扣（z 1.47、1.30）", adopt="采信", conf="高",
         views={"soft.front": ("harness", 0.09, 0.17, 1.42, 1.52), "armored.front": ("harness", 0.09, 0.17, 1.42, 1.52)}),
    dict(id="harness.back", layer="L3", name="肩带（背段）", cls="harness", seg="躯干后", z=(1.12, 1.50), az=(145, 175),
         how="肩顶 → 竖直到 z 1.24 → 斜收进腰后三角扣板；两只调节扣（z 1.48、1.20）", adopt="采信", conf="高",
         views={"soft.back": ("harness", 0.07, 0.17, 1.15, 1.52)}),
    dict(id="harness.belt", layer="L3", name="腰带 + 前扣 + 后三角扣板", cls="harness", seg="腰", z=(1.095, 1.145), az=None,
         how="宽 5 cm 一圈；前中扣 8 × 5 cm；后中三角扣板（肩带、脊线在此汇合）", adopt="采信", conf="高", views={}),
    dict(id="harness.leg", layer="L3", name="腿带", cls="harness", seg="大腿根", z=(0.78, 1.10), az=None,
         how="腰带前侧 → 斜向内下到大腿内侧（扣 z 0.92）→ 绕过臀下（扣 z 0.80）→ 斜向外上回到胯侧腰带", adopt="采信", conf="高",
         views={"soft.front": ("harness", 0.05, 0.16, 0.88, 1.06), "soft.back": ("harness", 0.0, 0.2, 0.76, 0.97), "armored.front": ("harness", 0.05, 0.16, 0.86, 1.06)}),
    # L2 气囊（软态在外层显出分块）
    dict(id="bladder.abdomen", layer="L2", name="腹部气囊（左右两块）", cls="bladder", seg="躯干前", z=(1.13, 1.31), az=(6, 34),
         how="外层下的气囊在面上显出分块：高出 1.1 cm、四周收边；中间让出拉链；腰带以上、肋下（正视 z 1.15～1.31）", adopt="采信（分色图腹部绿块）", conf="中",
         views={"soft.front": ("bladder", -0.1, 0.1, 1.12, 1.35), "soft.side": ("bladder", -0.06, 0.1, 0.97, 1.22)}),
    dict(id="bladder.thigh", layer="L2", name="大腿气囊（外侧包裹）", cls="bladder", seg="大腿", z=(0.62, 0.92), az=(12, 172),
         how="从前外侧包到后外侧（正视 x 0.13～0.21、背视 0.11～0.21）", adopt="采信", conf="高",
         views={"soft.front": ("bladder", 0.11, 0.23, 0.6, 0.95), "soft.back": ("bladder", 0.09, 0.23, 0.58, 0.92)}),
    dict(id="bladder.calf", layer="L2", name="小腿气囊（后侧）", cls="bladder", seg="小腿", z=(0.30, 0.52), az=(115, 178),
         how="侧视在小腿后、正视看不到 → 放在后侧偏外（az 115～178）", adopt="采信（位置取侧视）", conf="中",
         views={"soft.side": ("bladder", 0.0, 0.15, 0.27, 0.56)}),
    dict(id="panel.back", layer="L3", name="背阔两侧面板", cls="bladder", seg="躯干后", z=(1.20, 1.43), az=(125, 160),
         how="分色图涂成绿（气囊），DESIGN 只要腿腹气囊 → 只做面板接缝，不鼓起", adopt="改判", conf="中",
         views={"soft.back": ("bladder", 0.07, 0.18, 1.18, 1.45)}),
    dict(id="panel.hip", layer="L3", name="腰后两侧绿块", cls="bladder", seg="臀侧", z=(0.89, 1.08), az=(110, 150),
         how="不采信：腰带下、腿带上的一小块，按面料", adopt="不采信", conf="中",
         views={"soft.back": ("bladder", 0.09, 0.18, 0.88, 1.09)}),
    dict(id="panel.groin", layer="L3", name="胯前 V 区绿块", cls="bladder", seg="躯干前下", z=(0.79, 1.09), az=None,
         how="不采信：腿带之间的胯前，按面料（腹部气囊下沿止于 z 0.98）", adopt="不采信", conf="中",
         views={"soft.front": ("bladder", -0.12, 0.1, 0.78, 1.09)}),
    # L5 头盔（X1 重做）
    dict(id="helmet.shell", layer="L5", name="盔壳", cls="helmet", seg="头", z=(1.53, 1.80), az=None,
         how="硬表面切面壳，宽 0.25、深 0.24；盔顶前凸眉骨；石墨色（不用灰壳）", adopt="改（DESIGN 9.1.1 ①）", conf="高",
         views={"soft.front": ("helmet", -0.15, 0.15, 1.5, 1.82), "soft.side": ("helmet", -0.15, 0.15, 1.5, 1.82), "soft.back": ("helmet", -0.15, 0.15, 1.5, 1.82)}),
    dict(id="helmet.visor", layer="L5", name="透明面罩（睁眼，上掀）", cls="visor_clear", seg="头", z=(1.70, 1.78), az=(-40, 40),
         how="窄面罩，睁眼态上掀收在眉骨下；闭眼时落下", adopt="改（收窄）", conf="中",
         views={"soft.front": ("visor_clear", -0.12, 0.12, 1.68, 1.8), "soft.side": ("visor_clear", -0.2, 0.0, 1.68, 1.8)}),
    dict(id="helmet.sunvisor", layer="L5", name="遮光面罩", cls="visor_gold", seg="头", z=(1.56, 1.69), az=(-40, 40),
         how="暗琥珀金（不是镜面金），比设定图窄；闭眼落下", adopt="改（DESIGN 9.1.1 ①）", conf="中",
         views={"armored.front": ("visor_gold", -0.12, 0.12, 1.54, 1.72), "armored.side": ("visor_gold", -0.2, 0.0, 1.54, 1.72)}),
    # L4 鳞甲（X2 用，这里先记范围）
    dict(id="scale.shoulder", layer="L4", name="肩 / 上臂鳞片", cls="scale", seg="上臂", z=(1.20, 1.50), az=(-30, 210),
         how="前后错叠小鳞片，尖端朝下", adopt="采信", conf="高",
         views={"armored.front": ("scale", 0.12, 0.3, 1.18, 1.52), "armored.side": ("scale", -0.08, 0.16, 1.18, 1.52)}),
    dict(id="scale.forearm", layer="L4", name="前臂鳞片", cls="scale", seg="前臂", z=(0.94, 1.19), az=(0, 200),
         how="前臂外侧到背侧", adopt="采信", conf="高", views={"armored.front": ("scale", 0.19, 0.35, 0.92, 1.2)}),
    dict(id="scale.spine", layer="L4", name="脊背鳞片", cls="scale", seg="躯干后", z=(1.10, 1.50), az=(150, 210),
         how="沿脊线两侧，脊线留出", adopt="采信", conf="中", views={}),
    dict(id="scale.thigh", layer="L4", name="大腿外侧甲板", cls="scale", seg="大腿", z=(0.66, 1.0), az=(40, 140),
         how="成片甲板", adopt="采信", conf="高", views={"armored.front": ("scale", 0.12, 0.24, 0.64, 1.0)}),
    dict(id="scale.shin", layer="L4", name="小腿前侧甲板", cls="scale", seg="小腿", z=(0.25, 0.52), az=(-30, 60),
         how="成片甲板", adopt="采信", conf="高", views={"armored.front": ("scale", 0.19, 0.26, 0.24, 0.52)}),
    dict(id="scale.chest", layer="L4", name="胸前鳞块", cls="scale", seg="躯干前", z=(1.23, 1.52), az=None,
         how="不采信：躯干正面中线保持软态（DESIGN 9.1.1 ②）", adopt="不采信", conf="高",
         views={"armored.front": ("scale", -0.11, 0.12, 1.22, 1.53)}),
]

# —— 接缝线走向（软态外层；X1 在服装低模里做成边环）——
# kind：plane = 平面与服装面的交线（直、不锯齿）；ring = 绕肢体一圈；line = 沿方位的纵缝
SEAMS = [
    dict(id="seam.zipper", how="前中 y = 0 平面，z 0.84～1.50（拉链）", kind="plane"),
    dict(id="seam.collar", how="领口一圈 z 1.47，立领上沿 z 1.53", kind="ring"),
    dict(id="seam.yoke.front", how="胸前育克：腋前 z 1.36 → 拉链 z 1.33，左右各一", kind="plane"),
    dict(id="seam.yoke.back", how="背育克：腋后 z 1.42 水平一道", kind="plane"),
    dict(id="seam.armhole", how="袖窿：过肩关节、垂直于上臂轴的斜平面（装袖），只取离手臂轴 7.5 cm 内的一段", kind="ring"),
    dict(id="seam.side", how="躯干侧缝 az ±95°，腋下 → 胯侧", kind="line"),
    dict(id="seam.waist", how="腰线 z 1.10（被腰带压住）", kind="plane"),
    dict(id="seam.elbow", how="肘部活动片：肘上 3 cm、肘下 4 cm 两圈", kind="ring"),
    dict(id="seam.cuff", how="袖口 = 手套腕口（手套压在外）", kind="ring"),
    dict(id="seam.inseam", how="腿内侧纵缝 az −90°，胯 → 靴口", kind="line"),
    dict(id="seam.knee", how="膝部活动片：膝上 z 0.64、膝下 z 0.46 两圈（护膝压在中间）", kind="ring"),
    dict(id="seam.shin", how="小腿前侧纵缝 az ±25°，膝下 → 靴口（正视两条）", kind="line"),
    dict(id="seam.boot", how="靴口 z 0.25", kind="ring"),
]

# —— 鳞片区（X2；这里定范围，鳞片尖朝下、前后错叠）——
SCALE_ZONES = ["scale.shoulder", "scale.forearm", "scale.spine", "scale.thigh", "scale.shin"]

# —— 站姿地标（X1 设定图量得，米；身体底模按此对比比例）——
LANDMARKS = {"crotch": 0.82, "belt": 1.12, "kneepad": 0.56, "boot_top": 0.25, "glove": 0.90, "hand_x": 0.28,
             "helmet_bottom": 1.53, "shoulder_width": 0.52, "helmet_width": 0.257, "helmet_depth": 0.24}
