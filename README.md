---
title: Vertical Clipper
emoji: 🎬
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
short_description: Turn 16:9 videos into 9:16 clips that follow the speaker
---

# Vertical Clipper

**Live demo:** _link to be added after deployment (see section 5b)_

> The demo runs on a free server. It sleeps when idle (the first visit can take about a minute to wake up), stores files only for a few hours, and handles one or two videos at a time. **YouTube sometimes blocks downloads from hosting servers.** If you see that message, download the video yourself and use **Upload video**.

Turn a long 16:9 video (a YouTube link or an uploaded file) into vertical 9:16 clips, ready for Shorts, Reels and TikTok. The tool splits the video into clips automatically, lets you adjust each clip's start and end, and crops every clip so the speaker stays in frame.

Everything runs on your own computer. It uses only free and open-source software: FFmpeg, Python, OpenCV and yt-dlp. No API keys or accounts are needed.

---

## 1. Quick start with Docker (recommended)

1. Install [Docker Desktop](https://www.docker.com/products/docker-desktop/) and start it.
2. Open a terminal in this folder and run:
   ```
   docker compose up --build
   ```
3. Open http://localhost:8000 in your browser.

Your uploads and exported clips are saved in the `workdir` folder next to this file.

To stop, press `Ctrl+C` in the terminal, or run `docker compose down`.

## 2. Run without Docker (Windows, macOS or Linux)

You need Python 3.11 or newer. FFmpeg is included automatically, so you do not need to install it separately. If you already have FFmpeg, the tool uses it.

```
python -m venv .venv
.venv\Scripts\activate          (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
python -m uvicorn app.main:app --port 8000
```

Then open http://localhost:8000.

## 3. How to use it

1. **Add a video.** Paste a YouTube link and press *Load from YouTube*, or choose a file with *Upload video*. Files can be MP4, MOV, MKV or WebM, up to 2 GB by default.
2. **Wait for processing.** The progress bar shows each step. Scene detection can take a few minutes for long videos.
3. **Review the clips.** The tool creates clips automatically at scene changes, with no clip longer than 60 seconds. You can:
   - change a clip's **start** and **end** with the number boxes, the ±1 s buttons, or *Use current time* while the video is playing;
   - press **Save timing** after you change a clip;
   - press **Add clip from current time** to create a new clip.
4. **Export.** Press **Export clip** for one clip, or **Export all clips** for everything. When it is ready, use **Download clip** or **Download all (.zip)**.

Each exported file is 1080 × 1920 (MP4, H.264 video and AAC audio).

## 4. How the vertical crop works

- A 9:16 window the full height of the video is cut from each frame.
- The tool looks for faces about five times per second and follows the largest one.
- The crop position is smoothed, and small head movements are ignored, so the frame does not shake.
- If no face is visible, the crop stays where it last was.

## 5. Settings

Copy `.env.example` to `.env` to see the options. The app reads them as environment variables.

| Variable | Default | Meaning |
|---|---|---|
| `CLIPPER_WORK_DIR` | `./workdir` | Where videos and clips are stored |
| `CLIPPER_MAX_UPLOAD_MB` | `2048` (Docker image: `500`) | Largest upload accepted |
| `CLIPPER_MAX_SOURCE_MINUTES` | `240` (Docker image: `30`) | Longest source video accepted |
| `CLIPPER_RETENTION_HOURS` | `12` | Files not touched for this long are deleted |
| `CLIPPER_MAX_ACTIVE_JOBS` | `4` | Queued or running jobs allowed at once; more get a "busy" message |
| `FFMPEG_PATH` | (auto) | Use a specific FFmpeg program |

## 5b. Deploy a free live copy (Hugging Face Spaces)

1. Create a free account at huggingface.co and a new **Space** with SDK **Docker** and visibility **Public**.
2. Create a write token at huggingface.co/settings/tokens (keep it private).
3. Clone your Space, copy this project into it, and push:
   ```
   git remote add space https://huggingface.co/spaces/<your-user>/<space-name>
   git push space master:main
   ```
   Enter your Hugging Face username and the token as the password.
4. Wait for the build to finish, then open the Space URL. `/api/health` should return `"ok": true`.

The README front matter at the top tells Spaces which port to use.

## 6. Project layout

```
app/
  main.py       web API and routes
  config.py     settings and limits
  ingest.py     YouTube download (validated links only)
  media.py      reads video details, crop geometry
  splitter.py   automatic scene detection and clip building
  tracker.py    face tracking and smoothing
  exporter.py   FFmpeg output
  jobs.py       background jobs and progress
  store.py      saves video and clip details to disk
static/         the web page (HTML, CSS, JavaScript; no build step)
tests/          automated tests
```

## 7. Tests

```
pytest
```

The tests cover splitting rules, smoothing and crop maths, the FFmpeg command, input validation, and a full run on a generated video (upload, split, trim, extend, export, zip).

## 8. Security and limits

- Only `https://` links to YouTube hosts are accepted.
- Uploads are saved under server-chosen names. The user's file name is only shown as a title.
- Uploads and source length have size and duration limits.
- FFmpeg is run with an argument list, never a shell command, so file names cannot inject commands.
- Errors shown to users are plain messages. Unexpected errors are logged on the server only.
- The app has no login. Run it on your own computer, or put it behind your own access control before exposing it to a network.

## 9. Known limits

- Face tracking uses OpenCV's built-in frontal-face detector. It works best when the speaker faces the camera. Profile views or small faces may lose tracking, and the crop then stays in place.
- Background jobs and progress are held in memory. If the server restarts during a job, the video is marked as failed and can be re-added.
- YouTube changes often. If downloads start failing, update the downloader with `pip install -U yt-dlp` and restart.
- Export time depends on the computer and clip length. It has not been benchmarked yet.
