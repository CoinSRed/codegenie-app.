/**
 * app.js — PORTX Game Launcher UI logic.
 * No frameworks: plain DOM + the Storage / NativeBridge helpers.
 */
(function () {
  "use strict";

  let games = [];
  let searchTerm = "";
  let pendingImport = null; // { uri, displayName, kind, payload, sizeBytes }
  let pendingCoverDataUrl = null;

  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => Array.from(document.querySelectorAll(sel));

  // ---------- small utilities ----------

  function uid() {
    return "g_" + Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
  }

  function formatBytes(bytes) {
    if (!bytes || bytes <= 0) return "Unknown size";
    const units = ["B", "KB", "MB", "GB"];
    let i = 0;
    let n = bytes;
    while (n >= 1024 && i < units.length - 1) {
      n /= 1024;
      i++;
    }
    return `${n.toFixed(n >= 10 || i === 0 ? 0 : 1)} ${units[i]}`;
  }

  function toast(message, isError) {
    const el = $("#toast");
    el.textContent = message;
    el.classList.remove("hidden");
    el.classList.toggle("error", !!isError);
    clearTimeout(toast._t);
    toast._t = setTimeout(() => el.classList.add("hidden"), 3600);
  }

  function statusLabel(game) {
    switch (game.status) {
      case "ready":
        return "Ready to play";
      case "needs-install":
        return "Not installed";
      case "unsupported":
        return "Unsupported format";
      case "checking":
        return "Checking…";
      default:
        return "Imported";
    }
  }

  // ---------- rendering ----------

  function render() {
    renderHero();
    renderGrid();
  }

  function renderHero() {
    const hero = $("#hero");
    if (games.length === 0) {
      hero.classList.add("hidden");
      return;
    }
    const featured = games.slice().sort((a, b) => (b.lastPlayed || 0) - (a.lastPlayed || 0))[0];
    hero.classList.remove("hidden");
    $("#heroArt").style.backgroundImage = featured.cover ? `url(${featured.cover})` : "none";
    $("#heroTitle").textContent = featured.name;
    $("#heroStatus").textContent = statusLabel(featured);
    $("#heroMeta").textContent = formatBytes(featured.sizeBytes);
    $("#heroPlay").onclick = () => playGame(featured.id);
  }

  function renderGrid() {
    const grid = $("#gameGrid");
    const empty = $("#emptyState");
    const filtered = games.filter((g) =>
      g.name.toLowerCase().includes(searchTerm.toLowerCase())
    );

    $("#libraryCount").textContent =
      games.length === 1 ? "1 game" : `${games.length} games`;

    if (games.length === 0) {
      empty.classList.add("show");
      grid.innerHTML = "";
      return;
    }
    empty.classList.remove("show");

    grid.innerHTML = filtered
      .map((g) => {
        const dotClass =
          g.status === "ready" ? "ready" : g.status === "unsupported" ? "error" : "";
        const coverStyle = g.cover ? `style="background-image:url(${g.cover})"` : "";
        return `
        <div class="game-card ${g.status === "unsupported" ? "unsupported" : ""}" data-id="${g.id}">
          <div class="card-cover" ${coverStyle}>
            ${g.cover ? "" : coverFallbackSvg()}
            <span class="card-status-dot ${dotClass}"></span>
          </div>
          <div class="card-body">
            <div class="card-name">${escapeHtml(g.name)}</div>
            <div class="card-meta">${formatBytes(g.sizeBytes)} · ${statusLabel(g)}</div>
            <div class="card-actions">
              <button class="card-btn play" data-action="play" title="Play">${playSvg()}</button>
              <button class="card-btn" data-action="settings" title="Settings">${gearSvg()}</button>
              <button class="card-btn danger" data-action="remove" title="Remove">${xSvg()}</button>
            </div>
          </div>
        </div>`;
      })
      .join("");
  }

  function escapeHtml(s) {
    const d = document.createElement("div");
    d.textContent = s;
    return d.innerHTML;
  }

  function coverFallbackSvg() {
    return `<svg viewBox="0 0 24 24"><path d="M4 16l4.5-6 3.5 4.5 2.5-3L20 16" fill="none" stroke="currentColor" stroke-width="1.4"/><rect x="3" y="4" width="18" height="16" rx="2" fill="none" stroke="currentColor" stroke-width="1.4"/></svg>`;
  }
  function playSvg() {
    return `<svg viewBox="0 0 24 24"><path d="M7 5v14l11-7L7 5Z" fill="currentColor"/></svg>`;
  }
  function gearSvg() {
    return `<svg viewBox="0 0 24 24"><path d="M12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Z" fill="none" stroke="currentColor" stroke-width="1.6"/></svg>`;
  }
  function xSvg() {
    return `<svg viewBox="0 0 24 24"><path d="M6 6l12 12M18 6L6 18" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>`;
  }

  // ---------- add game flow ----------

  function openAddModal() {
    pendingImport = null;
    pendingCoverDataUrl = null;
    $("#stepDetails").classList.add("hidden");
    $("#stepPick").classList.remove("hidden");
    $("#pickHint").textContent = "";
    $("#inputGameName").value = "";
    $("#inputPackageName").value = "";
    $("#packageNameHint").textContent = "";
    $("#coverPreview").style.backgroundImage = "";
    $("#detectedInfo").classList.remove("show");
    $("#addModal").classList.remove("hidden");
  }

  function closeModals() {
    $$(".modal-overlay, .drawer").forEach((el) => el.classList.add("hidden"));
  }

  async function handlePickFolder() {
    if (!NativeBridge.isNative()) {
      toast("Folder picking needs the Android app — this preview is browser-only.", true);
      return;
    }
    try {
      $("#pickHint").textContent = "Opening folder picker…";
      const { uri, displayName } = await NativeBridge.pickFolder();
      $("#pickHint").textContent = `Reading "${displayName}"…`;

      const info = await NativeBridge.inspectFolder(uri);
      pendingImport = {
        uri,
        displayName,
        kind: info.kind,
        payload: info.payload,
        sizeBytes: info.sizeBytes,
      };

      $("#inputGameName").value = displayName || "";
      renderDetectedInfo(info);
      renderPackageField(info);

      $("#stepPick").classList.add("hidden");
      $("#stepDetails").classList.remove("hidden");
    } catch (err) {
      console.error(err);
      $("#pickHint").textContent = "Folder selection was cancelled or failed.";
    }
  }

  function renderDetectedInfo(info) {
    const box = $("#detectedInfo");
    box.classList.add("show");
    let line;
    switch (info.kind) {
      case "apk":
        line = "Found an installable APK inside this folder. You'll be asked to install it before the first launch.";
        break;
      case "package-ref":
        line = `This folder is linked to the installed app "${info.payload}". It will launch directly.`;
        break;
      case "native-binary":
        line = "This folder contains a native executable with no Android package. Most PC game binaries need a compatible runtime or engine that this launcher does not provide, so it can't be launched from here.";
        break;
      default:
        line = "No launchable Android package or executable was found in this folder.";
    }
    box.innerHTML = `${line}<br><br>Size: ${formatBytes(info.sizeBytes)}`;
  }

  function renderPackageField(info) {
    const input = $("#inputPackageName");
    const hint = $("#packageNameHint");

    if (info.kind === "package-ref") {
      input.value = info.payload || "";
      hint.textContent = "Detected from this folder's package.txt. Edit it if it's wrong.";
    } else if (info.kind === "apk") {
      input.value = "";
      hint.textContent =
        "Leave this blank for now — you can add it from the game's details after installing the APK, so Play launches it directly next time.";
    } else {
      input.value = "";
      hint.textContent =
        "If this game's app is already installed on your device, enter its package name here so Play can launch it directly.";
    }
  }

  async function handlePickCover() {
    if (!NativeBridge.isNative()) {
      toast("Image picking needs the Android app.", true);
      return;
    }
    try {
      const { dataUrl } = await NativeBridge.pickImage();
      pendingCoverDataUrl = dataUrl;
      $("#coverPreview").style.backgroundImage = `url(${dataUrl})`;
    } catch (err) {
      // user cancelled — not an error worth surfacing
    }
  }

  async function handleSaveGame() {
    const name = $("#inputGameName").value.trim();
    if (!name) {
      toast("Give the game a name first.", true);
      return;
    }
    if (!pendingImport) {
      toast("Pick a folder first.", true);
      return;
    }

    const manualPackage = $("#inputPackageName").value.trim();
    const apkUri = pendingImport.kind === "apk" ? pendingImport.payload : null;
    const packageName =
      manualPackage || (pendingImport.kind === "package-ref" ? pendingImport.payload : null) || null;

    const status = await resolveStatus(packageName, apkUri);

    const game = {
      id: uid(),
      name,
      folderUri: pendingImport.uri,
      detectedKind: pendingImport.kind,
      apkUri,
      packageName,
      sizeBytes: pendingImport.sizeBytes || 0,
      cover: pendingCoverDataUrl,
      status,
      createdAt: Date.now(),
      lastPlayed: 0,
    };

    games = await Storage.addGame(game);
    render();
    closeModals();
    toast(`${name} added to your library.`);
  }

  /** Works out a game's status from what we currently know about it. */
  async function resolveStatus(packageName, apkUri) {
    if (packageName) {
      try {
        const res = await NativeBridge.isPackageInstalled(packageName);
        return res.installed ? "ready" : "needs-install";
      } catch (e) {
        return "needs-install";
      }
    }
    if (apkUri) return "needs-install";
    return "unsupported";
  }

  // ---------- play / launch ----------

  async function playGame(id) {
    const game = games.find((g) => g.id === id);
    if (!game) return;

    if (!NativeBridge.isNative()) {
      toast("Launching needs the Android app — this preview is browser-only.", true);
      return;
    }

    try {
      if (game.packageName) {
        const res = await NativeBridge.isPackageInstalled(game.packageName);
        if (res.installed) {
          await NativeBridge.launchPackage(game.packageName);
          await touchLastPlayed(id);
          await updateGameStatus(id, "ready");
          return;
        }

        await updateGameStatus(id, "needs-install");
        if (game.apkUri) {
          toast(`Installing ${game.name} — confirm the system prompt, then press Play again.`);
          await NativeBridge.installApk(game.apkUri);
        } else {
          toast(`${game.name} isn't installed on this device. Install it, then press Play again.`, true);
        }
        return;
      }

      if (game.apkUri) {
        toast(
          `Installing ${game.name} — once it's installed, open its details and link its package name so Play launches it directly next time.`
        );
        await NativeBridge.installApk(game.apkUri);
        return;
      }

      toast(
        `${game.name} can't be launched directly. PC game ports need a compatible runtime or engine that this launcher doesn't provide.`,
        true
      );
    } catch (err) {
      console.error(err);
      toast(`Couldn't launch ${game.name}. ${err.message || ""}`, true);
    }
  }

  async function touchLastPlayed(id) {
    games = await Storage.updateGame(id, { lastPlayed: Date.now() });
    render();
  }

  async function updateGameStatus(id, status) {
    games = await Storage.updateGame(id, { status });
    render();
  }

  // ---------- per-game settings drawer ----------

  function formatDate(ts) {
    if (!ts) return "Never";
    return new Date(ts).toLocaleString(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    });
  }

  function detectedKindLabel(kind) {
    switch (kind) {
      case "apk":
        return "Installable APK found in the folder";
      case "package-ref":
        return "Linked to an installed app (package.txt)";
      case "native-binary":
        return "Native executable — needs a compatible runtime";
      default:
        return "No launchable package found";
    }
  }

  function openGameSettings(id) {
    const game = games.find((g) => g.id === id);
    if (!game) return;

    $("#gsTitle").textContent = "Game details";
    $("#gsBody").innerHTML = `
      <div class="settings-group" style="border-top:none;padding-top:0;display:flex;gap:12px;align-items:flex-start;">
        <div class="cover-preview" style="${game.cover ? `background-image:url(${game.cover})` : ""}">
          ${game.cover ? "" : coverFallbackSvg()}
        </div>
        <label class="field" style="flex:1;margin-bottom:0;">
          <span>Name</span>
          <input type="text" id="gsName" value="${escapeHtml(game.name)}" />
        </label>
      </div>

      <div class="settings-group">
        <h3>Launch</h3>
        <p class="hint">${detectedKindLabel(game.detectedKind)}</p>
        <label class="field">
          <span>Linked package name</span>
          <input type="text" id="gsPackage" placeholder="e.g. com.studio.mygame" value="${escapeHtml(game.packageName || "")}" autocapitalize="none" autocorrect="off" />
        </label>
        <button class="btn-outline" id="btnSavePackage" style="width:100%;margin-bottom:8px;">Save &amp; check status</button>
        ${
          game.apkUri
            ? `<button class="btn-outline" id="btnInstallApk" style="width:100%;">Open installer for this game's APK</button>`
            : ""
        }
      </div>

      <div class="settings-group">
        <h3>Info</h3>
        <p class="hint">Status: ${statusLabel(game)}</p>
        <p class="hint">Size: ${formatBytes(game.sizeBytes)}</p>
        <p class="hint">Added: ${formatDate(game.createdAt)}</p>
        <p class="hint">Last played: ${formatDate(game.lastPlayed)}</p>
        <p class="hint" style="word-break:break-all;">Source: ${escapeHtml(game.folderUri)}</p>
      </div>

      <div class="settings-group">
        <button class="btn-outline" id="btnForget" style="width:100%;color:var(--danger);border-color:rgba(255,90,106,.4);">Remove from library</button>
      </div>
    `;
    $("#gameSettingsDrawer").classList.remove("hidden");

    $("#gsName").addEventListener("change", async (e) => {
      const newName = e.target.value.trim();
      if (!newName) return;
      games = await Storage.updateGame(id, { name: newName });
      render();
    });

    $("#btnSavePackage").onclick = async () => {
      const pkg = $("#gsPackage").value.trim() || null;
      const status = await resolveStatus(pkg, game.apkUri);
      games = await Storage.updateGame(id, { packageName: pkg, status });
      render();
      toast(
        pkg
          ? status === "ready"
            ? "Linked and confirmed installed."
            : "Saved — that package isn't installed yet."
          : "Package link removed."
      );
    };

    if (game.apkUri) {
      $("#btnInstallApk").onclick = async () => {
        try {
          await NativeBridge.installApk(game.apkUri);
        } catch (e) {
          toast("Couldn't open the installer.", true);
        }
      };
    }

    $("#btnForget").onclick = async () => {
      games = await Storage.removeGame(id);
      render();
      closeModals();
      toast(`${game.name} removed.`);
    };
  }

  async function removeGame(id) {
    const game = games.find((g) => g.id === id);
    games = await Storage.removeGame(id);
    render();
    toast(game ? `${game.name} removed.` : "Game removed.");
  }

  // ---------- launcher settings ----------

  async function openLauncherSettings() {
    const settings = await Storage.getLauncherSettings();
    $("#setResolution").value = settings.resolution || "Native";
    $("#setFps").value = settings.fps || "60";
    $("#setVsync").checked = settings.vsync !== false;
    $("#setPreset").value = settings.preset || "High";
    $("#setTexture").value = settings.texture || "Medium";
    $("#settingsDrawer").classList.remove("hidden");

    $("#cacheHint").textContent = "Checking cache size…";
    if (NativeBridge.isNative()) {
      try {
        const { bytes } = await NativeBridge.getCacheSize();
        $("#cacheHint").textContent = `Cache size: ${formatBytes(bytes)}`;
      } catch (e) {
        $("#cacheHint").textContent = "Cache size: unavailable";
      }
    } else {
      $("#cacheHint").textContent = "Cache size: unavailable in browser preview";
    }
  }

  async function persistLauncherSettings() {
    const settings = {
      resolution: $("#setResolution").value,
      fps: $("#setFps").value,
      vsync: $("#setVsync").checked,
      preset: $("#setPreset").value,
      texture: $("#setTexture").value,
    };
    await Storage.saveLauncherSettings(settings);
  }

  async function handleClearCache() {
    if (!NativeBridge.isNative()) {
      toast("Cache clearing needs the Android app.", true);
      return;
    }
    try {
      await NativeBridge.clearCache();
      toast("Launcher cache cleared.");
      $("#cacheHint").textContent = "Cache size: 0 B";
    } catch (e) {
      toast("Couldn't clear cache.", true);
    }
  }

  // ---------- wiring ----------

  function wireEvents() {
    $("#btnAddGame").addEventListener("click", openAddModal);
    $("#btnAddGameEmpty").addEventListener("click", openAddModal);
    $("#btnPickFolder").addEventListener("click", handlePickFolder);
    $("#btnPickCover").addEventListener("click", handlePickCover);
    $("#btnSaveGame").addEventListener("click", handleSaveGame);
    $("#btnSettings").addEventListener("click", openLauncherSettings);
    $("#btnClearCache").addEventListener("click", handleClearCache);

    $$("[data-close]").forEach((el) => el.addEventListener("click", closeModals));
    $$(".modal-overlay, .drawer").forEach((overlay) => {
      overlay.addEventListener("click", (e) => {
        if (e.target === overlay) closeModals();
      });
    });

    ["setResolution", "setFps", "setVsync", "setPreset", "setTexture"].forEach((id) => {
      document.getElementById(id).addEventListener("change", persistLauncherSettings);
    });

    $("#searchInput").addEventListener("input", (e) => {
      searchTerm = e.target.value;
      renderGrid();
    });

    $("#gameGrid").addEventListener("click", (e) => {
      const card = e.target.closest(".game-card");
      if (!card) return;
      const action = e.target.closest("[data-action]")?.dataset.action;
      const id = card.dataset.id;
      if (action === "play") playGame(id);
      else if (action === "settings") openGameSettings(id);
      else if (action === "remove") removeGame(id);
    });
  }

  async function init() {
    wireEvents();
    games = await Storage.getLibrary();
    render();
  }

  document.addEventListener("DOMContentLoaded", init);
})();
