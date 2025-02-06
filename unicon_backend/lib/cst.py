from collections.abc import MutableSequence, Sequence

import libcst as cst

UNUSED_VAR = cst.Name(value="_")

type ProgramVariable = cst.Name
type ProgramFragment = Sequence[
    cst.SimpleStatementLine | cst.BaseCompoundStatement | cst.BaseSmallStatement
]
type ProgramBody = MutableSequence[cst.SimpleStatementLine | cst.BaseCompoundStatement]

# A program can be made up of sub programs, especially with subgraphs
Program = cst.Module


def cst_str(v: str) -> cst.SimpleString:
    return cst.SimpleString(value=repr(v))


def cst_var(v: str | bool) -> cst.Name:
    return cst.Name(value=str(v))


def assemble_fragment(
    fragment: ProgramFragment,
) -> Sequence[cst.SimpleStatementLine | cst.BaseCompoundStatement]:
    """
    Assemble a program fragement into a list of `cst.Module` statements.

    We allow for `cst.BaseSmallStatement` to be included in the fragment for convenience during assembly,
    however they are not valid statements in a `cst.Module`. As such, we convert them to `cst.SimpleStatementLine`.
    """
    return [
        cst.SimpleStatementLine([stmt]) if isinstance(stmt, cst.BaseSmallStatement) else stmt
        for stmt in fragment
    ]


import libcst as cst
from libcst.codemod import CodemodContext
from libcst.codemod.visitors import AddImportsVisitor, GatherImportsVisitor, ImportItem


class RemoveImportsVisitors(cst.CSTTransformer):
    """
    A visitor that removes all import statements from the code.
    """

    def leave_Import(self, _og_node: cst.Import, _updated_node: cst.Import) -> cst.RemovalSentinel:
        return cst.RemoveFromParent()

    def leave_ImportFrom(
        self, _og_node: cst.ImportFrom, _updated_node: cst.ImportFrom
    ) -> cst.RemovalSentinel:
        return cst.RemoveFromParent()


def hoist_imports(program: cst.Module) -> cst.Module:
    """
    Hoist all import statements to the top of the program. Additionally, it combines and remove imports to
    prevent duplicate imports.
    """
    context = CodemodContext()
    gather_imports_visitor = GatherImportsVisitor(context)
    program.visit(gather_imports_visitor)
    removed_imports = program.visit(RemoveImportsVisitors())
    add_imports_visitor = AddImportsVisitor(
        context,
        [ImportItem(module_name_str) for module_name_str in gather_imports_visitor.module_imports]
        + [
            ImportItem(module_name_str, obj_name=obj_name_str)
            for module_name_str, obj_name_strs in gather_imports_visitor.object_mapping.items()
            for obj_name_str in obj_name_strs
        ],
    )
    program = removed_imports.visit(add_imports_visitor)
    return program
