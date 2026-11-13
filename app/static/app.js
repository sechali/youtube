/**
 * Media Downloader Pro - Main Application Logic
 */

document.addEventListener("DOMContentLoaded", () => {
  // ========================================================================
  // THEME SWITCHER
  // ========================================================================
  const themeToggleBtn = document.getElementById("theme-toggle-btn");
  const themeIconSun = document.getElementById("theme-icon-sun");
  const themeIconMoon = document.getElementById("theme-icon-moon");

  function initTheme() {
    const saved = localStorage.getItem("media-downloader-theme") || "dark";
    setTheme(saved);
  }

  function setTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("media-downloader-theme", theme);
    if (theme === "dark") {
      themeIconSun.classList.add("hidden");
      themeIconMoon.classList.remove("hidden");
    } else {
      themeIconSun.classList.remove("hidden");
      themeIconMoon.classList.add("hidden");
    }
  }

  themeToggleBtn.addEventListener("click", () => {
    const current = document.documentElement.getAttribute("data-theme") || "dark";
    setTheme(current === "dark" ? "light" : "dark");
  });

  initTheme();

  // ========================================================================
  // TOAST NOTIFICATIONS
  // ========================================================================
  const toastContainer = document.getElementById("toast-container");

  function showToast(message, type = "info") {
    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    toastContainer.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = "0";
      toast.style.transform = "translateX(20px)";
      toast.style.transition = "all 0.3s ease";
      setTimeout(() => toast.remove(), 300);
    }, 4000);
  }

  // ========================================================================
  // TAB NAVIGATION
  // ========================================================================
  const tabBtns = document.querySelectorAll(".tab-btn");
  const tabPanes = document.querySelectorAll(".tab-pane");

  tabBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      const targetId = btn.getAttribute("data-tab");
      tabBtns.forEach((b) => b.classList.remove("active"));
      tabPanes.forEach((p) => p.classList.remove("active"));

      btn.classList.add("active");
      const targetPane = document.getElementById(targetId);
      if (targetPane) targetPane.classList.add("active");

      // Auto refresh on tab switch
      if (targetId === "history-tab") loadHistory();
      if (targetId === "settings-tab") {
        loadSettings();
        loadSystemStatus();
        loadDashboardStats();
      }
    });
  });

  // ========================================================================
  // FORMAT VISIBILITY TOGGLE (SINGLE DOWNLOAD)
  // ========================================================================
  const formatSelect = document.getElementById("format-select");
  const videoExtField = document.getElementById("video-ext-field");
  const resolutionField = document.getElementById("resolution-field");
  const audioFormatField = document.getElementById("audio-format-field");
  const audioQualityField = document.getElementById("audio-quality-field");
  const subtitleCheckbox = document.getElementById("subtitle-checkbox");
  const subtitleOptionsBox = document.getElementById("subtitle-options-box");
  const embedSubLabel = document.getElementById("embed-sub-label");
  const playlistCheckbox = document.getElementById("playlist-checkbox");
  const playlistItemsInput = document.getElementById("playlist-items");

  function updateSingleFormatVisibility() {
    const isAudio = formatSelect.value === "audio";
    videoExtField.classList.toggle("hidden", isAudio);
    resolutionField.classList.toggle("hidden", isAudio);
    audioFormatField.classList.toggle("hidden", !isAudio);
    audioQualityField.classList.toggle("hidden", !isAudio);
    if (embedSubLabel) embedSubLabel.classList.toggle("hidden", isAudio);
  }

  formatSelect.addEventListener("change", updateSingleFormatVisibility);

  subtitleCheckbox.addEventListener("change", () => {
    subtitleOptionsBox.classList.toggle("hidden", !subtitleCheckbox.checked);
  });

  playlistCheckbox.addEventListener("change", () => {
    playlistItemsInput.classList.toggle("hidden", !playlistCheckbox.checked);
  });

  // Paste clipboard helper
  const pasteBtn = document.getElementById("paste-btn");
  const urlInput = document.getElementById("url-input");
  pasteBtn.addEventListener("click", async () => {
    try {
      const text = await navigator.clipboard.readText();
      if (text) {
        urlInput.value = text.trim();
        showToast("Link berhasil ditempel dari clipboard!", "info");
      }
    } catch {
      showToast("Gagal membaca clipboard. Silakan tempel secara manual (Ctrl+V).", "error");
    }
  });

  // ========================================================================
  // INSPECT SINGLE URL
  // ========================================================================
  const inspectBtn = document.getElementById("inspect-btn");
  const inspectProgress = document.getElementById("inspect-progress");
  const previewCard = document.getElementById("preview-card");
  const previewThumb = document.getElementById("preview-thumb");
  const previewTitle = document.getElementById("preview-title");
  const previewPlatform = document.getElementById("preview-platform");
  const previewDuration = document.getElementById("preview-duration");
  const previewUploader = document.getElementById("preview-uploader");
  const previewPlaylistBadge = document.getElementById("preview-playlist-badge");
  const subtitlesInfoBadge = document.getElementById("subtitles-info-badge");
  const resolutionSelect = document.getElementById("resolution-select");

  const playlistSelectorCard = document.getElementById("playlist-selector-card");
  const playlistSelectorSummary = document.getElementById("playlist-selector-summary");
  const playlistItemsContainer = document.getElementById("playlist-items-container");
  const selectAllPlaylistBtn = document.getElementById("select-all-playlist-btn");
  const deselectAllPlaylistBtn = document.getElementById("deselect-all-playlist-btn");

  inspectBtn.addEventListener("click", async () => {
    const url = urlInput.value.trim();
    if (!url) {
      showToast("Masukkan URL video terlebih dahulu.", "error");
      return;
    }

    inspectBtn.disabled = true;
    inspectProgress.classList.remove("hidden");
    previewCard.classList.add("hidden");
    playlistSelectorCard.classList.add("hidden");

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
      previewUploader.textContent = `Saluran / Uploader: ${data.uploader}`;
      if (data.thumbnail) {
        previewThumb.src = data.thumbnail;
        previewThumb.classList.remove("hidden");
      } else {
        previewThumb.classList.add("hidden");
      }

      if (data.is_playlist) {
        previewPlaylistBadge.textContent = `Playlist (${data.playlist_count} item)`;
        previewPlaylistBadge.classList.remove("hidden");
        playlistCheckbox.checked = true;
        playlistItemsInput.classList.remove("hidden");
        renderPlaylistSelector(data.playlist_videos || []);
      } else {
        previewPlaylistBadge.classList.add("hidden");
        playlistCheckbox.checked = false;
        playlistItemsInput.classList.add("hidden");
      }

      if (data.subtitles_available && data.subtitles_available.length > 0) {
        subtitlesInfoBadge.textContent = `Subtitle terdeteksi: ${data.subtitles_available.slice(0, 5).join(", ")}${data.subtitles_available.length > 5 ? "..." : ""}`;
        subtitlesInfoBadge.classList.remove("hidden");
      } else {
        subtitlesInfoBadge.classList.add("hidden");
      }

      populateResolutions(data.resolutions);
      previewCard.classList.remove("hidden");
      showToast("Informasi media berhasil diambil!", "success");
    } catch (err) {
      showToast(err.message, "error");
    } finally {
      inspectBtn.disabled = false;
      inspectProgress.classList.add("hidden");
    }
  });

  urlInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      inspectBtn.click();
    }
  });

  function populateResolutions(resolutions) {
    const list = Array.isArray(resolutions) && resolutions.length > 0 ? resolutions : [1080, 720, 480, 360];
    resolutionSelect.innerHTML = '<option value="best" selected>Resolusi Tertinggi (Best)</option>';
    for (const h of list) {
      const opt = document.createElement("option");
      opt.value = String(h);
      let label = `${h}p`;
      if (h >= 2160) label += " (4K UHD)";
      else if (h >= 1440) label += " (2K QHD)";
      else if (h >= 1080) label += " (Full HD)";
      else if (h >= 720) label += " (HD)";
      opt.textContent = label;
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
      playlistItemsInput.value = "";
      return;
    }

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

  if (playlistItemsContainer) {
    playlistItemsContainer.addEventListener("change", (e) => {
      if (e.target.classList.contains("playlist-checkbox-item")) {
        updatePlaylistSelectionRange();
      }
    });
  }

  if (selectAllPlaylistBtn) {
    selectAllPlaylistBtn.addEventListener("click", () => {
      playlistItemsContainer.querySelectorAll(".playlist-checkbox-item").forEach((cb) => (cb.checked = true));
      updatePlaylistSelectionRange();
    });
  }

  if (deselectAllPlaylistBtn) {
    deselectAllPlaylistBtn.addEventListener("click", () => {
      playlistItemsContainer.querySelectorAll(".playlist-checkbox-item").forEach((cb) => (cb.checked = false));
      updatePlaylistSelectionRange();
    });
  }

  // ========================================================================
  // SINGLE DOWNLOAD ACTION
  // ========================================================================
  const downloadBtn = document.getElementById("download-btn");
  const singleProgressBox = document.getElementById("single-progress-box");
  const singleProgressTitle = document.getElementById("single-progress-title");
  const singleProgressStatus = document.getElementById("single-progress-status");
  const singleProgressPct = document.getElementById("single-progress-pct");
  const singleProgressBar = document.getElementById("single-progress-bar");
  const singleProgressMeta = document.getElementById("single-progress-meta");
  const singleStopBtn = document.getElementById("single-stop-btn");
  const singleResumeBtn = document.getElementById("single-resume-btn");
  const singleOpenBtn = document.getElementById("single-open-btn");

  let currentSingleTaskId = null;

  downloadBtn.addEventListener("click", async () => {
    const url = urlInput.value.trim();
    if (!url) {
      showToast("Masukkan URL video terlebih dahulu.", "error");
      return;
    }

    const isPlaylist = playlistCheckbox.checked;
    const playlistItems = isPlaylist ? playlistItemsInput.value.trim() : null;

    const payload = {
      url,
      format_type: formatSelect.value,
      resolution: resolutionSelect.value,
      video_ext: document.getElementById("video-ext-select").value,
      audio_format: document.getElementById("audio-format-select").value,
      audio_quality: document.getElementById("audio-quality-select").value,
      download_subtitles: subtitleCheckbox.checked,
      subtitles_lang: document.getElementById("subtitle-lang-input").value.trim() || "id,en",
      embed_subtitles: document.getElementById("embed-subtitle-checkbox").checked,
      download_playlist: isPlaylist,
      playlist_items: playlistItems,
    };

    try {
      const res = await fetch("/api/download", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Gagal memulai unduhan.");

      currentSingleTaskId = data.task_id;
      showToast("Unduhan berhasil dimasukkan ke antrian!", "success");

      // Show single progress card
      singleProgressBox.classList.remove("hidden");
      singleProgressTitle.textContent = previewTitle.textContent !== "-" ? previewTitle.textContent : "Unduhan Media";
      singleProgressStatus.textContent = "Menunggu antrian...";
      singleProgressPct.textContent = "0%";
      singleProgressBar.style.width = "0%";
      singleProgressBar.classList.add("indeterminate");
      singleProgressMeta.textContent = "Kecepatan: - | ETA: -";

      singleStopBtn.classList.remove("hidden");
      singleResumeBtn.classList.add("hidden");
      singleOpenBtn.classList.add("hidden");

      // Trigger queue refresh immediately
      pollTasks();
    } catch (err) {
      showToast(err.message, "error");
    }
  });

  singleStopBtn.addEventListener("click", async () => {
    if (!currentSingleTaskId) return;
    try {
      await fetch(`/api/tasks/${currentSingleTaskId}/cancel`, { method: "POST" });
      showToast("Permintaan pembatalan dikirim.", "info");
      singleStopBtn.classList.add("hidden");
      singleResumeBtn.classList.remove("hidden");
      pollTasks();
    } catch (err) {
      showToast("Gagal membatalkan task: " + err.message, "error");
    }
  });

  singleResumeBtn.addEventListener("click", async () => {
    if (!currentSingleTaskId) return;
    try {
      const res = await fetch(`/api/tasks/${currentSingleTaskId}/resume`, { method: "POST" });
      const data = await res.json();
      currentSingleTaskId = data.task_id;
      showToast("Unduhan di-resume!", "success");
      singleResumeBtn.classList.add("hidden");
      singleStopBtn.classList.remove("hidden");
      pollTasks();
    } catch (err) {
      showToast("Gagal melanjutkan unduhan: " + err.message, "error");
    }
  });

  singleOpenBtn.addEventListener("click", async () => {
    try {
      await fetch("/api/open-folder", { method: "POST" });
    } catch {
      showToast("Gagal membuka folder di explorer.", "error");
    }
  });

  // ========================================================================
  // BATCH DOWNLOAD ACTIONS
  // ========================================================================
  const batchUrlsInput = document.getElementById("batch-urls-input");
  const batchCountDisplay = document.getElementById("batch-count-display");
  const batchClearBtn = document.getElementById("batch-clear-btn");
  const batchDownloadBtn = document.getElementById("batch-download-btn");
  const batchFormatSelect = document.getElementById("batch-format-select");
  const batchResolutionGroup = document.getElementById("batch-resolution-group");
  const batchAudioQualityGroup = document.getElementById("batch-audio-quality-group");

  batchUrlsInput.addEventListener("input", () => {
    const lines = batchUrlsInput.value
      .split("\n")
      .map((l) => l.trim())
      .filter((l) => l.startsWith("http://") || l.startsWith("https://"));
    batchCountDisplay.textContent = `${lines.length} link terdeteksi`;
  });

  batchClearBtn.addEventListener("click", () => {
    batchUrlsInput.value = "";
    batchCountDisplay.textContent = "0 link terdeteksi";
  });

  batchFormatSelect.addEventListener("change", () => {
    const isAudio = batchFormatSelect.value === "audio";
    batchResolutionGroup.classList.toggle("hidden", isAudio);
    batchAudioQualityGroup.classList.toggle("hidden", !isAudio);
  });

  batchDownloadBtn.addEventListener("click", async () => {
    const lines = batchUrlsInput.value
      .split("\n")
      .map((l) => l.trim())
      .filter((l) => l.startsWith("http://") || l.startsWith("https://"));

    if (lines.length === 0) {
      showToast("Masukkan setidaknya 1 link valid untuk diunduh.", "error");
      return;
    }

    const payload = {
      urls: lines,
      format_type: batchFormatSelect.value,
      resolution: document.getElementById("batch-resolution-select").value,
      audio_quality: document.getElementById("batch-audio-quality-select").value,
      video_ext: "mp4",
      audio_format: "mp3",
      download_subtitles: false,
    };

    try {
      const res = await fetch("/api/batch-download", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Gagal memulai unduhan batch.");

      showToast(`Berhasil menambahkan ${data.total} unduhan ke antrian!`, "success");
      batchUrlsInput.value = "";
      batchCountDisplay.textContent = "0 link terdeteksi";

      // Switch to Queue tab to see progress
      const queueTabBtn = document.querySelector('[data-tab="queue-tab"]');
      if (queueTabBtn) queueTabBtn.click();
      pollTasks();
    } catch (err) {
      showToast(err.message, "error");
    }
  });

  // ========================================================================
  // QUEUE MONITORING & POLLING
  // ========================================================================
  const queueItemsContainer = document.getElementById("queue-items-container");
  const queueEmpty = document.getElementById("queue-empty");
  const activeQueueCount = document.getElementById("active-queue-count");
  const autoStreamDeleteCheckbox = document.getElementById("auto-stream-delete-checkbox");
  const autoDownloadedTasks = new Set();

  if (autoStreamDeleteCheckbox) {
    const savedAutoStream = localStorage.getItem("media-downloader-auto-stream") === "true";
    autoStreamDeleteCheckbox.checked = savedAutoStream;
    autoStreamDeleteCheckbox.addEventListener("change", () => {
      localStorage.setItem("media-downloader-auto-stream", autoStreamDeleteCheckbox.checked ? "true" : "false");
      showToast(
        autoStreamDeleteCheckbox.checked
          ? "Mode Auto-Download & Cleanup diaktifkan (Hemat storage server)."
          : "Mode Auto-Download dinonaktifkan.",
        "info"
      );
    });
  }

  function triggerAutoDownload(taskId, title) {
    showToast(`Mengunduh "${title.slice(0, 30)}..." ke laptop & server membersihkan storage!`, "success");
    const iframe = document.createElement("iframe");
    iframe.style.display = "none";
    iframe.src = `/api/tasks/${taskId}/download-stream`;
    document.body.appendChild(iframe);
    setTimeout(() => iframe.remove(), 60000);
  }

  async function pollTasks() {
    try {
      const res = await fetch("/api/tasks");
      const data = await res.json();
      const tasks = data.tasks || [];

      // Auto-download ke client & hapus dari server jika fitur aktif
      if (autoStreamDeleteCheckbox && autoStreamDeleteCheckbox.checked) {
        tasks.forEach((t) => {
          if (t.status === "completed" && t.file_path && !autoDownloadedTasks.has(t.task_id)) {
            autoDownloadedTasks.add(t.task_id);
            triggerAutoDownload(t.task_id, t.title || "media");
          }
        });
      }

      // Update badge
      const activeTasks = tasks.filter((t) => t.status === "downloading" || t.status === "processing" || t.status === "queued");
      if (activeTasks.length > 0) {
        activeQueueCount.textContent = activeTasks.length;
        activeQueueCount.classList.remove("hidden");
      } else {
        activeQueueCount.classList.add("hidden");
      }

      // Update single progress card if active
      if (currentSingleTaskId) {
        const cur = tasks.find((t) => t.task_id === currentSingleTaskId);
        if (cur) {
          singleProgressTitle.textContent = cur.title || "Unduhan Media";
          singleProgressStatus.textContent = cur.status_text || cur.status;
          singleProgressPct.textContent = `${cur.progress || 0}%`;
          singleProgressBar.style.width = `${cur.progress || 0}%`;
          singleProgressBar.classList.toggle("indeterminate", cur.status === "queued" || cur.status === "processing");
          singleProgressMeta.textContent = `Kecepatan: ${cur.speed || "-"} | ETA: ${cur.eta || "-"}`;

          if (cur.status === "completed") {
            singleStopBtn.classList.add("hidden");
            singleResumeBtn.classList.add("hidden");
            singleOpenBtn.classList.remove("hidden");
          } else if (cur.status === "cancelled" || cur.status === "failed") {
            singleStopBtn.classList.add("hidden");
            singleResumeBtn.classList.remove("hidden");
            singleOpenBtn.classList.add("hidden");
          }
        }
      }

      renderQueue(tasks);
    } catch (err) {
      console.warn("Polling error:", err);
    }
  }

  function renderQueue(tasks) {
    if (!queueItemsContainer) return;
    if (tasks.length === 0) {
      queueEmpty.classList.remove("hidden");
      queueItemsContainer.innerHTML = "";
      return;
    }

    queueEmpty.classList.add("hidden");
    queueItemsContainer.innerHTML = "";

    tasks.forEach((t) => {
      const card = document.createElement("div");
      card.className = "queue-card-item";

      let statusBadgeClass = "badge-neutral";
      if (t.status === "downloading" || t.status === "processing") statusBadgeClass = "badge-info";
      if (t.status === "completed") statusBadgeClass = "badge-success";
      if (t.status === "failed" || t.status === "cancelled") statusBadgeClass = "badge-danger";

      const isIndeterminate = t.status === "queued" || t.status === "processing";

      card.innerHTML = `
        <div class="queue-card-top">
          <span class="queue-card-title" title="${escapeHtml(t.title || t.url)}">${escapeHtml(t.title || t.url)}</span>
          <span class="badge ${statusBadgeClass}">${escapeHtml(t.status.toUpperCase())}</span>
        </div>
        <div style="font-size:0.8rem;color:var(--text-muted);margin-bottom:8px;">
          ${escapeHtml(t.status_text || "-")} • Format: ${escapeHtml((t.file_format || t.format_type || "").toUpperCase())} ${escapeHtml(t.resolution ? `(${t.resolution})` : "")}
        </div>
        <div class="progress-track" style="margin-bottom:8px;">
          <div class="progress-fill ${isIndeterminate ? "indeterminate" : ""}" style="width: ${t.progress || 0}%;"></div>
        </div>
        <div class="progress-card-footer">
          <span>Kecepatan: ${escapeHtml(t.speed || "-")} | ETA: ${escapeHtml(t.eta || "-")} (${t.progress || 0}%)</span>
          <div class="progress-card-btns">
            ${
              t.status === "downloading" || t.status === "queued"
                ? `<button type="button" class="btn btn-sm btn-danger cancel-task-btn" data-id="${t.task_id}">Batal</button>`
                : ""
            }
            ${
              t.status === "cancelled" || t.status === "failed"
                ? `<button type="button" class="btn btn-sm btn-secondary resume-task-btn" data-id="${t.task_id}">Resume</button>`
                : ""
            }
            ${
              t.status === "completed" && t.file_path
                ? `<button type="button" class="btn btn-sm btn-outline open-file-btn" data-path="${escapeHtml(t.file_path)}">Buka File</button>`
                : ""
            }
          </div>
        </div>
      `;
      queueItemsContainer.appendChild(card);
    });

    // Attach card action listeners
    queueItemsContainer.querySelectorAll(".cancel-task-btn").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const id = btn.getAttribute("data-id");
        await fetch(`/api/tasks/${id}/cancel`, { method: "POST" });
        showToast("Unduhan dibatalkan.", "info");
        pollTasks();
      });
    });

    queueItemsContainer.querySelectorAll(".resume-task-btn").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const id = btn.getAttribute("data-id");
        await fetch(`/api/tasks/${id}/resume`, { method: "POST" });
        showToast("Unduhan dilanjutkan kembali.", "success");
        pollTasks();
      });
    });

    queueItemsContainer.querySelectorAll(".open-file-btn").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const path = btn.getAttribute("data-path");
        await fetch("/api/open-file", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ file_path: path }),
        });
      });
    });
  }

  // Start continuous polling every 1.5 seconds
  setInterval(pollTasks, 1500);

  // ========================================================================
  // HISTORY ACTIONS & FILTERING
  // ========================================================================
  const historyTbody = document.getElementById("history-tbody");
  const historyTable = document.getElementById("history-table");
  const historyEmpty = document.getElementById("history-empty");
  const historySearchInput = document.getElementById("history-search-input");
  const historyStatusFilter = document.getElementById("history-status-filter");
  const refreshHistoryBtn = document.getElementById("refresh-history-btn");
  const clearHistoryBtn = document.getElementById("clear-history-btn");

  let historyDebounce = null;

  async function loadHistory() {
    const search = historySearchInput ? historySearchInput.value.trim() : "";
    const status = historyStatusFilter ? historyStatusFilter.value : "all";

    const params = new URLSearchParams();
    if (search) params.set("search", search);
    if (status && status !== "all") params.set("status", status);

    try {
      const res = await fetch(`/api/history?${params.toString()}`);
      const data = await res.json();
      renderHistory(data.items || []);
    } catch (err) {
      console.warn("Gagal memuat riwayat:", err);
    }
  }

  function renderHistory(items) {
    if (!historyTbody) return;
    if (items.length === 0) {
      historyEmpty.classList.remove("hidden");
      historyTable.classList.add("hidden");
      historyTbody.innerHTML = "";
      return;
    }

    historyEmpty.classList.add("hidden");
    historyTable.classList.remove("hidden");
    historyTbody.innerHTML = "";

    items.forEach((item) => {
      const tr = document.createElement("tr");

      let badgeClass = "badge-neutral";
      if (item.status === "completed") badgeClass = "badge-success";
      if (item.status === "failed") badgeClass = "badge-danger";

      const sizeStr = item.file_size ? formatBytes(item.file_size) : "-";

      tr.innerHTML = `
        <td class="history-title-cell" title="${escapeHtml(item.title)}">
          <div>${escapeHtml(item.title || "Media")}</div>
          <div style="font-size:0.75rem;color:var(--text-dim);">${escapeHtml(item.url)}</div>
        </td>
        <td><span class="tag-pill tag-platform">${escapeHtml(item.platform || "Web")}</span></td>
        <td>${escapeHtml((item.file_format || item.format_type || "").toUpperCase())} • ${escapeHtml(item.resolution || "")}</td>
        <td>${sizeStr}</td>
        <td><span class="badge ${badgeClass}">${escapeHtml(item.status)}</span></td>
        <td style="font-size:0.78rem;color:var(--text-muted);">${escapeHtml(item.created_at || "-")}</td>
        <td>
          <div style="display:flex;gap:6px;">
            ${
              item.status === "completed" && item.file_exists && item.file_path
                ? `<button type="button" class="btn btn-sm btn-outline open-hist-btn" data-path="${escapeHtml(item.file_path)}" title="Buka di Windows Explorer">Explorer</button>`
                : ""
            }
            ${
              item.status === "completed" && item.file_exists
                ? `<a href="/api/history/${item.id}/file" class="btn btn-sm btn-primary" title="Download File">Unduh</a>`
                : ""
            }
            ${
              item.status !== "completed"
                ? `<button type="button" class="btn btn-sm btn-secondary resume-hist-btn" data-id="${item.id}">Coba Lagi</button>`
                : ""
            }
            <button type="button" class="btn btn-sm btn-danger del-hist-btn" data-id="${item.id}" title="Hapus dari riwayat">✕</button>
          </div>
        </td>
      `;
      historyTbody.appendChild(tr);
    });

    historyTbody.querySelectorAll(".open-hist-btn").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const path = btn.getAttribute("data-path");
        await fetch("/api/open-file", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ file_path: path }),
        });
      });
    });

    historyTbody.querySelectorAll(".resume-hist-btn").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const id = btn.getAttribute("data-id");
        try {
          await fetch(`/api/history/${id}/resume`, { method: "POST" });
          showToast("Unduhan dimulai ulang!", "success");
          const queueTabBtn = document.querySelector('[data-tab="queue-tab"]');
          if (queueTabBtn) queueTabBtn.click();
          pollTasks();
        } catch (err) {
          showToast(err.message, "error");
        }
      });
    });

    historyTbody.querySelectorAll(".del-hist-btn").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const id = btn.getAttribute("data-id");
        await fetch(`/api/history/${id}`, { method: "DELETE" });
        showToast("Item riwayat dihapus.", "info");
        loadHistory();
      });
    });
  }

  if (historySearchInput) {
    historySearchInput.addEventListener("input", () => {
      clearTimeout(historyDebounce);
      historyDebounce = setTimeout(loadHistory, 300);
    });
  }

  if (historyStatusFilter) {
    historyStatusFilter.addEventListener("change", loadHistory);
  }

  if (refreshHistoryBtn) refreshHistoryBtn.addEventListener("click", loadHistory);

  if (clearHistoryBtn) {
    clearHistoryBtn.addEventListener("click", async () => {
      if (confirm("Apakah Anda yakin ingin menghapus semua riwayat unduhan?")) {
        await fetch("/api/history", { method: "DELETE" });
        showToast("Semua riwayat telah dibersihkan.", "info");
        loadHistory();
      }
    });
  }

  // ========================================================================
  // SETTINGS & SYSTEM STATUS
  // ========================================================================
  const folderInput = document.getElementById("folder-input");
  const pickFolderBtn = document.getElementById("pick-folder-btn");
  const openFolderBtn = document.getElementById("open-folder-btn");

  const cookieMode = document.getElementById("cookie-mode");
  const cookieBrowserGroup = document.getElementById("cookie-browser-group");
  const cookieBrowser = document.getElementById("cookie-browser");
  const cookieFileGroup = document.getElementById("cookie-file-group");
  const cookieFileInput = document.getElementById("cookie-file-input");
  const pickCookiesBtn = document.getElementById("pick-cookies-btn");

  const sysFfmpeg = document.getElementById("sys-ffmpeg");
  const sysYtdlp = document.getElementById("sys-ytdlp");
  const sysDisk = document.getElementById("sys-disk");
  const sysFfmpegPath = document.getElementById("sys-ffmpeg-path");
  const ffmpegBadge = document.getElementById("ffmpeg-badge");
  const diskBadge = document.getElementById("disk-badge");

  async function loadSettings() {
    try {
      const res = await fetch("/api/settings");
      const data = await res.json();
      folderInput.value = data.download_dir || "";
      cookieMode.value = data.cookie_mode || "none";
      cookieBrowser.value = data.cookie_browser || "chrome";
      cookieFileInput.value = data.cookie_file || "";
      updateCookieVisibility();
    } catch (err) {
      console.warn("Gagal mengambil pengaturan:", err);
    }
  }

  function updateCookieVisibility() {
    const val = cookieMode.value;
    cookieBrowserGroup.classList.toggle("hidden", val !== "browser");
    cookieFileGroup.classList.toggle("hidden", val !== "file");
  }

  cookieMode.addEventListener("change", async () => {
    updateCookieVisibility();
    await saveCookieSettings();
  });

  cookieBrowser.addEventListener("change", saveCookieSettings);

  async function saveCookieSettings() {
    try {
      await fetch("/api/settings/cookies", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          cookie_mode: cookieMode.value,
          cookie_browser: cookieBrowser.value,
          cookie_file: cookieFileInput.value,
        }),
      });
      showToast("Pengaturan cookies tersimpan.", "info");
    } catch {
      showToast("Gagal menyimpan cookies.", "error");
    }
  }

  pickFolderBtn.addEventListener("click", async () => {
    try {
      const res = await fetch("/api/settings/pick-folder", { method: "POST" });
      const data = await res.json();
      if (data.download_dir) {
        folderInput.value = data.download_dir;
        showToast("Folder penyimpanan berhasil diubah!", "success");
      }
    } catch (err) {
      showToast("Gagal memilih folder: " + err.message, "error");
    }
  });

  openFolderBtn.addEventListener("click", async () => {
    try {
      await fetch("/api/open-folder", { method: "POST" });
    } catch {
      showToast("Gagal membuka folder di explorer.", "error");
    }
  });

  const cookieFileUpload = document.getElementById("cookie-file-upload");
  const uploadCookiesBtn = document.getElementById("upload-cookies-btn");

  if (uploadCookiesBtn && cookieFileUpload) {
    uploadCookiesBtn.addEventListener("click", () => cookieFileUpload.click());
    cookieFileUpload.addEventListener("change", async () => {
      if (!cookieFileUpload.files || cookieFileUpload.files.length === 0) return;
      const file = cookieFileUpload.files[0];
      const formData = new FormData();
      formData.append("file", file);
      try {
        showToast("Mengunggah file cookies.txt ke server...", "info");
        const res = await fetch("/api/settings/upload-cookies", {
          method: "POST",
          body: formData,
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Gagal upload cookies.");
        cookieFileInput.value = data.cookie_file;
        showToast("File cookies.txt berhasil diunggah ke server!", "success");
        loadSettings();
      } catch (err) {
        showToast(err.message, "error");
      }
    });
  }

  pickCookiesBtn.addEventListener("click", async () => {
    try {
      const res = await fetch("/api/settings/pick-cookies", { method: "POST" });
      const data = await res.json();
      if (data.cookie_file) {
        cookieFileInput.value = data.cookie_file;
        showToast("File cookies.txt berhasil dipilih!", "success");
      }
    } catch (err) {
      showToast(err.message, "error");
    }
  });

  async function loadSystemStatus() {
    try {
      const res = await fetch("/api/system-status");
      const data = await res.json();

      if (data.ffmpeg_installed) {
        sysFfmpeg.textContent = `Terpasang (${data.ffmpeg_version})`;
        sysFfmpeg.className = "info-val text-success";
        ffmpegBadge.textContent = "FFmpeg: OK";
        ffmpegBadge.className = "badge badge-success";
      } else {
        sysFfmpeg.textContent = "Tidak Ditemukan";
        sysFfmpeg.className = "info-val text-danger";
        ffmpegBadge.textContent = "FFmpeg: Missing";
        ffmpegBadge.className = "badge badge-danger";
      }

      sysYtdlp.textContent = data.ytdlp_version || "Aktif";
      sysDisk.textContent = `${data.free_disk_gb || 0} GB Tersedia`;
      diskBadge.textContent = `Sisa: ${data.free_disk_gb || 0} GB`;
      sysFfmpegPath.textContent = data.ffmpeg_path || "-";
    } catch (err) {
      console.warn("Gagal mengambil status sistem:", err);
    }
  }

  async function loadDashboardStats() {
    try {
      const res = await fetch("/api/stats");
      const data = await res.json();
      document.getElementById("stat-total").textContent = data.total_downloads || 0;
      document.getElementById("stat-completed").textContent = data.completed_count || 0;
      document.getElementById("stat-failed").textContent = data.failed_count || 0;
      document.getElementById("stat-size").textContent = formatBytes(data.total_bytes || 0);
    } catch (err) {
      console.warn("Gagal memuat statistik:", err);
    }
  }

  function formatBytes(bytes) {
    if (!bytes || bytes <= 0) return "0 MB";
    const units = ["B", "KB", "MB", "GB", "TB"];
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

  const checkYtdlpBtn = document.getElementById("check-ytdlp-btn");
  const upgradeYtdlpBtn = document.getElementById("upgrade-ytdlp-btn");
  const ytdlpUpdateBadge = document.getElementById("ytdlp-update-badge");
  const autoUpdateYtdlpCheckbox = document.getElementById("auto-update-ytdlp-checkbox");

  if (checkYtdlpBtn) {
    checkYtdlpBtn.addEventListener("click", async () => {
      checkYtdlpBtn.disabled = true;
      checkYtdlpBtn.textContent = "Memeriksa...";
      try {
        const res = await fetch("/api/ytdlp/check-update");
        const data = await res.json();
        ytdlpUpdateBadge.classList.remove("hidden");

        if (data.update_available) {
          ytdlpUpdateBadge.textContent = `Tersedia: v${data.latest_version}`;
          ytdlpUpdateBadge.className = "badge badge-info";
          upgradeYtdlpBtn.classList.remove("hidden");
          upgradeYtdlpBtn.textContent = `Update ke v${data.latest_version}`;
          showToast(`Versi baru yt-dlp tersedia (v${data.latest_version})!`, "info");
        } else {
          ytdlpUpdateBadge.textContent = "Versi Terbaru";
          ytdlpUpdateBadge.className = "badge badge-success";
          upgradeYtdlpBtn.classList.add("hidden");
          showToast(`yt-dlp sudah versi paling mutakhir (v${data.current_version}).`, "success");
        }
      } catch (err) {
        showToast("Gagal memeriksa update: " + err.message, "error");
      } finally {
        checkYtdlpBtn.disabled = false;
        checkYtdlpBtn.textContent = "Cek Update yt-dlp";
      }
    });
  }

  if (upgradeYtdlpBtn) {
    upgradeYtdlpBtn.addEventListener("click", async () => {
      upgradeYtdlpBtn.disabled = true;
      upgradeYtdlpBtn.textContent = "Mengupdate...";
      showToast("Sedang mengunduh dan mengupdate yt-dlp via pip...", "info");

      try {
        const res = await fetch("/api/ytdlp/update", { method: "POST" });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Gagal mengupdate.");

        showToast(`yt-dlp berhasil diupdate ke versi ${data.new_version}!`, "success");
        upgradeYtdlpBtn.classList.add("hidden");
        ytdlpUpdateBadge.textContent = "Versi Terbaru";
        ytdlpUpdateBadge.className = "badge badge-success";
        loadSystemStatus();
      } catch (err) {
        showToast("Error update: " + err.message, "error");
        upgradeYtdlpBtn.disabled = false;
        upgradeYtdlpBtn.textContent = "Coba Update Lagi";
      }
    });
  }

  if (autoUpdateYtdlpCheckbox) {
    // Load auto-update setting
    fetch("/api/settings/auto-update")
      .then((r) => r.json())
      .then((d) => {
        autoUpdateYtdlpCheckbox.checked = !!d.enabled;
      })
      .catch(() => {});

    autoUpdateYtdlpCheckbox.addEventListener("change", async () => {
      try {
        await fetch("/api/settings/auto-update", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ enabled: autoUpdateYtdlpCheckbox.checked }),
        });
        showToast(
          autoUpdateYtdlpCheckbox.checked
            ? "Auto-update yt-dlp diaktifkan."
            : "Auto-update yt-dlp dinonaktifkan.",
          "info"
        );
      } catch {
        showToast("Gagal menyimpan preferensi auto-update.", "error");
      }
    });
  }

  // Initial load
  loadSettings();
  loadSystemStatus();
  loadHistory();
  loadDashboardStats();
  pollTasks();
});
