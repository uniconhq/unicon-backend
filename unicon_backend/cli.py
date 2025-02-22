import copy
import json
from datetime import datetime, timedelta
from typing import Annotated
from uuid import uuid4

import typer
from rich.console import Console
from rich.syntax import Syntax
from rich.table import Table
from sqlalchemy import select
from sqlmodel import col

from unicon_backend.evaluator.tasks.base import TaskType

rich_console = Console()

app = typer.Typer(name="Unicon 🦄 CLI")

permify_app = typer.Typer()
app.add_typer(permify_app, name="permify", help="Initialize and seed permissions")


@permify_app.command(name="init")
def init_perms_schema(
    schema_file: Annotated[
        typer.FileText | None,
        typer.Argument(
            help="If not provided, the default schema file ('unicon.perm') will be used"
        ),
    ] = None,
) -> None:
    """Initializes permission schema"""
    import importlib.resources

    import permify as p
    from permify.exceptions import NotFoundException

    from unicon_backend.constants import PERMIFY_HOST, PERMIFY_TENANT_ID

    schema: str = (
        schema_file.read()
        if schema_file
        else importlib.resources.files("unicon_backend").joinpath("unicon.perm").read_text()
    )

    if (schema_write_body := p.SchemaWriteBody.from_dict({"schema": schema})) is None:
        # This should never happen, there is no validation/parsing done on the schema
        raise ValueError("Failed to create schema payload!")

    rich_console.print(f"Permify Host: [bold blue]{PERMIFY_HOST}[/bold blue]")

    schema_api = p.SchemaApi(p.ApiClient(p.Configuration(host=PERMIFY_HOST)))

    try:
        # NOTE: 10 is an arbitrary page size chosen
        # We assume that the current schema, it there is one, is within the first 10 schemas
        existing_schemas = schema_api.schemas_list(
            PERMIFY_TENANT_ID, p.SchemaListBody(page_size=10)
        )
        if curr_schema_v := existing_schemas.head:
            assert existing_schemas.schemas is not None
            curr_schema = next(s for s in existing_schemas.schemas if s.version == curr_schema_v)
            rich_console.print(
                f"Current schema version: [bold red]{curr_schema_v}[/bold red] ({curr_schema.created_at})"
            )
            typer.confirm(
                "Are you sure you want to overwrite and invalidate this schema?", abort=True
            )
    except NotFoundException:
        rich_console.print("No existing schema found, initializing new schema...")

    write_resp = schema_api.schemas_write(PERMIFY_TENANT_ID, schema_write_body)
    if (schema_version := write_resp.schema_version) is None:
        raise ValueError("Failed to create schema, is the schema valid?")

    rich_console.print(f"Initialized schema version: [bold green]{schema_version}[/bold green] 🥳")
    rich_console.print(
        "If you like update permissions for existing records in the database, run: [bold magenta]permify seed[/bold magenta]"
    )


@permify_app.command(name="seed")
def seed_perms():
    """Add permission tuples for all existing records in the database. Existing tuples will be cleared."""
    import permify as p

    from unicon_backend.constants import PERMIFY_HOST, PERMIFY_TENANT_ID

    rich_console.print(f"Permify Host: [bold blue]{PERMIFY_HOST}[/bold blue]")

    schema_api = p.SchemaApi(p.ApiClient(p.Configuration(host=PERMIFY_HOST)))
    existing_schemas = schema_api.schemas_list(PERMIFY_TENANT_ID, p.SchemaListBody())
    if not existing_schemas.head:
        rich_console.print(
            "No schema found, please initialize a schema first. Run: [bold magenta]permify init[/bold magenta]"
        )

    from sqlalchemy import select

    from unicon_backend.database import SessionLocal
    from unicon_backend.lib.permissions import delete_all_permission_records, permission_create
    from unicon_backend.models.links import UserRole
    from unicon_backend.models.organisation import Group, Organisation, Project, Role
    from unicon_backend.models.problem import ProblemORM, SubmissionORM

    rich_console.print(f"Current schema version: [bold red]{existing_schemas.head}[/bold red]")
    typer.confirm("Are you sure you want to remove all existing permission tuples?", abort=True)
    delete_all_permission_records()

    rich_console.print("Seeding new permissions under the current schema...")
    model_classes = [Project, Role, ProblemORM, SubmissionORM, UserRole, Organisation, Group]
    with SessionLocal() as session:
        for model_class in model_classes:
            models = session.scalars(select(model_class)).all()
            for model in models:
                permission_create(model)
            rich_console.print(
                f"[bold magenta]{model_class.__name__}[/bold magenta] (count: {len(models)})"
            )
    rich_console.print("Permissions seeded successfully 🌈")


@app.command(name="seed")
def seed(username: str, password: str, problem_defns: list[typer.FileText]):
    """Seed the database with sample data"""
    from unicon_backend.database import SessionLocal
    from unicon_backend.dependencies.auth import AUTH_PWD_CONTEXT
    from unicon_backend.dependencies.project import role_permissions
    from unicon_backend.evaluator.problem import Problem
    from unicon_backend.models.organisation import Organisation, Project, Role
    from unicon_backend.models.problem import ProblemORM
    from unicon_backend.models.user import UserORM

    db_session = SessionLocal()
    hash_password = AUTH_PWD_CONTEXT.hash(password)

    admin_user = db_session.scalar(select(UserORM).where(col(UserORM.username) == username))
    if admin_user:
        typer.confirm("User already exists. Add data to existing user?", abort=True)
    else:
        admin_user = UserORM(username=username, password=hash_password)
        db_session.add(admin_user)
        db_session.flush()

    organisation = Organisation(name="Unicon", description="Rainbows", owner_id=admin_user.id)

    loaded_problem_defns = [json.loads(problem_defn.read()) for problem_defn in problem_defns]
    for problem_defn in loaded_problem_defns:
        problem_defn["started_at"] = datetime.now()
        problem_defn["ended_at"] = datetime.now() + timedelta(weeks=2)
        problem_defn["closed_at"] = datetime.now() + timedelta(weeks=3)

    project = Project(
        name="Sparkles",
        organisation=organisation,
        problems=[
            ProblemORM.from_problem(Problem.model_validate(problem_defn))
            for problem_defn in loaded_problem_defns
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
    """Assemble all programming tasks in provided problem definition"""
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
        for testcase in task.testcases:
            testcase.attach_user_inputs(task.required_inputs)
            assembled_prog = testcase.run()

            syntax_highlighted_code = Syntax(
                assembled_prog.code, "python", theme="material", line_numbers=True, word_wrap=True
            )
            table.add_row(str(testcase.id), syntax_highlighted_code)

        rich_console.print(table)


@app.command(name="migrate-file-format")
def migrate_file_format():
    from unicon_backend.database import SessionLocal
    from unicon_backend.models.problem import TaskAttemptORM, TaskORM

    db_session = SessionLocal()
    # Query all tasks

    tasks = db_session.scalars(select(TaskORM).where(TaskORM.type == TaskType.PROGRAMMING)).all()

    path_to_file_map = {}

    def fix_file(old_file: dict, lookup=True):
        path = old_file.get("name")
        if path in path_to_file_map and lookup:
            return path_to_file_map[path]

        new_file = old_file.copy()
        if not new_file.get("id"):
            new_file["id"] = str(uuid4())
        if not new_file.get("path"):
            new_file["path"] = path

        path_to_file_map[new_file["path"]] = new_file
        return new_file

    def is_probably_file(data):
        """This is a guess. I assume that if the data has a key 'data' and the value is a dictionary with a key 'name', then it is a file."""
        return type(data) == dict and "name" in data

    corrected = 0
    has_files_field = 0
    has_something_looking_updated = 0
    had_no_files = 0
    for task in tasks:
        has_files = False
        other_fields = copy.deepcopy(task.other_fields)
        # We do a brief check on the task. If the files field isn't empty or if the required_inputs field already has "path" instead of "name",
        # we skip the task as the format seems to have already been updated.
        files = other_fields.get("files", [])
        if files:
            has_files_field += 1
            continue

        has_updated_file_format = False
        for required_input in other_fields.get("required_inputs"):
            if (
                "data" in required_input
                and type(required_input["data"]) == dict
                and "path" in required_input["data"]
            ):
                has_updated_file_format = True
                has_files = True
                has_something_looking_updated += 1
                break

        if has_updated_file_format:
            continue

        # Manipulate task.other_fields
        # files
        # required_file_inputs
        for required_input in other_fields.get("required_inputs"):
            # If data is a file, transform it.
            if (
                "data" in required_input
                and type(required_input["data"]) == dict
                and "name" in required_input["data"]
            ):
                has_files = True
                required_input["data"] = fix_file(required_input["data"])

        # For files field in tasks - populate with existing files
        testcases = other_fields.get("testcases")
        assert type(testcases) == list, "Testcases should be a list"
        for testcase in testcases:
            for node in testcase.get("nodes"):
                assert type(node) == dict, "Node should be a dictionary"
                if node["type"] != "INPUT_STEP":
                    continue
                for output in node.get("outputs"):
                    if is_probably_file(output["data"]):
                        output["data"] = fix_file(output["data"])
                        files.append(output["data"])

        other_fields["files"] = files
        rich_console.print(task)
        if has_files:
            corrected += 1
            task.other_fields = other_fields
            db_session.add(task)
        else:
            had_no_files += 1

    rich_console.print(f"Corrected {corrected} out of {len(tasks)} tasks")
    rich_console.print(f"Skipped {has_files_field} tasks with non-empty files field.")
    rich_console.print(f"Skipped {has_something_looking_updated} tasks with updated file format")
    rich_console.print(f"Skipped {had_no_files} tasks with no files")

    # Query all TaskAttempts
    task_attempts = db_session.scalars(
        select(TaskAttemptORM).where(TaskAttemptORM.task_type == TaskType.PROGRAMMING)
    ).all()

    corrected_task_attempts = 0
    for task_attempt in task_attempts:
        assert type(task_attempt.other_fields.get("user_input")) == list, (
            "TaskAttempt.other_fields['user_input'] should be a list"
            + repr(task_attempt.other_fields.get("user_input"))
        )

        other_fields = copy.deepcopy(task_attempt.other_fields)
        for user_input in other_fields.get("user_input"):
            if is_probably_file(user_input["data"]) and "path" not in user_input["data"]:
                user_input["data"] = fix_file(user_input["data"], lookup=False)
                corrected_task_attempts += 1
                task_attempt.other_fields = other_fields
                db_session.add(task_attempt)

    rich_console.print(
        f"Corrected {corrected_task_attempts} out of {len(task_attempts)} task attempts"
    )
    db_session.commit()


if __name__ == "__main__":
    app()
