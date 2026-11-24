# PORTX EMULATOR — build plan

## Verified facts (Stage 1)
- Base: `brunodev85/winlator` → app source lives in the submodule `brunodev85/winlator-app`
  (pinned here at commit `f8a211ce7fd776de9a2642b45d166016876eaa86`, Winlator 11.2).
- License: **LGPL-2.1** (LICENSE file checked in both repos). Redistributing a modified build requires
  publishing our modifications + keeping notices. Bundled parts keep their own licences
  (Wine LGPL, Box64 MIT, DXVK zlib, VKD3D LGPL, Mesa/Turnip MIT) — to be listed in NOTICE before release.
- Build: Gradle 8.14.5, AGP 8.4.2, compileSdk 35, minSdk 26, **targetSdk 28**, NDK 24.0.8215888,
  CMake 3.22.1, ABI arm64-v8a only. Native code (~7 MB C/C++) builds with the app.
- `targetSdk 28` is deliberate upstream: Android blocks executing binaries from app data on targetSdk >= 29.
  So the emulator APK is **sideload-only** (not Google Play) and we must NOT raise targetSdk.
- Package name `com.winlator` is hard-coded in native headers (`winlator.h`, `vortek.h`, `gladio.h`) and
  `AppUtils.java`. Rebranding the applicationId means patching those and verifying every runtime path.
  Until verified, PORTX EMULATOR keeps `com.winlator` (uninstall official Winlator first).
- GPU reality: Turnip = Adreno only. Mali/Xclipse use Vortek (system Vulkan driver wrapper) or Gladio (GL).
  Upstream states Turnip on Mali fails to start. Smart Optimization must detect GPU and never force Turnip.

## Architecture
```
codegenie-app (this branch: portx-emulator)
├── .github/workflows/build-emulator.yml   clones pinned upstream, applies overlay, builds APK
├── overlay/                               ONLY our changes (copied over upstream before build)
│   ├── res/values/strings.xml             branding
│   └── (later) java/com/portx/...         library, importer, smart optimization, WebView UI
├── scripts/apply-overlay.sh
└── docs/PLAN.md
```
Upstream is fetched at build time (not copied here) so the repo stays small; the overlay + pinned commit
is the corresponding source for LGPL purposes.

PORTX UI: a `PortxActivity` hosting the existing HTML/CSS/JS in a WebView, with a `@JavascriptInterface`
bridge (replaces the Capacitor plugin). It calls Winlator's own container/launch code
(`XServerDisplayActivity` extras: `container_id`, `exec_path`, `shortcut_path`).

## Stages
1. Study source + licences ........ DONE (above)
2. Fork pipeline .................. build pinned upstream with PORTX branding on GitHub Actions  <- current
3. Engine verification ........... confirm Wine/Box64/DXVK/Vortek components install & a test exe starts
4. Library + folder import ....... SAF import, .exe detection, per-game config -> Winlator containers/shortcuts
5. Containers .................... create/edit/delete/assign, resolution, driver, env vars (reuse Winlator container API)
6. Smart Optimization ............ real device detection, GPU-based backend choice, RAM profiles, benchmark
7. Controls + overlay ............ reuse Winlator input controls; FPS/RAM/temp overlay
8. APK + test ..................... debug APK from CI, tested on a real device by the user

## Honest limits
- No device in the build environment: nothing is runtime-tested by me; the user's phone is the test bench.
- 4 GB RAM / Mali phones: compatibility depends on the driver; GTA V is an advanced target, not a promise.
- Benchmarks must come from a running game on the device; no simulated numbers.
