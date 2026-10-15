# AGENTS.md · 给 Codex 的工作规则

总规则在 `CLAUDE.md`，分工在 `docs/WORKFLOW.md`。开工前读这两份，再读 `docs/ROADMAP.md` 里标为 `[Codex]` 的任务和对应的 `docs/PATTERNS.md` 章节。

## 你不能做的

- 不修改 `src/geometry/` 的几何母版（零件外形、轴心、行程、化剑转轴）。
- 不修改 `docs/PATTERNS.md` 里定下的做法，不自创新的视觉规则（含颜色、尾焰、光效）。
- 不参照任何影视、游戏、动画或现有 IP 的飞行器与机甲造型。
- 不加与任务无关的工程（测试框架、许可证台账、长篇报告）。

发现规则本身有问题，写进本轮 `review/.../SUMMARY.md`，由作者转给 Claude。

## 每轮工作

- 只在功能分支上工作，开工前先合并最新 main；一轮只改一个方向；每一类先做一个、截图给作者确认，再铺开同类。
- 截图前 `export CHROME_PATH="$PWD/scripts/chrome.sh"`；固定审图机位 30°、120°、210°、300°。
- 每轮在 `review/<YYYYMMDD>-codex-<任务>/` 放 BEFORE / AFTER 截图和不超过一屏的 SUMMARY.md，更新 ROADMAP 当前进度，提交并推送，停下等作者确认。
