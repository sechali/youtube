// const form = document.getElementById("download-form");
const urlInput = document.getElementById("url-input");
const inspectBtn = document.getElementById("inspect-btn");
const downloadBtn = document.getElementById("download-btn");
const folderInput = document.getElementById("folder-input");
const pickFolderBtn = document.getElementById("pick-folder-btn");
const inspectProgress = document.getElementById("inspect-progress");
const cookieModeSelect = document.getElementById("cookie-mode");
const cookieBrowserSelect = document.getElementById("cookie-browser");
const cookieFileInput = document.getElementById("cookie-file-input");
const pickCookiesBtn = document.getElementById("pick-cookies-btn");

const formatSelect = document.getElementById("format-select");
const resolutionField = document.getElementById("resolution-field");
const resolutionSelect = document.getElementById("resolution-select");
const audioQualityField = document.getElementById("audio-quality-field");
const audioQualitySelect = document.getElementById("audio-quality-select");
const playlistCheckbox = document.getElementById("playlist-checkbox");
const playlistItemsInput = document.getElementById("playlist-items");

const previewCard = document.getElementById("preview-card");
const previewThumb = document.getElementById("preview-thumb");
const previewTitle = document.getElementById("preview-title");
const previewPlatform = document.getElementById("preview-platform");
const previewDuration = document.getElementById("preview-duration");
const previewUploader = document.getElementById("preview-uploader");
const previewPlaylistBadge = document.getElementById("preview-playlist-badge");

const playlistSelectorCard = document.getElementById("playlist-selector-card");
const playlistSelectorSummary = document.getElementById("playlist-selector-summary");
const playlistItemsContainer = document.getElementById("playlist-items-container");
const selectAllPlaylistBtn = document.getElementById("select-all-playlist-btn");
const deselectAllPlaylistBtn = document.getElementById("deselect-all-playlist-btn");

const progressBox = document.getElementById("progress-box");
const progressStatus = document.getElementById("progress-status");
const progressPct = document.getElementById("progress-pct");
const progressBar = document.getElementById("progress-bar");
const progressMeta = document.getElementById("progress-meta");
const stopBtn = document.getElementById("stop-btn");
const resumeBtn = document.getElementById("resume-btn");
const saveFileLink = document.getElementById("save-file-link");
const errorBox = document.getElementById("error-box");

const historyTable = document.getElementById("history-table");
const historyTbody = document.getElementById("history-tbody");
const historyEmpty = document.getElementById("history-empty");
const refreshHistoryBtn = document.getElementById("refresh-history-btn");
const clearHistoryBtn = document.getElementById("clear-history-btn");
const queueCard = document.getElementById("queue-card");
const queueList = document.getElementById("queue-list");

let pollTimer = null;
let currentTaskId = null;
let lastResumableTaskId = null;

function showError(msg) {
  errorBox.textContent = msg;
  errorBox.classList.remove("hidden");
}

function clearError() {
  errorBox.textContent = "";
  errorBox.classList.add("hidden");
}

function formatBytes(bytes) {
  if (!bytes || bytes <= 0) return "-";
  const units = ["B", "KB", "MB", "GB"];
  let idx = 0;
  let val = bytes;
  while (val >= 1024 && idx < units.length - 1) {
    val /= 1024;
    idx += 1;
  }
  return `${val.toFixed(1)} ${units[idx]}`;
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text ?? "";
  return div.innerHTML;
}

function updateFormatVisibility() {
  const isAudio = formatSelect.value === "audio";
  resolutionField.classList.toggle("hidden", isAudio);
  audioQualityField.classList.toggle("hidden", !isAudio);
}

formatSelect.addEventListener("change", updateFormatVisibility);

playlistCheckbox.addEventListener("change", () => {
  playlistItemsInput.classList.toggle("hidden", !playlistCheckbox.checked);
});

function populateResolutions(resolutions) {
  const defaults = [1080, 720, 480, 360];
  const list = Array.isArray(resolutions) && resolutions.length > 0 ? resolutions : defaults;
  resolutionSelect.innerHTML = '<option value="best">Terbaik (Best)</option>';
  for (const h of list) {
    const opt = document.createElement("option");
    opt.value = String(h);
    opt.textContent = `${h}p`;
    resolutionSelect.appendChild(opt);
  }
}

function renderPlaylistSelector(videos) {
  if (!videos || videos.length === 0) {
    playlistSelectorCard.classList.add("hidden");
    playlistItemsContainer.innerHTML = "";
    return;
  }

  playlistItemsContainer.innerHTML = "";
  playlistSelectorCard.classList.remove("hidden");

  for (const v of videos) {
    const row = document.createElement("label");
    row.className = "playlist-item-row";
    row.innerHTML = `
      <input type="checkbox" class="playlist-checkbox-item" data-index="${v.index}" checked />
      <span class="playlist-item-num">#${v.index}</span>
      <span class="playlist-item-title" title="${escapeHtml(v.title)}">${escapeHtml(v.title)}</span>
      <span class="playlist-item-duration">${escapeHtml(v.duration || "-")}</span>
    `;
    playlistItemsContainer.appendChild(row);
  }

  updatePlaylistSelectionRange();
}

function updatePlaylistSelectionRange() {
  const checkboxes = playlistItemsContainer.querySelectorAll(".playlist-checkbox-item");
  const total = checkboxes.length;
  if (total === 0) return;

  const selectedIndices = [];
  checkboxes.forEach((cb) => {
    if (cb.checked) {
      selectedIndices.push(parseInt(cb.getAttribute("data-index"), 10));
    }
  });

  playlistSelectorSummary.textContent = `Dipilih ${selectedIndices.length} dari ${total} video:`;

  if (selectedIndices.length === 0) {
    playlistItemsInput.value = "";
    return;
  }

  if (selectedIndices.length === total) {
    playlistItemsInput.value = ""; // Default: download semua
    return;
  }

  // Format menjadi rentang (misal 1-3,5,7-9)
  const ranges = [];
  let start = selectedIndices[0];
  let prev = selectedIndices[0];

  for (let i = 1; i < selectedIndices.length; i++) {
    const curr = selectedIndices[i];
    if (curr === prev + 1) {
      prev = curr;
    } else {
      ranges.push(start === prev ? `${start}` : `${start}-${prev}`);
      start = curr;
      prev = curr;
    }
  }
  ranges.push(start === prev ? `${start}` : `${start}-${prev}`);
  playlistItemsInput.value = ranges.join(",");
}

playlistItemsContainer.addEventListener("change", (e) => {
  if (e.target.classList.contains("playlist-checkbox-item")) {
    updatePlaylistSelectionRange();
  }
});

selectAllPlaylistBtn.addEventListener("click", () => {
  const checkboxes = playlistItemsContainer.querySelectorAll(".playlist-checkbox-item");
  checkboxes.forEach((cb) => {
    cb.checked = true;
  });
  updatePlaylistSelectionRange();
});

deselectAllPlaylistBtn.addEventListener("click", () => {
  const checkboxes = playlistItemsContainer.querySelectorAll(".playlist-checkbox-item");
  checkboxes.forEach((cb) => {
    cb.checked = false;
  });
  updatePlaylistSelectionRange();
});

inspectBtn.addEventListener("click", async () => {
  const url = urlInput.value.trim();
  if (!url) {
    showError("Masukkan URL terlebih dahulu.");
    return;
  }
  clearError();
  inspectBtn.disabled = true;
  inspectBtn.textContent = "Memeriksa...";
  inspectProgress.classList.remove("hidden");

  try {
    const res = await fetch("/api/inspect", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Gagal memeriksa URL.");

    previewTitle.textContent = data.title;
    previewPlatform.textContent = data.platform;
    previewDuration.textContent = data.duration;
    previewUploader.textContent = `Uploader: ${data.uploader}`;
    previewThumb.src = data.thumbnail || "";
    previewThumb.classList.toggle("hidden", !data.thumbnail);

    if (data.is_playlist) {
      previewPlaylistBadge.textContent = `Playlist (${data.playlist_count} item)`;
      previewPlaylistBadge.classList.remove("hidden");
      playlistCheckbox.checked = true;
      playlistItemsInput.classList.remove("hidden");
    } else {
      previewPlaylistBadge.classList.add("hidden");
      playlistCheckbox.checked = false;
      playlistItemsInput.classList.add("hidden");
    }

    renderPlaylistSelector(data.playlist_videos || []);

    populateResolutions(data.resolutions);
    previewCard.classList.remove("hidden");
  } catch (err) {
    showError(err.message);
  } finally {
    inspectBtn.disabled = false;
    inspectBtn.textContent = "Cek Info";
    inspectProgress.classList.add("hidden");
  }
});

urlInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    e.preventDefault();
    inspectBtn.click();
  }
});

downloadBtn.addEventListener("click", async () => {
  const url = urlInput.value.trim();
  if (!url) {
    showError("Masukkan URL video/playlist terlebih dahulu.");
    return;
  }

  if (playlistCheckbox.checked && playlistSelectorCard && !playlistSelectorCard.classList.contains("hidden")) {
    const checkboxes = playlistItemsContainer.querySelectorAll(".playlist-checkbox-item");
    if (checkboxes.length > 0) {
      const anyChecked = Array.from(checkboxes).some((cb) => cb.checked);
      if (!anyChecked) {
        showError("Pilih minimal satu video dari playlist untuk diunduh.");
        return;
      }
    }
  }

  clearError();
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }

  stopBtn.disabled = false;
  stopBtn.textContent = "Stop";
  stopBtn.classList.remove("hidden");
  resumeBtn.classList.add("hidden");
  lastResumableTaskId = null;
  saveFileLink.classList.add("hidden");
  progressBox.classList.remove("hidden");
  progressStatus.textContent = "Memulai unduhan...";
  progressPct.textContent = "0%";
  progressBar.style.width = "0%";
  progressBar.classList.add("indeterminate");
  progressMeta.textContent = "Kecepatan: - | ETA: -";

  try {
    const res = await fetch("/api/download", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        url,
        format_type: formatSelect.value,
        resolution: resolutionSelect.value,
        audio_quality: audioQualitySelect.value,
        download_playlist: playlistCheckbox.checked,
        playlist_items: playlistCheckbox.checked ? playlistItemsInput.value.trim() || null : null,
        output_dir: folderInput.value.trim() || null,
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Gagal memulai unduhan.");

    currentTaskId = data.task_id;
    loadQueue();
    pollTask(data.task_id);
  } catch (err) {
    showError(err.message);
    stopBtn.classList.add("hidden");
  }
});

stopBtn.addEventListener("click", async () => {
  if (!currentTaskId) return;
  stopBtn.disabled = true;
  stopBtn.textContent = "Menghentikan...";
  progressStatus.textContent = "Menghentikan unduhan...";
  try {
    await fetch(`/api/tasks/${currentTaskId}/cancel`, { method: "POST" });
  } catch {
    // Biarkan polling menangani status akhir
  }
});

function startTaskPolling(taskId) {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
  clearError();
  currentTaskId = taskId;
  lastResumableTaskId = null;
  downloadBtn.disabled = true;
  stopBtn.disabled = false;
  stopBtn.textContent = "Stop";
  stopBtn.classList.remove("hidden");
  resumeBtn.classList.add("hidden");
  saveFileLink.classList.add("hidden");
  progressBox.classList.remove("hidden");
  progressBar.classList.add("indeterminate");
  progressStatus.textContent = "Melanjutkan unduhan...";
  pollTask(taskId);
}

resumeBtn.addEventListener("click", async () => {
  if (!lastResumableTaskId) return;
  resumeBtn.disabled = true;
  try {
    const res = await fetch(`/api/tasks/${lastResumableTaskId}/resume`, { method: "POST" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Gagal melanjutkan unduhan.");
    startTaskPolling(data.task_id);
  } catch (err) {
    showError(err.message);
  } finally {
    resumeBtn.disabled = false;
  }
});

function pollTask(taskId) {
  pollTimer = setInterval(async () => {
    try {
      const res = await fetch(`/api/tasks/${taskId}`);
      if (!res.ok) return;
      const task = await res.json();

      let statusLabel = task.status_text || "Memproses...";
      if (task.playlist_count > 0 && task.playlist_index > 0) {
        statusLabel = `[${task.playlist_index}/${task.playlist_count}] ${statusLabel}`;
      }

      const pctVal = task.progress ?? 0;
      const isIndeterminate =
        task.status === "queued" ||
        task.status === "processing" ||
        (task.status === "downloading" && pctVal <= 0);

      progressStatus.textContent = statusLabel;
      progressPct.textContent = isIndeterminate && task.status !== "processing" ? "..." : `${pctVal}%`;
      progressBar.classList.toggle("indeterminate", isIndeterminate);
      if (!isIndeterminate) {
        progressBar.style.width = `${pctVal}%`;
      }
      progressMeta.textContent = `Kecepatan: ${task.speed} | ETA: ${task.eta}`;
      loadQueue();

      if (task.status === "completed") {
        clearInterval(pollTimer);
        pollTimer = null;
        currentTaskId = null;
        lastResumableTaskId = null;
        downloadBtn.disabled = false;
        stopBtn.classList.add("hidden");
        resumeBtn.classList.add("hidden");
        progressBar.classList.remove("indeterminate");
        progressBar.style.width = "100%";
        if (task.file_name) {
          saveFileLink.href = `/api/tasks/${encodeURIComponent(taskId)}/file`;
          saveFileLink.classList.remove("hidden");
        }
        loadHistory();
      } else if (task.status === "cancelled") {
        clearInterval(pollTimer);
        pollTimer = null;
        currentTaskId = null;
        lastResumableTaskId = taskId;
        downloadBtn.disabled = false;
        stopBtn.classList.add("hidden");
        resumeBtn.classList.remove("hidden");
        progressBar.classList.remove("indeterminate");
        loadHistory();
      } else if (task.status === "failed") {
        clearInterval(pollTimer);
        pollTimer = null;
        currentTaskId = null;
        lastResumableTaskId = taskId;
        downloadBtn.disabled = false;
        stopBtn.classList.add("hidden");
        resumeBtn.classList.remove("hidden");
        progressBar.classList.remove("indeterminate");
        showError(task.error || "Terjadi kesalahan saat mengunduh.");
        loadHistory();
      }
    } catch {
      // Abaikan error jaringan sementara saat polling
    }
  }, 600);
}

async function loadHistory() {
  try {
    const res = await fetch("/api/history");
    const data = await res.json();
    const items = data.items || [];

    historyTbody.innerHTML = "";
    if (items.length === 0) {
      historyEmpty.classList.remove("hidden");
      historyTable.classList.add("hidden");
      return;
    }

    historyEmpty.classList.add("hidden");
    historyTable.classList.remove("hidden");

    for (const item of items) {
      const tr = document.createElement("tr");
      let statusHtml = `<span class="status-fail" title="${escapeHtml(item.error_message || "")}">Gagal</span>`;
      if (item.status === "completed") {
        statusHtml = '<span class="status-ok">Selesai</span>';
      } else if (item.status === "cancelled") {
        statusHtml = '<span class="status-cancelled">Dihentikan</span>';
      }

      const downloadAction = item.file_exists
        ? `<a class="btn btn-secondary btn-sm" href="/api/history/${item.id}/file" download>Simpan</a>`
        : "";
      const resumeAction =
        item.status === "cancelled" || item.status === "failed"
          ? `<button class="btn btn-primary btn-sm" data-resume-id="${item.id}">Resume</button>`
          : "";

      tr.innerHTML = `
        <td class="title-cell" title="${escapeHtml(item.title)}">${escapeHtml(item.title)}</td>
        <td>${escapeHtml(item.platform)}</td>
        <td>${escapeHtml(item.format_type.toUpperCase())} (${escapeHtml(item.resolution)})</td>
        <td>${formatBytes(item.file_size)}</td>
        <td>${statusHtml}</td>
        <td>${escapeHtml(item.created_at)}</td>
        <td>
          <div style="display:flex;gap:6px;">
            ${downloadAction}
            ${resumeAction}
            <button class="btn btn-danger btn-sm" data-delete-id="${item.id}">Hapus</button>
          </div>
        </td>
      `;
      historyTbody.appendChild(tr);
    }
  } catch (err) {
    showError("Gagal memuat riwayat unduhan.");
  }
}

historyTbody.addEventListener("click", async (e) => {
  const resumeTarget = e.target.closest("button[data-resume-id]");
  if (resumeTarget) {
    const id = resumeTarget.getAttribute("data-resume-id");
    resumeTarget.disabled = true;
    try {
      const res = await fetch(`/api/history/${id}/resume`, { method: "POST" });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Gagal melanjutkan unduhan.");
      startTaskPolling(data.task_id);
    } catch (err) {
      showError(err.message);
      resumeTarget.disabled = false;
    }
    return;
  }

  const btn = e.target.closest("button[data-delete-id]");
  if (!btn) return;
  const id = btn.getAttribute("data-delete-id");
  await fetch(`/api/history/${id}`, { method: "DELETE" });
  loadHistory();
});

async function loadSettings() {
  try {
    const res = await fetch("/api/settings");
    const data = await res.json();
    if (data.download_dir) {
      folderInput.value = data.download_dir;
    }
    if (data.cookie_mode) {
      cookieModeSelect.value = data.cookie_mode;
    }
    if (data.cookie_browser) {
      cookieBrowserSelect.value = data.cookie_browser;
    }
    if (data.cookie_file !== undefined) {
      cookieFileInput.value = data.cookie_file;
    }
    updateCookieVisibility();
  } catch {
    // Abaikan jika gagal memuat pengaturan awal
  }
}

function updateCookieVisibility() {
  const mode = cookieModeSelect.value;
  cookieBrowserSelect.classList.toggle("hidden", mode !== "browser");
  cookieFileInput.classList.toggle("hidden", mode !== "file");
  pickCookiesBtn.classList.toggle("hidden", mode !== "file");
}

async function saveCookieSettings() {
  try {
    await fetch("/api/settings/cookies", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        cookie_mode: cookieModeSelect.value,
        cookie_browser: cookieBrowserSelect.value,
        cookie_file: cookieFileInput.value.trim(),
      }),
    });
  } catch {
    showError("Gagal menyimpan pengaturan cookies.");
  }
}

cookieModeSelect.addEventListener("change", () => {
  updateCookieVisibility();
  saveCookieSettings();
});
cookieBrowserSelect.addEventListener("change", saveCookieSettings);
cookieFileInput.addEventListener("change", saveCookieSettings);

pickCookiesBtn.addEventListener("click", async () => {
  pickCookiesBtn.disabled = true;
  pickCookiesBtn.textContent = "Membuka...";
  clearError();
  try {
    const res = await fetch("/api/settings/pick-cookies", { method: "POST" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Gagal memilih file cookies.txt.");
    if (data.cookie_mode) cookieModeSelect.value = data.cookie_mode;
    if (data.cookie_file !== undefined) cookieFileInput.value = data.cookie_file;
    updateCookieVisibility();
  } catch (err) {
    showError(err.message);
  } finally {
    pickCookiesBtn.disabled = false;
    pickCookiesBtn.textContent = "Pilih cookies.txt";
  }
});

pickFolderBtn.addEventListener("click", async () => {
  pickFolderBtn.disabled = true;
  pickFolderBtn.textContent = "Membuka...";
  clearError();
  try {
    const res = await fetch("/api/settings/pick-folder", { method: "POST" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Gagal memilih folder.");
    if (data.download_dir) {
      folderInput.value = data.download_dir;
    }
  } catch (err) {
    showError(err.message);
  } finally {
    pickFolderBtn.disabled = false;
    pickFolderBtn.textContent = "Pilih Folder";
  }
});

folderInput.addEventListener("change", async () => {
  const val = folderInput.value.trim();
  if (!val) return;
  try {
    const res = await fetch("/api/settings/folder", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ download_dir: val }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Folder tidak valid.");
    folderInput.value = data.download_dir;
  } catch (err) {
    showError(err.message);
  }
});

refreshHistoryBtn.addEventListener("click", loadHistory);

clearHistoryBtn.addEventListener("click", async () => {
  await fetch("/api/history", { method: "DELETE" });
  loadHistory();
});

function formatQueueStatusBadge(status, progress) {
  if (status === "completed") return '<span class="pill pill-completed">Sudah Selesai</span>';
  if (status === "downloading" || status === "processing") {
    const pctText = status === "processing" ? "Konversi" : `${progress ?? 0}%`;
    return `<span class="pill pill-downloading">Sedang Proses (${pctText})</span>`;
  }
  if (status === "cancelled") return '<span class="pill pill-cancelled">Dihentikan</span>';
  if (status === "failed") return '<span class="pill pill-failed">Gagal</span>';
  return '<span class="pill pill-queued">Dalam Antrian</span>';
}

async function loadQueue() {
  try {
    const res = await fetch("/api/tasks");
    const data = await res.json();
    const tasks = data.tasks || [];

    if (tasks.length === 0) {
      queueCard.classList.add("hidden");
      queueList.innerHTML = "";
      return;
    }

    queueCard.classList.remove("hidden");
    queueList.innerHTML = "";

    for (const t of tasks) {
      const box = document.createElement("div");
      box.className = "queue-task";

      const isActive = t.status === "queued" || t.status === "downloading" || t.status === "processing";
      let actionHtml = "";
      if (isActive) {
        actionHtml = `<button class="btn btn-danger btn-sm" data-queue-stop="${t.task_id}">Stop</button>`;
      } else if (t.status === "completed" && t.file_name) {
        actionHtml = `<a class="btn btn-success btn-sm" href="/api/tasks/${encodeURIComponent(t.task_id)}/file" download>Simpan</a>`;
      } else if (t.status === "cancelled" || t.status === "failed") {
        actionHtml = `<button class="btn btn-primary btn-sm" data-queue-resume="${t.task_id}">Resume</button>`;
      }

      const items = t.items || [];
      const subItemsHtml = items.length
        ? `<div class="queue-subitems">${items
            .map(
              (it) => `
              <div class="queue-subitem">
                <span class="queue-subitem-title">${it.index}. ${escapeHtml(it.title)}</span>
                ${formatQueueStatusBadge(it.status, it.progress)}
              </div>`
            )
            .join("")}</div>`
        : "";

      box.innerHTML = `
        <div class="queue-task-header">
          <span class="queue-task-title">${escapeHtml(t.title)}</span>
          <div style="display:flex;align-items:center;gap:8px;">
            ${formatQueueStatusBadge(t.status, t.progress)}
            ${actionHtml}
          </div>
        </div>
        <div class="muted-text">${escapeHtml(t.status_text || "")}</div>
        ${subItemsHtml}
      `;
      queueList.appendChild(box);
    }
  } catch {
    // Abaikan error sementara saat memuat antrian
  }
}

queueList.addEventListener("click", async (e) => {
  const stopTarget = e.target.closest("button[data-queue-stop]");
  if (stopTarget) {
    const tid = stopTarget.getAttribute("data-queue-stop");
    stopTarget.disabled = true;
    await fetch(`/api/tasks/${tid}/cancel`, { method: "POST" });
    loadQueue();
    return;
  }
  const resumeTarget = e.target.closest("button[data-queue-resume]");
  if (resumeTarget) {
    const tid = resumeTarget.getAttribute("data-queue-resume");
    resumeTarget.disabled = true;
    try {
      const res = await fetch(`/api/tasks/${tid}/resume`, { method: "POST" });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Gagal melanjutkan unduhan.");
      startTaskPolling(data.task_id);
      loadQueue();
    } catch (err) {
      showError(err.message);
      resumeTarget.disabled = false;
    }
  }
});

updateFormatVisibility();
loadSettings();
loadQueue();
loadHistory();
