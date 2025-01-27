from http import HTTPStatus
from typing import Annotated

import libcst
from fastapi import Depends, HTTPException
from sqlalchemy.orm import selectinload
from sqlmodel import Session, col, select

from unicon_backend.dependencies.common import get_db_session
from unicon_backend.models.problem import ProblemORM, TaskORM
from unicon_backend.schemas.problem import ParsedFunction


def get_problem_by_id(
    id: int,
    db_session: Annotated[Session, Depends(get_db_session)],
) -> ProblemORM:
    if (
        problem_orm := db_session.scalar(
            select(ProblemORM)
            .where(ProblemORM.id == id)
            .options(selectinload(ProblemORM.tasks.and_(col(TaskORM.updated_version_id) == None)))
        )
    ) is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Problem definition not found!")
    return problem_orm


def parse_python_functions_from_file_content(content: str) -> list[ParsedFunction]:
    try:
        module = libcst.parse_module(content)
        functions = [node for node in module.body if isinstance(node, libcst.FunctionDef)]
        function_names = set()
        results = []
        for function in functions[::-1]:
            # In the case of duplicate function names, consider the last function and ignore preceding ones.
            if function.name.value in function_names:
                continue
            function_names.add(function.name.value)

            results.append(
                ParsedFunction(
                    name=function.name.value,
                    args=[param.name.value for param in function.params.params],
                    kwargs=[param.name.value for param in function.params.kwonly_params],
                    star_args=isinstance(function.params.star_arg, libcst.Param),
                    star_kwargs=function.params.star_kwarg is not None,
                )
            )

        results = results[::-1]
        return results
    except libcst.ParserSyntaxError as e:
        raise HTTPException(HTTPStatus.BAD_REQUEST, "Invalid Python code!") from e
