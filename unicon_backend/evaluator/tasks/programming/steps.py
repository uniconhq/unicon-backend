import abc
from collections import deque
from collections.abc import Iterable
from enum import Enum
from functools import cached_property
from typing import ClassVar, Self, Union

from pydantic import model_validator

from unicon_backend.evaluator.tasks.programming.artifact import File, PrimitiveData
from unicon_backend.lib.common import CustomBaseModel
from unicon_backend.lib.graph import Graph, GraphNode, NodeSocket

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
    def subgraph_socket_ids(self) -> set[str]:
        """
        Socket IDs that are used to connect to the subgraph of a Step.
        """
        ...

    def get_subgraph_node_ids(self, graph: "ComputeGraph") -> set[int]:
        def gather_subgraph(socket_id: str) -> set[int]:
            subgraph_socket: StepSocket | None = self.get_socket(socket_id)
            if subgraph_socket is None:
                raise ValueError(f"Subgraph socket {socket_id} not found!")

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

        subgraph_node_ids: set[int] = set()
        for socket_id in self.subgraph_socket_ids:
            subgraph_node_ids |= gather_subgraph(socket_id)

        return subgraph_node_ids

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

        subgraph_node_ids: set[int] = set()
        for node in self.nodes:
            subgraph_node_ids |= node.get_subgraph_node_ids(self)

        # We do not consider subgraph nodes when determining the flow order (topological order) of the main compute graph
        # The responsibility of determining the order of subgraph nodes is deferred to the step itself
        topological_order: list[Step] = self.topological_sort(subgraph_node_ids)

        program: Program = []
        for node in topological_order:
            # Output of a step will be stored in a variable in the format `var_{step_id}_{socket_id}`
            # It is assumed that every step will always output the same number of values as the number of output sockets
            # As such, all we need to do is to pass in the correct variables to the next step

            input_variables: dict[SocketName, ProgramVariable] = {}
            file_inputs: dict[SocketName, File] = {}

            for in_edge in self.in_edges_index[node.id]:
                in_node: Step = self.node_index[in_edge.from_node_id]

                # Find the socket that the link is connected to
                for socket in filter(lambda socket: socket.id == in_edge.to_socket_id, node.inputs):
                    # Get origining node socket from in_node
                    in_node_socket: StepSocket = next(
                        filter(lambda socket: socket.id == in_edge.from_socket_id, in_node.outputs)
                    )

                    if in_node_socket.data is not None and isinstance(in_node_socket.data, File):
                        # NOTE: File objects are passed directly to the next step and not serialized as a variable
                        file_inputs[socket.id] = in_node_socket.data
                    else:
                        input_variables[socket.id] = self._create_link_variable(
                            in_node, in_node_socket.id
                        )

            program.append(node.run(input_variables, file_inputs, debug))

        return self._assemble_program(program)


class InputStep(Step):
    subgraph_socket_ids: ClassVar[set[str]] = set()

    @model_validator(mode="after")
    def check_non_empty_outputs(self) -> Self:
        if len(self.outputs) == 0:
            raise ValueError("Input step must have at least one output")

        for output in self.outputs:
            if output.data is None:
                raise ValueError(f"Output socket {output.id} must have data")

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
                    f"{self.get_output_variable(output.id)} = {_serialize_data(output.data)}"
                )

        return program


class StringMatchStep(Step):
    subgraph_socket_ids: ClassVar[set[str]] = set()

    def run(self, var_inputs: dict[SocketName, ProgramVariable], _, debug: bool) -> Program:
        output_socket_name: str = self.outputs[0].id

        return [
            self.debug_stmt() if debug else "",
            f"{self.get_output_variable(output_socket_name)} = str({var_inputs[self.inputs[0].id]}) == str({var_inputs[self.inputs[1].id]})",
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

    subgraph_socket_ids: ClassVar[set[str]] = set()

    function_identifier: str

    def run(
        self,
        var_inputs: dict[SocketName, ProgramVariable],
        file_inputs: dict[SocketName, File],
        debug: bool,
    ) -> Program:
        # Get the input file that we are running the function from
        program_file: File | None = file_inputs.get("DATA.IN.FILE")
        if program_file is None:
            raise ValueError("No program file provided")

        # Gather all function arguments
        positional_args: list[str] = [
            var_inputs[socket.id] for socket in self.inputs if socket.id.startswith("DATA.IN.ARG")
        ]
        keyword_args: dict[str, str] = {
            socket_name.split(".")[1]: program_variable
            for socket_name, program_variable in var_inputs.items()
            if socket_name.startswith("DATA.IN.KWARG")
        }

        function_args_str: str = (
            ", ".join([*positional_args, ""]) + f"**{keyword_args}" if keyword_args else ""
        )

        return [
            self.debug_stmt() if debug else "",
            # Import statement for the function
            f"from {program_file.file_name.split('.py')[0]} import {self.function_identifier}",
            # Function invocation
            f"{self.get_output_variable(self.outputs[0].id)} = {self.function_identifier}({function_args_str})",
        ]


class LoopStep(Step):
    subgraph_socket_ids: ClassVar[set[str]] = {"CONTROL.IN.PREDICATE", "CONTROL.OUT.BODY"}

    def run(
        self,
        var_inputs: dict[SocketName, ProgramVariable],
        file_inputs: dict[SocketName, File],
        debug: bool,
    ) -> Program:
        raise NotImplementedError("LoopStep is not implemented yet")
