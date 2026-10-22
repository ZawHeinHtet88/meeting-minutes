# AI Meeting Minutes CLI

Convert local meeting recordings into accurate Burmese transcripts and standalone HTML minutes. The pipeline extracts compact WAV audio locally, transcribes it with Gemini Flash through your authenticated Google Antigravity CLI session, and uses your authenticated OpenCode session for conservative cleanup and structured meeting analysis. No separate API key is required.

## Features

- MP4, MP3, WAV, M4A, and WEBM input
- Recursive batch processing and `--force` regeneration
- Cached conversion to 16 kHz mono WAV
- Burmese/English transcription through Antigravity CLI and Gemini Flash
- Best-effort speaker diarization with anonymous `Speaker 1`, `Speaker 2`, … labels
- Automatic audio chunking below Antigravity's attachment limit
- Timestamped transcript segments with wrong-script and Unicode quality checks
- Conservative OpenCode transcript cleanup
- Project-local `meeting-minutes-summarizer` OpenCode skill
- Long-transcript analysis chunking and consolidation
- Content-addressed audio, transcript, cleanup, and analysis caches
- Per-chunk transcript caching so interrupted long recordings resume instead of restarting
- Automatic subdivision of a chunk when both Gemini transcription prompts are filter-blocked
- Responsive, safely escaped standalone HTML

## Prerequisites

- Python 3.10 or newer
- [Antigravity CLI](https://antigravity.google/docs/cli/install), authenticated with Google
- [OpenCode V2](https://opencode.ai/v2/docs/cli), authenticated with the provider used for analysis

Install Antigravity CLI on Windows PowerShell:

```powershell
irm https://antigravity.google/cli/install.ps1 | iex
agy
```

Complete the one-time Google sign-in, then verify the transcription model:

```powershell
agy models
```

Verify OpenCode's analysis model:

```powershell
opencode models
```

## Installation

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

macOS/Linux activation and environment setup:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env`:

```dotenv
OPENCODE_MODEL=openai/gpt-6-luna
OPENCODE_VARIANT=high

ANTIGRAVITY_MODEL=gemini-3.8-flash-medium
ANTIGRAVITY_TIMEOUT=15m
TRANSCRIPTION_LANGUAGE=my

OUTPUT_DIR=site
CACHE_DIR=output/.cache
```

All AI model selections come from `.env`; the application never silently switches models.

### Configuration

| Variable | Meaning |
| --- | --- |
| `OPENCODE_MODEL` | Exact provider/model ID shown by `opencode models` |
| `OPENCODE_VARIANT` | OpenCode reasoning variant, such as `high` |
| `ANTIGRAVITY_MODEL` | Exact model slug shown by `agy models` |
| `ANTIGRAVITY_TIMEOUT` | Maximum time for each audio chunk, such as `15m` |
| `TRANSCRIPTION_LANGUAGE` | `my`, `en`, or `auto`; use `my` for Burmese meetings |
| `OUTPUT_DIR` | Static-site directory containing only `index.html` and report HTML files |
| `CACHE_DIR` | Private working cache for extracted audio, transcripts, and AI responses |

The summarization instructions live in `.opencode/skills/meeting-minutes-summarizer/SKILL.md`. OpenCode runs from the project directory so the project-local skill is discovered even when `meeting.py` is launched elsewhere.

## Usage

Process one recording:

```powershell
python meeting.py meeting.mp4
```

Process recordings recursively:

```powershell
python meeting.py .\recordings\
```

Regenerate transcription, analysis, and report:

```powershell
python meeting.py meeting.mp4 --force
```

Reports are written directly into `OUTPUT_DIR`, and `index.html` is regenerated as a landing page linking every report. Cache/audio files stay outside the static-site folder. Existing reports are skipped unless `--force` is supplied.

## Pipeline and caching

1. PyAV (Python bindings for FFmpeg libraries) extracts 16 kHz mono PCM WAV into `CACHE_DIR/audio/`; no separate `ffmpeg.exe` command is required.
2. WAV files are split into attachment-safe chunks of at most two minutes under `CACHE_DIR/audio_chunks/`; shorter chunks reduce omissions and timestamp drift.
3. Antigravity headless mode attaches each WAV to the configured Gemini Flash model and returns strictly validated timestamped JSON segments. Each transcription run combines Antigravity's terminal sandbox with one-run tool approval because headless media preparation cannot display an interactive permission prompt.
   A harmless Gemini filter false-positive is retried once with a neutral transcription prompt using the same configured model.
   Placeholder/example responses are also rejected and retried rather than being written into a report.
4. OpenCode conservatively cleans the text, applies `@meeting-minutes-summarizer`, and returns validated JSON.
5. Python renders the escaped standalone HTML report.

Transcript caches include the audio hash, Antigravity model, language, prompt version, and cache format. AI caches include the transcript hash and exact OpenCode model/variant. Deleting `CACHE_DIR` is safe; it only causes work to run again.

For long recordings, every successful audio chunk is saved immediately under
`CACHE_DIR/transcript_chunks/`. If a later chunk fails, run the same command again
without `--force`; completed chunks are reused. When both prompts are blocked by a
Gemini filter, only that chunk is split into shorter clips and retried automatically.

## Static hosting

The generated `site/` folder is a complete static website. Preview it locally:

```powershell
python -m http.server 8000 --directory site
```

Then open `http://localhost:8000`.

For public hosting, the simplest option is [Netlify Drop](https://app.netlify.com/drop): drag the entire `site/` folder onto the page. Cloudflare Pages and GitHub Pages also work because the site contains only standalone HTML files and needs no server-side runtime.

### Publish source code and the site together on GitHub

This repository includes `.github/workflows/pages.yml`. It publishes only `site/` to
GitHub Pages while keeping the Python source code in the same repository. In the GitHub
repository, open **Settings → Pages** and set **Source** to **GitHub Actions**. Every push
to `main` that changes `site/` automatically redeploys the website.

The committed repository should include `.env.example`, never `.env`. `output/`, audio,
transcript caches, virtual environments, and credentials remain excluded by `.gitignore`.

Meeting reports may contain private information. Review them before publishing and use access controls when public hosting is inappropriate.

## Accuracy and privacy

Audio is extracted locally, then attached to Google Antigravity for transcription. Transcript text is sent to the configured OpenCode provider for cleanup and analysis. Do not use this pipeline for recordings that those services are not permitted to process.

The program rejects empty, invalid-Unicode, and obvious wrong-script transcripts rather than generating misleading minutes. AI summaries can still make mistakes; review the transcript and minutes before relying on decisions or action items.

## Tests

Provider calls are mocked in automated tests:

```powershell
pytest -q
```

## Troubleshooting

- **Antigravity CLI not found:** install it from the official link, restart the terminal, or verify `%LOCALAPPDATA%\agy\bin\agy.exe`.
- **Antigravity authentication error:** run `agy` interactively once and complete Google OAuth.
- **Antigravity model unavailable:** run `agy models` and copy an exact slug into `.env`.
- **OpenCode CLI/model error:** run `opencode models` and verify both OpenCode settings.
- **Transcription times out:** increase `ANTIGRAVITY_TIMEOUT` (for example, `30m`).
- **Poor Burmese output:** set `TRANSCRIPTION_LANGUAGE=my` and use a current Gemini Flash model from `agy models`.

Never commit `.env`. Only `.env.example` belongs in source control.
