/**
 * storage.js
 * Persists the game library and per-game/launcher settings.
 * Uses the Capacitor Preferences plugin on-device (backed by
 * SharedPreferences on Android, so it survives app restarts), and falls
 * back to localStorage when Preferences isn't available (browser preview).
 */
(function (global) {
  const LIBRARY_KEY = "portx.library.v1";
  const LAUNCHER_SETTINGS_KEY = "portx.settings.v1";

  function getPreferences() {
    return (
      (global.Capacitor &&
        global.Capacitor.Plugins &&
        global.Capacitor.Plugins.Preferences) ||
      null
    );
  }

  async function rawGet(key) {
    const prefs = getPreferences();
    if (prefs) {
      const { value } = await prefs.get({ key });
      return value;
    }
    return global.localStorage.getItem(key);
  }

  async function rawSet(key, value) {
    const prefs = getPreferences();
    if (prefs) {
      return prefs.set({ key, value });
    }
    return global.localStorage.setItem(key, value);
  }

  const Storage = {
    async getLibrary() {
      const raw = await rawGet(LIBRARY_KEY);
      if (!raw) return [];
      try {
        return JSON.parse(raw);
      } catch (e) {
        console.error("Corrupt library data, resetting.", e);
        return [];
      }
    },

    async saveLibrary(games) {
      await rawSet(LIBRARY_KEY, JSON.stringify(games));
    },

    async addGame(game) {
      const games = await this.getLibrary();
      games.push(game);
      await this.saveLibrary(games);
      return games;
    },

    async updateGame(id, patch) {
      const games = await this.getLibrary();
      const idx = games.findIndex((g) => g.id === id);
      if (idx !== -1) {
        games[idx] = Object.assign({}, games[idx], patch);
        await this.saveLibrary(games);
      }
      return games;
    },

    async removeGame(id) {
      const games = await this.getLibrary();
      const next = games.filter((g) => g.id !== id);
      await this.saveLibrary(next);
      return next;
    },

    async getLauncherSettings() {
      const raw = await rawGet(LAUNCHER_SETTINGS_KEY);
      if (!raw) {
        return {
          resolution: "Native",
          fps: "60",
          vsync: true,
          preset: "High",
          texture: "Medium",
        };
      }
      try {
        return JSON.parse(raw);
      } catch (e) {
        return {};
      }
    },

    async saveLauncherSettings(settings) {
      await rawSet(LAUNCHER_SETTINGS_KEY, JSON.stringify(settings));
    },
  };

  global.Storage = Storage;
})(window);
