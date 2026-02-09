import Lake
open Lake DSL

package "LeanBindgen" where
  version := v!"0.1.0"

lean_lib «LeanBindgen» where
  -- add library configuration options here

@[default_target]
lean_exe "leanbindgen" where
  root := `Main

/-
  extern_lib tells Lake: "This package depends on a native (C) static library.
  Please build it and link it into any binaries that need it."

  Inside, we use three Lake build helpers:
    • `inputFile`      — registers a source file as a build dependency
    • `buildO`         — compiles a .c file to a .o object file
    • `buildStaticLib` — archives .o files into a .a static library

  Lake will automatically link this static library when building our lean_exe,
  so the @[extern "lean_simple_math_add"] symbol becomes available at link time.
-/
extern_lib «simpleMathFfi» pkg := do
  let cDir := pkg.dir / "c"
  let buildDir := pkg.buildDir / "c"

  -- Compile c/simple_math.c → build/c/simple_math.o
  let simpleMathO ← buildO
    (buildDir / "simple_math.o")                    -- output .o path
    (← inputFile (cDir / "simple_math.c") false)    -- input .c source
    #["-I", cDir.toString]                          -- include path (weak args, not traced)

  -- Compile c/ffi.c → build/c/ffi.o
  let ffiO ← buildO
    (buildDir / "ffi.o")
    (← inputFile (cDir / "ffi.c") false)
    #["-I", cDir.toString]

  -- Archive both .o files into a static library
  -- nameToStaticLib handles platform naming: "libsimpleMathFfi.a" on Unix
  -- pkg.staticLibDir resolves to <buildDir>/lib on Unix
  let libFile := pkg.staticLibDir / nameToStaticLib "simpleMathFfi"
  buildStaticLib libFile #[simpleMathO, ffiO]
