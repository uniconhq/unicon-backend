import abc
from collections.abc import Iterable
from enum import Enum
from typing import Any, Self, Union

from pydantic import model_validator

from unicon_backend.lib.common import CustomBaseModel
from unicon_backend.lib.graph import Graph, GraphEdge, GraphNode

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
    LOOP_STEP = "LOOP_STEP"
    BREAKING_CONDITION = "BREAKING_CONDITION_STEP"

    # Comparison Operations
    STRING_MATCH = "STRING_MATCH_STEP"


class Step(CustomBaseModel, GraphNode, abc.ABC, polymorphic=True):
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
        if len(self.inputs) != self.expected_num_inputs:
            raise ValueError(
                f"Step {self.id} ({self.type}) expects {self.expected_num_inputs} inputs, but got {len(self.inputs)}"
            )
        if len(self.outputs) != self.expected_num_outputs:
            raise ValueError(
                f"Step {self.id} ({self.type}) expects {self.expected_num_outputs} outputs, but got {len(self.outputs)}"
            )
        return self

    def debug_stmt(self) -> str:
        return f"# Step {self.id}: {self.type.value}"

    def get_output_variable(self, output: SocketName) -> str:
        return f"var_{self.id}_{output}"

    @abc.abstractmethod
    def run(self, inputs: dict[SocketName, ProgramVariable], debug: bool) -> Program: ...


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
                    yield from flatten(x)
                else:
                    yield x

        # Flatten the program into a list of strings
        # TODO: Have a clear separation between the different parts of the program,
        #       right now the whole program have no spacing (no blank lines) between different logical parts
        return "\n".join(flatten(program))

    def run(self, debug: bool = True) -> AssembledProgram:
        topological_order: list[Step] = self.topological_sort()

        program: Program = []
        for node in topological_order:
            # Output of a step will be stored in a variable in the format `var_{step_id}_{socket_id}`
            # It is assumed that every step will always output the same number of values as the number of output sockets
            # As such, all we need to do is to pass in the correct variables to the next step

            input_variables: dict[str, Any] = {}

            for in_edge_id in self.in_edges_index[node.id]:
                in_edge: GraphEdge = self.edge_index[in_edge_id]
                in_node: Step = self.node_index[in_edge.from_node_id]

                # Find the socket that the link is connected to
                for socket in filter(lambda socket: socket.id == in_edge.to_socket_id, node.inputs):
                    input_variables[socket.name] = self._create_link_variable(in_node, socket.name)

            program.append(node.run(input_variables, debug))

        return self._assemble_program(program)


class StringMatchStep(Step):
    def run(self, inputs: dict[SocketName, ProgramVariable], debug: bool) -> Program:
        return []
