/*
 * ffi.c -- The "glue" layer between Lean and the raw C library.
 *
 * WHY THIS FILE EXISTS:
 * Lean's FFI passes UInt32 as C uint32_t, but the original C library
 * uses plain `int`. This thin wrapper adapts the types so the Lean
 * extern declaration can call the C library without modifying it.
 *
 * In later phases, the transpiler will generate this file automatically
 * for every C header it processes.
 */

#include <stdint.h>
#include "simple_math.h"

uint32_t lean_simple_math_add(uint32_t a, uint32_t b) {
    return (uint32_t)add((int)a, (int)b);
}
