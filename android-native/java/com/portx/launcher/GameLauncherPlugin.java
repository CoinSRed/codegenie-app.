package com.portx.launcher;

import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.ContentResolver;
import android.content.Intent;
import android.content.UriPermission;
import android.content.pm.ApplicationInfo;
import android.content.pm.PackageManager;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Canvas;
import android.graphics.drawable.Drawable;
import android.net.Uri;
import android.os.SystemClock;
import android.util.Base64;

import androidx.activity.result.ActivityResult;
import androidx.documentfile.provider.DocumentFile;

import com.getcapacitor.JSArray;
import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.ActivityCallback;
import com.getcapacitor.annotation.CapacitorPlugin;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.IOException;
import java.io.InputStream;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.regex.Pattern;

/**
 * GameLauncherPlugin
 *
 * Native half of PORTX Game Launcher. Registered under the bridge name
 * "GameLauncher" and called from www/js/native.js.
 *
 * Folder import
 * -------------------------------------------------------------------------
 * pickFolder() opens the Storage Access Framework tree picker
 * (ACTION_OPEN_DOCUMENT_TREE), persists read access with
 * takePersistableUriPermission(), then walks the chosen tree with AndroidX
 * DocumentFile - on a background thread, with a time and entry budget so a
 * multi-GB game folder can never freeze the app.
 *
 * Rejection codes (err.code on the JS side):
 *   CANCELLED          - the user backed out of the picker
 *   PERMISSION_DENIED  - Android refused (or later revoked) access to the tree
 *   EMPTY_FOLDER       - the folder has no files or sub-folders
 *   NO_PICKER          - no app on the device can show a folder picker
 *   SCAN_FAILED        - unexpected error while reading the folder
 *
 * Classification ("kind"):
 *   apk            - contains a .apk (installable through the system installer)
 *   package-ref    - contains package.txt naming an installed app to launch
 *   native-binary  - contains a PC-style executable (.exe / .x86_64)
 *   game-data      - contains game data (OBB, PAK, PCK, Data/ dirs, ...) but no
 *                    launchable runtime
 *   unknown        - non-empty folder with nothing recognisable
 * Every kind is importable; the UI shows "Imported - Runtime not detected"
 * when nothing launchable was found.
 */
@CapacitorPlugin(name = "GameLauncher")
public class GameLauncherPlugin extends Plugin {

    private static final int MAX_SCAN_DEPTH = 6;
    private static final int MAX_SCAN_ENTRIES = 4000;
    private static final long MAX_SCAN_MILLIS = 8000;
    private static final int COVER_MAX_DIMENSION = 800;
    private static final int MAX_PACKAGE_CANDIDATES = 25;
    // e.g. com.studio.game - used to recognise folders named after an Android package.
    private static final Pattern PACKAGE_NAME = Pattern.compile("^[A-Za-z][A-Za-z0-9_]*(\\.[A-Za-z0-9_]+)+$");

    // ---------------------------------------------------------------
    // Folder picking (Storage Access Framework)
    // ---------------------------------------------------------------

    @PluginMethod
    public void pickFolder(PluginCall call) {
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT_TREE);
        intent.addFlags(
            Intent.FLAG_GRANT_READ_URI_PERMISSION
                | Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION
                | Intent.FLAG_GRANT_PREFIX_URI_PERMISSION
        );
        try {
            startActivityForResult(call, intent, "pickFolderResult");
        } catch (ActivityNotFoundException e) {
            call.reject("This device has no app that can pick a folder.", "NO_PICKER");
        } catch (Exception e) {
            call.reject("Couldn't open the folder picker: " + e.getMessage(), "NO_PICKER");
        }
    }

    @ActivityCallback
    private void pickFolderResult(final PluginCall call, ActivityResult result) {
        if (call == null) return;

        Intent data = result.getData();
        if (result.getResultCode() != Activity.RESULT_OK || data == null || data.getData() == null) {
            call.reject("No folder was selected.", "CANCELLED");
            return;
        }

        final Uri treeUri = data.getData();
        final boolean persisted = persistReadPermission(treeUri);

        // The activity callback runs on the main thread; scanning must not.
        getBridge().execute(new Runnable() {
            @Override
            public void run() {
                try {
                    DocumentFile dir = DocumentFile.fromTreeUri(getContext(), treeUri);
                    if (dir == null || !dir.exists() || !dir.isDirectory() || !dir.canRead()) {
                        releaseQuietly(treeUri);
                        call.reject(
                            "Android denied access to that folder. Pick a sub-folder instead and tap \"Use this folder\".",
                            "PERMISSION_DENIED"
                        );
                        return;
                    }

                    ScanResult scan = scanTree(dir);
                    if (scan.isEmpty()) {
                        releaseQuietly(treeUri);
                        call.reject("That folder is empty.", "EMPTY_FOLDER");
                        return;
                    }

                    JSObject ret = describe(scan);
                    ret.put("uri", treeUri.toString());
                    ret.put("displayName", dir.getName() != null ? dir.getName() : "Imported game");
                    ret.put("persisted", persisted);
                    call.resolve(ret);
                } catch (SecurityException e) {
                    releaseQuietly(treeUri);
                    call.reject("Android denied access to that folder.", "PERMISSION_DENIED");
                } catch (Exception e) {
                    call.reject("Couldn't read that folder: " + e.getMessage(), "SCAN_FAILED");
                }
            }
        });
    }

    /** Persists read access across restarts. Returns true only if Android confirms it. */
    private boolean persistReadPermission(Uri treeUri) {
        try {
            getContext()
                .getContentResolver()
                .takePersistableUriPermission(treeUri, Intent.FLAG_GRANT_READ_URI_PERMISSION);
        } catch (SecurityException e) {
            return false;
        }
        return isPersisted(treeUri);
    }

    private boolean isPersisted(Uri treeUri) {
        ContentResolver resolver = getContext().getContentResolver();
        List<UriPermission> permissions = resolver.getPersistedUriPermissions();
        for (UriPermission p : permissions) {
            if (p.getUri().equals(treeUri) && p.isReadPermission()) return true;
        }
        return false;
    }

    private void releaseQuietly(Uri treeUri) {
        try {
            getContext()
                .getContentResolver()
                .releasePersistableUriPermission(treeUri, Intent.FLAG_GRANT_READ_URI_PERMISSION);
        } catch (Exception ignored) {
            // Nothing to release, or already released.
        }
    }

    // ---------------------------------------------------------------
    // Folder re-inspection / access checks
    // ---------------------------------------------------------------

    @PluginMethod
    public void inspectFolder(final PluginCall call) {
        final String uriStr = call.getString("uri");
        if (uriStr == null || uriStr.isEmpty()) {
            call.reject("Missing 'uri'.", "SCAN_FAILED");
            return;
        }

        getBridge().execute(new Runnable() {
            @Override
            public void run() {
                try {
                    DocumentFile dir = DocumentFile.fromTreeUri(getContext(), Uri.parse(uriStr));
                    if (dir == null || !dir.exists() || !dir.isDirectory() || !dir.canRead()) {
                        call.reject(
                            "This folder is no longer accessible. Permission may have been revoked.",
                            "PERMISSION_DENIED"
                        );
                        return;
                    }
                    ScanResult scan = scanTree(dir);
                    if (scan.isEmpty()) {
                        call.reject("That folder is empty.", "EMPTY_FOLDER");
                        return;
                    }
                    call.resolve(describe(scan));
                } catch (SecurityException e) {
                    call.reject("Android denied access to that folder.", "PERMISSION_DENIED");
                } catch (Exception e) {
                    call.reject("Couldn't read that folder: " + e.getMessage(), "SCAN_FAILED");
                }
            }
        });
    }

    @PluginMethod
    public void checkFolderAccess(final PluginCall call) {
        final String uriStr = call.getString("uri");
        if (uriStr == null || uriStr.isEmpty()) {
            call.reject("Missing 'uri'.", "SCAN_FAILED");
            return;
        }

        getBridge().execute(new Runnable() {
            @Override
            public void run() {
                boolean accessible = false;
                try {
                    Uri uri = Uri.parse(uriStr);
                    DocumentFile dir = DocumentFile.fromTreeUri(getContext(), uri);
                    accessible = isPersisted(uri) && dir != null && dir.exists() && dir.canRead();
                } catch (Exception ignored) {
                    accessible = false;
                }
                JSObject ret = new JSObject();
                ret.put("accessible", accessible);
                call.resolve(ret);
            }
        });
    }

    /** Frees the persisted permission slot of a folder that was removed from the library. */
    @PluginMethod
    public void releaseFolder(PluginCall call) {
        String uriStr = call.getString("uri");
        if (uriStr != null && !uriStr.isEmpty()) {
            releaseQuietly(Uri.parse(uriStr));
        }
        call.resolve(new JSObject());
    }

    // ---------------------------------------------------------------
    // Scanning
    // ---------------------------------------------------------------

    private static class ScanResult {
        long totalSize = 0;
        int fileCount = 0;
        int folderCount = 0;
        boolean truncated = false;
        long deadline = 0;
        DocumentFile apkFile = null;
        DocumentFile packageRefFile = null;
        DocumentFile nativeBinary = null;
        final Set<String> signals = new LinkedHashSet<>();
        final Set<String> packageCandidates = new LinkedHashSet<>();

        boolean isEmpty() {
            return fileCount == 0 && folderCount == 0;
        }
    }

    private ScanResult scanTree(DocumentFile root) {
        ScanResult scan = new ScanResult();
        scan.deadline = SystemClock.elapsedRealtime() + MAX_SCAN_MILLIS;
        addPackageCandidate(scan, root.getName());
        scanFolder(root, scan, 0);
        return scan;
    }

    /** Bounded walk (depth, entry count and wall-clock) so huge folders can't hang the app. */
    private void scanFolder(DocumentFile dir, ScanResult scan, int depth) {
        if (depth > MAX_SCAN_DEPTH) {
            scan.truncated = true;
            return;
        }

        for (DocumentFile child : dir.listFiles()) {
            if (scan.fileCount + scan.folderCount >= MAX_SCAN_ENTRIES
                || SystemClock.elapsedRealtime() > scan.deadline) {
                scan.truncated = true;
                return;
            }

            String name = child.getName();
            String lower = name == null ? "" : name.toLowerCase(Locale.ROOT);

            if (child.isDirectory()) {
                scan.folderCount++;
                if (isGameFolderName(lower)) scan.signals.add("DATA");
                addPackageCandidate(scan, name);
                scanFolder(child, scan, depth + 1);
                if (scan.truncated) return;
                continue;
            }

            scan.fileCount++;
            scan.totalSize += Math.max(0, child.length());
            classifyFile(child, lower, scan);
        }
    }

    private void addPackageCandidate(ScanResult scan, String name) {
        if (name == null || scan.packageCandidates.size() >= MAX_PACKAGE_CANDIDATES) return;
        if (PACKAGE_NAME.matcher(name).matches()) scan.packageCandidates.add(name);
    }

    private boolean isGameFolderName(String lower) {
        return lower.equals("data")
            || lower.equals("assets")
            || lower.equals("streamingassets")
            || lower.equals("obb")
            || lower.equals("paks")
            || lower.equals("binaries")
            || lower.equals("content")
            || lower.equals("engine")
            || lower.equals("managed")
            || lower.endsWith("_data");
    }

    private void classifyFile(DocumentFile file, String lower, ScanResult scan) {
        if (lower.endsWith(".apk")) {
            scan.signals.add("APK");
            if (scan.apkFile == null) scan.apkFile = file;
        } else if (lower.equals("package.txt")) {
            scan.signals.add("package.txt");
            if (scan.packageRefFile == null) scan.packageRefFile = file;
        } else if (lower.endsWith(".obb")) {
            scan.signals.add("OBB");
        } else if (lower.endsWith(".pak")) {
            scan.signals.add("PAK");
        } else if (lower.endsWith(".pck")) {
            scan.signals.add("PCK");
        } else if (lower.endsWith(".exe")) {
            scan.signals.add("EXE");
            if (scan.nativeBinary == null) scan.nativeBinary = file;
        } else if (lower.endsWith(".x86_64")) {
            scan.signals.add("BIN");
            if (scan.nativeBinary == null) scan.nativeBinary = file;
        } else if (lower.endsWith(".dll")) {
            scan.signals.add("DLL");
        } else if (lower.endsWith(".so")) {
            scan.signals.add("SO");
        } else if (lower.endsWith(".unity3d")
            || lower.endsWith(".assets")
            || lower.endsWith(".ucas")
            || lower.endsWith(".utoc")
            || lower.endsWith(".wad")
            || lower.endsWith(".vpk")) {
            scan.signals.add("DATA");
        }
    }

    private JSObject describe(ScanResult scan) {
        JSObject ret = new JSObject();
        ret.put("sizeBytes", scan.totalSize);
        ret.put("fileCount", scan.fileCount);
        ret.put("folderCount", scan.folderCount);
        ret.put("truncated", scan.truncated);

        JSArray signals = new JSArray();
        for (String s : scan.signals) signals.put(s);
        ret.put("signals", signals);

        // A folder named after an installed app (com.studio.game) identifies the game.
        String detectedPackage = detectInstalledApp(scan, ret);

        if (scan.apkFile != null) {
            ret.put("kind", "apk");
            ret.put("payload", scan.apkFile.getUri().toString());
        } else if (scan.packageRefFile != null) {
            String pkg = readSmallTextFile(scan.packageRefFile);
            ret.put("kind", "package-ref");
            ret.put("payload", pkg != null ? pkg.trim() : "");
        } else if (detectedPackage != null) {
            ret.put("kind", "installed-app");
            ret.put("payload", detectedPackage);
        } else if (scan.nativeBinary != null) {
            ret.put("kind", "native-binary");
            ret.put("payload", scan.nativeBinary.getName());
        } else if (!scan.signals.isEmpty()) {
            ret.put("kind", "game-data");
        } else {
            ret.put("kind", "unknown");
        }
        return ret;
    }

    /**
     * Looks for a folder name that is the package name of an app installed on
     * this device. On a hit, fills detectedPackage / detectedLabel / detectedIcon.
     * If none is installed, the first candidate is reported as suggestedPackage.
     */
    private String detectInstalledApp(ScanResult scan, JSObject ret) {
        PackageManager pm = getContext().getPackageManager();
        for (String pkg : scan.packageCandidates) {
            try {
                ApplicationInfo info = pm.getApplicationInfo(pkg, 0);
                ret.put("detectedPackage", pkg);
                ret.put("detectedLabel", String.valueOf(pm.getApplicationLabel(info)));
                String icon = iconDataUrl(pm.getApplicationIcon(info));
                if (icon != null) ret.put("detectedIcon", icon);
                return pkg;
            } catch (PackageManager.NameNotFoundException ignored) {
                // Not installed - try the next candidate.
            } catch (Exception ignored) {
                // Icon/label lookup failed - keep scanning.
            }
        }
        if (!scan.packageCandidates.isEmpty()) {
            ret.put("suggestedPackage", scan.packageCandidates.iterator().next());
        }
        return null;
    }

    private String iconDataUrl(Drawable drawable) {
        if (drawable == null) return null;
        try {
            int size = 256;
            Bitmap bitmap = Bitmap.createBitmap(size, size, Bitmap.Config.ARGB_8888);
            Canvas canvas = new Canvas(bitmap);
            drawable.setBounds(0, 0, size, size);
            drawable.draw(canvas);
            ByteArrayOutputStream out = new ByteArrayOutputStream();
            bitmap.compress(Bitmap.CompressFormat.PNG, 100, out);
            bitmap.recycle();
            return "data:image/png;base64," + Base64.encodeToString(out.toByteArray(), Base64.NO_WRAP);
        } catch (Exception e) {
            return null;
        }
    }

    private String readSmallTextFile(DocumentFile file) {
        try (InputStream in = getContext().getContentResolver().openInputStream(file.getUri())) {
            if (in == null) return null;
            ByteArrayOutputStream out = new ByteArrayOutputStream();
            byte[] buf = new byte[1024];
            int read;
            int totalRead = 0;
            // package.txt is expected to be a single short line; cap at 4KB.
            while ((read = in.read(buf)) != -1 && totalRead < 4096) {
                out.write(buf, 0, read);
                totalRead += read;
            }
            return out.toString("UTF-8");
        } catch (IOException e) {
            return null;
        }
    }

    // ---------------------------------------------------------------
    // Package install / launch
    // ---------------------------------------------------------------

    @PluginMethod
    public void isPackageInstalled(PluginCall call) {
        String packageName = call.getString("packageName");
        if (packageName == null || packageName.isEmpty()) {
            call.reject("Missing 'packageName'.");
            return;
        }
        PackageManager pm = getContext().getPackageManager();
        boolean installed;
        try {
            pm.getPackageInfo(packageName, 0);
            installed = true;
        } catch (PackageManager.NameNotFoundException e) {
            // Fall back to the launcher lookup in case package visibility hides getPackageInfo.
            installed = pm.getLaunchIntentForPackage(packageName) != null;
        }
        JSObject ret = new JSObject();
        ret.put("installed", installed);
        call.resolve(ret);
    }

    @PluginMethod
    public void launchPackage(PluginCall call) {
        String packageName = call.getString("packageName");
        if (packageName == null || packageName.isEmpty()) {
            call.reject("Missing 'packageName'.");
            return;
        }

        Intent launchIntent = getContext().getPackageManager().getLaunchIntentForPackage(packageName);
        if (launchIntent == null) {
            call.reject("'" + packageName + "' is not installed or has no launchable activity.");
            return;
        }

        launchIntent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        getContext().startActivity(launchIntent);
        call.resolve(new JSObject());
    }

    @PluginMethod
    public void installApk(PluginCall call) {
        String uriStr = call.getString("uri");
        if (uriStr == null) {
            call.reject("Missing 'uri'.");
            return;
        }

        Intent intent = new Intent(Intent.ACTION_VIEW);
        intent.setDataAndType(Uri.parse(uriStr), "application/vnd.android.package-archive");
        intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_ACTIVITY_NEW_TASK);

        // No resolveActivity() pre-check: on Android 11+ package visibility
        // makes it return null even when a system installer exists.
        try {
            getContext().startActivity(intent);
            call.resolve(new JSObject());
        } catch (ActivityNotFoundException e) {
            call.reject("No package installer is available on this device.");
        } catch (SecurityException e) {
            call.reject("Android blocked opening this APK. Allow PORTX to install apps in system settings and try again.");
        }
    }

    // ---------------------------------------------------------------
    // Cover image picking
    // ---------------------------------------------------------------

    @PluginMethod
    public void pickImage(PluginCall call) {
        Intent intent = new Intent(Intent.ACTION_GET_CONTENT);
        intent.setType("image/*");
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        try {
            startActivityForResult(call, intent, "pickImageResult");
        } catch (ActivityNotFoundException e) {
            call.reject("This device has no app that can pick an image.");
        }
    }

    @ActivityCallback
    private void pickImageResult(final PluginCall call, ActivityResult result) {
        if (call == null) return;

        if (result.getResultCode() != Activity.RESULT_OK || result.getData() == null) {
            call.reject("Image selection was cancelled.");
            return;
        }

        final Uri imageUri = result.getData().getData();
        if (imageUri == null) {
            call.reject("No image was returned.");
            return;
        }

        getBridge().execute(new Runnable() {
            @Override
            public void run() {
                try {
                    Bitmap bitmap = decodeScaled(imageUri, COVER_MAX_DIMENSION);
                    if (bitmap == null) {
                        call.reject("That file isn't a readable image.");
                        return;
                    }
                    // Re-encoded + downscaled so the saved library stays small.
                    ByteArrayOutputStream out = new ByteArrayOutputStream();
                    bitmap.compress(Bitmap.CompressFormat.JPEG, 85, out);
                    bitmap.recycle();

                    JSObject ret = new JSObject();
                    ret.put(
                        "dataUrl",
                        "data:image/jpeg;base64," + Base64.encodeToString(out.toByteArray(), Base64.NO_WRAP)
                    );
                    call.resolve(ret);
                } catch (IOException e) {
                    call.reject("Failed to read the selected image: " + e.getMessage());
                } catch (OutOfMemoryError e) {
                    call.reject("That image is too large to use as a cover.");
                }
            }
        });
    }

    private Bitmap decodeScaled(Uri uri, int maxDim) throws IOException {
        ContentResolver resolver = getContext().getContentResolver();

        BitmapFactory.Options bounds = new BitmapFactory.Options();
        bounds.inJustDecodeBounds = true;
        try (InputStream in = resolver.openInputStream(uri)) {
            if (in == null) return null;
            BitmapFactory.decodeStream(in, null, bounds);
        }
        if (bounds.outWidth <= 0 || bounds.outHeight <= 0) return null;

        int longest = Math.max(bounds.outWidth, bounds.outHeight);
        int sample = 1;
        while (longest / (sample * 2) >= maxDim) sample *= 2;

        BitmapFactory.Options opts = new BitmapFactory.Options();
        opts.inSampleSize = sample;
        Bitmap bitmap;
        try (InputStream in = resolver.openInputStream(uri)) {
            if (in == null) return null;
            bitmap = BitmapFactory.decodeStream(in, null, opts);
        }
        if (bitmap == null) return null;

        int big = Math.max(bitmap.getWidth(), bitmap.getHeight());
        if (big > maxDim) {
            float scale = (float) maxDim / big;
            int w = Math.max(1, Math.round(bitmap.getWidth() * scale));
            int h = Math.max(1, Math.round(bitmap.getHeight() * scale));
            Bitmap scaled = Bitmap.createScaledBitmap(bitmap, w, h, true);
            if (scaled != bitmap) bitmap.recycle();
            bitmap = scaled;
        }
        return bitmap;
    }

    // ---------------------------------------------------------------
    // Cache management
    // ---------------------------------------------------------------

    @PluginMethod
    public void getCacheSize(PluginCall call) {
        long size = dirSize(getContext().getCacheDir());
        JSObject ret = new JSObject();
        ret.put("bytes", size);
        call.resolve(ret);
    }

    @PluginMethod
    public void clearCache(PluginCall call) {
        deleteContents(getContext().getCacheDir());
        call.resolve(new JSObject());
    }

    private long dirSize(File dir) {
        if (dir == null || !dir.exists()) return 0;
        long total = 0;
        File[] files = dir.listFiles();
        if (files == null) return 0;
        for (File f : files) {
            total += f.isDirectory() ? dirSize(f) : f.length();
        }
        return total;
    }

    private void deleteContents(File dir) {
        if (dir == null || !dir.exists()) return;
        File[] files = dir.listFiles();
        if (files == null) return;
        for (File f : files) {
            if (f.isDirectory()) {
                deleteContents(f);
            }
            //noinspection ResultOfMethodCallIgnored
            f.delete();
        }
    }
}
