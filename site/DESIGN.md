# agentckpt landing page: design notes (v3, Game Boy save checkpoint)

Brief: `/workspace/oss-factory/design/briefs/agentckpt.md`. Registry: `/workspace/oss-factory/design/registry.md`.
This replaces v2 (film bench) completely. There is no film, no grey paper, no grease pencil and no red anywhere.

## Direction / metaphor
A **Game Boy (DMG) platformer level with a checkpoint flag**.

| Game | agentckpt |
|---|---|
| the little robot running through the level | the coding agent, one step per turn |
| touching the checkpoint flag, flag rises, "SAVED" | `agentckpt snap` (shadow commit `b66469f`) |
| blocks shattering as the robot runs through them | the agent breaking or deleting files, untracked ones included |
| dithered block | an untracked file (git never saw it) |
| `CONTINUE? ▶ YES` and respawning at the flag, world rebuilt | `agentckpt restore b66469f` |
| a block the robot placed that stays after continue | a file created after the snap (restore never deletes) |
| bedrock rows at the bottom of the screen that never change | your real `.git`: HEAD, index and branches |
| HUD: SNAPSHOTS ×n · WORLD 1-x · TIME | page header / nav |
| levels WORLD 1-1 … 1-4 | sections: install, save, continue, limits |

## Palette: only the four DMG shades, nothing else
| Token | Hex | Use |
|---|---|---|
| `--c0` darkest | `#0f380f` | text, outlines, HUD bar, bedrock |
| `--c1` dark | `#306230` | secondary text, shading, bricks |
| `--c2` light | `#8bac0f` | LCD dot-matrix lines, dither, panels |
| `--c3` lightest | `#9bbc0f` | LCD background |
No fifth colour, no red, no white, no black, no transparency tints, no gradients, no shadows, no glow.
Images that are not ours (the terminal demo GIF) are re-quantised to these four colours (`demo-dmg.gif`).

## Type (self-hosted, OFL, Latin subset)
- **Silkscreen** 400/700: titles, HUD, labels, buttons. Set only at multiples of 8px (its pixel = 1/8 em),
  so glyphs land on whole pixels.
- **Pixelify Sans** 400/600: body copy and command lines (it has real lowercase, which commands need).
- In-canvas text uses a hand-built **3×5 pixel font** drawn on the integer-scaled canvas.
Metric-matched fallbacks prevent layout shift while fonts load.

## Texture and rendering
- LCD dot-matrix ground: a 4×4 SVG tile (one `#8bac0f` pixel line on `#9bbc0f`), not a CSS gradient.
- Pixel art drawn on `<canvas>` at native resolution (scene is 120 px tall) and scaled by an **integer** factor
  (3× on phones, 5× on desktop) with `image-rendering: pixelated`. Native width is computed so the scene fills
  the viewport. No smoothing and no sub-pixel positions.
- 1-bit-style **ordered dither** (checkerboard) for untracked blocks, bedrock and the screen wipe.
- Logo, favicon, OG image and social preview use the same sprites and palette.

## Layout (8 px grid)
- **HUD bar** (sticky, `#0f380f`): `AGENTCKPT` · `SNAPSHOTS ×n` · `WORLD 1-x` · `TIME` · menu links with a ▶ cursor.
- **Title screen = the level itself.** A full-bleed canvas scene. The title is set inside the sky at the top-left of
  the game screen, like a level title card. It is neither a centred title over an object nor left copy beside a
  right card. The bedrock strip at the bottom carries `GIT HEAD 63FC0AE · INDEX CLEAN`.
- Below it, a **dialog box** (double pixel border, game-text style) with the lede and two menu buttons.
- Sections are **levels**, each opened by a level banner (`WORLD 1-1 INSTALL`) on a brick strip:
  - PROLOGUE: why (three hint lines inside one dialog box)
  - WORLD 1-1 INSTALL: menu of options with an `[A] COPY` button
  - WORLD 1-2 SAVE / 1-3 CONTINUE: scroll-driven demo. A step menu with a ▶ cursor, plus a sticky
    "game screen" with three lanes: WORLD (working tree blocks), SAVE SLOTS (`.agentckpt`), BEDROCK (`.git`)
  - ITEMS: the eight commands as an inventory list
  - REPLAY: `agentckpt demo` recording, quantised to DMG green
  - WORLD 1-4 LIMITS: "KNOWN GLITCHES" list
  - END: `CONTINUE? ▶ DOCS / BLOG / GITHUB`
- Everything is left-aligned to the grid. No paper sheets, no stacked cards and no drop shadows.

## Animation (frame-by-frame, no easing)
- Canvas loop at **10 fps** (`setTimeout` frame stepping). Sprites move in whole native pixels. Sequence:
  the robot runs in → touches the flag → the flag climbs the pole in steps → `SAVED B66469F` → it runs through three
  file blocks (one dithered = untracked), each shattering in 4 frames → it drops a `NEW` block →
  `CONTINUE? ▶YES` blinks → dither wipe → the world is rebuilt with the robot at the flag. The `NEW` block is still
  there, and the bedrock text blinks `UNCHANGED`. The bedrock pixels never change.
- CSS animations use only `steps()`: blinking cursors, HUD counters, block shatter sprite (4 steps), button
  press (1 px down).
- `prefers-reduced-motion`: the canvas draws only the final frame (flag up, world rebuilt, NEW block kept, bedrock
  "UNCHANGED"); CSS animations are off.
- The loop pauses when the scene is off-screen or the tab is hidden.

## Logo
16×16 pixel checkpoint flag on a square `#9bbc0f` LCD field (no rounded corners, no outline frame), with pole,
flag, ground bricks and dithered bedrock, using the four DMG colours only. Exported as SVG with `crispEdges`
rects and as a 512 px PNG (32× nearest-neighbour).

## Self-check against playbook bans and the registry
| Rule | Result |
|---|---|
| Dark bg + cyan/purple/blue gradient | Pass. Mid-tone yellow-green LCD, four flat colours. |
| Gradient text / glow / glassmorphism | Pass. None; no CRT bloom either. |
| Left-copy/right-card hero | Pass. Full-bleed game screen with the title inside the sky. |
| Three-column feature cards | Pass. Dialog boxes, menus and lists. |
| SaaS template / Inter + mono | Pass. Silkscreen + Pixelify Sans only. |
| Cross-project bans: beige/kraft/manila paper, paper texture | Pass. LCD green, dot-matrix texture. |
| Red ink circles, stamps, red X | Pass. No red exists in the palette. |
| Typewriter fonts | Pass. Pixel fonts only. |
| Line-by-line receipt printing animation | Pass. Sprite animation; text appears as game dialog. |
| Hard-shadow paper stacks / centred skeuomorph + cards | Pass. Full-bleed scene, left-aligned levels on bricks. |
| Rounded app-icon logo with outlined cartoon object | Pass. Square 16×16 pixel sprite, no rounding, no outline frame. |
| vs toolsmoke (light warm paper, Fraunces/Courier Prime/Caveat, vermilion) | Different on every axis. |
| vs certfan (near-black, Anybody/Atkinson, acid yellow-green #d6ff3b + hot pink, vector lines) | certfan is dark with a single neon line accent. agentckpt is a mid-tone LCD field in four muted greens, pixel raster. No shared hex or font. |
| vs linelore (pure white, Schibsted Grotesk, international orange, kinetic type) | Different on every axis. |
| vs runbill (concrete grey, Unbounded/Red Hat, isometric 3D, cobalt) | Different on every axis. |
