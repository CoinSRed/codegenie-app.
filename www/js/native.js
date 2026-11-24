/**
 * native.js
 * Thin wrapper around the custom "GameLauncher" Capacitor plugin
 * (see android-native/java/.../GameLauncherPlugin.java).
 *
 * On a real Android build, window.Capacitor.Plugins.GameLauncher is the
 * native plugin registered by MainActivity. When this page is opened in a
 * plain desktop/mobile browser (e.g. while testing the UI), the native
 * bridge does not exist, so every call below resolves with a clearly
 * labelled "unsupported in browser preview" result instead of pretending
 * to succeed.
 */
(function (global) {
  function getNativePlugin() {
    return (global.Capacitor && global.Capacitor.Plugins && global.Capacitor.Plugins.GameLauncher) || null;
  }

  const isNative = () => !!getNativePlugin();

  async function callNative(method, args) {
    const plugin = getNativePlugin();
    if (!plugin) {
      throw new Error("NATIVE_UNAVAILABLE");
    }
    return plugin[method](args || {});
  }

  const NativeBridge = {
    isNative,

    /**
     * Opens the Android Storage Access Framework folder picker
     * (Intent.ACTION_OPEN_DOCUMENT_TREE) and persists read permission
     * for the chosen tree.
     * Resolves: { uri, displayName }
     */
    async pickFolder() {
      return callNative("pickFolder");
    },

    /**
     * Walks the chosen folder (via DocumentFile) and reports what was
     * found: total size, file count, and whether it contains something
     * this launcher knows how to start (an installable APK, or an
     * installed package reference file).
     * Resolves: { sizeBytes, fileCount, kind, payload }
     *   kind: "apk" | "package-ref" | "native-binary" | "unknown"
     */
    async inspectFolder(uri) {
      return callNative("inspectFolder", { uri });
    },

    /**
     * Opens the native image picker so the user can choose a custom
     * cover image. Resolves: { dataUrl }
     */
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
     * system package installer. The user still has to confirm the
     * system install dialog — this launcher cannot silently install apps.
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
