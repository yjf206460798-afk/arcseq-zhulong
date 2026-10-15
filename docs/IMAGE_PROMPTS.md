# GPT 出图提示词

概念图只锁定剪影、比例和大构件位置；细节（眉骨、鳞片瓦等）以几何母版为准。出新图时把定稿三视图作为附件，并在开头写“Same aircraft as the attached three-view”。

## 已用

| 图 | 文件 | 提示词 |
|---|---|---|
| 剪影探索（选 C） | `refs/concept/C0_剪影探索_选定C.png` | P1 |
| 大气形态三视图初版 | `refs/concept/C1_大气形态三视图_初版.png` | P2（基于 C） |
| 大气形态三视图定稿 | `refs/concept/C2_大气形态三视图_定稿.png` | P3（在 C1 上改） |
| 剑形态三视图 | `refs/concept/C3_剑形态三视图.png` | P4 |

### P1 · 剪影探索
```
Concept design exploration sheet: 6 different top-view (planform) silhouettes of an ORIGINAL single-seat aerospace fighter, shown as solid black silhouettes on a white background, arranged in a 3x2 grid, each labeled A to F.

Shared design brief for all six: overall shape reads like a sword or arrowhead. Long, needle-sharp faceted forward body (about 40% of length) flowing via long chine strakes into a cranked double-delta wing; a wide, flat, heavy rear "engine block" carrying twin vertical tails and three exhaust outlets side by side. Strong contrast between the blade-thin front and the massive rear. Length about 19 m, span about 10.5 m.

Vary between the six: chine width, wing crank position, wingtip shape, tail placement, and the outline of the rear block. Every silhouette must be instantly recognizable even at thumbnail size. Original design: must not resemble any existing film, game or anime aircraft, nor any real aircraft.
```

### P2 · 三视图
```
Orthographic three-view technical drawing sheet (top, side, front) on ONE sheet, all views to the same scale and perfectly consistent, of the ORIGINAL single-seat aerospace fighter "Zhulong", based on silhouette C from the previous sheet. Dark charcoal background, thin light-gray linework, flat gray fills, museum-blueprint style.

Form language: upper surfaces made of large, precise flat facets with crisp ridge lines (no blobby curves); completely flat waverider underside. Proportions: very low profile, needle nose, blade-like front 40%, wide heavy rear engine block. Length 19 m, span 10.5 m, height about 3.4 m.

Key features:
- Nose tip: a small round sensor aperture with an iris shutter.
- Tiny low single-seat canopy set under a faceted "brow" ridge, with a track for a sliding metal heat shield.
- Small canards that retract into slots in the chine.
- Cranked double-delta wing; outer wingtips hinge downward.
- One wide, flat 2D air intake on the belly, split by a central divider, hidden under the flat underside.
- Twin outward-canted vertical tails on the rear block, hinged to fold inward flat.
- Rear: two rectangular 2D jet nozzles flanking a central linear aerospike rocket nozzle.
- Reaction-control thruster clusters on the nose and wingtips; a row of small dorsal thrusters and vents along the spine.
- Dorsal payload bay door.
- Belly fully covered in thermal tiles in a fine scale-like pattern; dark carbon leading edges.

Fine, sparse, functional panel lines, hinge lines and hatches only where parts actually open or move. Matte graphite; a single very thin vermilion line along each chine from nose to wingtip. Original design, not resembling any existing aircraft from films, games, anime or real life. No text except small view labels.
```

### P3 · 在 C1 上修改
```
Edit the attached three-view drawing. Keep EVERYTHING the same (planform, proportions, faceted surfaces, the thin red chine lines, colors, style, layout, the dorsal bay, nozzles, wingtip fins), and change ONLY the following:

1. FRONT view: remove the two large dark trapezoid openings beside the cockpit. The only air intake is the wide flat slot on the belly.
2. Add a small round sensor aperture at the very tip of the nose with a thin iris-shutter outline, visible in top and side views.
3. Add a sharp faceted "brow" ridge directly above and in front of the canopy, and a thin track line showing where a metal heat shield slides forward to cover the canopy.
4. Belly thermal tiles: change the hexagonal pattern into overlapping, staggered scale-shaped tiles (like fish or dragon scales, pointing rearward), fine and subtle.
5. Make the twin vertical tails consistent in all three views: they rise from the outer edges of the rear engine block, canted outward.

All three views must remain perfectly consistent with each other and to the same scale.
```
结果：1、2、5 改到位；3、4 未改（建模时自己做）。

### P4 · 剑形态
```
Same aircraft as the attached three-view ("Zhulong"), now shown in its transformed SWORD MODE, as a new three-view sheet (top, side, front) in the same style, scale and colors.

Transformation: the canards are stowed inside the chine slots; both main wings pivot fully rearward until parallel to the fuselage, and their outer panels fold downward to lie flush against the sides of the rear body, so the planform becomes a long, narrow blade; the wingtip fins fold flat; the twin vertical tails rotate outward to horizontal and stick out sideways from the rear block, forming the crossguard of a sword; the rear engine block reads as the grip, and the central aerospike cone reads as the pommel; a metal heat shield covers the canopy. The thin red chine lines now run continuously from the nose tip to the crossguard like a sharpened blade edge, faintly glowing.

From the top view the whole aircraft must clearly read as a straight sword (blade, crossguard, grip, pommel), while still being believable as the same machine with all parts accounted for. Original design, not resembling any existing transforming vehicle from films, games or anime.
```
结果：俯视、前视成立；侧视把剑格画成竖片（忽略）；主翼收拢关系未交代（Z1 自己设计）。

## 待用（可选，不影响开工）

### P5 · 主视觉
```
Same aircraft as the attached three-view: the "Zhulong" aerospace fighter, three-quarter top-down isometric view, parked on a dark circular hangar turntable, background #101518. Industrial technical illustration: crisp thin outlines, soft four-tone flat shading on faceted surfaces, very fine panel lines, small red (left) and green (right) navigation lights, a faint warm amber glow in the nose sensor aperture. Calm, precise, premium, like a museum exhibit poster. Not a game render, no lens flares, no dramatic effects.
```

### P6 · 双形态对比
```
Same aircraft as the attached three-views, two states side by side in the same isometric view and style: LEFT atmosphere mode (canards out, wings spread, canopy visible, tails canted up); RIGHT sword mode (as in the sword-mode three-view: wings folded back flush, tails flat as a crossguard, heat shield over the canopy, red chine edges faintly glowing). Dark hangar turntable, industrial illustration style.
```

### P7 · 彩蛋剪影（机甲构思到剪影层之后再用）
留空，待构思。
