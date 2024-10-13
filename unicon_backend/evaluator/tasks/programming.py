import logging
from collections import defaultdict
from enum import Enum
from logging import getLogger
from queue import Queue
from typing import Any, Literal, NewType
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, RootModel

from unicon_backend.evaluator.tasks import Task, TaskEvalResult, TaskEvalStatus
from unicon_backend.workers import task_publisher

logger = getLogger(__name__)

# TEMP: suppress pika logging
logging.getLogger("pika").setLevel(logging.WARNING)


class ProgrammingLanguage(str, Enum):
    PYTHON = "PYTHON"


class ProgrammingEnvironment(BaseModel):
    language: ProgrammingLanguage
    options: dict[str, str]
    time_limit: int  # in seconds
    memory_limit: int  # in MB


class File(BaseModel):
    file_name: str
    content: str


class RunnerResponse(BaseModel):
    # Reference: https://github.com/uniconhq/unicon-runner/blob/main/unicon_runner/executor/run.py#L69-L73
    submission_id: str
    status: int
    stdout: str
    stderr: str


class Socket(BaseModel):
    id: int
    name: str


class Step(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    type: str
    inputs: list[Socket]
    outputs: list[Socket]


class Edge(BaseModel):
    id: int

    from_node_id: int
    from_socket_id: int

    to_node_id: int
    to_socket_id: int


class Testcase(BaseModel):
    id: int
    steps: list[Step]
    edges: list[Edge]

    def toposort(self) -> list[Step]:
        node_index: dict[int, Step] = {step.id: step for step in self.steps}
        out_edges_index: dict[int, list[int]] = defaultdict(list)
        in_edges_index: dict[int, list[int]] = defaultdict(list)

        for edge in self.edges:
            out_edges_index[edge.from_node_id].append(edge.to_node_id)
            in_edges_index[edge.to_node_id].append(edge.from_node_id)

        in_degrees: dict[int, int] = defaultdict(int)
        node_queue: Queue[int] = Queue(len(self.steps))

        for step_node in self.steps:
            in_degrees[step_node.id] = len(in_edges_index.get(step_node.id, []))
            if in_degrees[step_node.id] == 0:
                node_queue.put(step_node.id)

        topo_order: list[int] = []

        while not node_queue.empty():
            step_node_id: int = node_queue.get()
            topo_order.append(step_node_id)

            for to_step_node_id in out_edges_index.get(step_node_id, []):
                in_degrees[to_step_node_id] -= 1
                if in_degrees[to_step_node_id] == 0:
                    node_queue.put(to_step_node_id)

        if len(topo_order) != len(self.steps):
            raise ValueError(f"Testcase {self.id} has a cycle!")

        return [node_index[step_id] for step_id in topo_order]


class ProgrammingTaskExpectedAnswer(BaseModel):
    testcase_id: int
    step_id: int
    expected_answer: Any


SubmissionId = NewType("SubmissionId", UUID)


class ProgrammingTaskRequest(BaseModel):
    submission_id: SubmissionId
    environment: ProgrammingEnvironment
    templates: list[File]
    testcases: list[Testcase]
    user_input: list[File]
    expected_answer: list[ProgrammingTaskExpectedAnswer]
    executor_type: Literal["podman", "unsafe"] = "podman"


class ProgrammingTask(Task[list[File], SubmissionId, list[ProgrammingTaskExpectedAnswer]]):
    question: str
    environment: ProgrammingEnvironment
    templates: list[File]
    testcases: list[Testcase]
    executor_type: Literal["podman", "unsafe"] = "podman"

    def run(
        self,
        user_input: list[File],
        expected_answer: list[ProgrammingTaskExpectedAnswer],
    ) -> TaskEvalResult[SubmissionId]:
        submission_id = SubmissionId(uuid4())

        request = ProgrammingTaskRequest(
            submission_id=submission_id,
            environment=self.environment,
            templates=self.templates,
            testcases=self.testcases,
            user_input=user_input,
            expected_answer=expected_answer,
        )

        task_publisher.publish(request.model_dump_json(serialize_as_any=True))

        return TaskEvalResult(task_id=self.id, status=TaskEvalStatus.PENDING, result=submission_id)

    def validate_user_input(self, user_input: Any) -> list[File]:
        return RootModel[list[File]].model_validate(user_input).root

    def validate_expected_answer(self, expected_answer: Any) -> list[ProgrammingTaskExpectedAnswer]:
        return RootModel[list[ProgrammingTaskExpectedAnswer]].model_validate(expected_answer).root
