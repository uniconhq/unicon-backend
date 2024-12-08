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
