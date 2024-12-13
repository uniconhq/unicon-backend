from typing import Annotated

import typer
from rich.console import Console
from rich.syntax import Syntax
from rich.table import Table

rich_console = Console()
app = typer.Typer(name="Unicon 🦄 CLI")


@app.command(name="seed")
def seed(username: str, password: str):
    """Seed the database with initial admin user and organisation."""
    from unicon_backend.database import SessionLocal
    from unicon_backend.dependencies.auth import AUTH_PWD_CONTEXT
    from unicon_backend.models.organisation import Organisation, Project, Role
    from unicon_backend.models.user import UserORM

    db_session = SessionLocal()
    hash_password = AUTH_PWD_CONTEXT.hash(password)

    admin_user = UserORM(username=username, password=hash_password)
    db_session.add(admin_user)
    db_session.flush()

    organisation = Organisation(name="Unicon", description="Rainbows", owner_id=admin_user.id)
    project = Project(name="Sparkles", organisation=organisation)
    roles = [
        Role(name="admin", project=project, users=[admin_user]),
        *[Role(name=role, project=project) for role in ["member", "helper"]],
    ]

    db_session.add_all([organisation, project, *roles])
    db_session.commit()

    rich_console.print("Database seeded successfully 🌈")


@app.command(name="assemble")
def assemble(defn_file: Annotated[typer.FileText, typer.Option("--defn", mode="r")]):
    """Assemble the programs for all programming tasks in the given definition file."""
    from unicon_backend.evaluator.problem import Problem, ProgrammingTask
    from unicon_backend.models.problem import TaskType

    defn = Problem.model_validate_json(defn_file.read())
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

            syntax_highlighted_code = Syntax(
                assembled_prog.code, "python", theme="material", line_numbers=True, word_wrap=True
            )
            table.add_row(str(testcase.id), syntax_highlighted_code)

        rich_console.print(table)


if __name__ == "__main__":
    app()
