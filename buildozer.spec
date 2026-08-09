[app]

title = Subscription Tracker
package.name = subscriptiontracker
package.domain = org.example
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 0.2

# Kivy + pyjnius (pyjnius is bundled automatically on android)
requirements = python3,kivy

orientation = portrait
fullscreen = 0

# ---------- Icons ----------
# Legacy launcher icon (pre-Android 8) and a fallback
icon.filename = %(source.dir)s/data/icon.png
# Adaptive icon layers (Android 8 / API 26+)
icon.adaptive_foreground.filename = %(source.dir)s/data/icon_foreground.png
icon.adaptive_background.filename = %(source.dir)s/data/icon_background.png
# Themed (monochrome) icon for Android 13+ — remove if your buildozer
# version does not recognise this key.
icon.adaptive_monochrome.filename = %(source.dir)s/data/icon_monochrome.png

# Loading screen shown while the app starts (replaces buildozer's default)
presplash.filename = %(source.dir)s/data/presplash.jpg
android.presplash_color = #000000

# ---------- Android-specific ----------

# Background notification service (foreground so Android doesn't kill it)
services = Notify:servicenotify.py:foreground

# Permissions
android.permissions = POST_NOTIFICATIONS, FOREGROUND_SERVICE, RECEIVE_BOOT_COMPLETED, WAKE_LOCK

android.api = 36
android.minapi = 29
android.archs = arm64-v8a
android.allow_backup = True
android.accept_sdk_license = True
android.skip_update = False


[buildozer]
log_level = 2
warn_on_root = 0
