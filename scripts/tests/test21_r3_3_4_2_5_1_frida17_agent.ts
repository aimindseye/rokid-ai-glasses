import Java from "frida-java-bridge";

const TARGET_SERVICE = 'com.rokid.sprite.aiapp.externalapp.service.CXRLinkService';
const TARGET_MEDIA = 'com.rokid.sprite.aiapp.externalapp.IMediaStreamService';
const TARGET_STUB = TARGET_MEDIA + '$Stub';

function jstr(x: any): string | null {
  try { return x === null || x === undefined ? null : '' + x; } catch (_) { return null; }
}
function safe<T>(fn: () => T, dflt: T): T {
  try { return fn(); } catch (_) { return dflt; }
}
function fieldValue(obj: any, clazz: any, name: string): any {
  return safe(() => { const f = clazz.getDeclaredField(name); f.setAccessible(true); return f.get(obj); }, null);
}
function loaderRecord(loader: any): any {
  const rec: any = {
    loader_class: safe(() => '' + loader.getClass().getName(), 'UNRESOLVED'),
    loader_string: jstr(loader),
    parent: null,
    dex_elements: []
  };
  rec.parent = safe(() => jstr(loader.getParent()), null);
  try {
    let c: any = loader.getClass();
    let pathList: any = null;
    while (c && pathList === null) {
      pathList = fieldValue(loader, c, 'pathList');
      c = safe(() => c.getSuperclass(), null);
    }
    if (pathList) {
      const plc = pathList.getClass();
      const els = fieldValue(pathList, plc, 'dexElements');
      if (els) {
        const n = safe(() => els.length, 0);
        for (let i = 0; i < n; i++) {
          const e = els[i], ec = e.getClass(), df = fieldValue(e, ec, 'dexFile');
          rec.dex_elements.push({
            element: jstr(e),
            dex_file: jstr(df),
            dex_name: df ? safe(() => jstr(df.getName()), null) : null
          });
        }
      }
    }
  } catch (_) {}
  return rec;
}
function classRecord(name: string, loader: any): any {
  const out: any = {name, loaded: false, loader: null, superclass: null, interfaces: [], declared_methods: [], binder_field_classes: []};
  try {
    const cf = Java.ClassFactory.get(loader);
    const W = cf.use(name);
    const C = W.class;
    out.loaded = true;
    out.loader = loaderRecord(loader);
    out.superclass = safe(() => jstr(C.getSuperclass()), null);
    const ints = safe(() => C.getInterfaces(), [] as any[]);
    for (let i = 0; i < ints.length; i++) out.interfaces.push(jstr(ints[i]));
    const ms = safe(() => C.getDeclaredMethods(), [] as any[]);
    for (let i = 0; i < ms.length; i++) out.declared_methods.push(jstr(ms[i]));
    if (name === TARGET_SERVICE) {
      Java.choose(name, {
        onMatch(inst: any) {
          try {
            const fs = C.getDeclaredFields();
            for (let i = 0; i < fs.length; i++) {
              const f = fs[i]; f.setAccessible(true);
              const v = safe(() => f.get(inst), null);
              if (v) {
                const cn = safe(() => jstr(v.getClass().getName()), null);
                if (cn && (cn.indexOf('Binder') >= 0 || cn.indexOf('IMediaStreamService') >= 0 || cn.indexOf('Stub') >= 0)) out.binder_field_classes.push(cn);
              }
            }
          } catch (_) {}
        },
        onComplete() {}
      });
    }
  } catch (_) {}
  return out;
}
function findLoaderFor(name: string): any {
  let found: any = null;
  Java.enumerateClassLoaders({
    onMatch(loader: any) {
      if (found) return;
      try { loader.loadClass(name); found = loader; } catch (_) {}
    },
    onComplete() {}
  });
  return found;
}
function dexMemoryCandidates(): any[] {
  const seen: Record<string, number> = {};
  const out: any[] = [];
  for (const prot of ['r--', 'rw-', 'r-x']) {
    let ranges: any[] = [];
    try { ranges = Process.enumerateRanges({ protection: prot, coalesce: true }); } catch (_) { continue; }
    for (const r of ranges) {
      let matches: any[] = [];
      try { matches = Memory.scanSync(r.base, r.size, '64 65 78 0a'); } catch (_) { continue; }
      for (const m of matches) {
        const key = m.address.toString();
        if (seen[key]) continue;
        seen[key] = 1;
        try {
          const ver = m.address.add(4).readUtf8String(3);
          const zero = m.address.add(7).readU8();
          const size = m.address.add(0x20).readU32();
          const hsize = m.address.add(0x24).readU32();
          const endian = m.address.add(0x28).readU32();
          if (/^0[3-4][0-9]$/.test(ver) && zero === 0 && hsize === 0x70 && size >= 0x70 && size <= 67108864 && (endian === 0x12345678 || endian === 0x78563412)) out.push({address: key, size, version: ver, protection: prot});
        } catch (_) {}
        if (out.length >= 96) return out;
      }
    }
  }
  return out;
}

rpc.exports = {
  healthcheck() {
    return {schema: 'rokid.test21-r3.3.4.2.5.1.frida-health.v1', java_available: Java.available, frida_version: Frida.version};
  },
  snapshot() {
    const result: any = {schema: 'rokid.test21-r3.3.4.2.5.frida.v1', repair_schema: 'rokid.test21-r3.3.4.2.5.1.frida17.v1', process_id: Process.id, java_available: Java.available, targets: {}, matching_loaded_classes: [], memory_dex_candidates: []};
    if (!Java.available) return result;
    Java.performNow(() => {
      const loaded = Java.enumerateLoadedClassesSync();
      result.matching_loaded_classes = loaded.filter((x: string) => x.indexOf('CXRLink') >= 0 || x.indexOf('IMediaStreamService') >= 0).slice(0, 256);
      for (const n of [TARGET_SERVICE, TARGET_MEDIA, TARGET_STUB]) {
        const l = findLoaderFor(n);
        result.targets[n] = l ? classRecord(n, l) : {name: n, loaded: false};
      }
    });
    result.memory_dex_candidates = dexMemoryCandidates();
    return result;
  },
  readmemory(address: string, offset: number, length: number) {
    return ptr(address).add(offset).readByteArray(length);
  }
};
