import Lake
open Lake DSL
open System (FilePath)

package "test" where
  version := v!"0.0.1"

/--
Run lean-bindgen on our C headers to produce generated Lean + C glue files.
Invoke with `lake run bindgen` before `lake build`.
-/
script bindgen do
  let dir ← IO.currentDir

  -- Generate SimpleMath bindings
  let smDir := dir / "generated" / "simple_math"
  unless (← (smDir / "SimpleMath.lean").pathExists) do
    let out ← IO.Process.output {
      cmd := "python3"
      args := #["-m", "bindgen",
        (dir / "c" / "simple_math.h").toString,
        "-o", smDir.toString,
        "--module", "SimpleMath"]
      cwd := dir
    }
    if out.exitCode != 0 then
      IO.eprintln s!"lean-bindgen (SimpleMath) failed:\n{out.stderr}"
      return 1

  -- Generate HandleLib bindings
  let hlDir := dir / "generated" / "handle_lib"
  unless (← (hlDir / "HandleLib.lean").pathExists) do
    let out ← IO.Process.output {
      cmd := "python3"
      args := #["-m", "bindgen",
        (dir / "c" / "handle_lib.h").toString,
        "-o", hlDir.toString,
        "--module", "HandleLib"]
      cwd := dir
    }
    if out.exitCode != 0 then
      IO.eprintln s!"lean-bindgen (HandleLib) failed:\n{out.stderr}"
      return 1

  return 0

lean_lib «SimpleMath» where
  srcDir := "generated/simple_math"
  roots := #[`SimpleMath]

lean_lib «HandleLib» where
  srcDir := "generated/handle_lib"
  roots := #[`HandleLib]

@[default_target]
lean_exe "test" where
  root := `Main

extern_lib «simpleMathFfi» pkg := do
  let cDir := pkg.dir / "c"
  let genDir := pkg.dir / "generated" / "simple_math"
  let buildDir := pkg.buildDir / "c"
  let simpleMathO ← buildO
    (buildDir / "simple_math.o")
    (← inputFile (cDir / "simple_math.c") false)
    #["-I", cDir.toString]
  let ffiO ← buildO
    (buildDir / "simple_math_ffi.o")
    (← inputFile (genDir / "ffi.c") false)
    #["-I", cDir.toString]
  let libFile := pkg.staticLibDir / nameToStaticLib "simpleMathFfi"
  buildStaticLib libFile #[simpleMathO, ffiO]

extern_lib «handleLibFfi» pkg := do
  let cDir := pkg.dir / "c"
  let genDir := pkg.dir / "generated" / "handle_lib"
  let buildDir := pkg.buildDir / "c"
  let leanIncDir := (← getLeanIncludeDir).toString
  let handleLibO ← buildO
    (buildDir / "handle_lib.o")
    (← inputFile (cDir / "handle_lib.c") false)
    #["-I", cDir.toString]
  let handleFfiO ← buildO
    (buildDir / "handle_lib_ffi.o")
    (← inputFile (genDir / "ffi.c") false)
    #["-I", cDir.toString, "-I", leanIncDir]
  let libFile := pkg.staticLibDir / nameToStaticLib "handleLibFfi"
  buildStaticLib libFile #[handleLibO, handleFfiO]
