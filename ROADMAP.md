# Roadmap

> **North star:** Run `lean-bindgen sqlite3.h` and get a typed, compiling Lean 4 SQLite wrapper.

---

## Proper IR

We need a more robust intermediate representation that decouples parsing from code generation.

## Strings, Opaque Pointers & Constants

The minimum to bind any real library. SQLite's core API is opaque handles + strings + error codes.

- [ ] `const char *` parameters & return values → Lean `String`
- [ ] Opaque pointer types
- [ ] Output parameter
- [ ] `#define` integer constants and `enum` types
- [ ] `typedef` resolution

## Callbacks & Function Pointers

SQLite's `sqlite3_exec`, busy handlers, authorizer, etc. all take callbacks.

- [ ] Function pointer parameters → Lean closures
- [ ] Callback + `void *` user-data pairing

## Structs & Arrays

- [ ] Flat struct types
- [ ] Buffer parameters (`const void *data, int len`) → Lean `ByteArray`

---

## Future

Things to explore once the core is solid. Just brainstorming here.

- **Proof scaffolding** — emit theorem stubs for common safety properties (null checks, resource lifetimes)
- **More target libraries** — libcurl, libsodium, SDL2, libgit2, etc.
- **C++ `extern "C"` support** — detect and handle `extern "C"` blocks in C++ headers
- **Rust via cbindgen** — document the `cbindgen → .h → lean-bindgen → Lean` pipeline
