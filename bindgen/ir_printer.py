"""
ir_printer.py — Pretty-print IR for debugging

This utility provides human-readable output of the IR structure.
Useful for:
  - Debugging IR construction
  - Understanding type relationships
  - Implementing --emit-ir flag
"""

from typing import List

from .ir import (
    IRContext,
    Type,
    Function,
    IntType,
    FloatType,
    VoidType,
    PointerType,
    TypeAlias,
)


class IRPrinter:
    """
    Pretty-prints IR to text format.

    Output format:
      Types:
        Type(id=0, kind=IntType(INT, signed=True), spelling="int")
        Type(id=1, kind=FloatType(DOUBLE), spelling="double")

      Functions:
        Function(id=0, name="add", ret=0, params=[Param("a", 0), Param("b", 0)])
    """

    def __init__(self, ctx: IRContext):
        self.ctx = ctx

    def print_all(self) -> str:
        """Print entire IR to string."""
        lines: List[str] = []

        lines.append("=" * 70)
        lines.append(f"IR for {self.ctx.config.module_name}")
        lines.append("=" * 70)
        lines.append("")

        # Print types
        lines.append("Types:")
        lines.append("-" * 70)
        for typ in self.ctx.all_types():
            lines.append(self._format_type(typ))
        lines.append("")

        # Print functions
        lines.append("Functions:")
        lines.append("-" * 70)
        for func in self.ctx.all_functions():
            lines.append(self._format_function(func))
        lines.append("")

        # Print supported functions
        lines.append("Supported Functions:")
        lines.append("-" * 70)
        supported = self.ctx.get_supported_functions()
        if supported:
            for func_id in supported:
                func = self.ctx.get_function(func_id)
                if func:
                    lines.append(f"  - {func.c_name}")
        else:
            lines.append("  (none)")
        lines.append("")

        return "\n".join(lines)

    def _format_type(self, typ: Type) -> str:
        """Format a single type for display."""
        kind_str = self._format_type_kind(typ.kind)
        canonical_str = f", canonical={typ.canonical}" if typ.canonical else ""
        return f'  Type(id={typ.id}, kind={kind_str}, spelling="{typ.c_spelling}"{canonical_str})'

    def _format_type_kind(self, kind) -> str:
        """Format a TypeKind for display."""
        if isinstance(kind, IntType):
            return f"IntType({kind.kind.name}, signed={kind.is_signed})"
        elif isinstance(kind, FloatType):
            return f"FloatType({kind.kind.name})"
        elif isinstance(kind, VoidType):
            return "VoidType()"
        elif isinstance(kind, PointerType):
            return f"PointerType(pointee={kind.pointee}, kind={kind.kind.name}, const={kind.is_const})"
        elif isinstance(kind, TypeAlias):
            return f'TypeAlias(name="{kind.alias_name}", aliased={kind.aliased_type})'
        else:
            return f"{type(kind).__name__}(...)"

    def _format_function(self, func: Function) -> str:
        """Format a single function for display."""
        params_str = ", ".join(f'Param("{p.name}", {p.type_id})' for p in func.params)
        return (
            f'  Function(id={func.id}, name="{func.c_name}", '
            f"ret={func.return_type}, params=[{params_str}])"
        )


def print_ir(ctx: IRContext) -> str:
    """Convenience function to print IR context."""
    printer = IRPrinter(ctx)
    return printer.print_all()
