# Phase Status

> **Internal build history.** This file is a phase-by-phase development diary for
> maintainers. End users should start at [README.md](README.md) and the
> [GitHub Releases](https://github.com/Ojisan1/LyricsMiniplayer/releases) page.

| Phase | Name | Status |
|-------|------|--------|
| 0 | Project Foundation | Completed (approved) |
| 1 | Now Playing via SMTC | Completed (approved) |
| 2 | Floating Miniplayer Shell | Completed (approved) |
| 3 | Lyrics Fetching (Plain Text) | Completed (approved) |
| 4 / 4a / 4b | Timed lyrics + sync polish | Completed (approved) |
| 5 | Polish, Robustness & Packaging | Completed (approved) |
| 5a | Album art click-to-zoom overlay | Completed (approved) |
| UX-1 | Visual/UX polish — Tier 1 | Completed (reviewed, accepted) |
| UX-2 | Visual/UX polish — Tier 2 | Completed (reviewed, accepted) |
| UX-3 | Visual/UX polish — Tier 3 | 3.0 marquee, window shape and 3.1 sizing presets all accepted; 2 items deferred |
| Art | iTunes high-res album art | Completed (accepted) |
| Rel | v1.0.0 redistributable package | Completed |
| Art-1.1 | Prefer SMTC album when ranking iTunes art | Completed (accepted) |
| Rel | v1.1.0 redistributable package | Completed |
| Sec | August 2026 security review remediation | Completed |
| Rel | v1.2.0 redistributable package | Completed |
| Fix | Reject degenerate plain-only LRCLIB lyrics | Completed |
| Rel | v1.2.1 redistributable package | Completed |

## Overall

**v1.2.1 is packaged.** Plain-lyrics ingest now rejects run-on LRCLIB blobs with no line
breaks so search can return multiline (often timed) copies. Redistributable output is
`dist\LyricsMiniplayer-v1.2.1.zip`. See `RELEASE_NOTES_v1.2.1.md`.

v1.2.0 security hardening remains in place (bounded remote content, constrained artwork
fetch, hashed lockfile, release checksums/SBOM/provenance). See `SECURITY.md`.

The UX polish session was delivered one tier at a time. Tiers 1 and 2 are accepted in full. In
Tier 3, item 3.0 (title marquee), the window-shape fix and item 3.1 (window sizing presets) are
accepted; the remaining two Tier 3 items are deferred, with a recommendation to drop the shadow.

Tier 3 item 3.0 (title marquee) was reviewed live: **accepted** — scrolling
confirmed smooth on "Gravel Pit (feat. RZA, Method Man, …)". That review also turned up the
black square border around the window, now fixed (see below).

## UX polish pass — Tier 1 (landed)

All changes are in `ui/miniplayer.py` unless noted.

- **Lyric hierarchy:** three tiers (`past` `#808080`, `next` `#A0A0A0`, `current` `#FFFFFF` bold)
  replacing the previous two. The active line no longer changes font size, which removes the
  per-line reflow that caused scroll jumpiness. Line leading now scales with font size.
- **Accent discipline:** green is no longer the active-line color; it is reserved for the brand
  mark and interactive accents. All lyric tiers clear 4.5:1 contrast against the panel.
- **Theme:** removed `set_default_color_theme("dark-blue")`; sliders, switch, buttons, and the
  textbox scrollbar are now explicitly colored, ending the blue/green clash.
- **Chrome:** ghost header buttons (transparent, hover-brightened) replacing filled chips;
  header 28 → 32px; album art 64 → 72px with a real rounded-corner PIL mask and a hover
  brightness state.
- **Settings:** live value readouts ("14 pt", "85%"); Lyrics size row moved above Opacity.
- **First-launch position:** the window now opens near the tray at the bottom-right of the work
  area with a 16px (logical) gap from the right edge and above the taskbar. A position is written
  to `settings.json` only after the user actually drags the window, so the tray corner keeps
  being recomputed until then. A drag threshold means a plain click no longer writes settings.
- **Off-screen recovery:** a saved position that no longer lands on a connected display falls
  back to the default corner. Previously an unreachable position was unrecoverable, since a
  borderless window has no taskbar or Alt-Tab entry.

### Bug found and fixed during Tier 1

Geometry strings mix coordinate spaces: CustomTkinter scales the `WxH` part by the window
scaling factor but passes `+x+y` through as physical pixels. Any position computed from Win32
work-area pixels must therefore use the *scaled* window size.

This also affected the accepted Phase 5a art overlay, which centered a 600-logical (900 physical
at 150% scaling) window as though it were 600 physical. Measured with `GetWindowRect` on a
3840×2160 @ 150% display, the overlay sat 150px right and 150px below true center. Both the
overlay and the new default position now scale correctly; the overlay measures dead center.

### Validation performed

- `py_compile` and AST parse clean on all touched modules.
- Headless construction of the window exercising: settings panel open/close, both sliders and
  readouts, album art decode with rounded mask and hover variant, the no-op metadata guard, and
  a 12-line timed-lyric walk forward through all tiers plus a scrub back, confirming correct
  `past` / `current` / `next` tagging at every step and `Segoe UI` at equal size for active and
  inactive lines.
- Real window rects via `GetWindowRect`: first-launch gap measured 24 physical px (16 logical
  × 1.5) on both edges and fully on screen; art overlay centering offset measured 0, 0;
  off-screen saved position recovered to the default without being marked user-set; a valid
  saved position respected verbatim and round-tripped.
- `python main.py --once` and `--lyrics-test` both still working against a live Spotify session
  (84 timed lines fetched, cache hit confirmed).

**Not yet validated — needs the Program Director with music playing:** whether the white bold
active line reads better than green in practice, whether scrolling feels calmer now that the
size change is gone, and the album art rounding and hover at normal viewing distance.

**Review outcome:** accepted. Flow confirmed much improved by removing the active-line font
size change.

## UX polish pass — Tier 2 (landed)

- **2.0 Header removed (added at the Program Director's request):** the "Lyrics Miniplayer"
  brand label and its 32px strip are gone; the gear and hide buttons now sit inline with the
  song title. Only the title row gives up width — the artist and status lines keep the full
  metadata column. Measured: metadata column 294 logical px, title 232, controls 62. About
  36 logical px of vertical space returned to the lyrics panel.
- **2.1 Typed state screens:** a centered glyph + headline + subline panel replaces the muted
  paragraph previously used for every state. Six states — idle, loading (animated indeterminate
  bar, no glyph), not found, instrumental, offline, rate limited — with errors in amber. The
  lyrics panel and state panel share one slot, packed one at a time.
- **2.2 Eased scrolling:** normal line advances glide over 180ms in 6 frames on a quadratic
  ease-out; seeks, track changes and first loads still snap, which also preserves the existing
  two-pass reposition correction that depends on the scroll having already landed. A newer line
  change cancels and re-measures, so no travel is lost. Honours the Windows "show animations"
  accessibility preference.
- **2.3 Status line:** now `1:42 / 2:38 · Synced`, prefixed with `Paused · ` when paused, with
  a `Plain` badge for unsynced lyrics and no badge when there are none. Driven from data already
  passed to `update_track`, so no change to the sync engine. The passive progress bar from the
  original proposal was declined by the Program Director.
- **2.5 Tooltips:** a plain-Tk tooltip helper (CustomTkinter has none) with a 400ms delay on the
  gear, hide button, and album art. The art tooltip is suppressed when there is no art.
- **2.6 Tray menu:** Show and Hide collapse into one checked "Show lyrics" toggle, since one of
  the two was always a no-op. The current track appears as a disabled item above a separator and
  as the hover tooltip. Icon glyph enlarged for 16px rendering with a record hole.
- **2.7 Art overlay:** sized from the source resolution between 480 and 600 logical px instead of
  a fixed 600, with a mild unsharp mask when an upscale beyond 1.5x is unavoidable. Framed with a
  hairline border and an 8px inset. Escape closes it in addition to clicking.
- **2.8 Opacity floor** raised from 0.40 to 0.55 in both the slider and `core/settings.py`, since
  Tk applies `-alpha` to text as well and the bottom of the old range made lyrics unreadable.

Item 2.4's "taller grab strip" is retired — there is no header left to make taller. Middle-button
drag is still open and now more useful.

### Findings during Tier 2

- CustomTkinter adds roughly 2x `corner_radius` to a button's minimum width to keep the glyph
  clear of the rounding. The intended 26px circular buttons were rendering 45 logical px wide,
  costing 33px of title width. Reduced to `corner_radius=6`, which matches `ART_RADIUS`.
- Spotify's SMTC thumbnails measure 300x300 (verified against a live session), so the overlay
  cannot avoid upscaling; the minimum bound is what applies in practice. See the open question
  on overlay size below.

### Validation performed

- `py_compile` clean on all modules; `--once` and `--lyrics-test` working against a live session.
- Headless window build covering: header layout with measured widths and button alignment, all
  six state screens with glyph/spinner/subline pack state, error-string mapping for every message
  `core/lyrics.py` can produce, status line in five conditions, opacity floor in slider and
  settings loader, state-to-lyrics transition, tooltip show/hide and gating, and overlay sizing
  at 300 / 640 / 1200px sources with the resulting window geometry.
- Eased scrolling observed frame by frame: 6 distinct scroll positions with decreasing step
  sizes, monotonic forward, animation completing and clearing its handle; seeks confirmed to
  snap; reduce-motion path confirmed instant.
- Tray menu descriptor evaluated the way pystray evaluates it when rendering, confirming the
  callable signatures and that `checked` tracks window visibility.
- Full `MiniplayerApp` startup with a real tray icon, one SMTC poll and one sync tick.

**Test limitation:** the lyrics worker thread calls `root.after`, which tkinter only permits
while `mainloop()` is running, so the fetch-to-render path cannot be exercised outside the real
app. It is covered by direct `update_lyrics` calls instead. This is pre-existing Phase 3
architecture, not a Tier 2 change.

**Not yet validated — needs the Program Director:** whether the eased scroll reads as calmer or
laggier with music playing, whether Escape actually reaches the borderless art overlay, tray
menu and icon appearance at the real notification-area size, and whether the smaller/sharper
art overlay is preferred over the previous larger/softer one.

**Review outcome: accepted (2026-08-04).** Tier 2 was live-tested with no issues raised but was
never signed off as its own gate at the time; the Program Director has since confirmed it as
accepted, so the items above stand as built.

**Rebuild note — done.** The stale pre-UX-tier exe has been replaced. `build.ps1` was re-run on
2026-08-04 after 3.1 was accepted, producing `dist\LyricsMiniplayer.exe` (23.3 MB, onefile,
windowed) containing all three UX tiers. No spec changes were needed. See "Packaged build
verification" at the end of this document.

## Tier 3 — in progress

### 3.0 Title marquee (landed)

Chosen over ellipsis truncation. Engages only when the title overflows its 232 logical px; the
artist line is unaffected and does not marquee.

Sequence as approved: dwell 2s, glide left at 30 logical px/s until the tail is visible, rest
1.5s, return to the start, then stop for that track. Replayed on hover. One pass per track
change, never looping.

`_title_label` now lives inside a fixed-width clipping `CTkFrame` (`_title_clip`) and is moved
with `place(x=-offset)`, as specified. Verified in the installed CustomTkinter 6.0.0 that
`CTkBaseClass.place` routes kwargs through `_apply_argument_scaling`, which scales `x`/`y` — so
offsets stay logical and no raw `tk.Canvas` is needed. Measured: a −40 logical offset reaches Tk
as −60 physical at 150% scaling.

**Two implementer's calls inside the approved sequence**, both easy to change:

- The return trip runs at 60 logical px/s, double the outbound rate, so it reads as a rewind
  rather than a second read-through. The spec said "return to the start" without specifying a
  rate; a hard snap would have been the only alternative and would have jumped.
- Hover replay dwells 250ms rather than the full 2s, since a hover means the user wants to read
  the title now. The dwell is kept only to debounce a pointer passing through.

Measured durations at the approved 30 px/s: a modest overflow (+60px) is 2.3s out and 6.9s for
the whole sequence; a deliberately extreme 66-character title is 291px of travel, 9.7s out and
18.0s total. Long but self-terminating. This is the main thing to judge with music playing.

### Findings during 3.0

- A `place()`d child contributes nothing to its parent's requested size, so `_title_clip` would
  have kept `CTkFrame`'s 200px default height and pushed the lyrics panel down.
  `_sync_title_clip_height()` sets it from the label's own requested height (28 logical, which
  is `CTkLabel`'s default and matches the previous title row height, so the layout does not
  shift).
- `place_configure()` is **not** overridden by CustomTkinter and takes physical px, unlike
  `place()`. Using it would silently reintroduce the coordinate-space bug fixed twice already.
- `CTkFont` holds the *unscaled* logical size and widgets scale it per-render, so
  `font.measure()` returns logical px while `winfo_*` returns physical. Overflow is therefore
  measured from `winfo_reqwidth()` and converted down once, rather than mixing the two spaces.
- Widget scaling and window scaling are tracked separately by CustomTkinter, so a
  `_widget_scaling()` helper was added next to the existing `_window_scaling()`. They are equal
  unless `set_widget_scaling()` is called, which this app never does.

### Validation performed

- `py_compile` clean on all modules; `--once` and `--lyrics-test` working against a live session
  (84 timed lines, cache hit confirmed).
- 30-check headless harness, all passing: clip frame width 232 and height 28 logical with the
  title row and 294px metadata column unchanged from Tier 2; no travel for a short title and
  travel exactly `overflow + tail pad` for a long one; `place` x scaled logical→physical; the
  real `after` loop driven through dwell → glide → rest → return → stop with 23 distinct
  monotonic offsets and no looping afterwards; a mid-glide track change resetting the offset to
  0 and cancelling; per-second status clock updates *not* restarting a running pass; hover
  starting a pass when idle and being ignored mid-pass; reduce-motion scheduling nothing at all;
  and `hide()` / `destroy()` both cancelling cleanly.
- Full `MiniplayerApp` startup with a real tray icon, one SMTC poll and one sync tick: the live
  track title measured 146 logical px against a 232px clip, so no marquee was scheduled, which
  is the correct behaviour for a title that fits.

**Review outcome: accepted.** Tested live on "Gravel Pit (feat. RZA, Method Man, Ghostface
Killah, Raekwon & U-God)" — scrolling reported perfect and smooth, so the approved 30 px/s and
both implementer's calls above stand as built.

**Still unverified, low priority:** whether the 250ms hover replay ever triggers accidentally
while reaching for the gear or hide buttons, and whether a hard-clipped title is legible enough
when Windows animations are switched off, since the marquee is disabled entirely in that case.
The optional title tooltip below would cover the second one.

**Open option, not implemented:** a tooltip on the title showing the full text would cover both
the reduce-motion case and impatient reading. Not built — it is a new UX affordance and needs
approval first.

### Window shape — black border removed (landed, approved 2026-08-04)

Raised by the Program Director during the 3.0 review: the gray rounded panel was surrounded by
a black square-edged band. Not intentional. The root window sat on `BG` (`#0A0A0A`) while
`_frame` was packed with `padx=6, pady=6`, so the root showed through as a border — measured at
9 physical px of `#0B0B0B` at 150% scaling. The outer corners stayed square because a
borderless Tk window paints every pixel of its rectangle, so the panel's `corner_radius` only
ever rounded something drawn *inside* a hard square.

Fixed by matching the root's `fg_color` to `SURFACE` and clipping the window itself to a
rounded rectangle with `SetWindowRgn` / `CreateRoundRectRgn` (`_round_window_corners`, applied
once from `_round_corners`). **The 6px padding was deliberately kept** so the interior spacing
tuned in Tiers 1 and 2 is untouched — verified unchanged: title clip still 232 logical,
metadata column 294, album art 20 logical from the window edge.

**Why not DWM:** `DWMWA_WINDOW_CORNER_PREFERENCE` needs Windows build 22000+. The Program
Director is on **build 19045 (Windows 10 22H2)**, so it is unavailable. This also means the
remaining Tier 3 item "Win11 rounded corners / shadow" would be a no-op on their machine and
needs rescoping — the rounding half is now done by region clip instead; only the shadow is left,
and that has no cheap equivalent on Win10.

**Why not a transparent colour key:** it was tested and does antialias the curve (8 soft pixels
vs the region's hard edge), but any pixel exactly matching the key colour becomes transparent,
which would speckle dark album art. A first attempt keyed on magenta produced 19 bright magenta
fringe pixels along the corner. The region clip's hard edge was judged the smaller cost and was
the option chosen.

Region behaviour worth knowing: it is expressed in window-relative pixels and Windows takes
ownership of the region handle, so it must not be deleted, and it only needs applying once. The
corner areas fall outside the window, so clicks there pass through to whatever is behind.

Validated with pixel-level screenshot probes against a bright backdrop (so artifacts could not
hide against a dark desktop), 21 checks passing: no dark band on any edge, all four corners cut
away, the curve meeting the top edge at x=17 against an expected 18 physical (12 logical × 1.5),
zero fringe or halo pixels, and the clip surviving hide/show, moving the window, opacity 0.55
and 1.0, and opening/closing the settings panel. A follow-up regression confirmed the marquee,
timed-lyric highlighting, all six state screens, and the art overlay all still behave.

The album art zoom overlay was **left square** by decision — its hairline frame is meant to read
as a card.

### 3.1 Window sizing presets (landed)

Approved with all four details confirmed up front: three presets, a segmented button in the
settings panel, lyric font size kept independent of the preset, and a size change always
returning the window to the tray corner. Widths were then equalised at the Program Director's
request — **all three presets are 420 logical px wide and differ only in height.**

The window is `overrideredirect`, so it has no resize border and these presets are the only way
to change its size. The old `minsize(340, 300)` was inert and is now the shared width plus the
shortest preset — `CTk.geometry()` clamps the `WxH` part against `minsize`, so a preset below it
would have silently not applied.

| Preset | Logical size | Lyrics panel | Fully visible lines at 14pt |
|--------|--------------|--------------|------------------------------|
| Compact | 420 × 360 | 199 logical px | 7 |
| Standard | 420 × 500 (default) | 339 logical px | 11 |
| Tall | 420 × 680 | 519 logical px | 17 |

The shared width is expressed structurally rather than by coincidence: `WINDOW_WIDTH` is a single
constant and `WINDOW_PRESET_HEIGHTS` maps each name to a height only, so no preset can drift off
the common width. That matters because the simplification below depends on it.

- **Control:** a `CTkSegmentedButton` at the top of the settings panel, above Lyrics size, with
  the logical dimensions as the live readout (`420 × 500`) matching the `14 pt` / `85%` pattern.
- **Persistence:** new `window_size` field on `AppSettings`, written to `settings.json` and
  clamped on load in `core/settings.py`. An unknown or missing name falls back to `standard`,
  and the name is lowercased/stripped, so files written by older builds still load. No change to
  SMTC polling, LRCLIB fetching or sync timing.
- **Position:** a size change re-snaps to the tray corner and *clears* any dragged position
  rather than rewriting it, so the corner keeps being recomputed on later launches. This was the
  Program Director's explicit choice over preserving placement.

**Three things the fixed-size assumption had hidden**, each now handled:

- The rounded-corner region keeps the dimensions it was cut for, so it must be recut after every
  resize or the square corners come back. `_round_corners`' docstring previously justified
  applying it once *because* the window was a fixed size; that reasoning no longer holds.
- The active lyric line has to be re-centred, because the panel height changes underneath it.
- `minsize`, as above.

**What the equal width bought:** the title row is now completely unaffected by a size change, so
the resize path no longer touches the marquee at all. An earlier draft cancelled any running pass
and reset the offset, because a narrower Compact would have shrunk the clip from 232 to 192
logical px and invalidated the measured travel. With one width the clip stays 232 × 28 logical at
every preset and the travel is identical, so a pass in flight is simply left to finish instead of
being snapped back to the start — one less visible glitch and less code. Verified by measurement:
327.3 logical px of travel at both Standard and Tall for the same title.

### Bug found and fixed during 3.1

Re-centring the active lyric immediately after `geometry()` scrolled it clean **off screen** when
shrinking Tall → Compact. A `geometry()` request is granted through a `Configure` event, which is
a normal event and not an idle task, so `update_idletasks()` does not wait for it and the measure
ran against the panel's previous height. Confirmed as timing rather than arithmetic: a second
re-centre pass landed the line dead centre. Fixed by deferring through `after_idle`
(`_schedule_recenter`), which runs once the Configure has landed. This is the same class of
mistake as the geometry coordinate-space bug — an assumption that a measurement is ready when it
is not.

### Validation performed

- `py_compile` clean on all modules; `--once` and `--lyrics-test` working against a live session
  (95 timed lines on "Gravel Pit", cache hit confirmed).
- 59-check headless harness, all passing: preset names matching `core.models.WINDOW_SIZES`;
  `minsize` equal to the shared width and shortest preset; a saved preset applied at launch
  (measured 630×1020 physical = 420×680 logical at 150% scaling); for all three presets the
  measured size, a 24-physical-px (16 logical) tray-corner gap on both edges, the rect fully
  inside the work area, and the Tier 2 title clip still 232 × 28 logical; all three presets
  measuring one identical physical width; settings round-trip including unknown, missing and
  unnormalised preset names; a dragged position cleared and the window returned to the corner;
  `_refresh_setting_readouts` proven not to resize or move (CustomTkinter's `set()` only fires the
  command for a real press); a marquee pass in flight surviving a resize, continuing to advance
  afterwards, and measuring identical travel at the new height; the active line still visible and
  re-centred to within 0.0px both when shrinking and when growing back, with its `current` tag
  intact; all six state screens rendering at Compact with the subline wrap still fitting; and the
  art overlay still centring to within 1px.
- Rounded corners verified two independent ways at each preset: `GetWindowRgn` + `GetRgnBox`
  confirming the region was recut to the new size, and `ImageGrab` pixel probes against a bright
  backdrop confirming all four corners cut away and no bright band at any edge midpoint.
- Full `MiniplayerApp` startup with a real tray icon, one SMTC poll and one sync tick, then a
  preset change driven exactly as the button drives it: `window_size` written to `settings.json`,
  `window_position` nulled in the same write, and a further poll and sync tick surviving the
  resize.

**Review outcome: accepted (2026-08-04).** All four open judgment calls were confirmed good as
built: the line counts read well at all three heights, the tray-corner launch behaviour is what
was wanted, and the segmented button's segments are clear. The selected segment is shown by
brightness (`#565656` against `#1E1E1E`) rather than accent green, because CustomTkinter shares
one text colour across all segments and white on `#1DB954` is only 3:1, which would miss the
4.5:1 bar the rest of the text clears — accepted as built.

### Remaining Tier 3 items — deferred, UX session closed

Neither was built, and the UX polish session was closed out after 3.1 was accepted. Both remain
approved in principle only, so both need their details re-confirmed before anyone starts.

- **Track-change transition.** Not started. No design decided beyond the principle.
- **Shadow (rescoped).** The rounded-corners half is already done via the region clip.
  `DWMWA_WINDOW_CORNER_PREFERENCE` needs Windows build 22000+ and the target machine is 19045, so
  the DWM route is unavailable. Windows 10 has no cheap shadow equivalent for a borderless
  window; the only realistic implementation is a second layered always-on-top window behind the
  main one, which then has to track every move, hide, size change and opacity change and can be
  caught out of sync. **Recommendation: drop this item** rather than carry that complexity.

## Album art source — iTunes (accepted)

Replaces SMTC’s 300×300 branded thumbnails with clean iTunes artwork. UX art sizing, rounding,
hover, tooltip gating, and zoom overlay chrome are unchanged; only the byte source and a
centre-crop for non-square images were added.

### What landed

- **`core/artwork.py`:** `fetch_album_art(title, artist)` hits the iTunes Search API (no key),
  rewrites `artworkUrl100` to prefer `1200x1200bb` then `600x600bb`, streams with an 8s timeout
  and a 5 MB size cap, and returns raw encoded bytes or `None`.
- **`main.py`:** the lyrics worker fetches iTunes art first and marshals a successful result
  through `self._window.schedule(...)` + generation guard **before** waiting on LRCLIB, so art
  can paint as soon as it arrives. Failures never call `set_album_art(None)`, so the previous
  track’s art stays until new clean bytes arrive (placeholder only on first launch / idle /
  total failure with no prior art). SMTC thumbnail reads are no longer used for display.
- **`ui/miniplayer.py`:** `_centre_crop_square` runs before resize in `_rounded_thumbnail` and
  `_refresh_zoom_overlay`. Entry point remains `set_album_art(image_bytes)` only. Untouched:
  `ART_SIZE` / radius / padding, hover brightness, overlay border/inset/centering, tooltip
  gating, and the live `_refresh_zoom_overlay` call when the overlay is already open.

### Validation performed

- `py_compile` clean on `core/artwork.py`, `main.py`, `ui/miniplayer.py`.
- Centre-crop: 800×400 → 400×400; already-square unchanged; tall 200×600 through
  `_rounded_thumbnail` yields a true `ART_SIZE` square (no squash).
- URL rewrite: `100x100bb` → `1200x1200bb` / `600x600bb`.
- Live iTunes fetch for “Gravel Pit” / “Wu-Tang Clan”: 103 379 bytes, **1200×1200 JPEG**.

**Review outcome: accepted.** Clean hi-res art confirmed; previous cover held across track
changes; overlay growth toward 600 logical px is intended.

### Follow-up — album-aware match (local, pre-v1.1)

iTunes often ranks compilation / single entries above the studio album when searching by
title + artist only (seen on Emilíana Torrini “To Be Free” / “Dead Things” → *Rarities*).
`fetch_album_art` now takes the SMTC album name, includes it in the search term, and scores
hits by track + collection match so the playing album wins. Validated: those two tracks now
pick *Love in the Time of Science* (old first-hit was *Rarities*). **Review outcome: accepted** on the Emilíana Torrini album; packaged as v1.1.0.

### Prior handoff notes (kept for reference)

The Program Director asked the core developer to supply a better thumbnail than the 300×300
SMTC one, while keeping the art sizing, positioning and border work from Phase 5a / Tier 2 / Tier
3 intact. The contract and caveats that guided the work are below.

### The contract

`MiniplayerWindow.set_album_art(image_bytes: bytes | None)` in `ui/miniplayer.py` is the only
entry point, and it takes **raw encoded image bytes** — not a path, URL, PIL image or CTkImage.
Anything Pillow can open is fine (JPEG, PNG, WebP). It is called from two places today:
`update_track` (when `NowPlaying.thumbnail_bytes` is set) and `main._apply_lyrics_result` (with
bytes the lyrics worker fetched). Feed a new source in through the same door and every visual
behaviour below is preserved for free.

`set_album_art` already treats its input as untrusted: the decode is wrapped in try/except and
falls back to the placeholder on any failure, per the security baseline. Keep that property.

### What is source-independent and needs no attention

- The inline thumbnail's **size and position** — `ART_SIZE = 72`, `ART_RADIUS = 6`, packed with
  `padx=(0, 14)` inside a `meta_row` with `padx=14`, measuring 20 logical px from the window edge.
  A higher-resolution source only makes the LANCZOS downscale to 72px sharper.
- The **rounded corners of the inline art**, which live in the image's own alpha mask
  (`_rounded_thumbnail`) rather than on the widget, because the image covers the label's
  `corner_radius`. This is why the source must go through `set_album_art` and not hand in a
  pre-built `CTkImage` — doing that silently loses the rounding.
- The **hover brightness** variant, the **click-to-zoom** binding, and the art **tooltip**
  gating (`enabled=lambda: self._art_bytes is not None`).
- The overlay's **border and inset** — a `HAIRLINE` 1px frame around an 8px `ART_ZOOM_INSET`
  matte, which is what makes it read as a card. Its **centering** on the Windows work area is
  also source-independent.
- The **unsharp mask** self-disables: it only applies when `physical >= native *
  ART_SHARPEN_ABOVE` (1.5), so a high-resolution source simply stops triggering it. No change
  needed, and no risk of over-sharpening already-sharp art.

### Four caveats, in order of how likely they are to bite

**1. Non-square art will be visibly squashed.** This is the most likely regression.
`_rounded_thumbnail` does `image.resize((size, size))` unconditionally, and the overlay does the
same via `image.resize((physical, physical))`. Neither crops or preserves aspect ratio, because
SMTC art has always been square so it never came up. If the new source can ever return a
rectangular image, add a centre-crop to square **before** the resize in both places. The overlay
additionally takes `native = min(image.width, image.height)`, so a rectangular source also skews
its size calculation.

**2. The overlay will grow from 480 to 600 logical px, which is a size change.** This one needs
a decision. `_refresh_zoom_overlay` deliberately sizes from the source so that large art is not
downscaled: `logical = min(ART_ZOOM_MAX, max(ART_ZOOM_MIN, native / scaling))`. With today's
300×300 source at 150% scaling that yields 300/1.5 = 200, clamped up to the 480 minimum — so the
overlay is 480 logical today, and it upscales. Once the source exceeds roughly 900px it will
reach the 600 maximum instead. That is the designed behaviour and is almost certainly what the
Program Director wants from a better thumbnail, but it does mean the overlay gets bigger. **If the
overlay must stay exactly its current size, set `ART_ZOOM_MIN` and `ART_ZOOM_MAX` both to 480.**
The bounds are expressed in logical px and are independent of the source either way.

**3. Anything network-backed must stay off the UI thread and must not clear the art.** If the new
source involves an HTTP fetch, do it on a worker thread and marshal the result back through
`self._window.schedule(...)`, exactly as `main._fetch_lyrics_worker` does for the current art
fetch. Never call `set_album_art` from a worker thread. Also preserve the truthiness guards at
both call sites (`if track.thumbnail_bytes:` and `if thumb_bytes:`): they are what stop a poll
with no art from clearing good art. `set_album_art(None)` runs `_set_placeholder_art`, which
closes the zoom overlay, drops `_art_bytes` and disables the tooltip — so a slower source that
clears first would flash the ♪ placeholder on every track change. Note the existing trade-off
this creates: the previous track's art stays visible until new art arrives, so a slower source
widens that stale window. Per the spec, any network call needs a timeout and error handling.

**4. Keep a size cap and mind the geometry rule.** `core/smtc.py` caps thumbnails at
`_THUMB_MAX_BYTES = 5_000_000`; keep an equivalent sanity limit, since the original bytes are
retained in `_art_bytes` for the lifetime of the track (the overlay re-decodes from them, which
is what gives it full source quality). And if `_refresh_zoom_overlay`'s `zoom.geometry(...)` line
is touched at all, preserve the coordinate-space split: CustomTkinter scales the `WxH` part and
passes `+x+y` through as physical pixels. That bug has been fixed twice in this project.

### Also worth knowing

The art overlay is **square by decision**, not by accident, and its hairline frame is meant to
read as a card. `set_album_art` calls `_refresh_zoom_overlay` when the overlay is already open, so
the overlay follows track changes live — preserve that call. Finally, "no Spotify Web API and no
OAuth" is a locked architectural decision: if the intended new thumbnail source is the Spotify
Web API, that needs the Program Director's explicit sign-off before it is built, because it would
also reintroduce the credential handling the project has deliberately avoided.

## Summary of what landed

- **0–2:** Python app skeleton; SMTC now-playing (PyWinRT); always-on-top CustomTkinter window + system tray.
- **3–4b:** LRCLIB lyrics; timed LRC highlight/scroll; monotonic playhead; sticky highlight; 550ms lead; 100ms sync / 500ms SMTC poll.
- **5–5a:** Album art; settings + window position persistence; packaging (`dist\LyricsMiniplayer.exe`); click-to-zoom 600×600 overlay centered on Windows work area.

## Key paths

- Spec: `Spotify-Lyrics-Miniplayer-Product-Handoff.md`
- Entry: `main.py`
- Core: `core/smtc.py`, `core/lyrics.py`, `core/settings.py`, `core/models.py`
- UI: `ui/miniplayer.py`, `ui/tray.py`
- Build: `build.ps1` → `dist\LyricsMiniplayer.exe`
- Settings: `%APPDATA%\LyricsMiniplayer\settings.json`

## v1.2.1 release package

`build.ps1` builds the onefile exe and stages release artifacts under `dist\`:

- `LyricsMiniplayer-v1.2.1.zip` — `LyricsMiniplayer.exe`, `README.txt`, `LICENSE`
- `SHA256SUMS` — checksums for the exe and zip
- `sbom.cdx.json` — CycloneDX SBOM from the hashed lockfile
- `PROVENANCE.md` — Python version, lockfile hash, host OS/arch, build command

Repo docs for the release: root `README.md`, `RELEASE_NOTES_v1.2.1.md`, `SECURITY.md`,
`LICENSE`, `PHASE_STATUS.md`, and the product handoff. Attach the zip plus verification
artifacts to a GitHub Release named `v1.2.1`; do not commit `dist/` (already gitignored).

## v1.2.0 release package

Same artifact set as v1.2.1; zip name was `LyricsMiniplayer-v1.2.0.zip`. See
`RELEASE_NOTES_v1.2.0.md`.

## v1.1.0 release package

`build.ps1` (at the time) staged `dist\LyricsMiniplayer-v1.1.0.zip` containing the exe,
`README.txt`, and `LICENSE`.

## Packaged build verification (2026-08-04, pre-v1 art pass)

`build.ps1` re-run after item 3.1 was accepted; exit code 0, no missing-module warnings for
`customtkinter`, `winrt`, `PIL`, `pystray` or `requests`. `dist\LyricsMiniplayer.exe` is 23.3 MB
and now newer than every source file.

Verified by launching the exe itself and inspecting the real window from a DPI-aware process:

- Window rect 630×750 physical at 3186,1326 — identical to the dev-mode measurement of the
  Standard preset, including the tray-corner position.
- Process DPI awareness reports 2 (per-monitor), and `GetDpiForWindow` returns 144, so the
  packaged build is DPI-aware and not being bitmap-scaled by Windows.
- `GetWindowRgn` returns a region of 0,0,630,750, so the rounded-corner clip survives packaging.
- Live behaviour confirmed on screen against the running Spotify session: real album art, the
  title clipped to its marquee frame, `Paused · 0:48 / 4:17 · Synced`, and the correct timed
  lyric line highlighted white/bold and centred in the panel.
- Working set 77.8 MB for the main process plus 6.8 MB for the onefile bootstrap child, against
  the spec's "< 80 MB while idle" target.

**Measurement gotcha for anyone repeating this:** a DPI-unaware querying process gets virtualised
coordinates back from `GetWindowRect`, which made the window first appear to be 420×500 physical.
Call `SetProcessDpiAwareness(2)` in the querying process before measuring.

Last updated: 2026-08-05 (v1.2.1: reject degenerate plain LRCLIB lyrics / fall through to search.
Prior: v1.2.0 security hardening; v1.1.0 album-aware iTunes art; v1.0.0 packaged)
