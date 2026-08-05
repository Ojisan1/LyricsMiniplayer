# Product Requirements & Implementation Handoff

**Project Name:** Spotify Lyrics Miniplayer  
**Version:** 1.2.0  
**Date:** 2026-08-04 (original); status updated 2026-08-05  
**Status:** Shipped (historical product / implementation spec — not a “ready for development” brief)  

---

## 1. Project Overview

**One-sentence vision:**  
A lightweight, always-on-top Windows floating miniplayer that shows the currently playing Spotify track and time-synced lyrics that scroll in real time — with zero configuration required from the user.

**Problem being solved:**  
Spotify’s native miniplayer shows album art and track info but does not display lyrics. The full Spotify lyrics view requires switching focus to the main application. Users who want to follow lyrics while working in other applications currently have no clean, always-visible, low-friction solution that stays on top of other windows and requires no API keys or account linking.

**Target users:**  
Individual Windows users who listen to Spotify while working, coding, writing, or browsing and want synchronized lyrics visible without interrupting their current application focus. Primary user is the project owner (technical, values simplicity and zero-config tools).

**Success looks like:**  
- The app correctly detects the current Spotify track within 1–2 seconds of a change.  
- Timed lyrics appear and stay reasonably synchronized for the majority of tracks the user plays.  
- The floating window stays visible and useful without becoming distracting or resource-heavy.  
- The user can install and run the application with zero Spotify developer setup or API keys.

---

## 2. Team & Roles

| Role                    | Owner          | Responsibilities                                      |
|-------------------------|----------------|-------------------------------------------------------|
| Program Director        | User           | Final decisions, priorities, approvals                |
| Product Manager         | SuperGrok      | Requirements, prioritization, acceptance criteria     |
| Backend + Light Frontend| Cursor Grok    | Core logic, SMTC integration, lyrics fetching, light UI scaffolding |
| Frontend + UX Designer  | Claude         | Visual design, interaction design, polished UI        |

---

## 3. Goals & Non-Goals

### Goals
- Deliver a reliable floating “now playing + synced lyrics” window for Spotify on Windows.
- Use only free tools and libraries.
- Require zero configuration from the end user (no Spotify API keys, no login).
- Keep the application lightweight and non-intrusive.
- Build in clear phases with explicit approval gates.

### Non-Goals (Explicitly out of scope for this version)
- Playback controls (play / pause / skip / seek buttons)
- Displaying the Spotify queue
- Support for music players other than Spotify
- macOS or Linux support
- Lyrics editing, contribution, or offline lyric libraries
- Complex theming engines or high-customization UI
- Automatic updates / auto-updater

---

## 4. Target Platform & Technology Decisions

**Primary platform(s):**  
Windows 10 and Windows 11 (desktop)

**Confirmed technology choices:**  
- Language / Runtime: Python 3.11+ (developed/tested through 3.14)  
- Framework(s): CustomTkinter for the UI  
- Now-playing source: Windows System Media Transport Controls (SMTC) via PyWinRT (`winrt-Windows.Media.Control` and related packages; replaced the older `winsdk` package, which does not install cleanly on newer Python without a C++ toolchain)  
- Lyrics source: LRCLIB (https://lrclib.net) – free, no API key  
- Album art: iTunes Search API (no API key)  
- System tray: `pystray` + Pillow  
- Packaging: PyInstaller  
- Auth approach: None required  
- Key libraries: `customtkinter`, PyWinRT projections, `pystray`, `Pillow`, `requests`  
- Hosting / deployment target: Local executable (single .exe or simple folder distribution via GitHub Releases)

**Any hard constraints:**  
- Must run without any Spotify Developer account or client ID/secret  
- Must work offline for the UI shell (lyrics fetch requires network)  
- Prefer simple, readable code over clever abstractions  
- Development must be fully workable inside Cursor Pro with Grok

---

## 5. Key Architectural Decisions Already Made

These decisions should **not** be revisited during implementation unless a blocking technical issue is discovered:

- Now-playing data comes exclusively from Windows SMTC (not the Spotify Web API).  
- Timed lyrics come from LRCLIB.  
- The application is a system-tray resident process with a separate always-on-top floating window.  
- Python + CustomTkinter is the chosen stack for v1.  
- No user accounts, no cloud backend, no persistent server component.  
- Polling interval for SMTC will be approximately 1 second (can be tuned later).  
- Lyrics are fetched on track change and cached in memory (disk cache is optional for later).

---

## 6. High-Level Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     System Tray                         │
│              (Show / Hide / Quit menu)                  │
└──────────────────────────┬──────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│              Floating Miniplayer Window                 │
│  ┌─────────────┐  Title + Artist                        │
│  │  Album Art  │  ─────────────────────────────────     │
│  └─────────────┘  Timed Lyrics (scrolling + highlight)  │
│                   Status line                           │
└─────────────────────────────────────────────────────────┘
         ▲                              ▲
         │                              │
    SMTC Reader                    Lyrics Service
  (core/smtc.py)                 (core/lyrics.py)
         │                              │
         ▼                              ▼
  Windows SMTC API              LRCLIB HTTP API
  (title, artist,               (plain + timed LRC)
   position, state)
```

**Data flow:**
1. Background poll of SMTC every ~1s.
2. On track change → request lyrics from LRCLIB using title + artist + duration.
3. Continuous position updates drive the lyric line highlight and scroll position.

---

## 7. Data Model / Core Entities

**NowPlaying**
- title: str
- artist: str
- album: str
- duration_ms: int
- position_ms: int
- is_playing: bool
- thumbnail_bytes: optional bytes

**LyricLine**
- time_ms: int
- text: str

**LyricsResult**
- plain_lyrics: str | None
- timed_lines: list[LyricLine] | None
- source: str
- is_instrumental: bool
- error: str | None

**AppSettings** (future / Phase 5)
- window_position: (x, y)
- opacity: float
- font_size: int
- always_on_top: bool

---

## 8. Functional Requirements by Phase

> **Important Instruction for the implementing agent (Cursor Grok):**  
> Work **only** on the current phase.  
> At the end of every phase you must:  
> 1. Summarize exactly what was completed  
> 2. List the testing and validation performed  
> 3. Update any status / progress files  
> 4. Stop and wait for explicit user approval before starting the next phase  

### Phase 0 – Project Foundation
**Goal:** Establish a clean, runnable project skeleton.  
**Scope:**  
- Create folder structure  
- Write `requirements.txt`  
- Create empty modules with clear docstrings  
- Minimal `main.py` that starts without error  

**Acceptance Criteria:**  
- [ ] Project installs cleanly with `pip install -r requirements.txt`  
- [ ] `python main.py` launches without import or runtime errors  
- [ ] Folder structure matches the agreed layout  

### Phase 1 – Now Playing via SMTC
**Goal:** Reliably detect and report the currently playing Spotify track.  
**Scope:**  
- Implement SMTC reader (`core/smtc.py`)  
- Extract title, artist, album, duration, position, play state  
- Handle no-session, paused, and track-change cases  
- Basic live output (console or simple window)  

**Acceptance Criteria:**  
- [ ] Correctly reports track title and artist when Spotify is playing  
- [ ] Updates within 1–2 seconds of a track change  
- [ ] Correctly reflects paused vs playing state  
- [ ] Does not crash when Spotify is closed or no media is active  
- [ ] Works with both free and Premium Spotify accounts  

### Phase 2 – Floating Miniplayer Shell
**Goal:** Create the always-on-top floating window and system tray presence.  
**Scope:**  
- Floating window with dark theme  
- Display of title and artist  
- Always-on-top behavior  
- System tray icon with Show / Hide / Quit  
- Window can be moved and sent to tray  

**Acceptance Criteria:**  
- [ ] Window stays above other applications  
- [ ] Can be freely dragged  
- [ ] Closing or minimizing sends it to the system tray (does not quit the process)  
- [ ] Tray icon restores the window correctly  
- [ ] Title and artist update live from SMTC data  
- [ ] No unwanted focus stealing on track change  

### Phase 3 – Lyrics Fetching (Plain Text)
**Goal:** Fetch and display plain (non-timed) lyrics for the current track.  
**Scope:**  
- LRCLIB integration (`core/lyrics.py`)  
- Display lyrics in the miniplayer  
- Handle “no lyrics found” and network errors  
- Simple in-memory cache  

**Acceptance Criteria:**  
- [ ] Lyrics appear for common tracks  
- [ ] Clear message when lyrics are unavailable  
- [ ] Network failures do not crash the application  
- [ ] Cache prevents repeated identical requests for the same track  
- [ ] Lyrics are readable (contrast, wrapping, font size)  
- [ ] Works with the previously discussed Emilíana Torrini tracks  

### Phase 4 – Timed Lyrics + Scrolling Sync
**Goal:** Synchronize lyric highlighting and scrolling with actual playback position.  
**Scope:**  
- Parse timed LRC data from LRCLIB  
- Drive highlight from SMTC position  
- Keep current line visible / centered  
- Handle seeks, pauses, and track changes cleanly  

**Acceptance Criteria:**  
- [ ] Current line is correctly highlighted as the song plays  
- [ ] Scrolling is smooth under normal conditions  
- [ ] Seeking in Spotify updates the highlight within ~1 second  
- [ ] Pausing freezes the highlight at the correct line  
- [ ] Track change resets lyrics cleanly  
- [ ] No major timing drift over a typical 4–5 minute song  
- [ ] UI remains responsive while updating  

### Phase 5 – Polish, Robustness & Packaging
**Goal:** Make the application daily-driver ready and distributable.  
**Scope:**  
- Album art display  
- Better loading and error states  
- Window position memory  
- Basic settings (opacity, font size, always-on-top)  
- Packaging with PyInstaller  
- README  

**Acceptance Criteria:**  
- [ ] Album art appears when available  
- [ ] Application starts cleanly from the packaged executable  
- [ ] Can run for 30+ minutes without degradation  
- [ ] Memory usage stays reasonable  
- [ ] All previous acceptance criteria still pass  
- [ ] No console window in the packaged build  
- [ ] Basic README exists with usage instructions  

---

## 9. Non-Functional Requirements

- **Performance:** Target < 80 MB RAM while idle; smooth lyric updates without UI stuttering.  
- **Reliability / Error handling:** Network failures, missing lyrics, and SMTC unavailability must be handled gracefully with user-visible status messages. Never crash the process.  
- **Observability:** Basic console logging during development; no heavy telemetry required for v1.  
- **Accessibility baseline:** Sufficient color contrast for dark theme; readable font sizes.  
- **Internationalization:** Not required for v1 (English UI is acceptable).

---

## 10. Security Baseline (Required Practices)

Even though this is a local desktop application with minimal attack surface, the following practices must still be followed:

- Use only well-established, maintained libraries.  
- All data received from LRCLIB must be treated as untrusted input (validate structure before use).  
- Do not execute or evaluate any content received from external services.  
- Store no secrets in code (none are required for this project).  
- When packaging, avoid including unnecessary debug information or development files.  
- Do not log sensitive user data (track history beyond the current session is not stored).

---

## 11. Frontend / UX Notes (for Claude)

**Design direction:**  
Dark, minimal, inspired by Spotify’s own miniplayer aesthetic. Prefer clarity and low visual noise over decoration. Soft rounded corners, restrained use of accent color (Spotify green sparingly).

**Key user flows that need polished UI:**  
- First launch / nothing playing state  
- Track change transition  
- Lyrics loading → lyrics appeared  
- No lyrics available state  
- Seeking / pause behavior of the highlight  

**Components that should be built or refined by Claude:**  
- Overall miniplayer layout and spacing  
- Lyric line highlighting treatment  
- Album art presentation  
- Status / empty states  
- System tray menu clarity  

**Any specific interaction or visual requirements:**  
- Current lyric line should be clearly distinguishable (weight, color, or subtle background).  
- Scrolling should feel calm, not jumpy.  
- Window should feel “light” and unobtrusive.

---

## 12. Constraints & Guardrails

- Do not expand scope beyond what is written in this document without approval.  
- Prefer boring, proven solutions over clever new ones.  
- Keep the codebase simple and readable.  
- Work strictly phase-by-phase. Never start the next phase without explicit user approval.  
- All external network calls must have timeouts and error handling.  
- Avoid introducing new major dependencies without discussion.

---

## 13. Open Questions & Risks

| Question / Risk                              | Owner       | Status | Notes |
|----------------------------------------------|-------------|--------|-------|
| How reliable is album art retrieval via SMTC across Spotify versions? | Cursor Grok | Open   | May need fallback |
| LRCLIB rate limiting or occasional misses on less popular tracks | Product     | Open   | Acceptable for v1; monitor during testing |
| CustomTkinter limitations for very smooth scrolling | Cursor Grok | Open   | May need to evaluate canvas or alternative approach in Phase 4 |
| Long-term maintenance of PyWinRT SMTC bindings | Product   | Mitigated | Switched from `winsdk` to maintained PyWinRT projections for Python 3.14+ |

---

## 14. Definition of Done (Overall)

- [ ] All phases completed and explicitly approved by the Program Director  
- [ ] Acceptance criteria for every phase met  
- [ ] Security baseline practices followed  
- [ ] Code is clean, readable, and follows the structure defined in this document  
- [ ] Basic README with installation and usage instructions exists  
- [ ] Application can be packaged and run as a standalone executable  
- [ ] Ready for any desired visual polish pass by Claude  

---

**End of Handoff Document**

*This document is a historical product / implementation spec for v1. For current user-facing docs, start at `README.md` and the GitHub Releases page. Ambiguity about shipped behavior should be checked against the code and README rather than assumed from older phase language here.*
