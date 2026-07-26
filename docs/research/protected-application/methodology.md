# Methodology

Two deterministic private-evidence archives were verified against their internal SHA-256 manifests. The baseline and APK-enhanced JSON records were compared field by field.

DEX caller observations were deduplicated into logical sites using the target method and signature, caller class and method, caller signature, invoke kind, and code-unit offset. Source APK occurrences remain as replica evidence and are not counted as separate logical caller sites.

Runtime evidence, static DEX reachability, feature inference, and unresolved state remain separate classifications.
