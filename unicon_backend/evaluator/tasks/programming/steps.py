import abc
import logging
from collections import deque
from collections.abc import MutableSequence, Sequence
from enum import Enum, StrEnum
from functools import cached_property
from typing import TYPE_CHECKING, Any, ClassVar, Self, cast

import libcst as cst
from pydantic import PrivateAttr, model_validator

from unicon_backend.evaluator.tasks.programming.artifact import File, PrimitiveData
from unicon_backend.evaluator.tasks.programming.transforms import hoist_imports
from unicon_backend.lib.common import CustomBaseModel, CustomSQLModel
from unicon_backend.lib.graph import Graph, GraphEdge, GraphNode, NodeSocket
from unicon_backend.lib.helpers import partition

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)

type SocketId = str
type ProgramVariable = cst.Name
type ProgramFragment = Sequence[
    cst.SimpleStatementLine | cst.BaseCompoundStatement | cst.BaseSmallStatement
]
type ProgramBody = MutableSequence[cst.SimpleStatementLine | cst.BaseCompoundStatement]

# A program can be made up of sub programs, especially with subgraphs
Program = cst.Module


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


class StepType(str, Enum):
    PY_RUN_FUNCTION = "PY_RUN_FUNCTION_STEP"
    OBJECT_ACCESS = "OBJECT_ACCESS_STEP"

    # I/O Operations
    INPUT = "INPUT_STEP"
    OUTPUT = "OUTPUT_STEP"

    # Control Flow Operations
    LOOP = "LOOP_STEP"
    IF_ELSE = "IF_ELSE_STEP"

    # Comparison Operations
    STRING_MATCH = "STRING_MATCH_STEP"


class SocketType(str, Enum):
    DATA = "DATA"
    CONTROL = "CONTROL"


class SocketDir(str, Enum):
    IN = "IN"
    OUT = "OUT"


class StepSocket(NodeSocket[str]):
    type: SocketType
    direction: SocketDir

    # User facing name of the socket
    label: str

    # The data that the socket holds
    data: PrimitiveData | File | None = None

    @property
    def alias(self) -> str:
        return ".".join([self.type.value, self.direction.value, self.label])


Range = tuple[int, int]


class Step[SocketT: StepSocket](
    CustomBaseModel, GraphNode[str, SocketT], abc.ABC, polymorphic=True
):
    type: StepType

    _debug: bool = False

    # Socket aliases that are used to refer to subgraph sockets
    subgraph_socket_aliases: ClassVar[set[str]] = set()
    # The required number of data sockets
    required_control_io: ClassVar[tuple[Range, Range]] = ((-1, 1), (-1, 1))
    # The required number of control sockets
    # The maximum number by default is 1 for both input and output control sockets (CONTROL.IN and CONTROL.OUT)
    required_data_io: ClassVar[tuple[Range, Range]] = ((-1, -1), (-1, -1))

    @model_validator(mode="after")
    def check_required_inputs_and_outputs(self) -> Self:
        def satisfies_required(expected: Range, got: int) -> bool:
            match expected:
                case (-1, -1):
                    return True
                case (-1, upper_bound):
                    return got <= upper_bound
                case (lower_bound, -1):
                    return got >= lower_bound
                case (lower_bound, upper_bound):
                    return lower_bound <= got <= upper_bound
                case _:
                    return False  # This should never happen

        is_data_socket: Callable[[StepSocket], bool] = lambda socket: socket.type == SocketType.DATA

        num_data_in, num_control_in = list(map(len, partition(is_data_socket, self.inputs)))
        num_data_out, num_control_out = list(map(len, partition(is_data_socket, self.outputs)))

        for got, expected, label in zip(
            (num_data_in, num_data_out, num_control_in, num_control_out),
            self.required_data_io + self.required_control_io,
            ("data input", "data output", "control input", "control output"),
            strict=True,
        ):
            if not satisfies_required(expected, got):
                raise ValueError(f"Step {self.id} requires {expected} {label} sockets, found {got}")

        return self

    @cached_property
    def data_in(self) -> Sequence[SocketT]:
        return [socket for socket in self.inputs if socket.type == SocketType.DATA]

    @cached_property
    def data_out(self) -> Sequence[SocketT]:
        return [socket for socket in self.outputs if socket.type == SocketType.DATA]

    @cached_property
    def alias_map(self) -> dict[str, SocketT]:
        return {socket.alias: socket for socket in self.inputs + self.outputs}

    def run_subgraph(self, subgraph_socket_alias: str, graph: "ComputeGraph") -> Program:
        assert subgraph_socket_alias in self.subgraph_socket_aliases
        return graph.run(
            debug=self._debug, node_ids=self._get_subgraph_node_ids(subgraph_socket_alias, graph)
        )

    def get_all_subgraph_node_ids(self, graph: "ComputeGraph") -> set[str]:
        """Returns ids of nodes that part of a subgraph"""
        subgraph_node_ids: set[str] = set()
        for socket_alias in self.subgraph_socket_aliases:
            socket_id: str = self.alias_map[socket_alias].id
            subgraph_node_ids |= self._get_subgraph_node_ids(socket_id, graph)

        return subgraph_node_ids

    def _get_subgraph_node_ids(self, subgraph_socket_id: str, graph: "ComputeGraph") -> set[str]:
        subgraph_socket = self.get_socket(subgraph_socket_id)
        assert subgraph_socket is not None

        connected_node_ids = graph.get_connected_nodes(self.id, subgraph_socket_id)
        # NOTE: Assumes that there is only one edge connected to the subgraph socket
        if (start_node_id := connected_node_ids[0] if connected_node_ids else None) is None:
            # If no subgraph start node is found, then the subgraph is empty
            # This can happen if the a step allows an empty subgraph - we defer the check to the step
            return set()

        subgraph_node_ids: set[str] = set()
        bfs_queue: deque[str] = deque([start_node_id])
        while len(bfs_queue):
            if (frontier_node_id := bfs_queue.popleft()) in subgraph_node_ids:
                continue

            subgraph_node_ids.add(frontier_node_id)
            for out_edge in graph.out_edges_index[frontier_node_id]:
                if graph.link_type(out_edge) == SocketType.CONTROL:
                    bfs_queue.append(graph.node_index[out_edge.to_node_id].id)

            for in_edge in graph.in_edges_index[frontier_node_id]:
                if graph.link_type(in_edge) == SocketType.CONTROL:
                    bfs_queue.append(graph.node_index[in_edge.from_node_id].id)

        return subgraph_node_ids

    @abc.abstractmethod
    def run(
        self,
        graph: "ComputeGraph",
        in_vars: dict[SocketId, ProgramVariable],
        in_files: dict[SocketId, File],
    ) -> ProgramFragment: ...


class InputStep(Step[StepSocket]):
    required_data_io: ClassVar[tuple[Range, Range]] = ((0, 0), (1, -1))

    is_user: bool = False  # Whether the input is provided by the user

    @model_validator(mode="after")
    def check_non_empty_data_outputs(self) -> Self:
        if (
            not self.is_user
            and (empty_socket_ids := [socket.id for socket in self.data_out if socket.data is None])
            is None
        ):
            raise ValueError(f"Missing data for output sockets {','.join(empty_socket_ids)}")
        return self

    def run(self, graph: "ComputeGraph", *_) -> ProgramFragment:
        def _parse(data: str | int | float | bool) -> cst.BaseExpression:
            return cst.parse_expression(
                repr(data)
                if not isinstance(data, str)
                else (f'"{data}"' if not data.startswith(graph.VAR_PREFIX) else data)
            )

        program = []
        # If the input is a `File`, we skip the serialization and just pass the file object
        # directly to the next step. This is handled by the `ComputeGraph` class
        for socket in filter(lambda s: isinstance(s.data, PrimitiveData), self.data_out):
            program.append(
                cst.Assign(
                    targets=[cst.AssignTarget(graph.get_link_var(self, socket))],
                    value=_parse(cast(PrimitiveData, socket.data)),
                )
            )

        return program


class Operator(StrEnum):
    LESS_THAN = "<"
    EQUAL = "="
    GREATER_THAN = ">"


class Comparison(CustomSQLModel):
    operator: Operator
    value: Any

    @model_validator(mode="after")
    def check_value_type(self) -> Self:
        """For < and >, check the operator can be compared (i.e. primitive)"""
        if self.operator == Operator.EQUAL:
            return self
        if not isinstance(self.value, PrimitiveData):
            raise ValueError(f"Invalid comparison value {self.value} for operator {self.operator}")
        return self

    def compare(self, actual_value: Any):
        try:
            match self.operator:
                case Operator.EQUAL:
                    return actual_value == self.value
                case Operator.LESS_THAN:
                    return actual_value < self.value
                case Operator.GREATER_THAN:
                    return actual_value > self.value
                case _:
                    return False
        except:
            # if there was an exception, the type returned was incorrect.
            # so return False.
            return False  # noqa: B012


class OutputSocket(StepSocket):
    comparison: Comparison | None = None
    """Comparison to be made with the output of the socket. Optional."""
    public: bool = True
    """Whether output of the socket should be shown to less priviledged users."""


class OutputStep(Step[OutputSocket]):
    required_data_io: ClassVar[tuple[Range, Range]] = ((1, -1), (0, 0))

    def run(
        self, _graph: "ComputeGraph", in_vars: dict[SocketId, ProgramVariable], *_
    ) -> ProgramFragment:
        result_dict = cst.Dict(
            [
                cst.DictElement(key=cst.SimpleString(repr(socket.label)), value=in_vars[socket.id])
                for socket in self.data_in
            ]
        )
        return [
            cst.Import([cst.ImportAlias(name=cst.Name("json"))]),
            cst.Expr(
                cst.Call(
                    func=cst.Name("print"),
                    args=[
                        cst.Arg(
                            cst.Call(
                                func=cst.Attribute(value=cst.Name("json"), attr=cst.Name("dumps")),
                                args=[cst.Arg(result_dict)],
                            )
                        )
                    ],
                )
            ),
        ]


class StringMatchStep(Step[StepSocket]):
    required_data_io: ClassVar[tuple[Range, Range]] = ((2, 2), (1, 1))

    def run(
        self, graph: "ComputeGraph", in_vars: dict[SocketId, ProgramVariable], *_
    ) -> ProgramFragment:
        match_result_socket, [match_op_1, match_op_2] = self.data_out[0], self.data_in
        str_cast = lambda var: cst.Call(cst.Name("str"), args=[cst.Arg(var)])
        return [
            cst.Assign(
                targets=[cst.AssignTarget(graph.get_link_var(self, match_result_socket))],
                value=cst.Comparison(
                    left=str_cast(in_vars[match_op_1.id]),
                    comparisons=[
                        cst.ComparisonTarget(cst.Equal(), str_cast(in_vars[match_op_2.id]))
                    ],
                ),
            )
        ]


class ObjectAccessStep(Step[StepSocket]):
    """
    A step to retrieve a value from a dictionary.
    To use this step, the user must provide the key value to access the dictionary.
    """

    required_data_io: ClassVar[tuple[Range, Range]] = ((1, 1), (1, 1))

    key: str

    def run(
        self, graph: "ComputeGraph", in_vars: dict[SocketId, ProgramVariable], *_
    ) -> ProgramFragment:
        return [
            cst.Assign(
                targets=[cst.AssignTarget(graph.get_link_var(self, self.data_out[0]))],
                value=cst.Subscript(
                    value=in_vars[self.data_in[0].id],
                    slice=[cst.SubscriptElement(cst.Index(cst.SimpleString(repr(self.key))))],
                ),
            )
        ]


class PyRunFunctionStep(Step[StepSocket]):
    required_data_io: ClassVar[tuple[Range, Range]] = ((1, -1), (1, 2))

    _file_socket_alias: ClassVar[str] = "DATA.IN.FILE"
    _error_socket_alias: ClassVar[str] = "DATA.OUT.ERROR"

    function_identifier: str
    allow_error: bool = False

    @model_validator(mode="after")
    def check_module_file_input(self) -> Self:
        if not any(socket.alias == self._file_socket_alias for socket in self.data_in):
            raise ValueError("No module file input provided")
        return self

    @model_validator(mode="after")
    def check_error_socket(self) -> Self:
        data_out_socket_count = len(self.data_out)
        expected_sockets = 2 if self.allow_error else 1

        if data_out_socket_count != expected_sockets:
            raise ValueError(
                f"Expected {expected_sockets} output socket(s) when `allow_error` is {self.allow_error}"
            )

        has_error_socket = any(socket.alias == self._error_socket_alias for socket in self.data_out)
        if self.allow_error and not has_error_socket:
            raise ValueError(f"Missing error output socket {self._error_socket_alias}")
        if not self.allow_error and has_error_socket:
            raise ValueError(f"Unexpected error output socket {self._error_socket_alias}")

        return self

    @property
    def arg_sockets(self) -> Sequence[StepSocket]:
        sockets = [socket for socket in self.data_in if socket.label.startswith("ARG.")]
        return sorted(sockets, key=lambda socket: int(socket.label.split(".", 2)[1]))

    @property
    def kwarg_sockets(self) -> Sequence[StepSocket]:
        return [socket for socket in self.data_in if socket.label.startswith("KWARG.")]

    def run(
        self,
        graph: "ComputeGraph",
        in_vars: dict[SocketId, ProgramVariable],
        in_files: dict[SocketId, File],
    ) -> ProgramFragment:
        # Get the input file that we are running the function from
        file_socket_id = self.alias_map[self._file_socket_alias].id
        program_file: File | None = in_files.get(file_socket_id)
        if program_file is None:
            raise ValueError("No program file provided")

        # NOTE: Assume that there can only be one edge connected to the file input socket. This should ideally be validated.
        from_file_node_id = [
            edge.from_node_id
            for edge in graph.in_edges_index[self.id]
            if edge.to_socket_id == file_socket_id
        ][0]
        from_file_node = cast(InputStep, graph.node_index[from_file_node_id])
        is_user_provided_file: bool = from_file_node.is_user

        # NOTE: Assume that the program file is always a Python file
        module_name_str = program_file.name.split(".py")[0]

        func_name = cst.Name(self.function_identifier)
        args = [cst.Arg(in_vars[socket.id]) for socket in self.arg_sockets]
        kwargs = [
            cst.Arg(in_vars[socket.id], keyword=cst.Name(socket.label.split(".", 1)[1]))
            for socket in self.kwarg_sockets
        ]

        if error_socket := self.alias_map.get(self._error_socket_alias):
            out_var = graph.get_link_var(
                self, [socket for socket in self.data_out if socket.id != error_socket.id][0]
            )
            error_var = graph.get_link_var(self, error_socket)
        else:
            out_var = graph.get_link_var(self, self.data_out[0])
            error_var = cst.Name("_")

        return (
            [
                cst.Assign(
                    [cst.AssignTarget(cst.Tuple([cst.Element(out_var), cst.Element(error_var)]))],
                    cst.Call(
                        cst.Name("call_function_safe"),
                        [
                            cst.Arg(cst.SimpleString(repr(module_name_str))),
                            cst.Arg(cst.SimpleString(repr(self.function_identifier))),
                            cst.Arg(cst.Name(repr(self.allow_error))),
                            *args,
                            *kwargs,
                        ],
                    ),
                )
            ]
            if is_user_provided_file
            else [
                cst.ImportFrom(cst.Name(module_name_str), [cst.ImportAlias(func_name)]),
                cst.Assign([cst.AssignTarget(out_var)], cst.Call(func_name, args + kwargs)),
            ]
        )


class LoopStep(Step[StepSocket]):
    _pred_socket_alias: ClassVar[str] = "CONTROL.IN.PREDICATE"
    _body_socket_alias: ClassVar[str] = "CONTROL.OUT.BODY"

    subgraph_socket_aliases: ClassVar[set[str]] = {_pred_socket_alias, _body_socket_alias}
    required_control_io: ClassVar[tuple[Range, Range]] = ((1, 2), (1, 2))
    required_data_io: ClassVar[tuple[Range, Range]] = ((0, 0), (0, 0))

    def run(
        self, graph: "ComputeGraph", in_vars: dict[SocketId, ProgramVariable], *_
    ) -> ProgramFragment:
        return [
            cst.While(
                test=cst.Name("True"),
                body=cst.IndentedBlock(
                    [
                        *self.run_subgraph(self._pred_socket_alias, graph).body,
                        cst.If(
                            test=in_vars[self.alias_map[self._pred_socket_alias].id],
                            body=cst.SimpleStatementSuite([cst.Break()]),
                        ),
                        *self.run_subgraph(self._body_socket_alias, graph).body,
                    ]
                ),
            )
        ]


class IfElseStep(Step[StepSocket]):
    _pred_socket_alias: ClassVar[str] = "CONTROL.IN.PREDICATE"
    _if_socket_alias: ClassVar[str] = "CONTROL.OUT.IF"
    _else_socket_alias: ClassVar[str] = "CONTROL.OUT.ELSE"

    subgraph_socket_aliases: ClassVar[set[str]] = {
        _pred_socket_alias,
        _if_socket_alias,
        _else_socket_alias,
    }
    required_control_io: ClassVar[tuple[Range, Range]] = ((1, 2), (2, 3))
    required_data_io: ClassVar[tuple[Range, Range]] = ((0, 0), (0, 0))

    def run(
        self, graph: "ComputeGraph", in_vars: dict[SocketId, ProgramVariable], *_
    ) -> ProgramFragment:
        return [
            *self.run_subgraph(self._pred_socket_alias, graph).body,
            cst.If(
                test=in_vars[self.alias_map[self._pred_socket_alias].id],
                body=cst.IndentedBlock([*self.run_subgraph(self._if_socket_alias, graph).body]),
                orelse=cst.Else(
                    cst.IndentedBlock([*self.run_subgraph(self._else_socket_alias, graph).body])
                ),
            ),
        ]


StepClasses = (
    OutputStep
    | InputStep
    | PyRunFunctionStep
    | LoopStep
    | IfElseStep
    | StringMatchStep
    | ObjectAccessStep
)


class ComputeGraph(Graph[StepClasses, GraphEdge[str]]):  # type: ignore
    VAR_PREFIX: ClassVar[str] = "var_"
    _var_id: int = PrivateAttr(default=0)
    _var_id_map: dict[str, int] = PrivateAttr(default={})

    def _get_uniq_var_id(self, node_id: str) -> int:
        if (var_id := self._var_id_map.get(node_id)) is not None:
            return var_id
        self._var_id += 1
        self._var_id_map[node_id] = self._var_id
        return self._var_id

    def get_link_var(self, from_node: Step, from_socket: StepSocket) -> ProgramVariable:
        return cst.Name(
            f"{self.VAR_PREFIX}{self._get_uniq_var_id(from_node.id)}_{from_node.type.value}_{from_socket.label}"
        )

    def link_type(self, edge: GraphEdge[str]) -> SocketType:
        def get_step_socket(step_id: str, socket_id: str) -> StepSocket | None:
            node = self.node_index.get(step_id)
            return node.get_socket(socket_id) if node else None

        from_socket = get_step_socket(edge.from_node_id, edge.from_socket_id)
        to_socket = get_step_socket(edge.to_node_id, edge.to_socket_id)
        assert from_socket is not None and to_socket is not None

        if from_socket.type == to_socket.type and from_socket.direction != to_socket.direction:
            return from_socket.type

        raise ValueError(f"Invalid link between {from_socket.id} and {to_socket.id}")

    def run(self, debug: bool = True, node_ids: set[str] | None = None) -> Program:
        """
        Run the compute graph with the given user input.

        Args:
            debug (bool, optional): Whether to include debug statements in the program. Defaults to True.
            node_ids (set[int], optional): The node ids to run. Defaults to None.

        Returns:
            Program: The program that is generated from the compute graph
        """
        # If node_ids is provided, we exclude all other nodes
        # This is useful when we want to run only a subset of the compute graph
        node_ids_to_exclude: set[str] = set()
        if node_ids is not None:
            node_ids_to_exclude = set(self.node_index.keys()) - node_ids

        subgraph_node_ids: set[str] = set()
        for node in filter(lambda n: n.id not in node_ids_to_exclude, self.nodes):
            subgraph_node_ids |= node.get_all_subgraph_node_ids(self)

        # We do not consider subgraph nodes when determining the flow order (topological order) of the main compute graph
        # The responsibility of determining the order of subgraph nodes is deferred to the step itself
        topo_order = self.topological_sort(subgraph_node_ids | node_ids_to_exclude)

        program_body: ProgramBody = []
        for curr_node in topo_order:
            # Output of a step will be stored in a variable in the format `var_{step_id}_{socket_id}`
            # It is assumed that every step will always output the same number of values as the number of output sockets
            # As such, all we need to do is to pass in the correct variables to the next step
            in_vars: dict[SocketId, ProgramVariable] = {}
            in_files: dict[SocketId, File] = {}

            for in_edge in self.in_edges_index[curr_node.id]:
                from_n = self.node_index[in_edge.from_node_id]
                from_s_lst = [out_ for out_ in from_n.outputs if out_.id == in_edge.from_socket_id]
                if (from_s := from_s_lst[0] if from_s_lst else None) is None:
                    continue

                if (to_s := curr_node.get_socket(in_edge.to_socket_id)) is None:
                    continue

                if from_s.data is not None and isinstance(from_s.data, File):
                    # NOTE: File objects are passed directly to the next step and not serialized as a variable
                    in_files[to_s.id] = from_s.data
                else:
                    in_vars[to_s.id] = self.get_link_var(from_n, from_s)

            curr_node._debug = debug
            program_body.extend(assemble_fragment(curr_node.run(self, in_vars, in_files)))

        return hoist_imports(cst.Module(body=program_body))
