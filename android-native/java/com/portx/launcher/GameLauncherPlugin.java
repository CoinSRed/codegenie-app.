package com.portx.launcher;

import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.util.Base64;

import androidx.activity.result.ActivityResult;
import androidx.documentfile.provider.DocumentFile;

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

/**
 * GameLauncherPlugin
 *
 * Native half of PORTX Game Launcher. Registered under the bridge name
 * "GameLauncher" and called from www/js/native.js.
 *
 * Folder-import convention
 * -------------------------------------------------------------------------
 * An extracted game folder picked through this plugin is classified as:
 *
 *   "apk"            - the folder contains a .apk file. The game isn't
 *                       installed yet; installApk() starts the system
 *                       installer for it.
 *   "package-ref"     - the folder contains a small text file named
 *                       "package.txt" whose contents are the package name
 *                       of an app that is (or will be) installed on the
 *                       device, e.g. "com.studio.mygame". This lets a
 *                       folder of game assets point at the real
 *                       installed app so this launcher can start it.
 *   "native-binary"   - the folder contains an executable (ELF/PE) with no
 *                       Android package at all - a raw PC/console binary.
 *                       Android cannot run this without a compatible
 *                       runtime or engine, so this is reported, never
 *                       launched.
 *   "unknown"         - nothing recognizable was found.
 */
@CapacitorPlugin(name = "GameLauncher")
public class GameLauncherPlugin extends Plugin {

    private static final int MAX_SCAN_DEPTH = 6;
    private static final int MAX_SCAN_ENTRIES = 5000;

    // ---------------------------------------------------------------
    // Folder picking (Storage Access Framework)
    // ---------------------------------------------------------------

    @PluginMethod
    public void pickFolder(PluginCall call) {
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT_TREE);
        intent.addFlags(
            Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION
        );
        startActivityForResult(call, intent, "pickFolderResult");
    }

    @ActivityCallback
    private void pickFolderResult(PluginCall call, ActivityResult result) {
        if (call == null) return;

        if (result.getResultCode() != Activity.RESULT_OK || result.getData() == null) {
            call.reject("Folder selection was cancelled.");
            return;
        }

        Uri treeUri = result.getData().getData();
        if (treeUri == null) {
            call.reject("No folder was returned by the picker.");
            return;
        }

        // Persist access so we can still read this folder after the app restarts.
        try {
            getContext()
                .getContentResolver()
                .takePersistableUriPermission(
                    treeUri,
                    Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION
                );
        } catch (SecurityException e) {
            // Some providers don't support persistable permissions; the folder
            // still works for this session, so we don't fail the call for this.
        }

        DocumentFile dir = DocumentFile.fromTreeUri(getContext(), treeUri);
        String name = (dir != null && dir.getName() != null) ? dir.getName() : "Imported game";

        JSObject ret = new JSObject();
        ret.put("uri", treeUri.toString());
        ret.put("displayName", name);
        call.resolve(ret);
    }

    // ---------------------------------------------------------------
    // Folder inspection
    // ---------------------------------------------------------------

    @PluginMethod
    public void inspectFolder(PluginCall call) {
        String uriStr = call.getString("uri");
        if (uriStr == null) {
            call.reject("Missing 'uri'.");
            return;
        }

        DocumentFile dir = DocumentFile.fromTreeUri(getContext(), Uri.parse(uriStr));
        if (dir == null || !dir.exists() || !dir.isDirectory()) {
            call.reject("This folder is no longer accessible. Permission may have been revoked.");
            return;
        }

        ScanResult scan = new ScanResult();
        scanFolder(dir, scan, 0);

        JSObject ret = new JSObject();
        ret.put("sizeBytes", scan.totalSize);
        ret.put("fileCount", scan.fileCount);

        if (scan.apkFile != null) {
            ret.put("kind", "apk");
            ret.put("payload", scan.apkFile.getUri().toString());
        } else if (scan.packageRefFile != null) {
            String pkg = readSmallTextFile(scan.packageRefFile);
            ret.put("kind", "package-ref");
            ret.put("payload", pkg != null ? pkg.trim() : "");
        } else if (scan.nativeBinary != null) {
            ret.put("kind", "native-binary");
            ret.put("payload", scan.nativeBinary.getName());
        } else {
            ret.put("kind", "unknown");
        }

        call.resolve(ret);
    }

    private static class ScanResult {
        long totalSize = 0;
        int fileCount = 0;
        DocumentFile apkFile = null;
        DocumentFile packageRefFile = null;
        DocumentFile nativeBinary = null;
    }

    /** Bounded breadth/depth walk so a huge or deeply-nested folder can't hang the app. */
    private void scanFolder(DocumentFile dir, ScanResult scan, int depth) {
        if (depth > MAX_SCAN_DEPTH || scan.fileCount > MAX_SCAN_ENTRIES) return;

        for (DocumentFile child : dir.listFiles()) {
            if (scan.fileCount > MAX_SCAN_ENTRIES) return;

            if (child.isDirectory()) {
                scanFolder(child, scan, depth + 1);
                continue;
            }

            scan.fileCount++;
            scan.totalSize += Math.max(0, child.length());

            String name = child.getName();
            if (name == null) continue;
            String lower = name.toLowerCase();

            if (scan.apkFile == null && lower.endsWith(".apk")) {
                scan.apkFile = child;
            } else if (scan.packageRefFile == null && lower.equals("package.txt")) {
                scan.packageRefFile = child;
            } else if (scan.nativeBinary == null && looksLikeNativeExecutable(lower)) {
                scan.nativeBinary = child;
            }
        }
    }

    private boolean looksLikeNativeExecutable(String lowerName) {
        return lowerName.endsWith(".exe")
            || lowerName.endsWith(".dll")
            || lowerName.endsWith(".so")
            || lowerName.endsWith(".x86_64")
            || lowerName.endsWith(".bin")
            || (!lowerName.contains(".") && lowerName.length() > 0);
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
        boolean installed;
        try {
            getContext().getPackageManager().getPackageInfo(packageName, 0);
            installed = true;
        } catch (PackageManager.NameNotFoundException e) {
            installed = false;
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

        Uri apkUri = Uri.parse(uriStr);
        Intent intent = new Intent(Intent.ACTION_VIEW);
        intent.setDataAndType(apkUri, "application/vnd.android.package-archive");
        intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_ACTIVITY_NEW_TASK);

        if (intent.resolveActivity(getContext().getPackageManager()) == null) {
            call.reject("No package installer is available on this device.");
            return;
        }

        getContext().startActivity(intent);
        call.resolve(new JSObject());
    }

    // ---------------------------------------------------------------
    // Cover image picking
    // ---------------------------------------------------------------

    @PluginMethod
    public void pickImage(PluginCall call) {
        Intent intent = new Intent(Intent.ACTION_GET_CONTENT);
        intent.setType("image/*");
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        startActivityForResult(call, intent, "pickImageResult");
    }

    @ActivityCallback
    private void pickImageResult(PluginCall call, ActivityResult result) {
        if (call == null) return;

        if (result.getResultCode() != Activity.RESULT_OK || result.getData() == null) {
            call.reject("Image selection was cancelled.");
            return;
        }

        Uri imageUri = result.getData().getData();
        if (imageUri == null) {
            call.reject("No image was returned.");
            return;
        }

        try (InputStream in = getContext().getContentResolver().openInputStream(imageUri)) {
            if (in == null) {
                call.reject("Couldn't open the selected image.");
                return;
            }
            ByteArrayOutputStream buffer = new ByteArrayOutputStream();
            byte[] chunk = new byte[8192];
            int read;
            // Guard against picking an unexpectedly huge file (cap ~8MB source).
            int total = 0;
            while ((read = in.read(chunk)) != -1) {
                buffer.write(chunk, 0, read);
                total += read;
                if (total > 8 * 1024 * 1024) {
                    call.reject("That image is too large to use as a cover.");
                    return;
                }
            }

            String mime = getContext().getContentResolver().getType(imageUri);
            if (mime == null) mime = "image/jpeg";
            String b64 = Base64.encodeToString(buffer.toByteArray(), Base64.NO_WRAP);

            JSObject ret = new JSObject();
            ret.put("dataUrl", "data:" + mime + ";base64," + b64);
            call.resolve(ret);
        } catch (IOException e) {
            call.reject("Failed to read the selected image: " + e.getMessage());
        }
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
