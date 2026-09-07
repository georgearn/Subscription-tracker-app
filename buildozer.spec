[app]

title = Subscription Tracker
package.name = subscriptiontracker
package.domain = com.georgearn
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 1.8

# Kivy + pyjnius (pyjnius is bundled automatically on android)
requirements = python3,kivy

orientation = portrait
fullscreen = 0

# ---------- Icons ----------
# Adaptive icon layers (Android 8 / API 26+; minapi is 29, so legacy
# icon.filename and the API 33+ monochrome layer are not needed)
icon.adaptive_foreground.filename = %(source.dir)s/data/icon_foreground.png
icon.adaptive_background.filename = %(source.dir)s/data/icon_background.png

# Loading screen shown while the app starts (replaces buildozer's default)
presplash.filename = %(source.dir)s/data/presplash.jpg
android.presplash_color = #000000

# ---------- Android-specific ----------

# Background notification service (foreground so Android doesn't kill it)
services = Notify:servicenotify.py:foreground:foregroundServiceType=dataSync

# Permissions
android.permissions = POST_NOTIFICATIONS, FOREGROUND_SERVICE, FOREGROUND_SERVICE_DATA_SYNC, RECEIVE_BOOT_COMPLETED, WAKE_LOCK

android.api = 37
android.minapi = 29
android.archs = arm64-v8a
android.release_artifact = apk
android.allow_backup = True
android.accept_sdk_license = True

# FileProvider, so the app can share the generated .ics file with the
# calendar app via a content:// URI (needed for android_calendar.py).
android.res_xml = res/file_paths.xml
android.gradle_dependencies = androidx.core:core:1.13.1


[buildozer]
log_level = 2
warn_on_root = 0
