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
    "umbilical": (0.52, 0.38, 0.24), "hose": (0.52, 0.38, 0.24), "cable": (0.52, 0.38, 0.24), "skin": (1.0, 1.0, 1.0), "cap": (0.75, 0.75, 0.75),
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
    "helmet": ((0.12, 0.13, 0.14), 0.4, 0.0),
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
    "cable": ((0.035, 0.038, 0.04), 0.5, 0.0),  # 坐姿版重接的软管（没有烘焙 UV，不挂法线贴图）
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
        normal_map(m, b)
        if m.name in ("suit", "collar", "bladder", "strap", "cap"):
            b.inputs["Sheen Weight"].default_value = 0.35
            b.inputs["Sheen Roughness"].default_value = 0.6
        if m.name not in ("glass", "sunvisor", "inscription", "skin", "eye"):
            # 顶点明暗（颜色属性 ao，paint.py；没算过的件 paint.ensure_ao 写 1）乘进底色
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
        if m.name in ("glass", "sunvisor"):
            # 面罩是没有厚度的单层面：不用折射（单层面按实心玻璃折射会把脸扭歪），用“透明 + 镀膜反射”混合。
            # 透明面罩几乎全透、只留菲涅尔反射；遮光面罩是暗琥珀镀膜，大半挡住、透一点暗琥珀。
            tr = nt.nodes.new("ShaderNodeBsdfTransparent")
            tr.inputs[0].default_value = (1, 1, 1, 1) if m.name == "glass" else (0.55, 0.3, 0.06, 1)
            lw = nt.nodes.new("ShaderNodeLayerWeight")
            lw.inputs["Blend"].default_value = 0.08 if m.name == "glass" else 0.6
            mx = nt.nodes.new("ShaderNodeMixShader")
            if m.name == "glass":
                b.inputs["Base Color"].default_value = (0.02, 0.022, 0.025, 1)
                b.inputs["Roughness"].default_value = 0.04
                nt.links.new(lw.outputs["Fresnel"], mx.inputs[0])
            else:
                mv = nt.nodes.new("ShaderNodeMath")
                mv.operation = "MAXIMUM"
                mv.inputs[1].default_value = 0.82
                nt.links.new(lw.outputs["Fresnel"], mv.inputs[0])
                nt.links.new(mv.outputs[0], mx.inputs[0])
                b.inputs["Coat Weight"].default_value = 0.6
                b.inputs["Coat Roughness"].default_value = 0.05
            nt.links.new(tr.outputs[0], mx.inputs[1])
            nt.links.new(b.outputs[0], mx.inputs[2])
            nt.links.new(mx.outputs[0], out.inputs[0])
        if m.name == "skin":
            b.inputs["Subsurface Weight"].default_value = 0.15
            b.inputs["Subsurface Radius"].default_value = (0.01, 0.005, 0.003)
        if m.name == "eye":
            b.inputs["Coat Weight"].default_value = 1.0


# 法线贴图图集（lod.py 烘的）：材质 → 图集名
NORMAL_ATLAS = {"suit": "body", "glove": "body", "boot": "body", "skin": "body", "hose": "body",
                "helmet": "hard", "chrome": "hard", "umbilical": "hard"}


def normal_map(m, b):
    """材质用的法线贴图（有就接上：图像 → 法线贴图节点（切线空间）→ BSDF 法线）。"""
    k = NORMAL_ATLAS.get(m.name)
    img = bpy.data.images.get(f"xianzhu-{k}-nrm") if k else None
    if img is None:
        return
    nt = m.node_tree
    tx = nt.nodes.new("ShaderNodeTexImage")
    tx.image = img
    tx.image.colorspace_settings.name = "Non-Color"
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nm.space = "TANGENT"
    nt.links.new(tx.outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], b.inputs["Normal"])


def export_materials():
    """glTF 导出用的材质：只留 Principled（底色 = 配色卡、粗糙度、金属度）+ 法线贴图；铭文带透明贴图；面罩带透明度。
    顶点明暗 ao 走 COLOR_0，网页着色器自己乘（导出器认不出 Cycles 里的乘法节点）。"""
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
        normal_map(m, b)
        if m.name == "inscription":
            img = bpy.data.images.get("xz.inscription")
            if img:
                tx = nt.nodes.new("ShaderNodeTexImage")
                tx.image = img
                nt.links.new(tx.outputs["Color"], b.inputs["Base Color"])
                nt.links.new(tx.outputs["Alpha"], b.inputs["Alpha"])
        if m.name in ("glass", "sunvisor"):
            b.inputs["Alpha"].default_value = 0.12 if m.name == "glass" else 0.85
