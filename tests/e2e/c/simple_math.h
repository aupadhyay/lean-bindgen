#ifndef SIMPLE_MATH_H
#define SIMPLE_MATH_H

/*
 * A tiny C library that our Lean code will call through the FFI.
 * This file is the "user-provided" header -- the kind of file
 * our transpiler will eventually parse automatically.
 */

int add(int a, int b);

#endif /* SIMPLE_MATH_H */
