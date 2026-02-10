import SimpleMath

def main : IO Unit := do
  let result := SimpleMath.add 5 3
  IO.println s!"add(5, 3) = {result}"
