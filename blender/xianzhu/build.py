"""銜燭 几何母版 · Tripo 起稿路线（作者 2026-10-15 定；原 mhclo 服装壳退为后备：build_mhclo.py）。

    .venv/bin/python blender/xianzhu/build.py                       # 建模 → 骨架 → 减面烘焙 → 导出 assets/xianzhu*.glb、xianzhu.json
    .venv/bin/python blender/xianzhu/build.py --review <目录>        # 同上，再出交审图（review_x1.py）
    .venv/bin/python blender/xianzhu/build.py --no-export --review <目录>
    源 GLB 是参数（发布版在 Tripo 付费版按同输入、同参数重新生成后换文件重跑）：
    --draft-body <glb>  --draft-helmet <glb>  --draft-connector <glb>   （默认 refs/ai_draft/ 里的测试稿）

流程（WORKFLOW「AI 起稿」第 5 步）：
1. 身体（draft.py）：缩放到盔顶 1.80、站正、服装底形左右对称（单侧件：左胸脐带接口、软管保留单侧）；胸前乱码浮雕在左胸，
   取右半镜像时一并磨掉；起稿自带的头盔丢掉。全程保住 Tripo 的自定义法线（draft.keep_normals / restore_normals）。
2. 精修（refine.py）：扣具、护膝、靴底重做成干净硬棱；左胸换 Tripo 脐带接头；脊背暗朱红线；「銜燭」贴图。
3. 明暗（paint.py）：配色卡按件定材质，起伏读出来靠顶点明暗 ao。
4. 头盔（helmet_tripo.py）：Smart Mesh 修正版；暗琥珀遮光面罩拆成可动件（形态键 down）；颈环套住领口；天线保持细杆。
5. 骨架（rig.py）：人体骨架按段贴到底稿上 → 权重 Data Transfer → 坐姿（seat.py = 烛龙 seat 表）。
6. 减面与烘焙（lod.py）：网页常驻约 6 万三角形、座舱坐姿版约 3 万；高模细节烘成法线贴图。
母版是脚本，不是文件（docs/BLENDER.md 规矩 1）；产物 .glb / .json / 渲染图都不手改。
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402

import body as B  # noqa: E402
import draft  # noqa: E402
import geo  # noqa: E402
import helmet_tripo  # noqa: E402
import lod  # noqa: E402
import paint  # noqa: E402
import refine  # noqa: E402
import rig as RG  # noqa: E402
from mh import MH  # noqa: E402

PROPS = {"figure": "xianzhu"}
ASSETS = os.path.join(ROOT, "assets")

# 起稿零件 → 导出名、Tripo 种类（lod.TARGET）
NAMES = {"torso": "xz.suit.torso", "face": "xz.body.face"}
for _s in "lr":
    NAMES.update({f"uarm.{_s}": f"xz.suit.uarm.{_s}", f"farm.{_s}": f"xz.suit.farm.{_s}", f"thigh.{_s}": f"xz.suit.thigh.{_s}",
                  f"shin.{_s}": f"xz.suit.shin.{_s}", f"hand.{_s}": f"xz.glove.{_s}", f"boot.{_s}": f"xz.boot.{_s}"})
LAYER_RULES = (("xz.hw.", "L3"), ("xz.suit.", "L3"), ("xz.kneepad.", "L3"), ("xz.glove.", "L3"), ("xz.boot.", "L3"),
               ("xz.helmet.", "L5"), ("xz.body.", "body"), ("xz.seat.", "seat"))


def arg(name, default=None):
    a = sys.argv
    return a[a.index(name) + 1] if name in a else default


def sources():
    return {"body": arg("--draft-body", draft.DRAFT_BODY), "helmet": arg("--draft-helmet", draft.DRAFT_HELMET),
            "connector": arg("--draft-connector", draft.DRAFT_CONNECTOR)}


def model(src, tex_dir):
    """建模：返回 (起稿零件 {种类名: 对象}, 后加件列表, 头盔件 {名字: 对象}, 胸前接头信息, 日志)。"""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    t0 = time.time()
    log = {}
    parts, att, log["body"] = draft.build_body(PROPS, src["body"])
    extras = []
    for _, o in refine.build_hardware(parts, PROPS) + refine.kneepads(parts, PROPS) + refine.soles(parts, PROPS):
        extras.append(o)
    draft.DRAFT_CONNECTOR = src["connector"]
    items, plug = refine.connector(att, parts, PROPS)
    extras += [o for _, o in items] + att
    extras += [o for _, o in refine.spine_line(parts, PROPS)]
    extras += [o for _, o in refine.inscription(parts, PROPS, os.path.join(tex_dir, "xianzhu-inscription.png"))]
    log["paint"] = paint.paint(parts)
    for o in att:
        paint.shade(o)
    hel, log["helmet"] = helmet_tripo.build(parts, PROPS, src["helmet"])
    paint.shade(hel["xz.helmet.shell"], floor=0.45)
    # 名字、种类、层
    for k, o in parts.items():
        o.name = o.data.name = NAMES[k]
        o["tripo"] = k.split(".")[0]
    for o in att:
        o["tripo"] = "hose"
    hel["xz.helmet.shell"]["tripo"] = "shell"
    hel["xz.helmet.neckring"]["tripo"] = "neckring"
    for o in items:
        o[1]["tripo"] = "plug"
    every = list(parts.values()) + extras + list(hel.values())
    for o in every:
        for pre, lay in LAYER_RULES:
            if o.name.startswith(pre):
                o["layer"] = lay
                break
        for k, v in PROPS.items():
            o[k] = v
    paint.ensure_ao(every)
    log["model_s"] = round(time.time() - t0, 1)
    return parts, extras, hel, plug, log


def rigging(parts, extras, hel):
    """人体骨架贴到底稿上、权重传过去。返回 (Body, 日志)。"""
    mh = MH()
    body = B.Body(mh)
    body.smooth()
    body.rigged()
    B.stand(body)
    log = {"fit_median_m": RG.fit(body, parts)}
    RG.rest_from_pose(body)
    log["bones"] = RG.weight_parts(body, parts)
    rigid = [o for o in hel.values()] + [o for o in extras if o.name == "xz.body.cap"]
    soft = [o for o in extras if o not in rigid] + [o for n, o in hel.items() if n == "xz.suit.neckseal"]
    rigid = [o for o in rigid if o not in soft]
    RG.weight_extras(parts, soft)
    for o in rigid:
        RG.transfer(None, o, rigid="head")
    RG.attach(list(parts.values()) + extras + list(hel.values()), body.rig)
    body.obj.hide_render = True
    return body, log


def meshes():
    return [o for o in bpy.data.objects if o.type == "MESH" and o.name.startswith("xz.") and o.name != "xz.body" and not o.hide_render]


def export(objs, path):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.hide_set(False)
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", use_selection=True, export_extras=True, export_apply=False, export_normals=True,
                              export_texcoords=True, export_vertex_color="ACTIVE", export_all_vertex_colors=False, export_materials="EXPORT",
                              export_image_format="AUTO", export_yup=True, export_morph=True, export_skins=False, export_animations=False)


def tris(objs):
    n = 0
    for o in objs:
        o.data.calc_loop_triangles()
        n += len(o.data.loop_triangles)
    return n


def seated(body, parts, plug, lod1=True):
    """坐姿副本（座椅局部坐标，原点 SRP）：骨架摆进座椅，各件按骨架变形后复制成新对象（名字 + .seated）；头盔、脸、通讯帽
    跟头骨刚体走（遮光面罩的形态键一起变换）。盘绕软管换成胸前接头 → 座椅左侧接头的一根软管。返回新对象列表。"""
    from mathutils import Matrix

    from seat import SEAT

    stand = meshes()
    hose = bpy.data.objects.get("xz.suit.hose")
    chest = bpy.data.objects["xz.suit.umbilical"]
    Vc = draft.verts(chest)
    i_tip = int(np.argmin(np.linalg.norm(Vc - np.array(plug["chest_tip"]), axis=1)))
    i_mid = int(np.argmin(np.linalg.norm(Vc - (np.array(plug["chest_tip"]) - np.array(plug["chest_dir"]) * 0.05), axis=1)))
    dr = RG.Draped(body, parts["torso"])
    B.sit(dr, SEAT)
    Mh = RG.head_matrix(body.rig)
    dg = bpy.context.evaluated_depsgraph_get()
    out = []
    for o in stand:
        if o is hose:
            continue
        if o.data.shape_keys:
            me = o.data.copy()
            me.transform(Mh)
            for kb in me.shape_keys.key_blocks:
                for d in kb.data:
                    d.co = Mh @ d.co
        else:
            me = bpy.data.meshes.new_from_object(o.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
        n = bpy.data.objects.new(o.name + ".seated", me)
        for k in o.keys():
            n[k] = o[k]
        bpy.context.scene.collection.objects.link(n)
        out.append(n)
    sc = next(o for o in out if o.name == "xz.suit.umbilical.seated")
    Vs = draft.verts(sc)
    tip, mid = Vector(Vs[i_tip]), Vector(Vs[i_mid])
    Ms, stip, sdir = refine.seat_plug(SEAT["umbilical_port"])
    me = chest.data.copy()
    me.transform(Ms @ draft.unflat(plug["M"]).inverted())
    sp = bpy.data.objects.new("xz.seat.umbilical.seated", me)
    for k in chest.keys():
        sp[k] = chest[k]
    sp["layer"] = "seat"
    bpy.context.scene.collection.objects.link(sp)
    h = refine.seated_hose(tip, (tip - mid).normalized(), stip, sdir, PROPS)
    h["layer"] = "L3"
    paint.ensure_ao([sp, h])
    out += [sp, h]
    for o in stand:
        o.hide_render = True
    if lod1:
        lod.lod1([o for o in out if o is not sp])
    return out, Matrix()


def meta_json(stand, seat_objs, logs, src):
    from seat import SEAT

    return {
        "figure": "xianzhu", "units": "m", "state": "soft",
        "frame": "x 前、y 左、z 上；站姿原点在两脚之间地面，坐姿原点 = 座椅参考点 SRP（blender/xianzhu/seat.py = 烛龙 seat 表）",
        "sources": {k: os.path.relpath(v, ROOT) for k, v in src.items()},
        "layers": {o.name: o.get("layer") for o in stand},
        "morph": {"xz.helmet.sunvisor": {"down": "遮光面罩落下（闭眼）；0 = 收起（睁眼）"}},
        "textures": {"normal": ["xianzhu-body-nrm（2048²）", "xianzhu-hard-nrm（1024²）"], "decal": "xianzhu-inscription"},
        "seat": {k: (v.tolist() if hasattr(v, "tolist") else ({kk: vv.tolist() for kk, vv in v.items()} if isinstance(v, dict) else v)) for k, v in SEAT.items()},
        "tris": {"stand": tris(stand), "seated": tris(seat_objs)},
        "log": logs,
    }


def main():
    src = sources()
    tex_dir = os.path.join(ROOT, "dist", "xianzhu")
    os.makedirs(tex_dir, exist_ok=True)
    out_review = arg("--review")
    logs = {}
    parts, extras, hel, plug, logs["model"] = model(src, tex_dir)
    print("model", json.dumps(logs["model"], ensure_ascii=False, default=str)[:2000])
    if out_review:
        import review_x1  # noqa: F401
    body, logs["rig"] = rigging(parts, extras, hel)
    print("rig", logs["rig"]["fit_median_m"])
    logs["lod"], _ = lod.build(meshes(), tex_dir)
    stand = meshes()
    logs["tris_stand"] = tris(stand)
    print("lod", logs["tris_stand"], "tris")
    if out_review:
        review_x1.standing(os.path.join(ROOT, out_review), stand, logs["model"]["body"]["helmet_src"])
    seat_objs, _ = seated(body, parts, plug)
    logs["tris_seated"] = tris(seat_objs)
    print("seated", logs["tris_seated"], "tris")
    if out_review:
        review_x1.seated(os.path.join(ROOT, out_review), seat_objs)
    if arg("--save"):
        bpy.ops.wm.save_as_mainfile(filepath=arg("--save"))
    if "--no-export" in sys.argv:
        return
    import look

    look.export_materials()
    for img in bpy.data.images:
        if img.name.endswith("-nrm"):
            img.file_format = "JPEG"
    os.makedirs(ASSETS, exist_ok=True)
    for o in seat_objs:
        o.hide_render = True
    for o in stand:
        o.hide_render = False
    export(stand, os.path.join(ASSETS, "xianzhu.glb"))
    # 两份 GLB 零件同名：站姿件改名让位，坐姿件用原名导出
    names = {o: o.name for o in stand}
    for o in stand:
        o.name = o.name + ".stand"
    for o in seat_objs:
        o.name = o.name.replace(".seated", "")
    export(seat_objs, os.path.join(ASSETS, "xianzhu-seated.glb"))
    for o in seat_objs:
        o.name = o.name + ".seated"
    for o, n in names.items():
        o.name = n
    with open(os.path.join(ASSETS, "xianzhu.json"), "w") as fp:
        json.dump(meta_json(stand, seat_objs, logs, src), fp, ensure_ascii=False, separators=(",", ":"), default=str)
    print(f"export · stand {logs['tris_stand']} tris · seated {logs['tris_seated']} tris · {len(stand)} objects")


if __name__ == "__main__":
    main()
