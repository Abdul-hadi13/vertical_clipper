// Vertical Clipper front end. All user-provided text is written with textContent, never innerHTML.
"use strict";

const state = { videoId: null, video: null };
const $ = (id) => document.getElementById(id);

async function api(path, options = {}) {
  const init = { ...options };
  if (options.json !== undefined) {
    init.body = JSON.stringify(options.json);
    init.headers = { "Content-Type": "application/json" };
    delete init.json;
  }
  const response = await fetch(path, init);
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    if (typeof body.detail === "string") message = body.detail;
    else if (Array.isArray(body.detail) && body.detail[0]?.msg) message = body.detail[0].msg;
    throw new Error(message);
  }
  return body;
}

function showError(message) {
  const el = $("global-error");
  el.textContent = message || "";
  el.classList.toggle("hidden", !message);
}

function setBusy(busy) {
  document.querySelectorAll("#add-section button").forEach((b) => (b.disabled = busy));
}

function showProgress(fraction, message) {
  $("progress").classList.remove("hidden");
  $("progress-fill").style.width = `${Math.round(fraction * 100)}%`;
  $("progress-text").textContent = message || "";
}

function hideProgress() {
  $("progress").classList.add("hidden");
  $("progress-fill").style.width = "0";
}

// Polls a background job until it finishes. Resolves with the job result, rejects with its error.
function watchJob(jobId) {
  return new Promise((resolve, reject) => {
    const timer = setInterval(async () => {
      try {
        const job = await api(`/api/jobs/${jobId}`);
        showProgress(job.progress, job.message);
        if (job.status === "done") {
          clearInterval(timer);
          resolve(job.result);
        } else if (job.status === "error") {
          clearInterval(timer);
          reject(new Error(job.error || "Something went wrong"));
        }
      } catch (err) {
        clearInterval(timer);
        reject(err);
      }
    }, 800);
  });
}

async function runJob(jobId) {
  setBusy(true);
  showError("");
  try {
    return await watchJob(jobId);
  } catch (err) {
    showError(err.message);
    throw err;
  } finally {
    setBusy(false);
    hideProgress();
  }
}

async function openVideo(videoId) {
  state.videoId = videoId;
  await refresh();
  $("editor").classList.remove("hidden");
  $("editor").scrollIntoView({ behavior: "smooth" });
}

async function refresh() {
  state.video = await api(`/api/videos/${state.videoId}`);
  renderVideo();
}

function fmt(seconds) {
  const s = Math.max(0, seconds);
  const m = Math.floor(s / 60);
  return `${m}:${(s % 60).toFixed(1).padStart(4, "0")}`;
}

function renderVideo() {
  const v = state.video;
  $("video-title").textContent = v.title;
  $("bundle-link").classList.toggle("hidden", !v.bundle);
  if (v.bundle) $("bundle-link").href = `/api/videos/${v.id}/bundle`;

  if (v.status === "error") {
    showError(v.error || "This video could not be processed.");
    $("video-meta").textContent = "Processing failed.";
    return;
  }
  if (v.status !== "ready") {
    $("video-meta").textContent = "Still processing...";
    return;
  }

  $("video-meta").textContent = `${v.width}×${v.height} · ${fmt(v.duration)} · ${v.clips.length} clips`;
  const player = $("player");
  const src = `/api/videos/${v.id}/source`;
  if (!player.src.endsWith(src)) player.src = src;

  const container = $("clips");
  container.replaceChildren(...v.clips.map(renderClip));
}

function numberField(label, value, onInput) {
  const wrap = document.createElement("div");
  wrap.className = "field";
  const lab = document.createElement("label");
  lab.textContent = label;
  const row = document.createElement("div");
  row.className = "inline";
  const input = document.createElement("input");
  input.type = "number";
  input.step = "0.1";
  input.min = "0";
  input.value = value.toFixed(1);
  input.addEventListener("input", () => onInput(parseFloat(input.value)));
  row.append(input);
  for (const delta of [-1, 1]) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "small secondary";
    b.textContent = delta > 0 ? "+1 s" : "−1 s";
    b.addEventListener("click", () => {
      input.value = Math.max(0, parseFloat(input.value) + delta).toFixed(1);
      onInput(parseFloat(input.value));
    });
    row.append(b);
  }
  wrap.append(lab, row);
  return { wrap, input };
}

function renderClip(clip) {
  const v = state.video;
  const card = document.createElement("div");
  card.className = "clip";

  // Local draft values, saved only when the user presses Save timing.
  const draft = { start: clip.start, end: clip.end };

  const head = document.createElement("div");
  head.className = "clip-head";
  const title = document.createElement("strong");
  title.textContent = `Clip ${clip.number}`;
  const pill = document.createElement("span");
  pill.className = "status-pill" + (clip.output ? " done" : "");
  pill.textContent = clip.output ? "Exported" : "Not exported";
  const playBtn = button("Play", "secondary small", () => {
    $("player").currentTime = draft.start;
    $("player").play();
  });
  head.append(title, pill, playBtn);

  const grid = document.createElement("div");
  grid.className = "clip-grid";
  const duration = document.createElement("div");
  duration.className = "field";
  const durLabel = document.createElement("label");
  durLabel.textContent = "Length";
  const durValue = document.createElement("div");
  const updateLength = () => {
    durValue.textContent = `${(draft.end - draft.start).toFixed(1)} s`;
  };
  updateLength();
  duration.append(durLabel, durValue);

  const start = numberField("Start (s)", clip.start, (val) => {
    if (!Number.isNaN(val)) draft.start = val;
    updateLength();
  });
  const end = numberField("End (s)", clip.end, (val) => {
    if (!Number.isNaN(val)) draft.end = val;
    updateLength();
  });
  grid.append(start.wrap, end.wrap, duration);

  const actions = document.createElement("div");
  actions.className = "actions";
  actions.append(
    button("Use current time as start", "secondary small", () => {
      start.input.value = $("player").currentTime.toFixed(1);
      draft.start = parseFloat(start.input.value);
      updateLength();
    }),
    button("Use current time as end", "secondary small", () => {
      end.input.value = $("player").currentTime.toFixed(1);
      draft.end = parseFloat(end.input.value);
      updateLength();
    }),
    button("Save timing", "", async () => {
      showError("");
      state.video = await api(`/api/videos/${v.id}/clips/${clip.id}`, { method: "PATCH", json: draft });
      renderVideo();
    }),
    button("Export clip", "", async () => {
      const { job_id } = await api(`/api/videos/${v.id}/clips/${clip.id}/export`, { method: "POST" });
      await runJob(job_id);
      await refresh();
    }),
  );
  if (clip.output) {
    const link = document.createElement("a");
    link.className = "button-link small";
    link.href = `/api/videos/${v.id}/clips/${clip.id}/download`;
    link.textContent = "Download clip";
    actions.append(link);
  }

  card.append(head, grid, actions);
  return card;
}

function button(label, className, onClick) {
  const b = document.createElement("button");
  b.type = "button";
  b.textContent = label;
  if (className) b.className = className;
  b.addEventListener("click", async () => {
    try {
      await onClick();
    } catch (err) {
      showError(err.message);
    }
  });
  return b;
}

// ---------- page actions ----------

$("url-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  showError("");
  try {
    setBusy(true);
    const { video_id, job_id } = await api("/api/videos/from-url", { method: "POST", json: { url: $("url-input").value.trim() } });
    await runJob(job_id);
    await openVideo(video_id);
  } catch (err) {
    showError(err.message);
  } finally {
    setBusy(false);
    hideProgress();
  }
});

$("upload-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  showError("");
  const file = $("file-input").files[0];
  if (!file) return showError("Choose a video file first.");
  try {
    setBusy(true);
    showProgress(0, "Uploading");
    const form = new FormData();
    form.append("file", file);
    const { video_id, job_id } = await api("/api/videos/upload", { method: "POST", body: form });
    await runJob(job_id);
    await openVideo(video_id);
  } catch (err) {
    showError(err.message);
  } finally {
    setBusy(false);
    hideProgress();
  }
});

$("add-clip").addEventListener("click", async () => {
  // Adds a clip from the current playback position. The server keeps it within the allowed range.
  const player = $("player");
  const start = player.currentTime;
  const end = Math.min(start + 30, state.video.duration);
  try {
    state.video = await api(`/api/videos/${state.videoId}/clips`, { method: "POST", json: { start, end } });
    renderVideo();
  } catch (err) {
    showError(err.message);
  }
});
$("export-all").addEventListener("click", async () => {
  const { job_id } = await api(`/api/videos/${state.videoId}/export-all`, { method: "POST" });
  await runJob(job_id);
  await refresh();
});
