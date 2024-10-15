from collections import defaultdict, deque
from functools import cached_property
from typing import Generic, TypeVar

from pydantic import BaseModel


class NodeSocket(BaseModel):
    id: int
    name: str


class GraphNode(BaseModel):
    id: int
    inputs: list[NodeSocket]
    outputs: list[NodeSocket]


class GraphEdge(BaseModel):
    id: int

    from_node_id: int
    from_socket_id: int

    to_node_id: int
    to_socket_id: int


GraphNodeType = TypeVar("GraphNodeType", bound=GraphNode)


class Graph(BaseModel, Generic[GraphNodeType]):
    nodes: list[GraphNodeType]
    edges: list[GraphEdge]

    @cached_property
    def node_index(self) -> dict[int, GraphNodeType]:
        """Return a dictionary of node id to node object"""
        return {node.id: node for node in self.nodes}

    @cached_property
    def out_edges_index(self) -> defaultdict[int, list[int]]:
        """Return a dictionary of node id to a list of node ids that are connected by an edge from the node"""
        out_edges_index = defaultdict(list)
        for edge in self.edges:
            out_edges_index[edge.from_node_id].append(edge.to_node_id)
        return out_edges_index

    @cached_property
    def in_edges_index(self) -> defaultdict[int, list[int]]:
        """Return a dictionary of node id to a list of node ids that are connected by an edge to the node"""
        in_edges_index = defaultdict(list)
        for edge in self.edges:
            in_edges_index[edge.to_node_id].append(edge.from_node_id)
        return in_edges_index

    def topological_sort(self) -> None:
        """
        Perform a topological sort on the graph and update the nodes list in place
        Raises:
            ValueError: if the graph has a cycle
        """
        in_degrees: dict[int, int] = defaultdict(int)
        node_id_queue: deque[int] = deque(maxlen=len(self.nodes))

        for node in self.nodes:
            in_degrees[node.id] = len(self.in_edges_index.get(node.id, []))
            if in_degrees[node.id] == 0:
                node_id_queue.append(node.id)

        topo_order: list[int] = []  # topological order of node ids
        while len(node_id_queue):
            step_node_id: int = node_id_queue.popleft()
            topo_order.append(step_node_id)

            for to_step_node_id in self.out_edges_index.get(step_node_id, []):
                in_degrees[to_step_node_id] -= 1
                if in_degrees[to_step_node_id] == 0:
                    node_id_queue.append(to_step_node_id)

        if len(topo_order) != len(self.nodes):
            raise ValueError("Graph has a cycle")

        self.nodes = [self.node_index[node_id] for node_id in topo_order]