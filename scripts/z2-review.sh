#!/bin/sh
# Z2 整机交审截图（可重跑）：sh scripts/z2-review.sh <输出目录> [atmo|sword|all]
#   atmo：大气形态对 C2 俯 / 侧 / 前视叠图 + 固定四机位（A、B）+ 300 px 缩略图
#   sword：剑形态对 C3 叠图 + 化剑逐姿态正交俯视（两形态并排）+ 300 px 缩略图
# 先构建：.venv/bin/python blender/build.py && node src/figure/build.mjs && node src/figure/build.mjs --look=lines --out=dist/drawing.html
# 只看形（不烘焙）：PAGE_B=dist/fast.html PAGE_A=dist/fast-a.html（build.mjs --assets=dist/fast）
set -e
cd "$(dirname "$0")/.."
export CHROME_PATH="$PWD/scripts/chrome.sh"
OUT="${1:?输出目录}"
PART="${2:-all}"
PAGE_A="${PAGE_A:-dist/drawing.html}"
PAGE_B="${PAGE_B:-dist/index.html}"
LOOKS="${LOOKS:-A B}"
mkdir -p "$OUT"
S="timeout -k 5 300 node src/figure/shots.mjs $OUT"
SWORD="__arcseq.set('sword',1)"

# 1. 叠图：大气形态对 C2，剑形态对 C3（REFERENCE / AFTER / 50% OVERLAY）
SPEC="$OUT/overlay-spec.json"
python3 - "$SPEC" "$PART" "$LOOKS" "$PAGE_A" "$PAGE_B" <<'PY'
import json, sys
spec, part, looks, page_a, page_b = sys.argv[1:6]
c2, c3 = "refs/concept/C2_大气形态三视图_定稿.png", "refs/concept/C3_剑形态三视图.png"
d2 = json.load(open("refs/concept/C2_剪影.json", encoding="utf8"))["views"]
d3 = json.load(open("refs/concept/C3_剪影.json", encoding="utf8"))["views"]
tip = [9.5, 0, 1.65]


def anchors(d, view):
    k, (px, py) = d[view]["k_px_per_m"], d[view]["origin_px"]
    if view == "front":
        return [[tip, [px, py]], [[9.5, 3, 1.65], [px + 3 * k, py]]]
    return [[tip, [px, py]], [[9.5 - 17, 0, 1.65], [px + 17 * k, py]]]


views = []
if part in ("atmo", "all"):
    views += [("c2-top", c2, [40, 30, 1420, 760], 90, 90, anchors(d2, "top"), None),
              ("c2-side", c2, [560, 770, 1440, 1000], 90, 0, anchors(d2, "side"), None),
              ("c2-front", c2, [20, 770, 580, 1000], 0, 0, anchors(d2, "front"), None)]
if part in ("sword", "all"):
    views += [("c3-top", c3, [20, 100, 1430, 680], 90, 90, anchors(d3, "top"), "__arcseq.set('sword',1)"),
              ("c3-side", c3, [550, 760, 1430, 1010], 90, 0, anchors(d3, "side"), "__arcseq.set('sword',1)"),
              ("c3-front", c3, [20, 820, 570, 960], 0, 0, anchors(d3, "front"), "__arcseq.set('sword',1)")]
out = []
for look, page in (("A", page_a), ("B", page_b)):
    if look not in looks.split():
        continue
    for name, ref, crop, head, elev, anc, pre in views:
        d = {"name": f"{name}-{look}", "refName": name, "ref": ref, "crop": crop, "heading": head, "elevation": elev, "mode": "lines", "scale": 2, "zoom": 2, "page": page, "anchors": anc}
        if pre:
            d["pre"] = pre
        out.append(d)
json.dump(out, open(spec, "w"), indent=1)
PY
timeout -k 5 1800 node scripts/overlay.mjs "$OUT" "$SPEC"

# 2. 固定审图机位（A、B）+ 300 px 缩略图；BEFORE_FROM：上一轮交审目录（拷它的 AFTER-B-lines-az*.png 作 BEFORE）
if [ -n "$BEFORE_FROM" ] && [ "$PART" != sword ]; then
  for d in 030 120 210 300; do cp -f "$BEFORE_FROM/AFTER-B-lines-az$d.png" "$OUT/BEFORE-B-lines-az$d.png"; done
fi
for L in A:$PAGE_A B:$PAGE_B; do
  T=${L%%:*}; P=${L#*:}
  case " $LOOKS " in *" $T "*) ;; *) continue ;; esac
  if [ "$PART" != sword ]; then
    $S --page $P --mode lines --prefix AFTER-$T --scale 2
    $S --page $P --mode lines --prefix THUMB-atmo-$T --views 30 --thumb --scale 2
  fi
  if [ "$PART" != atmo ]; then
    $S --page $P --mode lines --prefix SWORD-$T --scale 2 --pre "$SWORD"
    $S --page $P --mode lines --prefix THUMB-sword-$T --views 30 --thumb --scale 2 --pre "$SWORD"
  fi
done

# 3. 化剑逐姿态：正交俯视（俯仰 90°）与 3/4 斜视，控件值 0 → 1
if [ "$PART" != atmo ]; then
  for t in 0 0.14 0.28 0.4 0.5 0.62 0.72 0.88 1; do
    $S --page $PAGE_A --mode lines --prefix POSE-top-$t --views 90 --elevation 90 --scale 1 --pre "__arcseq.set('sword',$t)"
    $S --page $PAGE_B --mode lines --prefix POSE-oblique-$t --views 30 --scale 1 --pre "__arcseq.set('sword',$t)"
  done
fi
python3 scripts/z2-sheets.py "$OUT"
