# Test 21 r3.3.4.2.5.1 — Frida 17 Java-Bridge API Repair, Compiled-Agent Qualification, and In-Place Runtime ClassLoader Resume

## Purpose

Repair the r3.3.4.2.5 runtime-observation harness after Frida 17.16.4 rejected the raw GumJS agent with `ReferenceError: 'Java' is not defined`.

Frida 17 no longer bundles the Java runtime bridge into agents created through the API. This repair follows Frida's documented API model: the TypeScript agent explicitly imports `frida-java-bridge`, Frida's `PackageManager` makes the pinned bridge available in a private host workspace, `frida.Compiler` builds a bundle, and only that compiled bundle is loaded through `session.create_script()`.

## Pinned qualification

- Frida host Python API: `17.16.4`
- Device `frida-server`: `17.16.4`
- Java bridge package: `frida-java-bridge@7.0.4`
- Existing venv default: `~/venvs/frida`

The bridge package is installed only into the timestamped private evidence workspace if absent there. It is not committed to the repository or included in sanitized evidence.

## Scientific scope preserved

The repair preserves r3.3.4.2.5's observation-only behavior. It does not replace Java methods, invoke `onBind`, alter Binder results, force-stop Hi Rokid, initiate CXR-L, execute recovered DEX, capture network traffic, or perform photo/audio operations.

## Proof gates

Before process attachment:

- exact Frida host version
- exact frida-server version
- `frida.PackageManager` API
- `frida.Compiler` API
- Java bridge available in private project root
- compiled bundle produced with import resolved

After attachment:

- Java bridge reports `Java.available=true`
- runtime snapshot succeeds
- original r3.3.4.2.5 DEX class-definition gates remain unchanged

## Failure semantics

Compilation or Java-bridge qualification failure is a prerequisite failure, not a service-origin result. No static or runtime absence conclusion may be drawn from it.
