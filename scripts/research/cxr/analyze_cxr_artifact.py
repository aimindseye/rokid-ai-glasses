#!/usr/bin/env python3
"""Inspect a locally supplied CXR-M AAR/JAR without publishing its contents."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

API_SUFFIXES = (
    "com/rokid/cxr/client/extend/CxrApi.class",
    "com/rokid/cxr/api/CxrApi.class",
    "com/rokid/cxr/m/CxrApi.class",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def class_names_from_jar(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as archive:
        return sorted(
            name[:-6].replace("/", ".")
            for name in archive.namelist()
            if name.endswith(".class") and not name.startswith("META-INF/versions/")
        )


def extract_classes_jar(artifact: Path, directory: Path) -> tuple[Path, str]:
    with zipfile.ZipFile(artifact) as archive:
        names = set(archive.namelist())
        if "classes.jar" in names:
            output = directory / "classes.jar"
            output.write_bytes(archive.read("classes.jar"))
            return output, "aar"
    return artifact, "jar"


def javap_public(jar: Path, class_name: str) -> list[str]:
    javap = shutil.which("javap")
    if not javap:
        return []
    result = subprocess.run(
        [javap, "-classpath", str(jar), "-public", class_name],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        return []
    return [line.rstrip() for line in result.stdout.splitlines() if line.strip()]


def analyze(artifact: Path) -> dict[str, object]:
    artifact = artifact.resolve()
    if not artifact.is_file():
        raise FileNotFoundError(artifact)
    if not zipfile.is_zipfile(artifact):
        raise ValueError("artifact is not a valid AAR/JAR ZIP container")

    with zipfile.ZipFile(artifact) as outer:
        outer_names = sorted(outer.namelist())
        native_libraries = [name for name in outer_names if name.startswith("jni/") and name.endswith(".so")]
        has_manifest = "AndroidManifest.xml" in outer_names

    with tempfile.TemporaryDirectory() as temporary:
        classes_jar, kind = extract_classes_jar(artifact, Path(temporary))
        classes = class_names_from_jar(classes_jar)
        api_candidates = [
            suffix[:-6].replace("/", ".")
            for suffix in API_SUFFIXES
            if suffix[:-6].replace("/", ".") in classes
        ]
        callback_candidates = sorted(
            item
            for item in classes
            if item.endswith("BluetoothStatusCallback")
            or item.endswith("WifiP2PStatusCallback")
        )
        public_api = {
            class_name: javap_public(classes_jar, class_name)
            for class_name in api_candidates + callback_candidates
        }
        api_text = "\n".join(line for lines in public_api.values() for line in lines)
        required_surface = {
            "getInstance": "getInstance(" in api_text,
            "initBluetooth": "initBluetooth(" in api_text,
            "isBluetoothConnected": "isBluetoothConnected(" in api_text,
            "deinitBluetooth": "deinitBluetooth(" in api_text,
        }

    return {
        "schema": "rokid.test19.cxr-artifact-inventory.v1",
        "artifact_name": artifact.name,
        "artifact_size": artifact.stat().st_size,
        "artifact_sha256": sha256(artifact),
        "container_kind": kind,
        "class_count": len(classes),
        "cxr_api_candidates": api_candidates,
        "callback_candidates": callback_candidates,
        "recognized_api_class": len(api_candidates) == 1,
        "public_api": public_api,
        "required_surface": required_surface,
        "required_surface_complete": all(required_surface.values()) if public_api else False,
        "native_libraries": native_libraries,
        "has_android_manifest": has_manifest,
        "artifact_bytes_embedded": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()

    report = analyze(Path(args.artifact))
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0 if report["recognized_api_class"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
