#!/bin/sh
# Z1 复刻样板交审截图（可重跑）：sh scripts/replica-review.sh [输出目录]
# 先构建：.venv/bin/python blender/build.py && node src/figure/build.mjs && node src/figure/build.mjs --look=metal --out=dist/metal.html
set -e
cd "$(dirname "$0")/.."
export CHROME_PATH="$PWD/scripts/chrome.sh"
OUT="${1:-review/20261015-Z1-replica}"
# LOOKS="B" sh scripts/replica-review.sh：只重出 B 画法的图（A 不变时）
LOOKS="${LOOKS:-A B}"
mkdir -p "$OUT"
S="timeout -k 5 300 node src/figure/shots.mjs $OUT"
ON="__arcseq.set('power',1);__arcseq.set('chine',1);__arcseq.set('chine.sweep',1);__arcseq.set('sensor',1)"
C2=refs/concept/C2_大气形态三视图_定稿.png
K1=refs/layout/K1_驾驶舱侧剖.png

# 1. 叠图（REFERENCE / AFTER / 50% OVERLAY）：外形对 C2 三视图（含机头尖放大），剖视对 K1；A、B 两种画法各一份
SPEC="$OUT/overlay-spec.json"
python3 - "$SPEC" "$C2" "$K1" "$LOOKS" <<'PY'
import json, sys
spec, c2, k1, looks = sys.argv[1:5]
tip, s76 = [9.5, 0, 1.65], [1.9, 0, 1.65]
views = [
    ("c2-top", c2, [60, 280, 640, 500], 90, 90, [[tip, [89, 390.5]], [s76, [590.6, 390.5]]], 3, 3, None),
    ("c2-side", c2, [570, 840, 960, 985], 90, 0, [[tip, [590, 929.5]], [s76, [912.4, 929.5]]], 2, 4, None),
    ("c2-front", c2, [180, 830, 420, 985], 0, 0, [[tip, [297, 923.7]], [[9.5, 1, 1.65], [343.67, 923.7]]], 2, 4, None),
    ("c2-tip-top", c2, [80, 365, 190, 416], 90, 90, [[tip, [89, 390.5]], [[8.5, 0, 1.65], [155, 390.5]]], 2, 8, "@focus"),
    ("c2-tip-side", c2, [582, 905, 690, 952], 90, 0, [[tip, [590, 929.5]], [[8.5, 0, 1.65], [632.42, 929.5]]], 2, 8, "@focus"),
    ("c2-tip-front", c2, [262, 895, 332, 955], 0, 0, [[tip, [297, 923.7]], [[9.5, 0.3, 1.65], [311, 923.7]]], 2, 8, "@focus"),
    ("k1-cut", k1, [40, 170, 1720, 650], 90, 0, [[[9.17, 0, 1.66], [97, 449]], [[2.17, 0, 1.66], [1637, 449]]], 3, 1, "__arcseq.cutaway(true)"),
]
out = []
for look, page in (("A", "dist/index.html"), ("B", "dist/metal.html")):
    if look not in looks.split():
        continue
    for name, ref, crop, head, elev, anchors, scale, zoom, pre in views:
        d = {"name": f"{name}-{look}", "refName": name, "ref": ref, "crop": crop, "heading": head, "elevation": elev, "mode": "lines", "scale": scale, "zoom": zoom, "page": page, "anchors": anchors}
        if pre == "@focus":
            d["after"] = "__arcseq.focus([9.0,0,1.66],7)"
        elif pre:
            d["pre"] = pre
        out.append(d)
json.dump(out, open(spec, "w"), indent=1)
PY
timeout -k 5 1800 node scripts/overlay.mjs "$OUT" "$SPEC"

# 2. 固定审图机位（A、B），BEFORE = Z1 look-dev 的同机位
for d in 030 120 210 300; do cp -f review/20261015-Z1-lookdev/AFTER-lines-az$d.png "$OUT/BEFORE-lines-az$d.png"; done
case " $LOOKS " in *" A "*) $S --mode lines --prefix AFTER-A --scale 2 ;; esac
case " $LOOKS " in *" B "*) $S --page dist/metal.html --mode lines --prefix AFTER-B --scale 2 ;; esac

# 3. 1× / 4× / 12× 特写（A、B 同机位）
for L in A:dist/index.html B:dist/metal.html; do
  T=${L%%:*}; P=${L#*:}
  case " $LOOKS " in *" $T "*) ;; *) continue ;; esac
  $S --page $P --mode lines --prefix CLOSE-$T --views 30 --tag 1x --scale 2
  $S --page $P --mode lines --prefix CLOSE-$T --views 30 --tag 4x-canopy --scale 2 --pre "__arcseq.focus('canopy',4)"
  $S --page $P --mode lines --prefix CLOSE-$T --views 60 --elevation 12 --tag 4x-rcs --scale 2 --pre "__arcseq.view(60,'lines',12);__arcseq.focus('rcs.l',4)"
  $S --page $P --mode lines --prefix CLOSE-$T --views 30 --elevation 10 --tag 12x-eye --scale 2 --pre "$ON;__arcseq.view(30,'lines',10);__arcseq.focus('sensor',12)"
  $S --page $P --mode lines --prefix CLOSE-$T --views 60 --tag 12x-roller --scale 2 --pre "__arcseq.view(60,'lines');__arcseq.focus([4.52,0.5,2.22],12)"
  $S --page $P --mode lines --prefix CLOSE-$T --views 90 --elevation 0 --tag 4x-cockpit-cut --scale 2 --pre "__arcseq.cutaway(true).then(()=>{__arcseq.view(90,'lines',0);__arcseq.focus([3.35,0,2.2],3.2)})"
done

# 4. 三张目标帧（A、B）与 300 px 缩略图
for L in A:dist/index.html B:dist/metal.html; do
  T=${L%%:*}; P=${L#*:}
  case " $LOOKS " in *" $T "*) ;; *) continue ;; esac
  $S --page $P --mode lines --prefix TARGET-1-parked-$T --views 30 --thumb --scale 2
  $S --page $P --mode lines --prefix TARGET-3-orbit-$T --views 330 --elevation 12 --thumb --scale 2 --pre "$ON;__arcseq.environment('space')"
done
case " $LOOKS " in *" A "*) timeout -k 5 300 node .claude/skills/anatomy/scripts/drive.mjs dist/index.html --height 1000 --actions scripts/target2.json ;; esac
case " $LOOKS " in *" B "*) timeout -k 5 300 node .claude/skills/anatomy/scripts/drive.mjs dist/metal.html --height 1000 --actions scripts/target2-b.json ;; esac
python3 scripts/replica-sheets.py "$OUT"
