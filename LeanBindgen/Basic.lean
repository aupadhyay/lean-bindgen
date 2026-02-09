/-
  LeanBindgen.Basic -- FFI declarations for simple_math.h

  This file is the "target output" of our transpiler. In later phases,
  it will be generated automatically from a C header.
-/

namespace LeanBindgen

/-
  `@[extern "lean_simple_math_add"]` tells the Lean compiler:
  "Don't use a Lean implementation -- call the C symbol `lean_simple_math_add` instead."
  The C function must match the unboxed ABI: uint32_t → uint32_t → uint32_t.

  `opaque` means this function has no Lean-side body at all.
  It only exists as a type signature that the compiler checks against the FFI call.
-/
@[extern "lean_simple_math_add"]
opaque add (a b : UInt32) : UInt32

end LeanBindgen
