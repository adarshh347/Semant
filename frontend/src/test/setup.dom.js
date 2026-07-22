// Intentionally minimal. The DOM environment itself is the whole harness: these
// tests assert with plain `expect`, so no custom matcher library is loaded and
// none is a dependency. Kept as a file (rather than removed from config) so a
// later gate has an obvious place to put DOM-wide setup if it ever needs one.
export { };
