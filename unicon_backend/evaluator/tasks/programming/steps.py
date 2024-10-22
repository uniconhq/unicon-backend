import abc
from collections.abc import Iterable
from enum import Enum
from functools import cached_property
from typing import ClassVar, Self, Union

from pydantic import model_validator

from unicon_backend.evaluator.tasks.programming.artifact import File, PrimitiveData
from unicon_backend.lib.common import CustomBaseModel
from unicon_backend.lib.graph import Graph, GraphEdge, GraphNode, NodeSocket

type SocketName = str
type ProgramVariable = str
type ProgramFragment = str
type AssembledProgram = str

# A program can be made up of sub programs, especially with subgraphs
Program = list[Union["Program", ProgramFragment]]


class StepType(str, Enum):
    PY_RUN_FUNCTION = "PY_RUN_FUNCTION_STEP"

    # I/O Operations
    INPUT = "INPUT_STEP"
    OUTPUT = "OUTPUT_STEP"

    # Control Flow Operations
    LOOP = "LOOP_STEP"

    # Comparison Operations
    STRING_MATCH = "STRING_MATCH_STEP"


class StepSocket(NodeSocket):
    """
    A socket that is used to connect steps to each other.

    Socket ID Format: <TYPE>.<DIRECTION>.<NAME>.<INDEX>
    - <NAME>.<INDEX> is optional and is used to differentiate between multiple sockets of the same type
        - Collectively, <NAME>.<INDEX> is referred to as the "label"

    There can be 2 types of sockets:

    1. Control Sockets: Used to control the flow of the program
        - e.g. CONTROL.IN.<NAME>.<INDEX>
    2. Data Sockets: Used to pass data between steps
        - e.g. DATA.OUT.<NAME>.<INDEX>
    """

    # The data that the socket holds
    data: PrimitiveData | File | None = None

    @cached_property
    def type(self) -> str:
        return self.id.split(".")[0]

    @cached_property
    def direction(self) -> str:
        return self.id.split(".")[1]

    @cached_property
    def label(self) -> str:
        return self.id.split(".", 2)[-1]


class Step(CustomBaseModel, GraphNode[StepSocket], abc.ABC, polymorphic=True):
    id: int
    type: StepType

    @property
    @abc.abstractmethod
    def expected_num_inputs(self) -> int:
        """Return the expected number of input sockets for the step"""
        ...

    @property
    @abc.abstractmethod
    def expected_num_outputs(self) -> int:
        """Return the expected number of output sockets for the step"""
        ...

    @model_validator(mode="after")
    def validate_num_inputs_outputs(self) -> Self:
        if len(self.inputs) != self.expected_num_inputs and self.expected_num_inputs != -1:
            raise ValueError(
                f"Step {self.id} ({self.type}) expects {self.expected_num_inputs} inputs, but got {len(self.inputs)}"
            )
        if len(self.outputs) != self.expected_num_outputs and self.expected_num_outputs != -1:
            raise ValueError(
                f"Step {self.id} ({self.type}) expects {self.expected_num_outputs} outputs, but got {len(self.outputs)}"
            )
        return self

    def debug_stmt(self) -> str:
        return f"# Step {self.id}: {self.type.value}"

    def get_output_variable(self, output: SocketName) -> str:
        return f"var_{self.id}_{output}"

    @abc.abstractmethod
    def run(
        self,
        var_inputs: dict[SocketName, ProgramVariable],
        file_inputs: dict[SocketName, File],
        debug: bool,
    ) -> Program: ...


class ComputeGraph(Graph[Step]):
    def _create_link_variable(self, from_node: Step, from_socket: str) -> str:
        """
        Create a variable name for the output of a node. The variable name must be unique across all nodes and sockets.

        Args:
            from_node (Step): The node that is outputting the variable
            from_socket (str): The socket that the variable is outputting from
        """
        return from_node.get_output_variable(from_socket)

    def _assemble_program(self, program: Program) -> AssembledProgram:
        def flatten(xs):
            for x in xs:
                if isinstance(x, Iterable) and not isinstance(x, str):
                    yield ""  # Add a blank line between different parts of the program
                    yield from flatten(x)
                else:
                    yield x

        # TODO: Handle different indentation levels
        return "\n".join(flatten(program))

    def run(self, user_input_step: "InputStep", debug: bool = True) -> AssembledProgram:
        """
        Run the compute graph with the given user input.

        Args:
            user_input_step (InputStep): The input step (id = 0) that contains the user input
            debug (bool, optional): Whether to include debug statements in the program. Defaults to True.
        """
        # Add user input step (node) to compute graph
        self.nodes.append(user_input_step)
        topological_order: list[Step] = self.topological_sort()

        program: Program = []
        for node in topological_order:
            # Output of a step will be stored in a variable in the format `var_{step_id}_{socket_id}`
            # It is assumed that every step will always output the same number of values as the number of output sockets
            # As such, all we need to do is to pass in the correct variables to the next step

            input_variables: dict[SocketName, ProgramVariable] = {}
            file_inputs: dict[SocketName, File] = {}

            for in_edge_id in self.in_edges_index[node.id]:
                in_edge: GraphEdge = self.edge_index[in_edge_id]
                in_node: Step = self.node_index[in_edge.from_node_id]

                # Find the socket that the link is connected to
                for socket in filter(lambda socket: socket.id == in_edge.to_socket_id, node.inputs):
                    # Get origining node socket from in_node
                    # TODO: Make this into a cached property
                    in_node_socket: StepSocket = next(
                        filter(lambda socket: socket.id == in_edge.from_socket_id, in_node.outputs)
                    )

                    if in_node_socket.data is not None and isinstance(in_node_socket.data, File):
                        # NOTE: File objects are passed directly to the next step and not serialized as a variable
                        file_inputs[socket.name] = in_node_socket.data
                    else:
                        input_variables[socket.name] = self._create_link_variable(
                            in_node, in_node_socket.name
                        )

            program.append(node.run(input_variables, file_inputs, debug))

        return self._assemble_program(program)


class InputStep(Step):
    expected_num_inputs: ClassVar[int] = 0
    expected_num_outputs: ClassVar[int] = -1  # Variable number of outputs

    @model_validator(mode="after")
    def check_non_empty_outputs(self) -> Self:
        if len(self.outputs) == 0:
            raise ValueError("Input step must have at least one output")

        for output in self.outputs:
            if output.data is None:
                raise ValueError(f"Output socket {output.name} must have data")

        return self

    def run(self, _, __, debug: bool) -> Program:
        def _serialize_data(data: str | int | float | bool) -> str:
            # TODO: Better handle of variables vs strings
            if isinstance(data, str):
                return f'"{data}"' if not data.startswith("var_") else data
            return str(data)

        program: Program = [self.debug_stmt() if debug else ""]
        for output in self.outputs:
            assert output.data is not None
            if isinstance(output.data, File):
                # If the input is a `File`, we skip the serialization and just pass the file object
                # directly to the next step. This is handled by the `ComputeGraph` class
                continue
            elif isinstance(output.data, PrimitiveData):
                program.append(
                    f"{self.get_output_variable(output.name)} = {_serialize_data(output.data)}"
                )

        return program


class StringMatchStep(Step):
    expected_num_inputs: ClassVar[int] = 2
    expected_num_outputs: ClassVar[int] = 1

    def run(self, var_inputs: dict[SocketName, ProgramVariable], _, debug: bool) -> Program:
        output_socket_name: str = self.outputs[0].name

        return [
            self.debug_stmt() if debug else "",
            f"{self.get_output_variable(output_socket_name)} = str({var_inputs[self.inputs[0].name]}) == str({var_inputs[self.inputs[1].name]})",
        ]


class PyRunFunctionStep(Step):
    """
    A step that runs a Python function.
    To use this step, the user must provide the function name and the arguments to the function via the input sockets.

    Socket Name Format:
    - ARG.{index}.{name}: For positional arguments
    - KWARG.{name}: For keyword arguments
    - FILE: For the `File` object that contains the Python function
    """

    expected_num_inputs: ClassVar[int] = -1
    expected_num_outputs: ClassVar[int] = (
        1  # Assume that the function will always return a single value
    )

    function_identifier: str

    def run(
        self,
        var_inputs: dict[SocketName, ProgramVariable],
        file_inputs: dict[SocketName, File],
        debug: bool,
    ) -> Program:
        # Get the input file that we are running the function from
        program_file: File | None = file_inputs.get("FILE")
        if program_file is None:
            raise ValueError("No program file provided")

        # Gather all function arguments
        positional_args: list[str] = [
            var_inputs[socket.name] for socket in self.inputs if socket.name.startswith("ARG.")
        ]
        keyword_args: dict[str, str] = {
            socket_name.split(".")[1]: program_variable
            for socket_name, program_variable in var_inputs.items()
            if socket_name.startswith("KWARG.")
        }

        function_args_str: str = (
            ", ".join([*positional_args, ""]) + f"**{keyword_args}" if keyword_args else ""
        )

        return [
            self.debug_stmt() if debug else "",
            # Import statement for the function
            f"from {program_file.file_name.split('.py')[0]} import {self.function_identifier}",
            # Function invocation
            f"{self.get_output_variable(self.outputs[0].name)} = {self.function_identifier}({function_args_str})",
        ]


class LoopStep(Step):
    expected_num_inputs: ClassVar[int] = -1
    expected_num_outputs: ClassVar[int] = 1

    subgraph: ComputeGraph

    def run(
        self,
        var_inputs: dict[SocketName, ProgramVariable],
        file_inputs: dict[SocketName, File],
        debug: bool,
    ) -> Program:
        subgraph_input_sockets: list[StepSocket] = []
        for input_socket in self.inputs:
            subgraph_input_sockets.append(
                StepSocket(
                    id=input_socket.id,
                    name=input_socket.name,
                    data=var_inputs[input_socket.name]
                    if input_socket.name in var_inputs
                    else file_inputs[input_socket.name],
                )
            )

        # Add the input step to the subgraph
        subgraph_program: AssembledProgram = self.subgraph.run(
            InputStep(id=0, inputs=[], outputs=subgraph_input_sockets, type=StepType.INPUT), debug
        )

        return [
            self.debug_stmt() if debug else "",
            "while True:",
            subgraph_program.replace("\n", "\n\t"),
        ]
