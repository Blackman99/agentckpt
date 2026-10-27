# agentckpt landing page: design notes (v4, "Remember to give your agent its meds")

User request (2026-10-13): turn agentckpt's landing page and logo into a pill, a humorous take on remembering to
give your agent its medicine. This version replaces v3 (Game Boy) completely: no pixels, no LCD green, no
Silkscreen.

## Reference object
A **7-day plastic pill organizer** (the MON–SUN strip with snap lids), plus the **"Drug Facts"** panel on the back of
an over-the-counter box. Both are moulded plastic and pharmacy objects, not printed paper.

| Pharmacy | agentckpt |
|---|---|
| the patient | your coding agent |
| one pill in a day compartment | one snapshot (`b66469f`); the organizer is the snapshot store `.agentckpt/` |
| "Take 1 snapshot before every agent turn" | `agentckpt snap` / the v0.2.0 hooks |
| the agent acting up (dizzy eyes, files flying) | an agent turn that edits or deletes files, untracked ones included |
| pop the lid, swallow the pill, symptoms gone | `agentckpt restore b66469f` puts the files back |
| **Interactions: none with git** | your `.git` HEAD, index and branches are never touched |
| Directions / Dosage | install and usage |
| Active ingredients | the commands |
| Side effects & warnings | known limits in v0.3.0 |
| Auto-refill | `agentckpt hook` for Codex, Claude Code, Gemini CLI, OpenCode; `agentckpt run` |

The jokes stay literal and short: *"Take 1 snapshot before every agent turn."*, *"Do not operate heavy refactors
without a snapshot."*, *"Ask your doctor if agentckpt is right for you. (It is.)"*

## Base tone and palette (5 flat colours, no gradients)
| Token | Hex | Use |
|---|---|---|
| `--pink` | `#f7c8d8` | page ground: "pharmacy pink" (light, warm, pink; the only pink ground in the factory) |
| `--ink` | `#1d2b6b` | text, rules, one half of every capsule (deep indigo) |
| `--shell` | `#fffafc` | capsule white half, Drug Facts panel, compartments |
| `--lid` | `#ef7aa1` | translucent organizer lids, buttons, hover states |
| `--mint` | `#9fe3cf` | "symptoms gone": restored state, "no interaction" badge |
None of these hex values appears in `design/registry.md`. There is no red ink, beige, glow or gradient. Plastic gloss is
a single flat white highlight stripe on each pill and lid.

## Type (self-hosted, OFL, Latin subset, static instances)
- **Archivo** Expanded Black (wdth 125, wght 800): headings and day letters, in the style of an OTC box brand mark.
- **Lexend** 400/600: body copy (a readability face, like patient leaflets).
- **Victor Mono** 400: commands only.
None of these families is registered by another project. They are not typewriter, pixel, rounded-fat, condensed
flip-board, stencil or engraved faces.

## Texture and rendering
- Flat vector **inline SVG** with moulded-plastic shapes: rounded compartments, capsule pills, lid hinges drawn as
  bars. One flat highlight per pill, no shadows (no hard or soft drop shadow) and no paper grain.
- Lids are slightly see-through, done with `fill-opacity` on the lid colour over the compartment; no blur and no
  glassmorphism.
- Motion uses CSS transforms only: lid **slides up**, pill **rolls** (rotate plus translate along an arc), agent
  **wobbles**, then settles.

## Layout
- **Hero = the organizer.** A full-width 7-compartment strip (MON–SUN) runs edge to edge. The `h1` is moulded into
  the organizer's front spine: "Remember to give your agent its meds." Below the strip sits the patient (a small
  round agent head) above its working tree (3 file chips), and under them the `.git` shelf "Interactions: none".
  This is neither a centred title plus object nor left copy beside a right card: the object is the frame.
- Sections are panels of a **Drug Facts** label, a single column with heavy indigo rules and bold left headings:
  **Uses · Directions (install) · How it works (interactive organizer) · Active ingredients (commands) ·
  Auto-refill (hooks) · Warnings / side effects (limits) · Interactions · Questions?** (docs, blog, GitHub).
- On mobile the strip keeps 7 compartments (about 48px each), and the Drug Facts rules stack.

## Animation
1. **Hero loop (about 9 s):** the agent works calmly, then misbehaves: spiral eyes, a wobble, and file chips fly off
   and fade (deleted, including `notes.md` untracked). Today's lid slides up, a capsule `b66469f` rolls out along an
   arc into the agent's mouth (*gulp*), and the eyes go back to `^ ^`. The files fly back into place, and the
   `.git` shelf never moves and shows "no interactions".
2. **Mechanism demo (scroll and tap):** a second organizer shows the session; each step (init, snap, agent turn,
   restore, check git) fills a compartment with a pill, makes the agent sick or makes it swallow the pill. The
   working-tree panel updates (a.txt modified, untracked.md deleted, new.py created and kept after restore).
3. **Micro-interactions:** capsule-shaped buttons whose halves separate by 2px on hover; copy buttons say
   "Dispense" and change to "Taken ✓"; compartment lids lift 4px on hover.
- `prefers-reduced-motion`: show the final healthy frame (lid open, pill taken, files back, git unchanged) with no
  loops; the step demo switches states without motion.
- Animations pause when off-screen. Only transform and opacity are animated.

## Logo
A single **capsule pill**, tilted −35°: indigo `#1d2b6b` half and lid-pink `#ef7aa1` half, a white highlight stripe and
a small white restore arrow (↺) on the indigo half. Transparent background with no tile, rounded square or outline.
Exported as SVG plus a 512px PNG; the favicon is the same capsule.

## Self-check against playbook bans and the registry (2026-10-13)
| Rule | Result |
|---|---|
| Dark ground + cyan/purple/blue gradient, gradient text, glow, glassmorphism | Pass. Light pink ground, flat colours, opacity-only lids, no blur. |
| Left-copy/right-card hero, 3-column cards, SaaS template, Inter + mono | Pass. Organizer strip hero, single-column Drug Facts panels, Archivo + Lexend + Victor Mono. |
| Paper/kraft/beige ground, paper texture, red ink, stamps, red X, typewriter, receipt printing, paper stacks | Pass. Moulded plastic and a white plastic panel. "Deleted" is shown by files flying off, not a red X. No line-by-line printing. |
| Rounded app-icon logo with bold-outline cartoon | Pass. Bare capsule on transparent background, no outline, no tile. |
| Base tone vs all 12 projects (warm paper, LCD yellow-green, near-black, white, concrete grey, saturated green, fog blue-grey, lilac, brass, navy, blue charcoal, cheese orange) | **Light pink** is new. Closest is postsleuth lilac `#ece7f3` (cool purple-grey, much paler); ours is clearly pink and warmer. |
| Palette | No hex shared. certfan's hot pink `#ff2e6a` is a neon accent on near-black; our `#ef7aa1` is a soft plastic pink on a pink ground. |
| Type | Archivo, Lexend and Victor Mono are unused elsewhere. |
| Texture / rendering | Moulded-plastic flat vector with one highlight per object. Not paper, pixel, fine-line, isometric, sign, elevation, octilinear, CSS-3D hinge, X-ray, rotateX flip-board or organic cheese cut-away. |
| Layout | Full-width 7-compartment strip with h1 on the spine, then Drug Facts panels. Not a report, HUD, figure plate, 12-col poster, isometric city, gantry, quay, metro map, vault wall, console, departures board or wedge. |
| Animation | Lid slides up, pill rolls along an arc, gulp, wobble then calm, files fly back. Not printing/stamping, steps(), line drawing, kinetic letters, falling blocks, lane change, crane, trains, key turning, conveyor scan, flips or cheese holes opening. |
| Logo | Capsule. Others are a stamp, pixel flag, fan, wordmark, cubes, shield, container, metro line, rack panel, monitor, flap tile and cheese wedge. |
