from typing import Annotated

import libcst as cst
import libcst.codemod.visitors as codemod
import typer
from libcst.codemod import CodemodContext
from rich.console import Console
from rich.syntax import Syntax
from rich.table import Table

from unicon_backend.evaluator.contest import Definition, ProgrammingTask
from unicon_backend.models.contest import TaskType

rich_console = Console()
app = typer.Typer(name="Unicon 🦄 CLI")


class RemoveImportsTransformer(cst.CSTTransformer):
    def leave_Import(self, _, __):
        return cst.RemoveFromParent()

    def leave_ImportFrom(self, _, __):
        return cst.RemoveFromParent()


class AddImportsTransformer(cst.CSTTransformer):
    def __init__(self, imports: set[str], import_froms: dict[str, set[str]]) -> None:
        self._imports = imports
        self._import_froms = import_froms
        super().__init__()

    def leave_Module(self, node: cst.Module, _) -> cst.Module:
        import_stmts = [
            cst.SimpleStatementLine(
                [cst.Import([cst.ImportAlias(name=cst.Name(module)) for module in self._imports])]
            ),
        ]
        import_from_stmts = [
            cst.SimpleStatementLine(
                [
                    cst.ImportFrom(
                        module=cst.Name(module),
                        names=[cst.ImportAlias(name=cst.Name(obj)) for obj in objs],
                    )
                ]
            )
            for module, objs in self._import_froms.items()
        ]
        return cst.Module(body=[*import_stmts, *import_from_stmts, *node.body])


@app.command(name="assemble")
def assemble(defn_file: Annotated[typer.FileText, typer.Option("--defn", mode="r")]):
    """Assemble the programs for all programming tasks in the given definition file."""
    defn = Definition.model_validate_json(defn_file.read())
    for task in defn.tasks:
        if task.type != TaskType.PROGRAMMING:
            continue

        assert isinstance(task, ProgrammingTask)

        table = Table(title=f"Task #{task.id} Assembled Programs")
        table.add_column("Testcase ID", style="magenta")
        table.add_column("Program", style="green")

        # NOTE: We use the templates to generate the input step
        # This is so that we do not need to take in any user input and can simply assemble
        # the task directly from the given definition for a quick test
        user_input_step = task.create_input_step(task.required_inputs)
        for testcase in task.testcases:
            assembled_prog = testcase.run(user_input_step)

            # TEMP: Proof of concept for import hoisting
            import_visitor = codemod.GatherImportsVisitor(CodemodContext())
            assembled_prog.visit(import_visitor)
            imports, import_froms = import_visitor.module_imports, import_visitor.object_mapping
            no_imports = assembled_prog.visit(RemoveImportsTransformer())
            transformed = no_imports.visit(AddImportsTransformer(imports, import_froms))

            syntax_highlighted_code = Syntax(
                transformed.code, "python", theme="material", line_numbers=True, word_wrap=True
            )
            table.add_row(str(testcase.id), syntax_highlighted_code)

        rich_console.print(table)


if __name__ == "__main__":
    app()
