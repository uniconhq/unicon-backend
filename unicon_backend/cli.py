from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from unicon_backend.evaluator.contest import Definition, ProgrammingTask
from unicon_backend.models.contest import TaskType

rich_console = Console()
app = typer.Typer(name="Unicon 🦄 CLI")


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
            table.add_row(str(testcase.id), assembled_prog.code)

        rich_console.print(table)


if __name__ == "__main__":
    app()
