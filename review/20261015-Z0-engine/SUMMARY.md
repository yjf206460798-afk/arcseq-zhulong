# Z0 · 开工准备（2026-10-15）

- 引擎：从 `arcseq-hangar` main（62d1b51）抽出通用部分到 `src/figure/engine/`（渲染、明暗五档、分级线条、投影、灯点、关节-机构-状态、演出导演、尾焰着色器、审图入口），作品数据只经 `DATA` 进来；歼-20 专用的风扇、登机梯、剖开、故障、改装对比、读数卡、声音、开场引导都没有带过来。Anatomy 技能、`chrome.sh`、`hull.mjs`、`weld.mjs`、`shots.mjs`、`perf.mjs`、`strip.py` 原样复制。
- 空场景：`node src/figure/build.mjs --variant=empty` → `dist/empty.html`；`AFTER-lines-az030.png` 只有转台与刻度环，控制台 `console: clean`。
- 概念图三视图的 14 处矛盾与取舍：`docs/DESIGN.md` 8.1。
