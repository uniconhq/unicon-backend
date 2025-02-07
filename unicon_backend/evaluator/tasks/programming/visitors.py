import libcst as cst
from pydantic import BaseModel


class ParsedFunction(BaseModel):
    name: str
    args: list[str]
    kwargs: list[str]
    star_args: bool
    star_kwargs: bool


class TypingCollector(cst.CSTVisitor):
    def __init__(self):
        self.stack: list[str] = []
        self.results: list[ParsedFunction] = []

    def visit_ClassDef(self, node: cst.ClassDef) -> bool | None:
        self.stack.append(node.name.value)

    def leave_ClassDef(self, _: cst.ClassDef) -> None:
        self.stack.pop()

    def visit_FunctionDef(self, node: cst.FunctionDef) -> bool | None:
        function_name = node.name.value
        is_method = len(self.stack) > 0
        self.stack.append(function_name)

        name = ".".join(
            [n for n in self.stack][:-1]
            # If it's a Class's __init__ method, use the Class directly as the function name
            + ([function_name] if not is_method or function_name != "__init__" else [])
        )

        # Remove any past declaration of the function, since this would overwrite it
        self.results = [result for result in self.results if result.name != name]

        self.results.append(
            ParsedFunction(
                name=name,
                args=[param.name.value for param in node.params.params],
                kwargs=[param.name.value for param in node.params.kwonly_params],
                star_args=isinstance(node.params.star_arg, cst.Param),
                star_kwargs=node.params.star_kwarg is not None,
            )
        )
        # Stop traversal (don't support inner functions)
        return False

    def leave_FunctionDef(self, _: cst.FunctionDef) -> None:
        self.stack.pop()
