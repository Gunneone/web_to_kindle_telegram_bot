# gunne design system · v1

The shared look of **gunne.one** and every app on its subdomains (Showtime, Stash Trak, Popscore, Swedeline and whatever comes next).
Apps may have their own style where it makes sense, but header, footer, background, type, color roles,
shapes and basic components come from here.

| What | Where |
|---|---|
| Stylesheet | `https://gunne.one/ds/v1/gunne.css` |
| Theme script | `https://gunne.one/ds/v1/theme.js` |
| Icon sprite (same-origin only) | `https://gunne.one/ds/v1/icons.svg` |
| Logos and app marks | `https://gunne.one/ds/v1/brand/` |
| Living style guide | `/design` on a local dev server (`FLASK_DEBUG=1`), not live |
| This guide (latest) | `gunne.one` repo → `static/ds/v1/DESIGN.md`, not live |
| Source | `gunne.one` repo → `static/ds/v1/` |

> **For AI coding assistants:** treat this file as binding. Use the `--g1-*` tokens and `g1-*` classes
> instead of inventing colors, radii, fonts or components. Never hardcode hex values in app code (the only
> exception is the app color registry in `gunne.css`). Every screen must work in light **and** dark.
> When something is missing, extend with tokens and follow the same rules; don't fork the look.

---

## TL;DR for a new project

1. Put the no-flash snippet in `<head>`, then link `gunne.css` (before your own CSS) and `theme.js` (with `defer`). See [Integration](#11-integration).
2. Set your app on `<html>`: `<html lang="en" data-g1-app="myapp">`. Register its color in `gunne.css` (see [App colors](#app-colors)).
3. Use the shared [header](#header) and [footer](#footer) markup. Your app's own mark on the left, the "a gunne.one project" badge in the footer.
4. Build with tokens (`var(--g1-…)`) and components (`g1-btn`, `g1-card`, `g1-badge`, `g1-stats`, `g1-callout`, `g1-input`, `g1-table`).
5. Blue for actions, orange for accents. Chamfer the top-left corner. Labels and numbers in mono. Every joke is
   [scribbled](#scribbles) by hand, never printed.
6. Check light, dark, mobile (390 px) and reduced motion before shipping. Run the [review checklist](#12-review-checklist).

---

## 1. Brand

**Personality: nerdy and precise, playful and witty.**
The layout is calm, aligned and exact, like a lab notebook. The personality comes from the jokes
scribbled in its margins, the orange details and small bits of motion. Never from clutter.

### The G1 mark

- Files: `brand/g1-mark.svg` (source, 64 × 64), plus `brand/g1-mark-48.png`, `-96.png`, `-192.png`, `-600.png` (transparent PNG).
- Orange `#F88414` G, blue `#2097F3` 1. Never recolor, outline, rotate (except the hover wiggle) or put it in a container.
- Minimum size 16 px. Keep clear space of at least a quarter of its width around it.
- The flag of the "1" (the 45° cut at its top-left) is where the chamfer shape comes from.

### App marks

Every app has its own logo in the header, in whatever style suits the app. Put the file in `brand/` and add
it here.

| App | Mark | Motif |
|---|---|---|
| Showtime | `brand/showtime-mark-v2.svg` | TV with clock hands |
| Stash Trak | `brand/stashtrak-mark.svg` | CS2 case with a StatTrak counter |
| Popscore | `brand/popscore-icon.png` | Popcorn bucket on midnight blue |
| Swedeline | `brand/swedeline-icon.svg` | An underline rising into an S |
| Should AI? | `brand/shouldai-mark.svg` | A robot as the knob of a yes/no switch |

---

## 2. Color

Colors are CSS custom properties defined with `light-dark()`, so every token has a light and a dark value.
**Use the semantic token, never the hex value.**

### Core tokens

| Token | Light | Dark | Use |
|---|---|---|---|
| `--g1-bg` | `#F5F6F8` | `#0E1116` | Page background |
| `--g1-surface` | `#FFFFFF` | `#161B22` | Cards, panels, secondary buttons |
| `--g1-surface-2` | `#EEF0F3` | `#1C222B` | Insets, hovers, code, callouts |
| `--g1-field` | `#FFFFFF` | `#12161C` | Input backgrounds |
| `--g1-chrome` | white 78 % | `#0E1116` 78 % | Sticky header (with blur) |
| `--g1-chrome-solid` | `#FFFFFF` | `#12161C` | Footer |
| `--g1-border` | `#DFE3E8` | `#28303B` | Default lines |
| `--g1-border-strong` | `#C3C9D1` | `#3A4452` | Button edges, table heads |
| `--g1-text` | `#141821` | `#E8ECF1` | Body text, headings |
| `--g1-text-muted` | `#5A6472` | `#98A3B1` | Secondary text, labels |
| `--g1-text-subtle` | `#737D8C` | `#7A8595` | Placeholders only |
| `--g1-primary` | `#1672C4` | `#2097F3` | Primary buttons, selected states |
| `--g1-primary-hover` | `#125FA3` | `#4AABF6` | Hover of the above |
| `--g1-on-primary` | `#FFFFFF` | `#0B1220` | Text on primary |
| `--g1-link` | `#1668B5` | `#5CB3F7` | Links |
| `--g1-focus` | `#1672C4` | `#2097F3` | Focus rings |
| `--g1-accent` | `#F88414` | `#F88414` | Orange fills, underlines, markers |
| `--g1-accent-text` | `#C65300` | `#F88414` | Orange text (readable) |
| `--g1-on-accent` | `#1A0E00` | `#1A0E00` | Text on orange |
| `--g1-accent-soft` | `#FFF1E3` | `#2A1A0B` | Soft orange backgrounds |
| `--g1-success` | `#1F7A45` | `#3FB96F` | Success |
| `--g1-warning` | `#8A6A00` | `#E3B341` | Warning (yellow, not orange) |
| `--g1-danger` | `#C9302C` | `#F06A64` | Errors, destructive actions |

Brand constants that never change with the theme: `--g1-orange: #F88414`, `--g1-blue: #2097F3`.

### Blue leads, orange accents

- **Blue** does the work: primary buttons, links, focus rings, selected states, info.
- **Orange** is the signature, used sparingly:
  - the active nav underline and card hover edges
  - `New` badges and small highlights (`.g1-hl` in eyebrows)
  - list bullets, blockquote bars, text selection, the input caret
- Never use orange for primary buttons, links or large filled areas. Never use `--g1-accent` as text on a
  light background: use `--g1-accent-text`.
- Warnings are **yellow** (`--g1-warning`), so that orange keeps meaning "brand", not "problem".

### App colors

Each app may add **exactly one** extra color, for its own content: hero numbers, charts, app badges, the
app button. Blue stays primary and orange stays the signature, in every app.

The registry lives in `gunne.css` and is activated with `data-g1-app` (on `<html>` in the app, or on any
element, e.g. a project card on the homepage):

| Token | Use |
|---|---|
| `--g1-app` | Fills: app button, app badge, chart series |
| `--g1-app-text` | App-colored text and big numbers |
| `--g1-on-app` | Text on `--g1-app` |
| `--g1-app-soft` | 14 % tint for panels and highlights |
| `--g1-app-brand` | Constant brand hex (logos only) |

| App | `--g1-app` light / dark | `--g1-app-text` light / dark |
|---|---|---|
| `showtime` | `#C62A2F` / `#F2555A` | `#C62A2F` / `#FF6369` |
| `stashtrak` | `#4D7A00` / `#A4D007` | `#4D7A00` / `#A4D007` |
| `popscore` | `#7A3FD1` / `#B18CFF` | `#7A3FD1` / `#B18CFF` |
| `swedeline` | `#8A6400` / `#FECC02` | `#8A6400` / `#FECC02` |
| `shouldai` | `#00727D` / `#80DEEA` | `#00727D` / `#80DEEA` |

**Adding a new app color:** pick a hue that is clearly different from blue, orange and the other apps.
Tune a light-mode value with ≥ 4.5:1 contrast on `#F5F6F8` (and for white text on it) and a dark-mode value
with ≥ 4.5:1 on `#0E1116`. Add a `[data-g1-app="name"]` block to `gunne.css`, a swatch to `/design`, and
a row to the tables above.

---

## 3. Typography

| Family | Token | Use |
|---|---|---|
| IBM Plex Sans 400 / 400 italic / 500 / 600 / 700 | `--g1-font-sans` | Everything by default |
| IBM Plex Mono 400 / 500 / 600 | `--g1-font-mono` | Eyebrows, labels, meta, table numbers, code |
| Caveat 600 | `--g1-font-hand` | [Scribbles](#scribbles): every joke and witty remark, nothing else |

Fonts are self-hosted from `gunne.one/ds/v1/fonts/` (Latin subset incl. German umlauts, SIL OFL 1.1).
**Never load fonts from Google or another CDN.**

| Token | Size | Typical use |
|---|---|---|
| `--g1-text-xs` | 12 px | Eyebrows, meta, badges (11 px), table heads |
| `--g1-text-sm` | 14 px | Buttons, nav, callouts, tables |
| `--g1-text-base` | 16 px | Body |
| `--g1-text-md` | 17 px | Prose |
| `--g1-text-lg` | 20 px | Card titles, lead |
| `--g1-text-xl` | 24 px | Prose h2 |
| `--g1-text-2xl` | 30 px | Section headings |
| `--g1-text-3xl` | 40 px | Stat values |
| `--g1-text-4xl` | 48 px | Page titles (`.g1-title`, fluid from 32 px) |

Rules:

- Headings are 700 (card titles 600), tight tracking (`-0.015em` to `-0.025em`), `text-wrap: balance`.
- **Sentence case** everywhere: "Things I've built", not "Things I've Built". Eyebrows are lowercase in
  the source and rendered uppercase by CSS.
- **Eyebrow** above every page title and section heading: `.g1-eyebrow`, mono, e.g.
  `// hello, world · dortmund, de` or `01 / principles`. Highlight separators with `<span class="g1-hl">`.
- **Numbers are nerdy:** big numbers in Plex Sans 700 with `tabular-nums` (`.g1-stat__value`); numbers in
  tables and meta in Plex Mono (`.g1-mono .g1-num`). Units are smaller and muted (`.g1-stat__unit`).
- Meta lines read like code: `last_updated = 2026-09-24` (`.g1-meta`, `=` in `.g1-hl`).
- Body line height 1.6, prose 1.7, prose width max 680 px.

### Scribbles

The notebook is printed; the jokes are written in its margins. **Every witty remark is a scribble**: a short
handwritten note in Caveat, orange, tilted by 2°. Print carries the information, handwriting carries the
personality. **No jokes in plain text, no information in handwriting.**

```html
<h1 class="g1-title">I build things. <span class="g1-scribble">(mostly to avoid boring stuff like filing my taxes)</span></h1>
```

**What counts as witty:** anything that's there for the laugh, i.e. the part you could delete without the
reader losing any information. When a sentence mixes both, split it: the fact stays printed, the punchline
moves into the scribble ("Small apps that answer questions like how much of my life went into TV shows.
*(questions nobody asked)*"). Nerdy framing (`// hello, world`, `01 / principles`, `last_updated = …`) is
formatting, not a joke, and stays in mono; only a value that is itself the joke gets scribbled.

| Pattern | Markup | Example |
|---|---|---|
| Aside after a line | `text <span class="g1-scribble">(aside)</span>` | What's keeping me busy these days. *(updated whenever I remember to)* |
| Correction | `<s>printed</s> <span class="g1-scribble">handwritten</span>` | Track the time you have ~~wasted~~ *spent* watching TV (the `<s>` stroke is hand-drawn in the scribble's ink) |
| Joke value in meta | `key <span class="g1-hl">=</span> <span class="g1-scribble">value</span>` | publishing_schedule = *every sometimes* |
| Footer one-liner | `<span class="g1-scribble">…</span>` in `.g1-footer__meta` | *built in dortmund, mostly instead of something else* |

- **Never on anything functional:** buttons, links, nav, labels, form fields, numbers, badges, errors, or
  anything a user needs to read to get something done. If a joke would have to go there, cut it.
- **Sparse:** at most one per block (a title, a lead, a card, a meta line, the footer) and no more than
  three in view at once. If there are more, cut the weakest joke; don't print it instead.
- **Short:** ideally under 10 words, one or two lines. Lowercase. In parentheses when it comments on the
  text right before it. No exclamation marks, no emoji.
- **Placement:** inline, right after the text it comments on. It flows next to the text on wide screens
  and wraps below it on phones.
- **Size is automatic:** 1.3 em (Caveat runs small, so this matches the surrounding text), 0.75 em inside
  `h1`, `h2` and `.g1-title` so it reads as a side note, and never below 18 px. Don't resize it yourself.
- **Always the component, never just the font:** orange (`--g1-accent-text`), weight 600, −2° tilt.
  Don't recolor it, stack several, or animate it. `.g1-hand` (font only) exists for the rare custom
  element that needs the handwriting without the note styling, e.g. a label on an illustration.
- Only one weight (600) is shipped. Preload `fonts/caveat-latin-600-normal.woff2` on pages that show a
  scribble above the fold; everywhere else it loads on demand.

---

## 4. Shape and space

### The chamfer

Everything is square except **one 45° cut at the top-left corner**, taken from the flag of the "1".

| Token | Size | Used by |
|---|---|---|
| `--g1-cut` | 14 px | Cards, stats, panels |
| `--g1-cut-sm` | 8 px | Buttons, inputs, selects (6 px on small buttons) |
| `--g1-cut-xs` | 5 px | Badges |

- No `border-radius` anywhere, except for things that are round by nature (avatars, coins, dots).
- Chamfered components (`.g1-card`, `.g1-btn`, `.g1-badge`, `.g1-chamfer`) draw their shape with
  `::before` (edge) and `::after` (fill). So:
  - **Don't set `background` or `border` on them**. Set the custom properties instead:
    `--g1-fill` (inside), `--g1-edge` (border color), `--g1-edge-w` (border width, default 1px),
    `--g1-c` (cut size).
  - Don't use their `::before` / `::after` for anything else.
  - Their content is **not clipped**, so menus and tooltips inside cards are fine.
- To chamfer any custom block, add `.g1-chamfer` and set the properties above.
- Inputs (`.g1-input`, `.g1-select`, `.g1-textarea`) use `clip-path` plus a gradient; they have no
  children, so that's safe.

### Space and layout

- 4 px grid: `--g1-space-1` … `-9` = 4, 8, 12, 16, 24, 32, 48, 64, 96 px.
- Widths: `--g1-width` 900 px (homepage, content sites), `--g1-width-wide` 1200 px (apps, dashboards),
  `--g1-width-prose` 680 px. Use `.g1-container`, `.g1-container--wide`, `.g1-container--prose`.
  An app can also set `:root { --g1-width: 1200px; }`.
- Gutter `--g1-gutter`: 20 px, 16 px under 480 px. Header height `--g1-header-h`: 64 px.
- Grids: `.g1-grid` (auto-fill, min 260 px), `.g1-grid--2` (min 340 px). Gap 16 px.
- Sections are separated by 64 px (`.g1-section`); page heads have 64 px on top.

---

## 5. Background and surfaces

- `body` gets the signature background automatically: **orange glow top-left, blue glow top-right,
  over faint 32 px graph paper**. Don't replace it; an app may override it only for a full-bleed
  experience (e.g. a video player).
- Content sits on solid surfaces (`--g1-surface`). Never put the grid or glow inside cards.
- Elevation is flat: borders, not shadows. The only shadow is the soft `drop-shadow` on hovered link cards.

---

## 6. Shared chrome

### Header

Sticky, 64 px, translucent `--g1-chrome` with blur, 1 px bottom border. Left: mark + name. Center/right:
nav. Right: theme toggle (and at most one or two more icon buttons). Active nav item:
`aria-current="page"` → orange underline. Under 720 px the nav moves to a scrollable second row.

**Apps use their own mark and name.** The homepage uses the G1 mark and "Gunne.one".

```html
<header class="g1-header">
  <div class="g1-container g1-container--wide g1-header__inner">
    <a class="g1-brand" href="/">
      <img class="g1-brand__mark" src="/static/brand/showtime-mark-v2.svg" alt="" width="28" height="28">
      <span>Showtime</span>
    </a>
    <nav class="g1-nav" aria-label="Main">
      <a href="/" aria-current="page">Shows</a>
      <a href="/stats">Stats</a>
    </nav>
    <div class="g1-header__actions">
      <button type="button" class="g1-btn g1-btn--ghost g1-btn--icon" data-g1-theme-toggle aria-label="Toggle dark mode">
        <svg class="g1-icon g1-when-light" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3c.132 0 .263 0 .393 0a7.5 7.5 0 0 0 7.92 12.446a9 9 0 1 1 -8.313 -12.454l0 .008"/></svg>
        <svg class="g1-icon g1-when-dark" viewBox="0 0 24 24" aria-hidden="true"><path d="M8 12a4 4 0 1 0 8 0a4 4 0 1 0 -8 0"/><path d="M3 12h1m8 -9v1m8 8h1m-9 8v1m-6.4 -15.4l.7 .7m12.1 -.7l-.7 .7m0 11.4l.7 .7m-12.1 -.7l-.7 .7"/></svg>
      </button>
    </div>
  </div>
</header>
```

`.g1-when-light` shows in light mode (the moon: "go dark"), `.g1-when-dark` in dark mode.

### Footer

Solid `--g1-chrome-solid`, 1 px top border. Row 1: app links left, social icons right. Row 2 (mono,
dashed divider): the family badge left, a one-liner right.

```html
<footer class="g1-footer">
  <div class="g1-container g1-container--wide">
    <div class="g1-footer__inner">
      <nav class="g1-footer__links" aria-label="Footer">
        <a href="/privacy">Privacy</a>
        <a href="https://github.com/gunneone/showtime">Source</a>
      </nav>
      <div class="g1-footer__social">
        <a href="https://github.com/gunneone" target="_blank" rel="noopener noreferrer" aria-label="GitHub"><svg class="g1-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M9 19c-4.3 1.4 -4.3 -2.5 -6 -3m12 5v-3.5c0 -1 .1 -1.4 -.5 -2c2.8 -.3 5.5 -1.4 5.5 -6a4.6 4.6 0 0 0 -1.3 -3.2a4.2 4.2 0 0 0 -.1 -3.2s-1.1 -.3 -3.5 1.3a12.3 12.3 0 0 0 -6.2 0c-2.4 -1.6 -3.5 -1.3 -3.5 -1.3a4.2 4.2 0 0 0 -.1 3.2a4.6 4.6 0 0 0 -1.3 3.2c0 4.6 2.7 5.7 5.5 6c-.6 .6 -.6 1.2 -.5 2v3.5"/></svg></a>
        <a href="https://linkedin.com/in/gunneone" target="_blank" rel="noopener noreferrer" aria-label="LinkedIn"><svg class="g1-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M8 11v5"/><path d="M8 8v.01"/><path d="M12 16v-5"/><path d="M16 16v-3a2 2 0 1 0 -4 0"/><path d="M3 7a4 4 0 0 1 4 -4h10a4 4 0 0 1 4 4v10a4 4 0 0 1 -4 4h-10a4 4 0 0 1 -4 -4l0 -10"/></svg></a>
        <a href="https://t.me/gunneone" target="_blank" rel="noopener noreferrer" aria-label="Telegram"><svg class="g1-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M15 10l-4 4l6 6l4 -16l-18 7l4 2l2 6l3 -4"/></svg></a>
      </div>
    </div>
    <div class="g1-footer__meta">
      <a class="g1-family" href="https://gunne.one"><img src="https://gunne.one/ds/v1/brand/g1-mark-48.png" alt="" width="16" height="16">a gunne.one project</a>
      <span>your data never leaves your browser</span>
    </div>
  </div>
</footer>
```

The one-liner on the right is the app's small promise (lowercase, mono, as above) or its joke (a
[scribble](#scribbles): `<span class="g1-scribble">built in dortmund, mostly instead of something else</span>`).
The homepage uses `© <year> gunne.one` on the left instead of the family badge.

---

## 7. Components

All components are plain CSS classes. In React, use them via `className`.

### Buttons: `.g1-btn`

| Variant | Class | Use |
|---|---|---|
| Default | `.g1-btn` | Most actions. Surface fill, strong edge. |
| Primary | `.g1-btn--primary` | **The one main action per view.** Blue. |
| App | `.g1-btn--app` | The main action inside an app-scoped area (e.g. "Open Showtime"). |
| Ghost | `.g1-btn--ghost` | Toolbars, icon buttons, low-emphasis actions. |
| Sizes | `.g1-btn--sm` (32 px), default (40 px), `.g1-btn--lg` (48 px) | |
| Icon only | `.g1-btn--icon` + `aria-label` | Square. |

- Label: verb first, sentence case, 1–3 words ("Export CSV", "See my projects").
- Add a trailing arrow for navigation: `<svg class="g1-icon g1-arrow">` (it nudges right on hover).
- Works on `<button>` and `<a>`. Disabled: `disabled` or `aria-disabled="true"`.

### Links

- Inline links: blue, thin underline at 40 % alpha, **orange underline on hover**. You get this for free
  from the base styles.
- Stand-alone links: `.g1-link` (600 weight, no underline until hover), usually with a `.g1-arrow`.
- External links get `target="_blank" rel="noopener noreferrer"` and an `arrow-up-right` icon.

### Cards: `.g1-card`

Parts: `.g1-card__head` (eyebrow/icon + badge), `.g1-card__title`, `.g1-card__text`, `.g1-card__foot`.

- Make the **whole card** the link (`<a class="g1-card">`) when it leads somewhere. It lifts 2 px and its
  edge turns orange on hover.
- `.g1-card--app` tints the edge with the app color (needs `data-g1-app` on it or an ancestor).
- Dense lists (tables, search results) are rows, not cards.

### Badges: `.g1-badge`

Mono, uppercase, 11 px, 5 px chamfer. Variants: default (neutral), `--accent` (orange, for "New"),
`--primary`, `--app`, `--soft` (orange tint). One or two words max.

### Stats: `.g1-stats` > `.g1-stat`

The nerdy big-number block. Joined cells with hairlines, 14 px chamfer on the group.

```html
<div class="g1-stats">
  <div class="g1-stat g1-stat--app">
    <div class="g1-stat__value">1,284<span class="g1-stat__unit">h 37 min</span></div>
    <div class="g1-stat__label">total watch time</div>
  </div>
</div>
```

`.g1-stat--app` colors the value with `--g1-app-text`.

### Callouts: `.g1-callout`

Flat box on `--g1-surface-2` with a 3 px left bar, icon first. Default bar is orange (tips, asides);
`--info`, `--success`, `--warning`, `--danger` for status. Say what happened, then what to do.

### Forms

`.g1-label` (mono, uppercase, xs) above `.g1-input` / `.g1-select` / `.g1-textarea` (40 px, 8 px chamfer,
orange caret, blue focus). Checkboxes, radios and ranges use the native control with `accent-color: blue`.
Placeholders are real examples ("Breaking Bad"), not instructions.

### Tables: `.g1-table`

Mono uppercase heads, hairline rows, hover row tint. Right-align numbers with `.g1-num` and set them in
mono (`.g1-mono`). Wrap wide tables in a container with `overflow-x: auto`.

### Icons: Tabler outline

- Set: [Tabler Icons](https://tabler.io/icons), **outline** only, MIT. Stroke 1.75, size `1.25em`
  (inherits color and font size). Class `.g1-icon`.
- Decorative icons: `aria-hidden="true"`. Icon-only buttons: `aria-label`.
- **Homepage (same origin):** `<svg class="g1-icon"><use href="/ds/v1/icons.svg#home"></use></svg>`.
- **Apps:** browsers don't allow `<use>` of an SVG from another origin, so either copy `icons.svg` into
  the app's static files, inline the SVG, or (React) use `@tabler/icons-react` with
  `<IconHome className="g1-icon" stroke={1.75} />`.
- Brand icons (GitHub, LinkedIn, Telegram, Steam) come from Tabler too (`brand-*`).
- Don't mix in other icon sets.

### Utilities

`.g1-mono`, `.g1-hand` (handwriting font only, see [Scribbles](#scribbles)), `.g1-num` (tabular figures), `.g1-muted`, `.g1-app-text`, `.g1-accent-text`, `.g1-hl`,
`.g1-meta`, `.g1-visually-hidden`, `.g1-skip-link`, `.g1-stack` (16 px vertical rhythm), `.g1-prose`.

---

## 8. Motion

Small, quick and purposeful. Tokens: `--g1-dur-fast` 120 ms, `--g1-dur` 200 ms, `--g1-dur-slow` 400 ms;
easing `--g1-ease` (smooth out) and `--g1-ease-spring` (slight overshoot, for playful bits).

The shared micro-animations:

| Where | What |
|---|---|
| Logo / app mark / family badge | Wiggle on hover |
| Link cards | Lift 2 px, edge turns orange |
| Buttons | Press down 1 px; trailing arrow nudges right |
| Footer social icons | Hop up 2 px |
| Theme toggle | Icon spins in, and colors cross-fade across the page |

- Animate only `transform`, `opacity` and colors. No layout animation, nothing longer than 400 ms, nothing
  that loops forever.
- `prefers-reduced-motion: reduce` is handled globally by `gunne.css`. Don't override it.
- App-specific celebrations (Showtime's confetti) are fine as long as they are rare, dismissable and
  respect reduced motion.

---

## 9. Voice and microcopy

Your smartest, slightly self-deprecating friend who happens to be a data scientist.

- **Plain, short, specific.** Contractions yes, jargon no.
- **Every joke is a [scribble](#scribbles).** Printed copy stays plain and informative; the wit is
  handwritten next to it. It's the author muttering in the margin, so it can be more candid than the
  rest. Good spots: titles, leads, card text, empty states, footer one-liners, 404s. Never in destructive
  confirmations or error messages that matter.
- **The correction** is the signature move: strike the printed word, scribble the honest one after it.
  "the time you've <s>wasted</s> *spent* watching TV". Once per page at most.
- **Nerdy framing** is welcome in meta: `last_updated = 2026-09-24`, `// hello, world`, `01 / principles`.
- Sentence case, no exclamation marks in system messages, no "please", no "successfully", no "click here".
- Errors: say what happened, then what to do. "This inventory is private. Set it to public in Steam and
  try again."
- Empty states are an invitation: headline names the next step, one line of body (plus an optional
  scribble), one button. "No shows yet. *(your couch misses you)*" → **Add a show**
- 404: always funny, always with a way home. "This page doesn't exist. *(it's procrastinating)* Try the
  homepage."

| Do | Don't |
|---|---|
| "Export saved" | "Your file was exported successfully!" |
| "Find out how much of your life went into TV shows" | "Welcome to Showtime, the ultimate TV tracker" |
| "See my projects" | "Click here to view projects" |
| "Steam is rate limiting us. Trying again in a minute." | "Error 429: Too Many Requests" |

---

## 10. Light and dark

Every app supports both. Default: follow the OS. The toggle stores an override.

- Tokens switch automatically via `light-dark()` and `color-scheme`. `data-theme="light|dark"` on
  `<html>` forces a theme; without it the OS setting applies.
- The override is stored in `localStorage` and, on `*.gunne.one`, in a `g1-theme` cookie on the parent
  domain, so **the choice follows the visitor across all apps**. Mention it in the app's privacy page.
- `theme.js` wires every `[data-g1-theme-toggle]` element (event delegation, works with React), exposes
  `window.g1Theme.get() / set('dark') / reset()`, and fires `g1:themechange` on `<html>`. Listen to it
  to re-render canvases or charts.
- Charts and canvases must read colors from tokens at draw time
  (`getComputedStyle(document.documentElement).getPropertyValue('--g1-text')`) and redraw on
  `g1:themechange`.
- Images: prefer transparent SVG/PNG that work on both backgrounds.

---

## 11. Integration

### Plain HTML, Flask, Jinja

```html
<!DOCTYPE html>
<html lang="en" data-g1-app="showtime">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <script>
    (function () {
      try {
        var m = document.cookie.match(/(?:^|;\s*)g1-theme=(light|dark)/);
        var t = m ? m[1] : localStorage.getItem('g1-theme');
        if (t !== 'light' && t !== 'dark') t = matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
        document.documentElement.setAttribute('data-theme', t);
      } catch (e) {}
    })();
  </script>
  <meta name="theme-color" media="(prefers-color-scheme: light)" content="#f5f6f8">
  <meta name="theme-color" media="(prefers-color-scheme: dark)" content="#0e1116">
  <link rel="preload" href="https://gunne.one/ds/v1/fonts/ibm-plex-sans-latin-400-normal.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="stylesheet" href="https://gunne.one/ds/v1/gunne.css">
  <link rel="stylesheet" href="/static/css/app.css"><!-- your app CSS, after gunne.css -->
  <script defer src="https://gunne.one/ds/v1/theme.js"></script>
</head>
<body class="g1-page">
  <a class="g1-skip-link" href="#main">Skip to content</a>
  <!-- header -->
  <main id="main">…</main>
  <!-- footer -->
</body>
</html>
```

- Make the base URL configurable (e.g. `G1_DS_URL`, default `https://gunne.one/ds/v1`) so local
  development can point at `http://localhost:5001/ds/v1` from the homepage repo.
- Your own CSS should be **unlayered** (plain CSS). It automatically wins over `gunne.css`.

### React + Vite + Tailwind v4

`index.html`: the same `<head>` snippet, `gunne.css` link and `theme.js` as above, **before** the app's
entry script, plus `data-g1-app` on `<html>`.

`styles.css`: map Tailwind to the tokens so utilities stay on-system:

```css
@import 'tailwindcss';

/* Colors and fonts come from gunne.css (linked in index.html). */
@theme inline {
  --color-bg: var(--g1-bg);
  --color-surface: var(--g1-surface);
  --color-surface-2: var(--g1-surface-2);
  --color-field: var(--g1-field);
  --color-line: var(--g1-border);
  --color-line-strong: var(--g1-border-strong);
  --color-fg: var(--g1-text);
  --color-muted: var(--g1-text-muted);
  --color-subtle: var(--g1-text-subtle);
  --color-primary: var(--g1-primary);
  --color-primary-hover: var(--g1-primary-hover);
  --color-on-primary: var(--g1-on-primary);
  --color-link: var(--g1-link);
  --color-accent: var(--g1-accent);
  --color-accent-fg: var(--g1-accent-text);
  --color-accent-soft: var(--g1-accent-soft);
  --color-app: var(--g1-app);
  --color-app-fg: var(--g1-app-text);
  --color-on-app: var(--g1-on-app);
  --color-app-soft: var(--g1-app-soft);
  --color-success: var(--g1-success);
  --color-warning: var(--g1-warning);
  --color-danger: var(--g1-danger);
  --font-sans: var(--g1-font-sans);
  --font-mono: var(--g1-font-mono);
  --font-hand: var(--g1-font-hand);
}

/* dark: variant follows the shared theme attribute */
@custom-variant dark (&:where([data-theme="dark"], [data-theme="dark"] *));
```

- Then write `bg-surface text-fg border-line`, `text-muted`, `bg-primary text-on-primary`,
  `text-app-fg`, `font-mono`… For scribbles, use the `g1-scribble` class rather than `font-hand`. Because the tokens already switch with the theme, you rarely need `dark:`.
- Use the `g1-*` component classes for shared components (`className="g1-btn g1-btn--primary"`), and
  Tailwind utilities for layout and app-specific details. Utilities override `g1` components when needed.
- `gunne.css` declares `@layer theme, base, g1, components, utilities;`, which puts it above Tailwind's
  preflight and below utilities. This only works if `gunne.css` is linked **before** the app CSS.
- Don't use Tailwind's `rounded-*`, `shadow-*` or palette colors (`bg-blue-500`) for UI chrome.
- Icons: `@tabler/icons-react`.

### Versioning

- `v1` only changes in backwards-compatible ways: new tokens, new components, bug fixes. Apps get these
  automatically (1 hour cache).
- Breaking changes go to `/ds/v2/`. Apps opt in by changing the URL.
- Fonts and brand files are cached for a year; never change a file in place, add a new name instead.
- **Deploy order:** the homepage (which serves `/ds/`) must be live before an app that links to it.

---

## 12. Review checklist

- [ ] `gunne.css` and `theme.js` linked, no-flash snippet in `<head>`, `data-g1-app` set
- [ ] Shared header (own mark, nav with `aria-current`, theme toggle) and footer (family badge)
- [ ] No hardcoded hex colors, font stacks, radii or shadows in app code
- [ ] Looks right in **light and dark**, at 390 px and at 1440 px
- [ ] One primary button per view; orange only for accents, never for primary actions or links
- [ ] Cards, buttons, badges and inputs have the top-left chamfer, no rounded corners
- [ ] Eyebrow above page and section titles; labels, meta and table numbers in mono
- [ ] Tabler icons only; icon-only buttons have `aria-label`
- [ ] Visible focus on every interactive element; keyboard reachable; skip link present
- [ ] Reduced motion respected, animations ≤ 400 ms
- [ ] Copy in sentence case, errors are clear
- [ ] Every joke is a scribble, every scribble is a joke; one per block, never on anything functional
- [ ] No third-party font or icon CDNs; privacy page mentions the `g1-theme` cookie
