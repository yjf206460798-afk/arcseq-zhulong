#!/bin/sh
# Z1 look-dev 交审截图（可重跑）：sh scripts/z1-review.sh [输出目录]
# 先构建：.venv/bin/python blender/build.py && node src/figure/build.mjs && node src/figure/build.mjs --variant=hull --out=dist/hull.html
set -e
cd "$(dirname "$0")/.."
export CHROME_PATH="$PWD/scripts/chrome.sh"
OUT="${1:-review/20261015-Z1-lookdev}"
mkdir -p "$OUT"
S="timeout -k 5 300 node src/figure/shots.mjs $OUT"
ON="__arcseq.set('power',1);__arcseq.set('chine',1);__arcseq.set('chine.sweep',1);__arcseq.set('sensor',1)"

# A. 固定审图机位：三种模式四方位（停机、未通电）+ 300 px 缩略图
for m in silhouette volume lines; do $S --mode $m --prefix AFTER --thumb; done

# B. 几何母版路线比较：Blender→网页 / 代码凸体→网页（同一机位、同一取景），Cycles 另出（blender/build.py --render-only）
$S --mode lines --prefix ROUTE-glb --views 30
$S --page dist/hull.html --mode lines --prefix ROUTE-hull --views 30
# 4× 特写：眉骨与座舱、鳞片样片（侧低机位）
$S --mode lines --prefix ROUTE-glb --views 30 --tag brow4x --pre "__arcseq.focus('canopy',3.6)"
$S --page dist/hull.html --mode lines --prefix ROUTE-hull --views 30 --tag brow4x --pre "__arcseq.focus('canopy',3.6)"
$S --mode lines --prefix ROUTE-glb --views 75 --elevation 14 --tag belly4x --pre "__arcseq.view(75,'lines',14);__arcseq.focus([5.2,0.5,1.2],4)"
$S --page dist/hull.html --mode lines --prefix ROUTE-hull --views 75 --elevation 14 --tag belly4x --pre "__arcseq.view(75,'lines',14);__arcseq.focus([5.2,0.5,1.2],4)"

# C. 四项基础质感：逐项关 / 开对照
$S --mode volume --prefix QA-ao-off --views 30 --tag canopy3x --pre "__arcseq.look({ao:0,detail:false});__arcseq.focus('canopy',3)"
$S --mode volume --prefix QA-ao-on --views 30 --tag canopy3x --pre "__arcseq.look({detail:false});__arcseq.focus('canopy',3)"
$S --mode lines --prefix QA-detail-off --views 300 --tag side4x --pre "__arcseq.view(300,'lines');__arcseq.look({detail:false});__arcseq.focus([6.0,-0.55,1.7],4)"
$S --mode lines --prefix QA-detail-on --views 300 --tag side4x --pre "__arcseq.view(300,'lines');__arcseq.focus([6.0,-0.55,1.7],4)"
$S --mode lines --prefix QA-glow-off --views 30
$S --mode lines --prefix QA-glow-on --views 30 --pre "$ON"
$S --mode lines --prefix QA-glow-on --views 30 --tag eye6x --pre "$ON;__arcseq.focus('sensor',6)"
node src/figure/aa.mjs "$OUT" --region 330,300,330,200

# D. 目标帧（之后每轮的验收基准）
$S --mode lines --prefix TARGET-1-parked --views 30
$S --mode lines --prefix TARGET-3-orbit --views 330 --elevation 12 --pre "$ON;__arcseq.environment('space')"
$S --mode lines --prefix TARGET-3-orbit --views 330 --elevation 12 --thumb --thumb-view 330 --pre "$ON;__arcseq.environment('space')"
