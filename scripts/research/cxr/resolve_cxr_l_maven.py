#!/usr/bin/env python3
"""Resolve and attest a bounded Rokid CXR-L Maven artifact without publishing it."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
import urllib.request
import zipfile
from pathlib import Path

DEFAULT_REPOSITORY = "https://maven.rokid.com/repository/maven-public"
GROUP_PATH = "com/rokid/cxr/client-l"
REQUIRED_CLASSES = (
    "com/rokid/cxr/link/CXRLink.class",
    "com/rokid/cxr/link/callbacks/ICXRLinkCbk.class",
    "com/rokid/cxr/link/utils/CxrDefs.class",
    "com/rokid/cxr/link/utils/CxrDefs$CXRSession.class",
    "com/rokid/cxr/link/utils/CxrDefs$CXRSessionType.class",
    "com/rokid/cxr/link/utils/GlassInfo.class",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def fetch(url: str, destination: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "rokid-test19-r2/1"})
    with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310
        destination.write_bytes(response.read())


def inspect_classes(aar: Path) -> tuple[list[str], dict[str, str]]:
    with zipfile.ZipFile(aar) as archive:
        if "classes.jar" not in archive.namelist():
            raise ValueError("AAR does not contain classes.jar")
        classes_jar = archive.read("classes.jar")
    with tempfile.TemporaryDirectory(prefix="test19-r2-cxrl-") as temp_value:
        temp = Path(temp_value)
        jar_path = temp / "classes.jar"
        jar_path.write_bytes(classes_jar)
        with zipfile.ZipFile(jar_path) as jar:
            names = sorted(name for name in jar.namelist() if name.endswith(".class"))
        missing = [name for name in REQUIRED_CLASSES if name not in names]
        if missing:
            raise ValueError("required CXR-L classes missing: " + ", ".join(missing))

        javap_output: dict[str, str] = {}
        javap = shutil.which("javap")
        if javap:
            for class_name in (
                "com.rokid.cxr.link.CXRLink",
                "com.rokid.cxr.link.callbacks.ICXRLinkCbk",
                "com.rokid.cxr.link.utils.CxrDefs$CXRSession",
            ):
                completed = subprocess.run(
                    [javap, "-classpath", str(jar_path), "-public", class_name],
                    check=False,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                )
                javap_output[class_name] = completed.stdout
                if completed.returncode != 0:
                    raise ValueError(f"javap failed for {class_name}")

            combined = "\n".join(javap_output.values())
            required_tokens = (
                "setCXRLinkCbk",
                "configCXRSession",
                "disconnect",
                "onCXRLConnected",
                "onGlassBtConnected",
            )
            absent = [token for token in required_tokens if token not in combined]
            if absent:
                raise ValueError("required CXR-L methods missing: " + ", ".join(absent))
        return names, javap_output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default="1.0.1")
    parser.add_argument("--output", required=True)
    parser.add_argument("--repository", default=DEFAULT_REPOSITORY)
    args = parser.parse_args()

    version = args.version.strip()
    if version != "1.0.1":
        print("TEST19_R2_CXR_L_VERSION_ATTESTATION=FAIL")
        print("REASON=ONLY_1.0.1_IS_APPROVED_FOR_THIS_DELIVERABLE")
        return 2

    output = Path(args.output).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    repository = args.repository.rstrip("/")
    base = f"{repository}/{GROUP_PATH}/{version}"
    artifact = output / f"client-l-{version}.aar"
    pom = output / f"client-l-{version}.pom"

    try:
        fetch(f"{base}/client-l-{version}.aar", artifact)
        fetch(f"{base}/client-l-{version}.pom", pom)
        class_names, javap_output = inspect_classes(artifact)
    except Exception as error:  # noqa: BLE001
        print("TEST19_R2_CXR_L_MAVEN_RESOLUTION=FAIL")
        print(f"ERROR_CLASS={error.__class__.__name__}")
        print(f"ERROR={error}")
        return 3

    result = {
        "schema": "rokid.test19-r2.cxr-l-artifact-attestation.v1",
        "coordinate": f"com.rokid.cxr:client-l:{version}",
        "repository": repository,
        "aar_file": str(artifact),
        "aar_sha256": sha256(artifact),
        "aar_size": artifact.stat().st_size,
        "pom_file": str(pom),
        "pom_sha256": sha256(pom),
        "pom_size": pom.stat().st_size,
        "required_classes_complete": True,
        "class_count": len(class_names),
        "javap_available": bool(javap_output),
        "required_methods_complete": True,
        "artifact_publication_allowed": False,
    }
    (output / "cxr-l-artifact-attestation.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if javap_output:
        (output / "cxr-l-javap-private.txt").write_text(
            "\n\n".join(
                f"## {name}\n{text}" for name, text in sorted(javap_output.items())
            ),
            encoding="utf-8",
        )

    print("TEST19_R2_CXR_L_MAVEN_RESOLUTION=PASS")
    print("TEST19_R2_CXR_L_API_SURFACE=PASS")
    print(f"CXR_L_COORDINATE={result['coordinate']}")
    print(f"CXR_L_AAR_SHA256={result['aar_sha256']}")
    print(f"CXR_L_POM_SHA256={result['pom_sha256']}")
    print(f"CXR_L_PRIVATE_ARTIFACT_DIRECTORY={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
