# Android MediaStore Export

PCAPdroid exports may be visible through Android MediaStore even when direct `adb pull` from `/sdcard/Download` fails.

## Query

```bash
adb shell content query \
  --user "$ANDROID_USER" \
  --uri content://media/external/file \
  --projection '_id:_display_name:relative_path:mime_type:_size:date_modified'
```

Use `scripts/capture/query_mediastore.sh` to save the inventory privately.

## Read a row

```bash
adb exec-out content read \
  --user "$ANDROID_USER" \
  --uri "content://media/external/file/$MEDIA_ID" \
  > private-output.part
```

Verify the resulting file is non-empty and, when available, that its local byte count matches the MediaStore `_size` value before renaming the temporary file.

Use `scripts/capture/pull_mediastore_exports.sh` for a guarded three-artifact pull.

MediaStore IDs, original export names, and private paths are evidence metadata and should not be published unless sanitized.
