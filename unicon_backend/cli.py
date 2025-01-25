from typing import Annotated

import typer
from rich.console import Console
from rich.syntax import Syntax
from rich.table import Table

from unicon_backend.dependencies.project import role_permissions
from unicon_backend.lib.permissions.permission import (
    debug_list_tuples,
    delete_all_permission_records,
    init_schema,
    permission_create,
)
from unicon_backend.models.organisation import Group

rich_console = Console()
app = typer.Typer(name="Unicon 🦄 CLI")

permify_app = typer.Typer()
app.add_typer(permify_app, name="permify")


@permify_app.command(name="init")
def init_permify():
    """Sends the schema file to permify."""
    schema_version = init_schema("unicon_backend/lib/permissions/unicon.perm")
    print(f"Schema version: {schema_version}. Please update your .env file.")


@permify_app.command(name="seed")
def seed_permify():
    """Clears permify's existing tuples and repopulates it using the current postgres database."""
    from sqlalchemy import select

    from unicon_backend.database import SessionLocal
    from unicon_backend.models.links import UserRole
    from unicon_backend.models.organisation import Organisation, Project, Role
    from unicon_backend.models.problem import ProblemORM, SubmissionORM

    # assume schema is initialised (run init-permify if not)
    delete_all_permission_records()
    model_classes = [Project, Role, ProblemORM, SubmissionORM, UserRole, Organisation, Group]
    with SessionLocal() as session:
        for model_class in model_classes:
            models = session.scalars(select(model_class)).all()
            for model in models:
                permission_create(model)

    rich_console.print("Permissions seeded successfully 🌈")


@permify_app.command(name="list")
def list_permify():
    debug_list_tuples()


@app.command(name="seed")
def seed(username: str, password: str, problem_defns: list[typer.FileText]):
    """Seed the database with initial admin user, organisation, roles, projects and problems."""
    from unicon_backend.database import SessionLocal
    from unicon_backend.dependencies.auth import AUTH_PWD_CONTEXT
    from unicon_backend.evaluator.problem import Problem
    from unicon_backend.models.organisation import Organisation, Project, Role
    from unicon_backend.models.problem import ProblemORM
    from unicon_backend.models.user import UserORM

    db_session = SessionLocal()
    hash_password = AUTH_PWD_CONTEXT.hash(password)

    admin_user = UserORM(username=username, password=hash_password)
    db_session.add(admin_user)
    db_session.flush()

    organisation = Organisation(name="Unicon", description="Rainbows", owner_id=admin_user.id)

    project = Project(
        name="Sparkles",
        organisation=organisation,
        problems=[
            ProblemORM.from_problem(Problem.model_validate_json(problem_defn.read()))
            for problem_defn in problem_defns
        ],
    )
    project.roles = [
        Role(
            name="admin",
            users=[admin_user],
            **{perm: True for perm in role_permissions["admin"]},
        ),
        *[
            Role(name=role, **{perm: True for perm in role_permissions[role]})
            for role in ["helper", "member"]
        ],
    ]

    db_session.add_all([organisation, project])
    db_session.commit()

    seed_permify()

    rich_console.print("Database seeded successfully 🌈")

    table = Table(show_header=True, show_lines=True)
    table.add_column("Entity", style="cyan bold", no_wrap=True)
    table.add_column("Details", style="white")
    # fmt: off
    table.add_row("User", f"{admin_user.username} (id: {admin_user.id})")
    table.add_row("Organisation", f"{organisation.name} (id: {organisation.id})")
    table.add_row("Project", f"{project.name} (id: {project.id})")
    table.add_row("Roles", "\n".join(role.name for role in project.roles))
    table.add_row("Problems", "\n".join(f"{problem.name} (id: {problem.id})" for problem in project.problems))
    # fmt: on

    rich_console.print(table)


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
