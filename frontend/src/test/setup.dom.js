// Intentionally minimal. The DOM environment itself is the whole harness: these
// tests assert with plain `expect`, so no custom matcher library is loaded and
// none is a dependency. Kept as a file (rather than removed from config) so a
// later gate has an obvious place to put DOM-wide setup if it ever needs one.
//
// CIRCUIT-001 P2 adds exactly one line, and it is load-bearing rather than
// cosmetic. React only honours `act(...)` when the environment declares itself an
// act environment; without the flag every mount logs a warning AND React is
// entitled to stop flushing effects synchronously — so a component test would be
// asserting against a half-rendered tree while still passing. Setting it globally
// is safe: the node-environment suites never call `act`, so it is simply unread
// there.
globalThis.IS_REACT_ACT_ENVIRONMENT = true;

export { };
