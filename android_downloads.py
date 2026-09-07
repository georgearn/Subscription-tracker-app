"""
Save exported files to the public Downloads folder via MediaStore
(Android 10+ scoped storage, no permission needed for files the app wrote
itself), and pick any file to import via the system file picker (Storage
Access Framework) — works for any file the user has access to, not just
this app's own exports, and needs no storage permission either.
"""


def is_supported():
    try:
        import android  # noqa: F401
        from jnius import autoclass  # noqa: F401
        return True
    except ImportError:
        return False


def _resolver():
    from jnius import autoclass
    activity = autoclass("org.kivy.android.PythonActivity").mActivity
    return activity.getContentResolver()


def save_text(filename, content, mime_type="application/json"):
    """Write content (str) as a new file in Downloads/. Returns the
    filename actually used (MediaStore may adjust it on a name clash)."""
    from jnius import autoclass
    MediaStore = autoclass("android.provider.MediaStore$Downloads")
    ContentValues = autoclass("android.content.ContentValues")

    resolver = _resolver()
    values = ContentValues()
    values.put("_display_name", filename)
    values.put("mime_type", mime_type)
    uri = resolver.insert(MediaStore.EXTERNAL_CONTENT_URI, values)
    if uri is None:
        raise RuntimeError("Could not create file in Downloads.")
    stream = resolver.openOutputStream(uri)
    try:
        stream.write(content.encode("utf-8"))
        stream.flush()
    finally:
        stream.close()
    return filename


_PICK_REQUEST_CODE = 0x4201


def pick_file(callback, mime_type="*/*"):
    from kivy.clock import Clock
    """Launch the system file picker (Storage Access Framework) so the
    user can pick any file from anywhere they have access to — not just
    files this app wrote — with no storage permission needed. Calls
    callback(text, display_name) once a file is chosen and read, or
    callback(None, None) if the user cancels or the read fails."""
    from jnius import autoclass
    from android import activity, mActivity

    Intent = autoclass("android.content.Intent")
    intent = Intent(Intent.ACTION_OPEN_DOCUMENT)
    intent.addCategory(Intent.CATEGORY_OPENABLE)
    intent.setType(mime_type)

    def on_result(request_code, result_code, data):
        # Runs on Android's activity-result thread, NOT the Kivy/GL
        # thread. callback() eventually builds Kivy widgets (Popup etc),
        # which must happen on the main thread -- so do the URI reading
        # here (that part is fine off-thread) but hop back via
        # Clock.schedule_once before calling callback().
        if request_code != _PICK_REQUEST_CODE:
            return
        try:
            activity.unbind(on_activity_result=on_result)
            Activity = autoclass("android.app.Activity")
            if result_code != Activity.RESULT_OK or data is None:
                Clock.schedule_once(lambda dt: callback(None, None))
                return
            uri = data.getData()
            text = _read_uri(uri)
            name = _query_display_name(uri)
            Clock.schedule_once(lambda dt: callback(text, name))
        except Exception as e:
            print(f"[SubTracker] Could not read picked file: {e}")
            Clock.schedule_once(
                lambda dt, err=str(e): callback(None, None, error=err))

    activity.bind(on_activity_result=on_result)
    mActivity.startActivityForResult(intent, _PICK_REQUEST_CODE)


def _read_uri(uri):
    from jnius import autoclass
    InputStreamReader = autoclass("java.io.InputStreamReader")
    BufferedReader = autoclass("java.io.BufferedReader")

    stream = _resolver().openInputStream(uri)
    reader = BufferedReader(InputStreamReader(stream, "UTF-8"))
    lines = []
    try:
        while True:
            line = reader.readLine()
            if line is None:
                break
            lines.append(line)
    finally:
        reader.close()
    return "\n".join(lines)


def _query_display_name(uri):
    from jnius import autoclass
    OpenableColumns = autoclass("android.provider.OpenableColumns")

    cursor = _resolver().query(uri, None, None, None, None)
    if cursor is None:
        return None
    try:
        idx = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
        if idx >= 0 and cursor.moveToFirst():
            return cursor.getString(idx)
    finally:
        cursor.close()
    return None
