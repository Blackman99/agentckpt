# agentckpt landing page: design notes (v3)

## Reference object
A **film-editing bench with a darkroom contact sheet** on it. A coding-agent session is a roll of film.
Each agent turn is one **frame**. A snapshot is a frame the editor has **circled in red grease pencil**
(china marker). A wrecked turn is a frame marked with a red **X / "NG"** (no good, standard slate/editing shorthand).
`restore` means the editor **winds the strip back to the circled frame**. The user's real git repo is the
**camera negative**: it sits in its own sleeve on the bench and is never cut. The orange negative stays still
while the work print runs.

Mapping used everywhere on the page:

| Film bench | agentckpt |
|---|---|
| work print running through the gate | working tree as the agent edits it |
| frame number / edge print | snapshot id (`b66469f`) and timecode |
| grease-pencil circle | `agentckpt snap` checkpoint |
| red X + "NG" | the turn that broke things |
| rewinding to the circled frame | `agentckpt restore <id>` |
| uncut orange camera negative | your `.git` (HEAD, index, branches untouched) |
| edit decision list (EDL) / cutting sheet | the init → snap → restore walkthrough |
| film-can masking-tape label | limits / notes |
| slate / clapper | install "takes" |

## Palette (no gradients anywhere)
- Bench / ground: warm grey `#cbc5b8`, with darker grey `#b9b2a3` for rules and shadows. Flat colour, plus a
  very faint paper-fibre texture (tiny inline SVG noise at 4% opacity).
- Photo paper (contact sheet): warm off-white `#efebe3`.
- Film base / rebate (strip): brown-black `#1c1815`. Sprocket holes are the ground colour showing through.
- Print image tones inside frames: `#2a2622` ink on `#e9e4da` (positive prints of the file tree).
- Camera negative (= git): colour-negative orange mask `#b4632c` with darker `#7c3f17` density, and
  edge print in negative-yellow `#f0c75a`.
- Grease pencil: china-marker red `#c3261b`.
- Darkroom safelight accent: amber `#d9861c`, used sparingly (frame counter, "now in gate" lamp, focus ring).
- Text: ink `#1f1b17`, muted `#5a534a`.
No cyan, purple or blue. No glow, no blur, no translucent glass. Shadows are short, hard and offset, like
paper lying on a bench.

## Type (four faces, all self-hosted, Latin subset, static instances)
- **Big Shoulders** 800 (condensed, industrial, film-can / slate lettering): headlines, frame numbers.
- **IBM Plex Mono** 400/600: edge print, EDL table, commands. Small uppercase, letter-spaced like
  Kodak edge codes.
- **Newsreader** 400 (+600): body copy, like an editor's handbook.
- **Permanent Marker**: grease-pencil annotations only (a handful of words: "keep", "NG", "untouched").
No Inter, no system-sans + mono pairing.

## Layout
1. **Edge-print bar** (nav): one thin dark strip across the top with sprocket holes and edge-print text
   `AGENTCKPT ▸ 5063 ▸ ROLL 01`, links typed in the same edge-print style.
2. **Hero: stacked, full width, no side card.**
   - A slate-style title block: huge condensed uppercase headline "EVERY AGENT TURN IS A FRAME.
     CUT BACK TO THE GOOD ONE." with "GOOD ONE" circled by a hand-drawn red SVG ellipse.
   - Below it, **full-bleed film strip** (the hero animation) spanning the viewport, with an editor's
     **gate** marker fixed in the middle and a frame counter.
   - Directly under the strip, the **orange negative** strip labelled "your .git (camera negative, never cut)".
   - Under that, a narrow single column of body copy, a typed install line and two buttons styled as
     film-can tape labels (flat, offset hard shadow).
3. **Contact sheet** ("why"): one sheet of photo paper with **two strips of frames** laid side by side,
   like a real contact sheet. Each frame is a pain point printed as a frame with a frame number. The
   pains are marked NG in grease pencil, and the last frame (agentckpt) is circled. It reads as a
   contact sheet, not a card grid: frames butt together on the strip, sprocket holes run above and below,
   and captions sit in the edge print.
4. **Edit decision list** (scroll-driven): a typed EDL table (`EVENT REEL TRANS SRC-IN SRC-OUT NOTE`)
   with rows 001 init, 002 snap, 003 agent, 004 restore, 005 verify. A sticky **viewer** beside it
   (a single film frame plus the negative) changes state as each row reaches the middle of the screen,
   and the active row gets a hand-drawn red tick. On phones the viewer sits at the top (sticky) and the
   rows stack. Rows can also be tapped.
5. **Command key**: the eight commands as an edge-code legend on a single strip of film leader.
6. **Projection print**: the existing demo.gif mounted in a vertical 35mm frame with sprocket rails.
7. **Slate**: install "takes" (TAKE 1 try with uvx, TAKE 2 install wheel from Releases, TAKE 3 use),
   with a clapper bar of black/off-white diagonal stripes and copy buttons.
8. **Masking-tape labels**: limits written on strips of tape stuck at slight angles.
9. **Footer**: edge-print strip again; links to Docs, Blog, GitHub, Releases.

## Animation
- **Hero strip loop (~12 s):** the work print advances one frame per agent turn behind the fixed gate
  (transform only). Frame 2 is "snap: before agent" and the grease-pencil circle draws around it
  (SVG stroke-dashoffset). Frames 3 to 5 show the file tree degrading (app.py marked M, utils.py
  missing, untracked notes.md missing, scratch.py new). Frame 5 gets a red X and "NG". Then the
  strip **rewinds fast** back to circled frame 2, the counter rolls back, and the gate frame shows
  "restored" with untracked notes.md back and scratch.py noted as left in place. The orange
  negative under it **never moves**; a grease-pencil tick "untouched" is drawn on it at the end.
- **EDL scroll demo:** IntersectionObserver picks the active row; the viewer frame swaps its print,
  the circle/X/tick marks draw, and the negative stays still with an "unchanged" mark.
- **Micro-interactions:** hovering a contact-sheet frame lifts it like a loupe (scale plus hard shadow);
  copy buttons show "copied" in grease pencil; tape labels straighten on hover; links get a
  grease-pencil underline.
- `prefers-reduced-motion`: no strip movement and no drawing. The final state is shown statically
  (circle, X, restored frame, tick).
- Performance: transform and opacity only, animation pauses when off-screen, no framework, fonts
  subset with metric-matched fallbacks.

## Banned-list self-check
| Banned | This design |
|---|---|
| Dark background with cyan/purple/blue gradients | **Pass.** Warm grey bench ground, flat colours, no cyan/purple/blue, no gradients. The old timeline is removed. |
| Gradient text | **Pass.** Solid ink text; emphasis is a hand-drawn red circle around words. |
| Glow | **Pass.** No box-shadow blur glows; only short hard offset shadows (paper on a bench). |
| Glassmorphism | **Pass.** No backdrop-filter, no translucency; the nav is an opaque film strip. |
| Left-copy / right-animated-card hero | **Pass.** Stacked hero: headline, full-bleed strip, negative, then copy. No side card. |
| Three-column feature cards | **Pass.** Pains are frames on a contact sheet (two butted strips with sprockets); commands are an edge-code legend on one strip. |
| Generic SaaS/devtool template layout | **Pass.** Every section maps to a bench object (strip, contact sheet, EDL, slate, tape labels, projection print). |
| Inter + monospace combo | **Pass.** Big Shoulders + Newsreader + IBM Plex Mono (edge print) + Permanent Marker; no Inter. |
| Overlap with toolsmoke (smoke-test bench / paper inspection report) | **Pass.** No report forms, stamps, checkboxes or typewriter face. Dominant objects are black film strips with sprockets and an orange negative on a grey bench; red is hand-drawn grease pencil, not stamps. |

Note: `assets/logo.svg` (also the bot avatar) still uses the old cyan/violet gradient. The page header
uses a typographic mark instead. Redrawing the logo is a separate decision because the avatar must change with it.
