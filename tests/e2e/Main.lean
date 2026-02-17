import SimpleMath
import HandleLib

def main : IO Unit := do
  -- Test scalar FFI
  let result := SimpleMath.add 5 3
  IO.println s!"add(5, 3) = {result}"

  -- Test opaque pointer + string FFI
  let h ← HandleLib.handle_create "hello-from-lean"
  let name ← HandleLib.handle_name h
  IO.println s!"handle_name = {name}"
  let rc ← HandleLib.handle_close h
  IO.println s!"handle_close = {rc}"
