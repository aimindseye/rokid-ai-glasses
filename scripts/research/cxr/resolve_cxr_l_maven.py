#!/usr/bin/env python3
"""Resolve and attest the exact Rokid CXR-L client-l:1.0.1 artifact.

The published CXRLink class is a thin subclass. Its effective public connection
methods are inherited from ExternalAppClient, so the attestation walks the
class hierarchy and validates exact JVM descriptors rather than looking only at
methods declared directly on CXRLink.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
import urllib.request
import zipfile
from pathlib import Path

DEFAULT_REPOSITORY = "https://maven.rokid.com/repository/maven-public"
GROUP_PATH = "com/rokid/cxr/client-l"
EXPECTED_AAR_SHA256 = "c23d34b3adc60d3fa16001645ce6172eaf4554173e7ef9c078595e672d50824e"
EXPECTED_POM_SHA256 = "d29ddfe5d8daa7e36400efef9b0ed40bc19f1cf452908260d5551aafd62f9f2a"
CXR_LINK_CLASS = "com.rokid.cxr.link.CXRLink"
EXTERNAL_CLIENT_CLASS = "com.rokid.sprite.aiapp.externalapp.example.ExternalAppClient"
CALLBACK_CLASS = "com.rokid.cxr.link.callbacks.ICXRLinkCbk"
SESSION_CLASS = "com.rokid.cxr.link.utils.CxrDefs$CXRSession"
SESSION_TYPE_CLASS = "com.rokid.cxr.link.utils.CxrDefs$CXRSessionType"
REQUIRED_CLASSES = (
    "com/rokid/cxr/link/CXRLink.class",
    "com/rokid/cxr/link/callbacks/ICXRLinkCbk.class",
    "com/rokid/cxr/link/utils/CxrDefs.class",
    "com/rokid/cxr/link/utils/CxrDefs$CXRSession.class",
    "com/rokid/cxr/link/utils/CxrDefs$CXRSessionType.class",
    "com/rokid/sprite/aiapp/externalapp/example/ExternalAppClient.class",
)
JAVAP_CLASSES = (
    CXR_LINK_CLASS,
    EXTERNAL_CLIENT_CLASS,
    CALLBACK_CLASS,
    SESSION_CLASS,
    SESSION_TYPE_CLASS,
)
REQUIRED_EFFECTIVE_METHODS = {
    "setCXRLinkCbk": "(Lcom/rokid/cxr/link/callbacks/ICXRLinkCbk;)V",
    "configCXRSession": "(Lcom/rokid/cxr/link/utils/CxrDefs$CXRSession;)Z",
    "connect": "(Ljava/lang/String;)Z",
    "disconnect": "()V",
}
REQUIRED_CALLBACK_METHODS = {
    "onCXRLConnected": "(Z)V",
    "onGlassBtConnected": "(Z)V",
    "onGlassAiAssistStart": "()V",
    "onGlassAiAssistStop": "()V",
}
GLASS_INFO_CLASS = "com/rokid/cxr/link/utils/GlassInfo.class"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def fetch(url: str, destination: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "rokid-test19-r2.2/1"})
    with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310
        destination.write_bytes(response.read())


def parse_declared_methods(javap_text: str) -> dict[str, list[str]]:
    methods: dict[str, list[str]] = {}
    pending_name: str | None = None
    for line in javap_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("descriptor:") and pending_name:
            descriptor = stripped.split(":", 1)[1].strip()
            methods.setdefault(pending_name, []).append(descriptor)
            pending_name = None
            continue
        if not stripped.endswith(";") or "(" not in stripped:
            pending_name = None
            continue
        match = re.search(r"([A-Za-z_$][A-Za-z0-9_$]*)\s*\(", stripped)
        pending_name = match.group(1) if match else None
    return {name: sorted(set(values)) for name, values in methods.items()}


def parse_superclass(javap_text: str, class_name: str) -> str:
    pattern = re.compile(
        rf"\bclass\s+{re.escape(class_name)}\s+extends\s+([A-Za-z0-9_.$]+)"
    )
    match = pattern.search(javap_text)
    return match.group(1) if match else ""


def run_javap(javap: Path, jar_path: Path, class_name: str) -> str:
    completed = subprocess.run(
        [str(javap), "-classpath", str(jar_path), "-p", "-s", class_name],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if completed.returncode != 0:
        raise ValueError(f"javap failed for {class_name}: {completed.stdout.strip()}")
    return completed.stdout


def inspect_classes(
    aar: Path,
    diagnostic_dir: Path,
    javap: Path,
) -> tuple[list[str], dict[str, object]]:
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

        (diagnostic_dir / "cxr-l-class-inventory-private.txt").write_text(
            "\n".join(names) + "\n", encoding="utf-8"
        )

        missing = [name for name in REQUIRED_CLASSES if name not in names]
        if missing:
            raise ValueError("required CXR-L classes missing: " + ", ".join(missing))

        javap_output = {
            class_name: run_javap(javap, jar_path, class_name)
            for class_name in JAVAP_CLASSES
        }
        declared = {
            class_name: parse_declared_methods(text)
            for class_name, text in javap_output.items()
        }
        superclass = parse_superclass(javap_output[CXR_LINK_CLASS], CXR_LINK_CLASS)
        if superclass != EXTERNAL_CLIENT_CLASS:
            raise ValueError(
                "unexpected CXRLink superclass: "
                + (superclass or "UNRESOLVED")
            )

        declaring_classes: dict[str, str] = {}
        for method_name, descriptor in REQUIRED_EFFECTIVE_METHODS.items():
            owner = ""
            for class_name in (CXR_LINK_CLASS, EXTERNAL_CLIENT_CLASS):
                if descriptor in declared[class_name].get(method_name, []):
                    owner = class_name
                    break
            if not owner:
                raise ValueError(
                    f"required effective CXR-L method missing or wrong descriptor: "
                    f"{method_name}{descriptor}"
                )
            declaring_classes[method_name] = owner

        callback_declared = declared[CALLBACK_CLASS]
        callback_names = {
            name for name in callback_declared if name != "ICXRLinkCbk"
        }
        expected_callback_names = set(REQUIRED_CALLBACK_METHODS)
        if callback_names != expected_callback_names:
            raise ValueError(
                "unexpected ICXRLinkCbk method set: "
                + ",".join(sorted(callback_names))
            )
        for method_name, descriptor in REQUIRED_CALLBACK_METHODS.items():
            if descriptor not in callback_declared.get(method_name, []):
                raise ValueError(
                    f"required callback method missing or wrong descriptor: "
                    f"{method_name}{descriptor}"
                )

        required_session_constructor = (
            "(Lcom/rokid/cxr/link/utils/CxrDefs$CXRSessionType;"
            "Ljava/lang/String;)V"
        )
        if required_session_constructor not in javap_output[SESSION_CLASS]:
            raise ValueError("CUSTOMAPP CXRSession constructor is missing")

        cxr_link_constructor = "(Landroid/content/Context;)V"
        if cxr_link_constructor not in javap_output[CXR_LINK_CLASS]:
            raise ValueError("CXRLink(Context) constructor is missing")

        (diagnostic_dir / "cxr-l-javap-private.txt").write_text(
            "\n\n".join(
                f"## {name}\n{text}" for name, text in javap_output.items()
            ),
            encoding="utf-8",
        )

        direct_count = sum(
            1
            for method_name, descriptor in REQUIRED_EFFECTIVE_METHODS.items()
            if descriptor in declared[CXR_LINK_CLASS].get(method_name, [])
        )
        return names, {
            "cxr_link_superclass": superclass,
            "method_declaring_classes": declaring_classes,
            "direct_cxr_link_required_method_count": direct_count,
            "required_effective_method_count": len(declaring_classes),
            "callback_methods": sorted(callback_names),
            "required_callback_method_count": len(REQUIRED_CALLBACK_METHODS),
            "customapp_session_constructor_present": True,
            "cxr_link_context_constructor_present": True,
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default="1.0.1")
    parser.add_argument("--output", required=True)
    parser.add_argument("--repository", default=DEFAULT_REPOSITORY)
    parser.add_argument("--javap", default="")
    parser.add_argument("--expected-aar-sha256", default=EXPECTED_AAR_SHA256)
    parser.add_argument("--expected-pom-sha256", default=EXPECTED_POM_SHA256)
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
    javap = Path(args.javap).expanduser().resolve() if args.javap else None

    try:
        if javap is None or not javap.is_file():
            raise ValueError("an explicit working --javap path is required")
        fetch(f"{base}/client-l-{version}.aar", artifact)
        fetch(f"{base}/client-l-{version}.pom", pom)
        artifact_hash = sha256(artifact)
        pom_hash = sha256(pom)
        if artifact_hash != args.expected_aar_sha256:
            raise ValueError(
                f"AAR SHA-256 mismatch: expected {args.expected_aar_sha256}, got {artifact_hash}"
            )
        if pom_hash != args.expected_pom_sha256:
            raise ValueError(
                f"POM SHA-256 mismatch: expected {args.expected_pom_sha256}, got {pom_hash}"
            )
        class_names, surface = inspect_classes(artifact, output, javap)
    except Exception as error:  # noqa: BLE001
        print("TEST19_R2_CXR_L_MAVEN_RESOLUTION=FAIL")
        print(f"ERROR_CLASS={error.__class__.__name__}")
        print(f"ERROR={error}")
        print(f"CXR_L_PRIVATE_ARTIFACT_DIRECTORY={output}")
        return 3

    result = {
        "schema": "rokid.test19-r2.cxr-l-artifact-attestation.v3",
        "coordinate": f"com.rokid.cxr:client-l:{version}",
        "repository": repository,
        "aar_file": str(artifact),
        "aar_sha256": artifact_hash,
        "aar_size": artifact.stat().st_size,
        "pom_file": str(pom),
        "pom_sha256": pom_hash,
        "pom_size": pom.stat().st_size,
        "exact_artifact_hashes_complete": True,
        "required_classes_complete": True,
        "class_count": len(class_names),
        "glass_info_class_present": GLASS_INFO_CLASS in class_names,
        "javap_path": str(javap),
        "required_methods_complete": True,
        "required_callback_methods": REQUIRED_CALLBACK_METHODS,
        "artifact_publication_allowed": False,
        **surface,
    }
    (output / "cxr-l-artifact-attestation.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    print("TEST19_R2_CXR_L_MAVEN_RESOLUTION=PASS")
    print("TEST19_R2_CXR_L_EXACT_ARTIFACT_HASHES=PASS")
    print("TEST19_R2_CXR_L_API_SURFACE=PASS")
    print(f"CXR_L_COORDINATE={result['coordinate']}")
    print(f"CXR_L_AAR_SHA256={result['aar_sha256']}")
    print(f"CXR_L_POM_SHA256={result['pom_sha256']}")
    print(f"CXR_L_CXR_LINK_SUPERCLASS={result['cxr_link_superclass']}")
    print(
        "CXR_L_DIRECT_CXR_LINK_REQUIRED_METHOD_COUNT="
        f"{result['direct_cxr_link_required_method_count']}"
    )
    print(
        "CXR_L_REQUIRED_EFFECTIVE_METHOD_COUNT="
        f"{result['required_effective_method_count']}"
    )
    for method_name in REQUIRED_EFFECTIVE_METHODS:
        print(
            f"CXR_L_METHOD_{method_name}_DECLARED_BY="
            f"{result['method_declaring_classes'][method_name]}"
        )
    print(
        "CXR_L_GLASS_INFO_CLASS_PRESENT="
        f"{str(result['glass_info_class_present']).upper()}"
    )
    print("CXR_L_CALLBACK_METHODS=" + ",".join(result["callback_methods"]))
    print(f"CXR_L_PRIVATE_ARTIFACT_DIRECTORY={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
