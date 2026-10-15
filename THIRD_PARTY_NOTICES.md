# Third-party notices

| 名称 | 版本 | 来源 | 许可 | 用法 |
|---|---|---|---|---|
| three.js | r168（0.168.0，npm `three`） | https://github.com/mrdoob/three.js | MIT（`src/figure/vendor/three.LICENSE`） | `src/figure/vendor/three.module.min.js` 原样存放；构建时把末尾的 `export{…}` 改成全局 `THREE` 后内联进 `dist/*.html` |
| Anatomy | 见 `.claude/skills/anatomy/UPSTREAM_COMMIT` | https://github.com/wheresryan22/anatomy | MIT（`.claude/skills/anatomy/LICENSE`） | 从 FIG.01 原样复制：截图 `drive.mjs`、Chrome 启动、页面卡片外壳（kit 的 `plateHtml` / `pageHtml`） |
| ARCSEQ 引擎 | FIG.01 `arcseq-hangar` main @ 62d1b51 | 本作者 | — | `src/figure/engine/` 由 FIG.01 `scene.js` / `build.mjs` 的通用部分抽出改写；`weld.mjs`、`shots.mjs`、`perf.mjs`、`hull.mjs`、`scripts/chrome.sh`、`scripts/strip.py` 原样复制 |
| Blender（bpy） | 5.2.2 LTS（pip） | https://www.blender.org | GPL-2.0-or-later | 只作建模与烘焙**工具**，在开发环境运行，不进 `dist/` 与发布包；它产出的 GLB / PNG 是本作品的数据 |
| 文泉驿正黑 | 系统字体（`/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc`） | http://wenq.org | GPL-2.0 with font embedding exception | 烘焙细节贴图时用来画机号与名字（字形栅格化进 `assets/zhulong-skin.png`），字体文件本身不进仓库 |
