#!/usr/bin/env python3
"""Produce an exact, read-only CXR-L SDK surface and native/JNI census.

The input AAR/POM remain private. The script emits a private machine-readable
census that a separate classifier sanitizes for publication.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Any

EXPECTED_VERSION = "1.0.1"
EXPECTED_AAR_SHA256 = "c23d34b3adc60d3fa16001645ce6172eaf4554173e7ef9c078595e672d50824e"
EXPECTED_POM_SHA256 = "d29ddfe5d8daa7e36400efef9b0ed40bc19f1cf452908260d5551aafd62f9f2a"


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def class_name_from_entry(entry: str) -> str:
    return entry[:-6].replace("/", ".")


def run_javap(javap: Path, jar: Path, class_name: str) -> str:
    completed = subprocess.run(
        [str(javap), "-classpath", str(jar), "-public", "-s", "-constants", class_name],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if completed.returncode != 0:
        raise ValueError(f"javap failed for {class_name}: {completed.stdout.strip()}")
    return completed.stdout


def parse_class_header(text: str, class_name: str) -> dict[str, Any]:
    header = ""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("public ") and (" class " in stripped or " interface " in stripped or " enum " in stripped):
            header = stripped.rstrip("{").strip()
            break
    if not header:
        return {
            "name": class_name,
            "public": False,
            "kind": "unknown",
            "superclass": "",
            "interfaces": [],
            "header": "",
        }
    kind = "interface" if " interface " in f" {header} " else "enum" if " enum " in f" {header} " else "class"
    superclass = ""
    interfaces: list[str] = []
    extends = re.search(r"\bextends\s+([^\s,{]+)", header)
    if extends and kind != "interface":
        superclass = extends.group(1)
    implements = re.search(r"\bimplements\s+(.+)$", header)
    if implements:
        interfaces = [item.strip() for item in implements.group(1).split(",") if item.strip()]
    elif kind == "interface" and extends:
        interfaces = [item.strip() for item in header.split(" extends ", 1)[1].split(",") if item.strip()]
    return {
        "name": class_name,
        "public": True,
        "kind": kind,
        "superclass": superclass,
        "interfaces": interfaces,
        "header": header,
    }


def parse_members(text: str, class_name: str, header: dict[str, Any]) -> list[dict[str, Any]]:
    members: list[dict[str, Any]] = []
    pending: dict[str, Any] | None = None
    simple_name = class_name.rsplit(".", 1)[-1]
    enum_class = header.get("superclass", "").startswith("java.lang.Enum") or header.get("kind") == "enum"

    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("descriptor:") and pending is not None:
            pending["descriptor"] = stripped.split(":", 1)[1].strip()
            expected_enum_descriptor = pending.pop("enum_descriptor_expected", "")
            if (
                pending.get("kind") == "enum_constant"
                and expected_enum_descriptor
                and pending["descriptor"] != expected_enum_descriptor
            ):
                pending["kind"] = "field"
                pending["normalization"] = "enum-backing-storage-reclassified-as-field"
            members.append(pending)
            pending = None
            continue
        if not stripped.startswith("public ") or not stripped.endswith(";"):
            continue
        if stripped.startswith("public static {}"):
            continue

        signature = stripped[:-1]
        if "(" in signature:
            match = re.search(r"([A-Za-z_$][A-Za-z0-9_$]*)\s*\(", signature)
            if not match:
                continue
            name = match.group(1)
            kind = "constructor" if name in {simple_name, class_name} else "method"
            pending = {
                "kind": kind,
                "name": name,
                "signature": signature,
                "descriptor": "",
                "static": " static " in f" {signature} ",
                "abstract": " abstract " in f" {signature} ",
                "final": " final " in f" {signature} ",
                "native": " native " in f" {signature} ",
                "synthetic_bridge": " bridge " in f" {signature} " or " synthetic " in f" {signature} ",
            }
        else:
            raw = signature
            before_value = raw.split(" = ", 1)[0]
            name = before_value.rsplit(" ", 1)[-1]
            value = raw.split(" = ", 1)[1] if " = " in raw else None
            type_part = before_value[: -len(name)].strip()
            # A real enum constant has the enum instance descriptor. Kotlin/Java
            # compiler backing arrays (for example an obfuscated `a` field with
            # descriptor `[L...;`) are ordinary fields, not supported values.
            expected_enum_descriptor = f"L{class_name.replace('.', '/')};"
            candidate_enum_constant = bool(
                enum_class
                and " static " in f" {raw} "
                and " final " in f" {raw} "
                and class_name in raw
            )
            pending = {
                "kind": "enum_constant" if candidate_enum_constant else "field",
                "enum_descriptor_expected": expected_enum_descriptor if candidate_enum_constant else "",
                "name": name,
                "signature": raw,
                "descriptor": "",
                "static": " static " in f" {raw} ",
                "final": " final " in f" {raw} ",
                "type_text": type_part,
                "constant_value": value,
            }
    return members


def parse_pom(path: Path) -> dict[str, Any]:
    root = ET.fromstring(path.read_text(encoding="utf-8"))
    namespace = ""
    if root.tag.startswith("{"):
        namespace = root.tag.split("}", 1)[0] + "}"
    def text(element: ET.Element, name: str) -> str:
        child = element.find(namespace + name)
        return (child.text or "").strip() if child is not None else ""
    dependencies: list[dict[str, str]] = []
    deps = root.find(namespace + "dependencies")
    if deps is not None:
        for dep in deps.findall(namespace + "dependency"):
            dependencies.append({
                "group_id": text(dep, "groupId"),
                "artifact_id": text(dep, "artifactId"),
                "version": text(dep, "version"),
                "scope": text(dep, "scope"),
                "type": text(dep, "type"),
                "optional": text(dep, "optional"),
            })
    return {
        "group_id": text(root, "groupId"),
        "artifact_id": text(root, "artifactId"),
        "version": text(root, "version"),
        "packaging": text(root, "packaging"),
        "dependencies": dependencies,
    }


def c_string(data: bytes, offset: int) -> str:
    if offset < 0 or offset >= len(data):
        return ""
    end = data.find(b"\x00", offset)
    if end < 0:
        end = len(data)
    return data[offset:end].decode("utf-8", errors="replace")


def elf_dynamic_symbols(data: bytes) -> dict[str, Any]:
    if len(data) < 64 or data[:4] != b"\x7fELF":
        raise ValueError("not an ELF file")
    elf_class = data[4]
    endian_id = data[5]
    endian = "<" if endian_id == 1 else ">" if endian_id == 2 else ""
    if not endian or elf_class not in {1, 2}:
        raise ValueError("unsupported ELF encoding")

    if elf_class == 1:
        header_fmt = endian + "HHIIIIIHHHHHH"
        values = struct.unpack_from(header_fmt, data, 16)
        e_shoff, e_shentsize, e_shnum, e_shstrndx = values[5], values[10], values[11], values[12]
        section_fmt = endian + "IIIIIIIIII"
        sym_fmt = endian + "IIIBBH"
        default_sym_size = 16
    else:
        header_fmt = endian + "HHIQQQIHHHHHH"
        values = struct.unpack_from(header_fmt, data, 16)
        e_shoff, e_shentsize, e_shnum, e_shstrndx = values[5], values[10], values[11], values[12]
        section_fmt = endian + "IIQQQQIIQQ"
        sym_fmt = endian + "IBBHQQ"
        default_sym_size = 24

    sections: list[dict[str, int | str]] = []
    for index in range(e_shnum):
        offset = e_shoff + index * e_shentsize
        values_s = struct.unpack_from(section_fmt, data, offset)
        if elf_class == 1:
            name, stype, flags, addr, soff, ssize, link, info, align, entsize = values_s
        else:
            name, stype, flags, addr, soff, ssize, link, info, align, entsize = values_s
        sections.append({
            "name_offset": name,
            "type": stype,
            "offset": soff,
            "size": ssize,
            "link": link,
            "entry_size": entsize,
        })
    if not (0 <= e_shstrndx < len(sections)):
        raise ValueError("invalid ELF section string index")
    shstr = sections[e_shstrndx]
    shstr_data = data[int(shstr["offset"]): int(shstr["offset"]) + int(shstr["size"])]
    for section in sections:
        section["name"] = c_string(shstr_data, int(section["name_offset"]))

    dynsym = next((section for section in sections if section.get("name") == ".dynsym"), None)
    if dynsym is None:
        return {"elf_class": 32 if elf_class == 1 else 64, "dynamic_symbols": [], "jni_exports": []}
    link = int(dynsym["link"])
    if not (0 <= link < len(sections)):
        raise ValueError("invalid ELF dynstr link")
    dynstr = sections[link]
    str_data = data[int(dynstr["offset"]): int(dynstr["offset"]) + int(dynstr["size"])]
    entry_size = int(dynsym["entry_size"]) or default_sym_size
    count = int(dynsym["size"]) // entry_size
    symbols: list[dict[str, Any]] = []
    for index in range(count):
        offset = int(dynsym["offset"]) + index * entry_size
        if elf_class == 1:
            st_name, st_value, st_size, st_info, st_other, st_shndx = struct.unpack_from(sym_fmt, data, offset)
        else:
            st_name, st_info, st_other, st_shndx, st_value, st_size = struct.unpack_from(sym_fmt, data, offset)
        name = c_string(str_data, st_name)
        if not name:
            continue
        binding = st_info >> 4
        stype = st_info & 0x0F
        symbols.append({
            "name": name,
            "binding": binding,
            "type": stype,
            "visibility": st_other & 0x03,
            "defined": st_shndx != 0,
            "size": st_size,
        })
    jni = sorted({item["name"] for item in symbols if item["name"].startswith("Java_") or item["name"] in {"JNI_OnLoad", "JNI_OnUnload"}})
    return {
        "elf_class": 32 if elf_class == 1 else 64,
        "dynamic_symbols": symbols,
        "jni_exports": jni,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--aar", required=True)
    parser.add_argument("--pom", required=True)
    parser.add_argument("--javap", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--version", default=EXPECTED_VERSION)
    parser.add_argument("--expected-aar-sha256", default=EXPECTED_AAR_SHA256)
    parser.add_argument("--expected-pom-sha256", default=EXPECTED_POM_SHA256)
    args = parser.parse_args()

    aar = Path(args.aar).expanduser().resolve()
    pom = Path(args.pom).expanduser().resolve()
    javap = Path(args.javap).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)

    if args.version != EXPECTED_VERSION:
        raise SystemExit("only client-l:1.0.1 is accepted")
    if not aar.is_file() or not pom.is_file() or not javap.is_file():
        raise SystemExit("AAR, POM, and javap must exist")
    aar_hash = sha256_path(aar)
    pom_hash = sha256_path(pom)
    if aar_hash != args.expected_aar_sha256:
        raise SystemExit(f"AAR SHA-256 mismatch: {aar_hash}")
    if pom_hash != args.expected_pom_sha256:
        raise SystemExit(f"POM SHA-256 mismatch: {pom_hash}")

    with zipfile.ZipFile(aar) as archive:
        entries = sorted(archive.namelist())
        if "classes.jar" not in entries:
            raise SystemExit("AAR does not contain classes.jar")
        classes_jar_bytes = archive.read("classes.jar")
        native_entries = [name for name in entries if name.startswith("jni/") and name.endswith(".so")]

        with tempfile.TemporaryDirectory(prefix="test20-r1-sdk-") as temp_value:
            temp = Path(temp_value)
            jar_path = temp / "classes.jar"
            jar_path.write_bytes(classes_jar_bytes)
            with zipfile.ZipFile(jar_path) as jar:
                class_entries = sorted(name for name in jar.namelist() if name.endswith(".class"))

            classes: list[dict[str, Any]] = []
            javap_chunks: list[str] = []
            failures: list[dict[str, str]] = []
            for entry in class_entries:
                name = class_name_from_entry(entry)
                try:
                    text = run_javap(javap, jar_path, name)
                    header = parse_class_header(text, name)
                    members = parse_members(text, name, header)
                    classes.append({**header, "members": members})
                    javap_chunks.append(f"============================================================\nCLASS={name}\n{text}")
                except Exception as error:  # noqa: BLE001
                    failures.append({"class": name, "error": str(error)})

            native_libraries: list[dict[str, Any]] = []
            for entry in native_entries:
                data = archive.read(entry)
                parts = entry.split("/")
                abi = parts[1] if len(parts) >= 3 else "unknown"
                name = parts[-1]
                try:
                    elf = elf_dynamic_symbols(data)
                    parse_status = "PASS"
                    parse_error = ""
                except Exception as error:  # noqa: BLE001
                    elf = {"elf_class": 0, "dynamic_symbols": [], "jni_exports": []}
                    parse_status = "FAIL"
                    parse_error = f"{error.__class__.__name__}: {error}"
                native_libraries.append({
                    "entry": entry,
                    "abi": abi,
                    "name": name,
                    "size": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "elf_parse_status": parse_status,
                    "elf_parse_error": parse_error,
                    **elf,
                })

    public_classes = [item for item in classes if item.get("public")]
    members = [member for item in public_classes for member in item["members"]]
    callback_classes = sorted(
        item["name"] for item in public_classes
        if item["kind"] == "interface" and (
            ".callbacks.I" in item["name"] or item["name"].startswith("com.rokid.sprite.aiapp.externalapp.I")
        )
    )
    enum_values = {
        item["name"]: [member["name"] for member in item["members"] if member["kind"] == "enum_constant"]
        for item in public_classes
        if any(member["kind"] == "enum_constant" for member in item["members"])
    }
    native_declared = [
        {"class": item["name"], **member}
        for item in public_classes
        for member in item["members"]
        if member.get("native")
    ]
    pom_data = parse_pom(pom)
    result = {
        "schema": "rokid.test20.r1.cxr-l-sdk-census.private.v1",
        "coordinate": "com.rokid.cxr:client-l:1.0.1",
        "artifact": {
            "aar_sha256": aar_hash,
            "aar_size": aar.stat().st_size,
            "pom_sha256": pom_hash,
            "pom_size": pom.stat().st_size,
            "aar_entry_count": len(entries),
            "classes_jar_sha256": hashlib.sha256(classes_jar_bytes).hexdigest(),
        },
        "pom": pom_data,
        "aar_entries": entries,
        "class_entry_count": len(class_entries),
        "javap_failure_count": len(failures),
        "javap_failures": failures,
        "public_class_count": len(public_classes),
        "public_member_count": len(members),
        "public_constructor_count": sum(1 for item in members if item["kind"] == "constructor"),
        "public_method_count": sum(1 for item in members if item["kind"] == "method"),
        "public_field_count": sum(1 for item in members if item["kind"] == "field"),
        "public_enum_constant_count": sum(1 for item in members if item["kind"] == "enum_constant"),
        "callback_classes": callback_classes,
        "enum_values": enum_values,
        "classes": public_classes,
        "native_declared_methods": native_declared,
        "native_libraries": native_libraries,
        "artifact_publication_allowed": False,
    }
    output_json = output / "test20-r1-sdk-census-private.json"
    output_json.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output / "test20-r1-javap-public-private.txt").write_text("\n\n".join(javap_chunks) + "\n", encoding="utf-8")

    print("TEST20_R1_SDK_AAR_SHA256=PASS")
    print("TEST20_R1_SDK_POM_SHA256=PASS")
    print(f"TEST20_R1_SDK_CLASS_ENTRY_COUNT={len(class_entries)}")
    print(f"TEST20_R1_SDK_PUBLIC_CLASS_COUNT={len(public_classes)}")
    print(f"TEST20_R1_SDK_PUBLIC_MEMBER_COUNT={len(members)}")
    print(f"TEST20_R1_SDK_CALLBACK_CLASS_COUNT={len(callback_classes)}")
    print(f"TEST20_R1_SDK_NATIVE_LIBRARY_COUNT={len(native_libraries)}")
    print(f"TEST20_R1_SDK_JAVAP_FAILURE_COUNT={len(failures)}")
    print(f"TEST20_R1_SDK_CENSUS={output_json}")
    if failures:
        print("TEST20_R1_SDK_CENSUS_STATUS=FAIL")
        return 1
    print("TEST20_R1_SDK_CENSUS_STATUS=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
