/**
 * native.js
 * Thin wrapper around the custom "GameLauncher" Capacitor plugin
 * (see android-native/java/.../GameLauncherPlugin.java).
 *
 * On a real Android build the native plugin registered by MainActivity is
 * reachable through Capacitor. When this page is opened in a plain
 * desktop/mobile browser (UI testing), no native bridge exists, so every
 * call rejects with code "NATIVE_UNAVAILABLE" instead of pretending to
 * succeed.
 *
 * Native rejections carry a machine-readable `err.code`:
 *   CANCELLED, PERMISSION_DENIED, EMPTY_FOLDER, NO_PICKER, SCAN_FAILED
 */
(function (global) {
  let cachedPlugin = null;

  function getNativePlugin() {
    if (cachedPlugin) return cachedPlugin;
    const cap = global.Capacitor;
    if (!cap) return null;

    // Not running inside the Android shell (plain browser preview).
    if (typeof cap.isNativePlatform === "function" && !cap.isNativePlatform()) {
      return null;
    }

    let plugin = (cap.Plugins && cap.Plugins.GameLauncher) || null;
    if (!plugin && typeof cap.registerPlugin === "function") {
      // Explicit registration is the reliable path in an unbundled web layer.
      plugin = cap.registerPlugin("GameLauncher");
    }
    cachedPlugin = plugin || null;
    return cachedPlugin;
  }

  const isNative = () => !!getNativePlugin();

  async function callNative(method, args) {
    const plugin = getNativePlugin();
    if (!plugin) {
      const err = new Error("NATIVE_UNAVAILABLE");
      err.code = "NATIVE_UNAVAILABLE";
      throw err;
    }
    return plugin[method](args || {});
  }

  const NativeBridge = {
    isNative,

    /**
     * Opens the Android Storage Access Framework folder picker
     * (Intent.ACTION_OPEN_DOCUMENT_TREE), persists read permission for the
     * chosen tree, and scans it with DocumentFile.
     * Resolves: {
     *   uri, displayName, persisted,
     *   sizeBytes, fileCount, folderCount, truncated,
     *   kind: "apk" | "package-ref" | "native-binary" | "game-data" | "unknown",
     *   payload, signals: string[]
     * }
     * Rejects with err.code CANCELLED / PERMISSION_DENIED / EMPTY_FOLDER /
     * NO_PICKER / SCAN_FAILED.
     */
    async pickFolder() {
      return callNative("pickFolder");
    },

    /** Re-scans an already-granted folder. Same result shape as pickFolder (minus uri). */
    async inspectFolder(uri) {
      return callNative("inspectFolder", { uri });
    },

    /** Resolves: { accessible: boolean } — false if the permission was lost. */
    async checkFolderAccess(uri) {
      return callNative("checkFolderAccess", { uri });
    },

    /** Releases the persisted permission of a folder no game uses any more. */
    async releaseFolder(uri) {
      return callNative("releaseFolder", { uri });
    },

    /** Native image picker for a custom cover. Resolves: { dataUrl } */
    async pickImage() {
      return callNative("pickImage");
    },

    /** Resolves: { installed: boolean } */
    async isPackageInstalled(packageName) {
      return callNative("isPackageInstalled", { packageName });
    },

    /** Launches an already-installed app by package name. */
    async launchPackage(packageName) {
      return callNative("launchPackage", { packageName });
    },

    /**
     * Starts installing an APK found inside an imported folder via the
     * system package installer. The user still has to confirm the system
     * dialog — this launcher cannot silently install apps.
     */
    async installApk(uri) {
      return callNative("installApk", { uri });
    },

    /** Resolves: { bytes } */
    async getCacheSize() {
      return callNative("getCacheSize");
    },

    async clearCache() {
      return callNative("clearCache");
    },
  };

  global.NativeBridge = NativeBridge;
})(window);
