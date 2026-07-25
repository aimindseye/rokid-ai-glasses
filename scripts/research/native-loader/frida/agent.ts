import Java from "frida-java-bridge";

type ObserverConfig = {
  classPrefixes: string[];
  hookRegisteredNativeTargets?: boolean;
};

const state = {
  registerNativesAddresses: new Set<string>(),
  registerNativesHookCount: 0,
  javaHookOverloadCount: 0,
  configured: false,
  registerReady: false,
  javaReady: false,
  agentReadyEmitted: false,
  registeredNativeAddresses: new Set<string>(),
};

function emit(event: string, fields: Record<string, unknown> = {}): void {
  send({ type: "loader_observer", event, ...fields });
}


function maybeReady(): void {
  if (state.agentReadyEmitted || !state.registerReady || !state.javaReady) return;
  state.agentReadyEmitted = true;
  emit("agent_ready", {
    registerNativesHookCount: state.registerNativesHookCount,
    javaHookOverloadCount: state.javaHookOverloadCount,
  });
}

function maybeHookRegisteredNative(
  className: string,
  methodName: string,
  signature: string,
  address: NativePointer,
  enabled: boolean,
): void {
  if (!enabled || address.isNull()) return;
  const key = address.toString();
  if (state.registeredNativeAddresses.has(key)) return;
  const range = Process.findRangeByAddress(address);
  if (range === null || !range.protection.includes("x")) return;
  state.registeredNativeAddresses.add(key);
  Interceptor.attach(address, {
    onEnter() {
      emit("registered_native_enter", { className, methodName, signature });
    },
    onLeave() {
      emit("registered_native_leave", { className, methodName, signature });
    },
  });
  emit("registered_native_hook_installed", { className, methodName, signature });
}

function safeCString(pointer: NativePointer): string {
  if (pointer.isNull()) return "";
  try {
    return pointer.readCString() ?? "";
  } catch (_) {
    return "<unreadable>";
  }
}

function tryClassName(jclass: NativePointer): string {
  try {
    const env = Java.vm.tryGetEnv();
    if (env === null) return "<java-env-unavailable>";
    return env.getClassName(jclass);
  } catch (_) {
    return "<unresolved-class>";
  }
}

function hookRegisterNativesAddress(address: NativePointer, symbol: string): boolean {
  const key = address.toString();
  if (state.registerNativesAddresses.has(key)) return false;
  state.registerNativesAddresses.add(key);
  state.registerNativesHookCount += 1;

  Interceptor.attach(address, {
    onEnter(args) {
      const jclass = args[1];
      const table = args[2];
      const count = args[3].toInt32();
      const stride = Process.pointerSize * 3;
      const methods: Record<string, unknown>[] = [];
      const className = tryClassName(jclass);
      for (let i = 0; i < count; i++) {
        const row = table.add(i * stride);
        const name = safeCString(row.readPointer());
        const signature = safeCString(row.add(Process.pointerSize).readPointer());
        const fn = row.add(Process.pointerSize * 2).readPointer();
        methods.push({
          index: i,
          name,
          signature,
          function: fn.toString(),
        });
        maybeHookRegisteredNative(
          className,
          name,
          signature,
          fn,
          Boolean((globalThis as any).__observerConfig?.hookRegisteredNativeTargets),
        );
      }
      emit("register_natives_attributed", {
        symbol,
        className,
        count,
        methods,
      });
    },
  });

  emit("register_natives_hook_installed", { symbol });
  return true;
}

function discoverRegisterNatives(): void {
  let newHooks = 0;
  for (const module of Process.enumerateModules()) {
    if (!module.name.includes("libart")) continue;
    for (const symbol of module.enumerateSymbols()) {
      if (!symbol.name.includes("RegisterNatives")) continue;
      if (hookRegisterNativesAddress(symbol.address, symbol.name)) newHooks += 1;
    }
  }

  if (state.registerNativesHookCount === 0) {
    emit("component_failed", {
      component: "register_natives",
      error: "no RegisterNatives hook installed",
    });
    return;
  }

  state.registerReady = true;
  emit("register_natives_hooks_ready", {
    totalHookCount: state.registerNativesHookCount,
    newHooks,
    disposition: newHooks === 0 ? "ALREADY_READY" : "READY",
  });
  maybeReady();
}

function hookAllOverloads(
  className: string,
  methodName: string,
  kind: string,
  filter?: (args: IArguments) => boolean,
): void {
  const klass = Java.use(className);
  const method = klass[methodName] as Java.MethodDispatcher;
  for (const overload of method.overloads) {
    overload.implementation = function (...args: unknown[]) {
      let shouldEmit = true;
      if (filter !== undefined) {
        try {
          shouldEmit = filter(args as unknown as IArguments);
        } catch (_) {
          shouldEmit = false;
        }
      }
      if (shouldEmit) emit("java_handoff", { kind, phase: "enter" });
      try {
        const result = overload.call(this, ...args);
        if (shouldEmit) emit("java_handoff", { kind, phase: "leave" });
        return result;
      } catch (error) {
        if (shouldEmit) emit("java_handoff", { kind, phase: "throw", error: String(error) });
        throw error;
      }
    };
    state.javaHookOverloadCount += 1;
  }
  emit("java_hook_installed", { className, methodName, kind, overloadCount: method.overloads.length });
}

function installJavaHooks(config: ObserverConfig): void {
  Java.perform(() => {
    hookAllOverloads("android.app.Application", "attach", "Application.attach");
    hookAllOverloads("android.app.LoadedApk", "makeApplication", "LoadedApk.makeApplication");
    hookAllOverloads(
      "android.app.Instrumentation",
      "callApplicationOnCreate",
      "Instrumentation.callApplicationOnCreate",
    );
    hookAllOverloads(
      "java.lang.ClassLoader",
      "loadClass",
      "ClassLoader.loadClass",
      (args) => {
        const name = String(args[0]);
        return config.classPrefixes.some((prefix) => name.startsWith(prefix));
      },
    );
    state.javaReady = true;
    emit("java_hooks_ready", { hookOverloadCount: state.javaHookOverloadCount });
    maybeReady();
  });
}

Process.attachModuleObserver({
  onAdded(_) {
    discoverRegisterNatives();
  },
});

rpc.exports = {
  configure(config: ObserverConfig) {
    if (state.configured) return { disposition: "ALREADY_CONFIGURED" };
    state.configured = true;
    (globalThis as any).__observerConfig = config;
    discoverRegisterNatives();
    installJavaHooks(config);
    return { disposition: "CONFIGURED" };
  },
};

emit("script_loaded");
