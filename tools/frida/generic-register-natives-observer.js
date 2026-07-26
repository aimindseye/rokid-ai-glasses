'use strict';
/* Generic observation-only RegisterNatives skeleton.
 * Deliberately omits product names, target signatures, bypasses, replacements,
 * return-value changes, and concealment logic.
 */
function installRegisterNativesObserver(moduleName, exportName) {
  const address = Module.findGlobalExportByName(exportName || 'RegisterNatives');
  if (address === null) {
    send({ event: 'register-natives-export-unavailable', module: moduleName || null });
    return false;
  }
  Interceptor.attach(address, {
    onEnter(args) {
      send({ event: 'register-natives-call', method_count: args[3].toInt32() });
    }
  });
  return true;
}
