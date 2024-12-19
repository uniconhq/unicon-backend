import abc
import logging
from collections import deque
from collections.abc import MutableSequence, Sequence
from enum import Enum, StrEnum
from functools import cached_property
from typing import TYPE_CHECKING, Any, ClassVar, Optional, Self

import libcst as cst
from pydantic import model_validator

from unicon_backend.evaluator.tasks.programming.artifact import File, PrimitiveData
from unicon_backend.evaluator.tasks.programming.transforms import hoist_imports
from unicon_backend.lib.common import CustomBaseModel, CustomSQLModel
from unicon_backend.lib.graph import Graph, GraphNode, NodeSocket
from unicon_backend.lib.helpers import partition
from unicon_backend.runner import ProgramResult

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


class StepSocket(NodeSocket):
    """
    A socket that is used to connect steps to each other.

    Socket ID Format: <TYPE>.<NAME>.<INDEX>
    - <NAME>.<INDEX> is optional and is used to differentiate between multiple sockets of the same type
        - Collectively, <NAME>.<INDEX> is referred to as the "label"

    There can be 2 types of sockets:

    1. Control Sockets: Used to control the flow of the program
        - e.g. CONTROL.<NAME>.<INDEX>
    2. Data Sockets: Used to pass data between steps
        - e.g. DATA.<NAME>.<INDEX>
    """

    # The data that the socket holds
    data: PrimitiveData | File | None = None

    @cached_property
    def type(self) -> str:
        return self.id.split(".")[0]

    @cached_property
    def label(self) -> str:
        return self.id.split(".", 2)[-1]


Range = tuple[int, int]


class Step(CustomBaseModel, GraphNode[StepSocket], abc.ABC, polymorphic=True):
    id: int
    type: StepType

    _debug: bool = False

    # Socket IDs that are used to connect to the subgraph of a `Step`
    subgraph_socket_ids: ClassVar[set[str]] = set()
    # The required number of data sockets
    required_control_io: ClassVar[tuple[Range, Range]] = ((-1, 1), (-1, 1))
    # The required number of control sockets
    # The maximum number by default is 1 for both input and output control sockets (CONTROL.IN and CONTROL.OUT)
    required_data_io: ClassVar[tuple[Range, Range]] = ((-1, -1), (-1, -1))

    @model_validator(mode="after")
    def check_required_inputs_and_outputs(self) -> Self:
        def satisfies_required(expected: Range, got: int) -> bool:
            # NOTE: -1 indicates that there is no limit
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
                    # This should never happen
                    return False

        is_data_socket: Callable[[StepSocket], bool] = lambda socket: socket.type == "DATA"

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
    def control_in(self) -> Sequence[StepSocket]:
        return [socket for socket in self.inputs if socket.type == "CONTROL"]

    @cached_property
    def control_out(self) -> Sequence[StepSocket]:
        return [socket for socket in self.outputs if socket.type == "CONTROL"]

    @cached_property
    def data_in(self) -> Sequence[StepSocket]:
        return [socket for socket in self.inputs if socket.type == "DATA"]

    @cached_property
    def data_out(self) -> Sequence[StepSocket]:
        return [socket for socket in self.outputs if socket.type == "DATA"]

    def get_subgraph_node_ids(self, subgraph_socket_id: str, graph: "ComputeGraph") -> set[int]:
        subgraph_socket: StepSocket | None = self.get_socket(subgraph_socket_id)
        if subgraph_socket is None:
            raise ValueError(f"Subgraph socket {subgraph_socket_id} not found!")

        subgraph_start_node: Step | None = None

        # Check both incoming and outgoing edges to find the subgraph start node
        # NOTE: Assumes that there is only one edge connected to the subgraph socket

        for out_edge in graph.out_edges_index[self.id]:
            if out_edge.from_socket_id == subgraph_socket.id:
                subgraph_start_node = graph.node_index[out_edge.to_node_id]
                break

        for in_edge in graph.in_edges_index[self.id]:
            if in_edge.to_socket_id == subgraph_socket.id:
                subgraph_start_node = graph.node_index[in_edge.from_node_id]
                break

        if subgraph_start_node is None:
            # If no subgraph start node is found, then the subgraph is empty
            # This can happen if the a step allows an empty subgraph - we defer the check to the step
            return set()

        subgraph_node_ids: set[int] = set()
        bfs_queue: deque[Step] = deque([subgraph_start_node])
        while len(bfs_queue):
            frontier_node = bfs_queue.popleft()
            if frontier_node.id in subgraph_node_ids:
                continue

            subgraph_node_ids.add(frontier_node.id)
            for out_edge in graph.out_edges_index[frontier_node.id]:
                from_socket_id = out_edge.from_socket_id
                to_socket_id = out_edge.to_socket_id

                if from_socket_id == "CONTROL.OUT" and to_socket_id == "CONTROL.IN":
                    bfs_queue.append(graph.node_index[out_edge.to_node_id])

            for in_edge in graph.in_edges_index[frontier_node.id]:
                to_socket_id = in_edge.to_socket_id
                from_socket_id = in_edge.from_socket_id

                if to_socket_id == "CONTROL.IN" and from_socket_id == "CONTROL.OUT":
                    bfs_queue.append(graph.node_index[out_edge.from_node_id])

        return subgraph_node_ids

    def get_all_subgraph_node_ids(self, graph: "ComputeGraph") -> set[int]:
        subgraph_node_ids: set[int] = set()

        for socket_id in self.subgraph_socket_ids:
            subgraph_node_ids |= self.get_subgraph_node_ids(socket_id, graph)

        return subgraph_node_ids

    def run_subgraph(self, subgraph_socket_id: str, graph: "ComputeGraph") -> Program:
        return graph.run(
            debug=self._debug, node_ids=self.get_subgraph_node_ids(subgraph_socket_id, graph)
        )

    def get_output_variable(self, output: SocketId) -> ProgramVariable:
        return cst.Name(f"var_{self.id}_{output}".replace(".", "_"))

    @abc.abstractmethod
    def run(
        self,
        var_inputs: dict[SocketId, ProgramVariable],
        file_inputs: dict[SocketId, File],
        graph: "ComputeGraph",
    ) -> ProgramFragment: ...


class InputStep(Step):
    required_data_io: ClassVar[tuple[Range, Range]] = ((0, 0), (1, -1))

    @model_validator(mode="after")
    def check_non_empty_data_outputs(self) -> Self:
        for socket in self.data_out:
            if socket.data is None:
                raise ValueError(f"Missing data for output socket {socket.id}")
        return self

    def run(self, *_) -> ProgramFragment:
        def _parse(data: str | int | float | bool) -> cst.BaseExpression:
            # TODO: Better handle of variables vs strings
            data_repr: str = (
                repr(data)
                if not isinstance(data, str)
                else (f'"{data}"' if not data.startswith("var_") else data)
            )
            return cst.parse_expression(data_repr)

        program = []
        for socket in self.data_out:
            if isinstance(socket.data, File):
                # If the input is a `File`, we skip the serialization and just pass the file object
                # directly to the next step. This is handled by the `ComputeGraph` class
                continue
            elif isinstance(socket.data, PrimitiveData):
                program.append(
                    cst.Assign(
                        targets=[cst.AssignTarget(self.get_output_variable(socket.id))],
                        value=_parse(socket.data),
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


class SocketResult(CustomSQLModel):
    """
    This class is used to store whether the result of an output socket is right or wrong.
    Note that whether or not to show this information (public) and other variables should be derived from data in Testcase.
    """

    id: str
    value: Any
    correct: bool


class ProcessedResult(ProgramResult):
    results: list[SocketResult] | None = None


class OutputSocketConfig(CustomSQLModel):
    id: str
    """ID of the socket."""
    label: str | None = ""
    """User facing label of the socket. Optional."""
    comparison: Comparison | None
    """Comparison to be made with the output of the socket. Optional."""
    public: bool = True
    """Whether output of the socket should be shown to less priviledged users."""

    @model_validator(mode="after")
    def set_default_label(self) -> Self:
        if self.label == "":
            self.label = self.id
        return self


class OutputStep(Step):
    required_data_io: ClassVar[tuple[Range, Range]] = ((1, -1), (0, 0))

    socket_metadata: list[OutputSocketConfig]

    @model_validator(mode="after")
    def check_all_sockets_have_config(self) -> Self:
        socket_ids = {socket.id for socket in self.data_in}
        metadata_socket_ids = {socket.id for socket in self.socket_metadata}

        if len(metadata_socket_ids) != len(self.socket_metadata):
            raise ValueError("Duplicate socket metadata configuration")

        if not socket_ids == metadata_socket_ids:
            raise ValueError(
                f"Socket ids differ: {metadata_socket_ids - socket_ids}, {socket_ids - metadata_socket_ids}"
            )
        return self

    def run(self, var_inputs: dict[SocketId, ProgramVariable], *_) -> ProgramFragment:
        result_dict = cst.Dict(
            [
                cst.DictElement(key=cst.SimpleString(repr(socket.id)), value=var_inputs[socket.id])
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


class StringMatchStep(Step):
    required_data_io: ClassVar[tuple[Range, Range]] = ((2, 2), (1, 1))

    def run(self, var_inputs: dict[SocketId, ProgramVariable], *_) -> ProgramFragment:
        return [
            cst.Assign(
                targets=[cst.AssignTarget(self.get_output_variable(self.outputs[0].id))],
                value=cst.Comparison(
                    left=cst.Call(cst.Name("str"), args=[cst.Arg(var_inputs[self.data_in[0].id])]),
                    comparisons=[
                        cst.ComparisonTarget(
                            cst.Equal(),
                            cst.Call(
                                cst.Name("str"), args=[cst.Arg(var_inputs[self.data_in[1].id])]
                            ),
                        )
                    ],
                ),
            )
        ]


class ObjectAccessStep(Step):
    """
    A step to retrieve a value from a dictionary.
    To use this step, the user must provide the key value to access the dictionary.
    """

    required_data_io: ClassVar[tuple[Range, Range]] = ((1, 1), (1, 1))

    key: str

    def run(self, var_inputs: dict[SocketId, ProgramVariable], *_) -> ProgramFragment:
        return [
            cst.Assign(
                targets=[cst.AssignTarget(self.get_output_variable(self.data_out[0].id))],
                value=cst.Subscript(
                    value=var_inputs[self.data_in[0].id],
                    slice=[cst.SubscriptElement(cst.Index(cst.SimpleString(repr(self.key))))],
                ),
            )
        ]


class PyRunFunctionStep(Step):
    """
    A step that runs a Python function.
    To use this step, the user must provide the function name and the arguments to the function via the input sockets.

    Socket Name Format:
    - DATA.IN.ARG.{index}.{name}: For positional arguments
    - DATA.IN.KWARG.{name}: For keyword arguments
    - DATA.IN.FILE: For the `File` object that contains the Python function
    """

    required_data_io: ClassVar[tuple[Range, Range]] = ((1, -1), (1, 2))

    _data_in_file_id: ClassVar[str] = "DATA.IN.FILE"

    function_identifier: str

    allow_error: bool = False
    _data_out_error_id: ClassVar[str] = "DATA.OUT.ERROR"

    @model_validator(mode="after")
    def check_module_file_input(self) -> Self:
        if not any(socket.label == "FILE" for socket in self.data_in):
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

        if self.allow_error and self._data_out_error_id not in [
            socket.id for socket in self.data_out
        ]:
            raise ValueError(f"Missing error output socket {self._data_out_error_id}")

        if not self.allow_error and self._data_out_error_id in [
            socket.id for socket in self.data_out
        ]:
            raise ValueError(f"Unexpected error output socket {self._data_out_error_id}")

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
        var_inputs: dict[SocketId, ProgramVariable],
        file_inputs: dict[SocketId, File],
        graph: "ComputeGraph",
    ) -> ProgramFragment:
        # Get the input file that we are running the function from
        program_file: File | None = file_inputs.get(self._data_in_file_id)
        if program_file is None:
            raise ValueError("No program file provided")

        # NOTE: Assume that there can only be one edge connected to the file input socket. This should ideally be validated.
        # NOTE: Assume that the user-provided input is always stored in the `Step` with id = 0
        is_user_provided_file: bool = [
            edge
            for edge in graph.in_edges_index[self.id]
            if edge.to_socket_id == self._data_in_file_id
        ][0].from_node_id == 0

        # NOTE: Assume that the program file is always a Python file
        module_name_str = program_file.name.split(".py")[0]

        func_name = cst.Name(self.function_identifier)
        args = [cst.Arg(var_inputs[socket.id]) for socket in self.arg_sockets]
        kwargs = [
            cst.Arg(var_inputs[socket.id], keyword=cst.Name(socket.label.split(".", 1)[1]))
            for socket in self.kwarg_sockets
        ]

        non_error_sockets = [
            socket for socket in self.data_out if socket.id != self._data_in_file_id
        ]
        output_var_name = self.get_output_variable(non_error_sockets[0].id)
        error_var_name = (
            self.get_output_variable(self._data_out_error_id) if self.allow_error else cst.Name("_")
        )

        return (
            [
                cst.Assign(
                    [
                        cst.AssignTarget(
                            cst.Tuple([cst.Element(output_var_name), cst.Element(error_var_name)])
                        )
                    ],
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
                cst.Assign([cst.AssignTarget(output_var_name)], cst.Call(func_name, args + kwargs)),
            ]
        )


class LoopStep(Step):
    _pred_socket_id: ClassVar[str] = "CONTROL.IN.PREDICATE"
    _body_socket_id: ClassVar[str] = "CONTROL.OUT.BODY"

    subgraph_socket_ids: ClassVar[set[str]] = {_pred_socket_id, _body_socket_id}
    required_control_io: ClassVar[tuple[Range, Range]] = ((1, 2), (1, 2))
    required_data_io: ClassVar[tuple[Range, Range]] = ((0, 0), (0, 0))

    def run(
        self, var_inputs: dict[SocketId, ProgramVariable], _, graph: "ComputeGraph"
    ) -> ProgramFragment:
        return [
            cst.While(
                test=cst.Name("True"),
                body=cst.IndentedBlock(
                    [
                        *self.run_subgraph(self._pred_socket_id, graph).body,
                        cst.If(
                            test=var_inputs[self._pred_socket_id],
                            body=cst.SimpleStatementSuite([cst.Break()]),
                        ),
                        *self.run_subgraph(self._body_socket_id, graph).body,
                    ]
                ),
            )
        ]


class IfElseStep(Step):
    _pred_socket_id: ClassVar[str] = "CONTROL.IN.PREDICATE"
    _if_socket_id: ClassVar[str] = "CONTROL.OUT.IF"
    _else_socket_id: ClassVar[str] = "CONTROL.OUT.ELSE"

    subgraph_socket_ids: ClassVar[set[str]] = {_pred_socket_id, _if_socket_id, _else_socket_id}
    required_control_io: ClassVar[tuple[Range, Range]] = ((1, 2), (2, 3))
    required_data_io: ClassVar[tuple[Range, Range]] = ((0, 0), (0, 0))

    def run(
        self, var_inputs: dict[SocketId, ProgramVariable], _, graph: "ComputeGraph"
    ) -> ProgramFragment:
        return [
            *self.run_subgraph(self._pred_socket_id, graph).body,
            cst.If(
                test=var_inputs[self._pred_socket_id],
                body=cst.IndentedBlock([*self.run_subgraph(self._if_socket_id, graph).body]),
                orelse=cst.Else(
                    cst.IndentedBlock([*self.run_subgraph(self._else_socket_id, graph).body])
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


class ComputeGraph(Graph[StepClasses]):
    def _create_link_variable(self, from_node: Step, from_socket: str) -> ProgramVariable:
        """
        Create a variable name for the output of a node. The variable name must be unique across all nodes and sockets.

        Args:
            from_node (Step): The node that is outputting the variable
            from_socket (str): The socket that the variable is outputting from
        """
        return from_node.get_output_variable(from_socket)

    def run(
        self,
        user_input_step: Optional["InputStep"] = None,
        debug: bool = True,
        node_ids: set[int] | None = None,
    ) -> Program:
        """
        Run the compute graph with the given user input.

        Args:
            user_input_step (InputStep, optional): The input step (id = 0) that contains the user input
            debug (bool, optional): Whether to include debug statements in the program. Defaults to True.
            node_ids (set[int], optional): The node ids to run. Defaults to None.

        Returns:
            Program: The program that is generated from the compute graph
        """
        # Add user input step (node) to compute graph
        if user_input_step is not None:
            self.nodes.append(user_input_step)

        # If node_ids is provided, we exclude all other nodes
        # This is useful when we want to run only a subset of the compute graph
        node_ids_to_exclude: set[int] = set()
        if node_ids is not None:
            node_ids_to_exclude = set(self.node_index.keys()) - node_ids

        subgraph_node_ids: set[int] = set()
        for node in self.nodes:
            if node.id not in node_ids_to_exclude:
                subgraph_node_ids |= node.get_all_subgraph_node_ids(self)

        # We do not consider subgraph nodes when determining the flow order (topological order) of the main compute graph
        # The responsibility of determining the order of subgraph nodes is deferred to the step itself
        topological_order: list[Step] = self.topological_sort(
            subgraph_node_ids | node_ids_to_exclude
        )

        program_body: ProgramBody = []
        for node in topological_order:
            # Output of a step will be stored in a variable in the format `var_{step_id}_{socket_id}`
            # It is assumed that every step will always output the same number of values as the number of output sockets
            # As such, all we need to do is to pass in the correct variables to the next step

            input_variables: dict[SocketId, ProgramVariable] = {}
            file_inputs: dict[SocketId, File] = {}

            for in_edge in self.in_edges_index[node.id]:
                in_node: Step = self.node_index[in_edge.from_node_id]

                # Find the socket that the link is connected to
                for socket in filter(lambda socket: socket.id == in_edge.to_socket_id, node.inputs):
                    in_node_sockets = [
                        socket for socket in in_node.outputs if socket.id == in_edge.from_socket_id
                    ]
                    assert len(in_node_sockets) <= 1

                    # If no sockets are connected to this input socket, skip.
                    if not in_node_sockets:
                        continue

                    # Get origining node socket from in_node
                    in_node_socket: StepSocket = in_node_sockets[0]

                    if in_node_socket.data is not None and isinstance(in_node_socket.data, File):
                        # NOTE: File objects are passed directly to the next step and not serialized as a variable
                        file_inputs[socket.id] = in_node_socket.data
                    else:
                        input_variables[socket.id] = self._create_link_variable(
                            in_node, in_node_socket.id
                        )

            node._debug = debug
            program_body.extend(assemble_fragment(node.run(input_variables, file_inputs, self)))

        return hoist_imports(cst.Module(body=program_body))
