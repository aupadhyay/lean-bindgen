import LeanBindgen

def main : IO Unit := do
  let a : UInt32 := 5
  let b : UInt32 := 3
  let result := LeanBindgen.add a b
  IO.println s!"add({a}, {b}) = {result}"
