"""材质：网页 / Cycles 用的“B 金属质感”配色卡，以及平涂审图用的分色 C 表颜色。

材质名就是网页材质名（随 glTF 导出）；颜色只在这里定一处。
"""
import bpy

# 分色 C 表（IMAGE_PROMPTS「建模用图」C 段）：平涂审图时与分色图直接比
SPLIT = {
    "suit": (0.75, 0.75, 0.75), "collar": (0.75, 0.75, 0.75), "bladder": (0.38, 0.70, 0.33), "strap": (0.96, 0.55, 0.15),
    "buckle": (0.96, 0.55, 0.15), "scale": (0.33, 0.61, 0.89), "helmet": (0.61, 0.47, 0.85), "brow": (0.61, 0.47, 0.85),
    "glass": (0.28, 0.85, 0.94), "sunvisor": (0.99, 0.82, 0.24), "vermilion": (0.93, 0.13, 0.10), "rubber": (0.52, 0.38, 0.24),
    "boot": (0.52, 0.38, 0.24), "sole": (0.52, 0.38, 0.24), "glove": (0.52, 0.38, 0.24), "kneepad": (0.52, 0.38, 0.24),
    "umbilical": (0.52, 0.38, 0.24), "hose": (0.52, 0.38, 0.24), "skin": (1.0, 1.0, 1.0), "cap": (0.75, 0.75, 0.75),
    "eye": (0.2, 0.2, 0.2), "chrome": (0.61, 0.47, 0.85), "metal": (0.96, 0.55, 0.15), "inscription": (0.75, 0.75, 0.75),
    "lens": (0.61, 0.47, 0.85),
}

# B 金属质感（烛龙配色卡的人物版）：主色哑光石墨面料、辅色更暗的橡胶件、标志色暗朱红脊线、头盔石墨壳 + 钛色眉骨 + 暗琥珀面罩
LOOK = {
    "suit": ((0.055, 0.062, 0.068), 0.78, 0.0),
    "collar": ((0.045, 0.05, 0.055), 0.8, 0.0),
    "bladder": ((0.07, 0.078, 0.085), 0.7, 0.0),
    "strap": ((0.11, 0.12, 0.125), 0.85, 0.0),
    "buckle": ((0.3, 0.32, 0.34), 0.38, 1.0),
    "metal": ((0.45, 0.48, 0.5), 0.35, 1.0),
    "chrome": ((0.75, 0.77, 0.78), 0.18, 1.0),
    "helmet": ((0.075, 0.082, 0.09), 0.42, 0.0),
    "brow": ((0.32, 0.34, 0.36), 0.3, 1.0),
    "glass": ((0.8, 0.86, 0.9), 0.03, 0.0),
    "sunvisor": ((0.32, 0.17, 0.035), 0.12, 0.6),
    "vermilion": ((0.28, 0.045, 0.025), 0.5, 0.0),
    "rubber": ((0.03, 0.033, 0.036), 0.65, 0.0),
    "boot": ((0.035, 0.038, 0.04), 0.6, 0.0),
    "sole": ((0.02, 0.021, 0.022), 0.85, 0.0),
    "glove": ((0.04, 0.043, 0.046), 0.6, 0.0),
    "kneepad": ((0.06, 0.066, 0.07), 0.45, 0.0),
    "umbilical": ((0.09, 0.095, 0.1), 0.4, 0.6),
    "hose": ((0.035, 0.038, 0.04), 0.5, 0.0),
    "skin": ((0.62, 0.47, 0.40), 0.55, 0.0),
    "cap": ((0.03, 0.032, 0.035), 0.85, 0.0),
    "eye": ((0.02, 0.02, 0.02), 0.2, 0.0),
    "inscription": ((0.45, 0.5, 0.52), 0.6, 0.0),
    "lens": ((0.02, 0.02, 0.025), 0.1, 0.0),
    "scale": ((0.09, 0.1, 0.11), 0.4, 0.8),
}


def flat_colours():
    """Workbench 平涂：材质视口色 = 分色 C 表。"""
    for m in bpy.data.materials:
        c = SPLIT.get(m.name, (0.5, 0.5, 0.5))
        m.diffuse_color = (*[x ** 2.2 for x in c], 1.0)  # 视口色是线性值；C 表按 sRGB 给


def look_colours():
    """Workbench 预览用的 B 色（Cycles 节点在 cycles_materials 里配）。"""
    for m in bpy.data.materials:
        c = LOOK.get(m.name, ((0.3, 0.3, 0.3), 0.5, 0.0))[0]
        m.diffuse_color = (*[min(1.0, x * 3.0) for x in c], 1.0)


def cycles_materials():
    """Cycles 节点：Principled BSDF；玻璃透射，遮光面罩半透的暗琥珀镀膜，面料加一点 sheen。"""
    for m in bpy.data.materials:
        spec = LOOK.get(m.name)
        if spec is None:
            continue
        col, rough, metal = spec
        m.use_nodes = True
        nt = m.node_tree
        nt.nodes.clear()
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        b = nt.nodes.new("ShaderNodeBsdfPrincipled")
        nt.links.new(b.outputs[0], out.inputs[0])
        b.inputs["Base Color"].default_value = (*col, 1.0)
        b.inputs["Roughness"].default_value = rough
        b.inputs["Metallic"].default_value = metal
        if m.name in ("suit", "collar", "bladder", "strap", "cap"):
            b.inputs["Sheen Weight"].default_value = 0.35
            b.inputs["Sheen Roughness"].default_value = 0.6
        if m.name in ("suit", "glove", "boot"):
            # 起稿件的顶点明暗（颜色属性 ao，paint.py）乘进底色
            at = nt.nodes.new("ShaderNodeAttribute")
            at.attribute_name = "ao"
            mix = nt.nodes.new("ShaderNodeMix")
            mix.data_type = "RGBA"
            mix.blend_type = "MULTIPLY"
            mix.inputs["Factor"].default_value = 1.0
            mix.inputs[6].default_value = (*col, 1.0)
            nt.links.new(at.outputs["Color"], mix.inputs[7])
            nt.links.new(mix.outputs[2], b.inputs["Base Color"])
        if m.name == "inscription":
            img = bpy.data.images.get("xz.inscription")
            if img:
                tx = nt.nodes.new("ShaderNodeTexImage")
                tx.image = img
                nt.links.new(tx.outputs["Color"], b.inputs["Base Color"])
                nt.links.new(tx.outputs["Alpha"], b.inputs["Alpha"])
        if m.name == "glass":
            b.inputs["Transmission Weight"].default_value = 1.0
            b.inputs["IOR"].default_value = 1.5
        if m.name == "sunvisor":
            b.inputs["Transmission Weight"].default_value = 0.35
            b.inputs["Coat Weight"].default_value = 0.6
            b.inputs["Coat Roughness"].default_value = 0.05
        if m.name == "skin":
            b.inputs["Subsurface Weight"].default_value = 0.15
            b.inputs["Subsurface Radius"].default_value = (0.01, 0.005, 0.003)
        if m.name == "eye":
            b.inputs["Coat Weight"].default_value = 1.0
