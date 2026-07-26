'use strict';
// Observation-only reachability marker. No Java bridge and no Interceptor hooks.
send({ event: 'agent-ready', zero_hook: true });
