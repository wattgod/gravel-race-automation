# Voice-recorded walkthrough (D19)

Talk through a page while using it. Get back a list of fixes per section.

## Record

1. Open any page built by `wordpress/generate_season_review.py` (e.g.
   `/goals/`, or an athlete's season review link) with `?walkthrough=1`
   added to the URL. A small **Record walkthrough** button appears in the
   bottom-right corner. Without the flag, nothing about the page changes.
2. Click it, allow the microphone, and talk through the page as you use it
   — click around, fill fields, say what's wrong out loud.
3. Click the button again (now **Stop walkthrough**) when you're done. Two
   files download: `walkthrough-<page>-<timestamp>.webm` (the audio) and
   `walkthrough-<page>-<timestamp>.json` (a timeline of which section was
   on screen and which fields you touched, timestamped). Nothing is
   uploaded anywhere — both files only ever exist on your machine.

## Process

1. First time only: `python3 -m venv ~/Walkthroughs/.venv && ~/Walkthroughs/.venv/bin/pip install mlx-whisper`
   (Apple Silicon; see below for other machines). `ffmpeg` must also be
   installed (`brew install ffmpeg`).
2. Move (or leave — the script watches this folder) both downloaded files
   into `~/Walkthroughs/inbox/`.
3. Run:
   ```
   ~/Walkthroughs/.venv/bin/python3 scripts/walkthrough.py
   ```
   or point it at specific files: `scripts/walkthrough.py a.webm a.json`.
4. Read the result at `~/Walkthroughs/<page>-<timestamp>.md` — grouped by
   section, each point tagged **friction** / **copy fix** / **bug** /
   **idea**, quoting what you said. The source files move to
   `~/Walkthroughs/done/`.
5. Anything tagged **friction** is also appended to this repo's
   `PAPERCUTS.md`, if the `papercut` CLI is on your PATH.

An audio file with no matching `.json` (e.g. a Voice Memos `.m4a` you
recorded separately) still works — it's grouped by two-minute time chunks
instead of by section.

## Transcription backend

Local only, tried in this order: `mlx-whisper` (fastest on Apple Silicon),
`openai-whisper`, `faster-whisper`, then a `whisper-cli`/`main` binary from
whisper.cpp on PATH. If none are available the script tells you what to
install rather than guessing or calling a cloud API — there is no
Anthropic API key on this machine, and this tool never uses one.

## Tagging

Set `OPENROUTER_API_KEY` to get the friction / copy fix / bug / idea tags
and a one-line note per item (cheap model, `google/gemini-2.5-flash` by
default — same model `papercut-review` uses). Without that key, the script
still writes the markdown, just as a plain per-section transcript with no
tags.
