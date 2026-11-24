# Building PORTX Game Launcher in Termux

This produces a real, installable **debug APK** from this project. It assumes
Termux with storage access set up on an Android device (Android 8+
recommended, more RAM = faster build — 4 GB+ is comfortable).

## 1. Install the toolchain

```bash
pkg update && pkg upgrade -y
pkg install -y nodejs-lts openjdk-17 git wget unzip
termux-setup-storage
```

## 2. Get the Android SDK command-line tools

Capacitor's Gradle build needs `ANDROID_HOME` pointing at a real Android SDK.

```bash
mkdir -p ~/android-sdk/cmdline-tools
cd ~/android-sdk/cmdline-tools
wget https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip
unzip commandlinetools-linux-*.zip
mv cmdline-tools latest
```

Add to `~/.bashrc` (then `source ~/.bashrc`):

```bash
export ANDROID_HOME=$HOME/android-sdk
export PATH=$PATH:$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools
```

Accept licenses and install the platform + build tools used by Capacitor 6:

```bash
yes | sdkmanager --licenses
sdkmanager "platform-tools" "platforms;android-34" "build-tools;34.0.0"
```

## 3. Copy this project onto the device

Put the whole `portx/` folder (everything in this delivery) somewhere under
your Termux home, e.g. `~/portx`.

```bash
cd ~/portx
npm install
```

## 4. Generate the Android project

This is the step that creates the full `android/` Gradle project (the
wrapper, `build.gradle` files, manifest, etc.) around the `www/` folder and
`capacitor.config.json` already in this delivery.

```bash
npx cap init "PORTX Game Launcher" "com.portx.launcher" --web-dir=www
npx cap add android
```

## 5. Drop in the custom native plugin

```bash
# Java source for the GameLauncher plugin + MainActivity
mkdir -p android/app/src/main/java/com/portx/launcher
cp android-native/java/com/portx/launcher/*.java \
   android/app/src/main/java/com/portx/launcher/
```

Capacitor's template already generates its own `MainActivity.java` under
that same package — **replace it** with the one in this delivery, which adds
the single line `registerPlugin(GameLauncherPlugin.class);`.

## 5b. Install the app icon

This delivery includes a ready-made adaptive icon (`res/`) instead of
Capacitor's generic default icon.

```bash
cp -r android-native/res/mipmap-mdpi/*    android/app/src/main/res/mipmap-mdpi/
cp -r android-native/res/mipmap-hdpi/*    android/app/src/main/res/mipmap-hdpi/
cp -r android-native/res/mipmap-xhdpi/*   android/app/src/main/res/mipmap-xhdpi/
cp -r android-native/res/mipmap-xxhdpi/*  android/app/src/main/res/mipmap-xxhdpi/
cp -r android-native/res/mipmap-xxxhdpi/* android/app/src/main/res/mipmap-xxxhdpi/
mkdir -p android/app/src/main/res/mipmap-anydpi-v26
cp android-native/res/mipmap-anydpi-v26/*.xml android/app/src/main/res/mipmap-anydpi-v26/
cp android-native/res/drawable/ic_launcher_foreground.png android/app/src/main/res/drawable/
cp android-native/res/values/ic_launcher_background.xml android/app/src/main/res/values/
```

This overwrites Capacitor's placeholder `ic_launcher`/`ic_launcher_round` at
every density and wires up the adaptive icon (`mipmap-anydpi-v26`) used on
Android 8+. `res/store-listing/play_store_icon_512.png` is a flat 512×512
copy for a store listing — it isn't used by the app itself.

## 6. Apply the manifest and Gradle additions

- Open `android/app/src/main/AndroidManifest.xml` and merge in the contents
  of `android-native/manifest/AndroidManifest-additions.xml` (the
  `<queries>` block and the `REQUEST_INSTALL_PACKAGES` permission).
- Open `android/app/build.gradle` and add the one dependency line from
  `android-native/gradle/build-gradle-additions.txt` to the `dependencies { }`
  block.
- Add `@capacitor/preferences` to the Capacitor plugin list by running:

```bash
npx cap sync android
```

(`cap sync` copies `www/` into the Android project and wires up installed
Capacitor plugins like Preferences automatically — run it again any time you
edit files under `www/`.)

## 7. Build the debug APK

```bash
cd android
chmod +x gradlew
./gradlew assembleDebug
```

On success, the APK is at:

```
android/app/build/outputs/apk/debug/app-debug.apk
```

Copy it to your phone's storage and install it (enable "install unknown
apps" for whichever app you use to open it):

```bash
cp app/build/outputs/apk/debug/app-debug.apk /sdcard/Download/
```

## 8. Rebuilding after changes

- Edited only `www/` (HTML/CSS/JS)? → `npx cap sync android` then
  `./gradlew assembleDebug` again.
- Edited `GameLauncherPlugin.java` or the manifest? → just
  `./gradlew assembleDebug` again from `android/`.

## Troubleshooting

- **`SDK location not found`** — make sure `ANDROID_HOME` is exported in the
  same shell session, or create `android/local.properties` with
  `sdk.dir=/data/data/com.termux/files/home/android-sdk`.
- **Out of memory during build** — add a `gradle.properties` in `android/`
  with `org.gradle.jvmargs=-Xmx1536m` to cap Gradle's memory use on
  lower-RAM devices.
- **`license not accepted`** — re-run `yes | sdkmanager --licenses`.
