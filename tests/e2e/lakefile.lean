import Lake
open Lake DSL
open System (FilePath)

package "test" where
  version := v!"0.0.1"

/--
Run lean-bindgen on our C header to produce `generated/SimpleMath.lean`
and `generated/ffi.c`.  Invoke with `lake run bindgen` before `lake build`.
-/
script bindgen do
  let dir ← IO.currentDir
  let genDir := dir / "generated"
  let genLean := genDir / "SimpleMath.lean"
  -- Only regenerate when the output is missing
  unless (← genLean.pathExists) do
    let out ← IO.Process.output {
      cmd := "python3"
      args := #["-m", "bindgen",
        (dir / "c" / "simple_math.h").toString,
        "-o", genDir.toString,
        "--module", "SimpleMath"]
      cwd := dir
    }
    if out.exitCode != 0 then
      IO.eprintln s!"lean-bindgen failed:\n{out.stderr}"
      return 1
  return 0

lean_lib «SimpleMath» where
  srcDir := "generated"
  roots := #[`SimpleMath]

@[default_target]
lean_exe "test" where
  root := `Main

extern_lib «simpleMathFfi» pkg := do
  let cDir := pkg.dir / "c"
  let genDir := pkg.dir / "generated"
  let buildDir := pkg.buildDir / "c"
  let simpleMathO ← buildO
    (buildDir / "simple_math.o")
    (← inputFile (cDir / "simple_math.c") false)
    #["-I", cDir.toString]
  let ffiO ← buildO
    (buildDir / "ffi.o")
    (← inputFile (genDir / "ffi.c") false)
    #["-I", cDir.toString]
  let libFile := pkg.staticLibDir / nameToStaticLib "simpleMathFfi"
  buildStaticLib libFile #[simpleMathO, ffiO]
