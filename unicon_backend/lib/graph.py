from collections import Counter, defaultdict, deque
from functools import cached_property
from itertools import chain
from typing import Generic, Self, TypeVar

from pydantic import BaseModel, model_validator


class NodeSocket(BaseModel):
    id: str


NodeSocketType = TypeVar("NodeSocketType", bound=NodeSocket)


class GraphNode(BaseModel, Generic[NodeSocketType]):
    id: int
    inputs: list[NodeSocketType]
    outputs: list[NodeSocketType]

    @model_validator(mode="after")
    def unique_socket_ids(self) -> Self:
        id_counter = Counter(map(lambda socket: socket.id, chain(self.inputs, self.outputs)))
        if id_counter.most_common(1)[0][1] > 1:
            raise ValueError("Socket ids must be unique")
        return self

    @cached_property
    def socket_index(self) -> dict[str, NodeSocketType]:
        """Return a dictionary of socket id to socket object"""
        return {socket.id: socket for socket in chain(self.inputs, self.outputs)}

    def get_socket(self, socket_id: str) -> NodeSocketType | None:
        return self.socket_index.get(socket_id)


class GraphEdge(BaseModel):
    id: int

    from_node_id: int
    from_socket_id: str

    to_node_id: int
    to_socket_id: str


GraphNodeType = TypeVar("GraphNodeType", bound=GraphNode)


class Graph(BaseModel, Generic[GraphNodeType]):
    nodes: list[GraphNodeType]
    edges: list[GraphEdge]

    @cached_property
    def node_index(self) -> dict[int, GraphNodeType]:
        """Return a dictionary of node id to node object"""
        return {node.id: node for node in self.nodes}

    @cached_property
    def out_nodes_index(self) -> defaultdict[int, list[int]]:
        """Return a dictionary of node id to a list of ids of nodes that are outgoing from the node"""
        out_nodes_index = defaultdict(list)
        for edge in self.edges:
            out_nodes_index[edge.from_node_id].append(edge.to_node_id)
        return out_nodes_index

    @cached_property
    def in_nodes_index(self) -> defaultdict[int, list[int]]:
        """Return a dictionary of node id to a list of ids of nodes that are incoming to the node"""
        in_nodes_index = defaultdict(list)
        for edge in self.edges:
            in_nodes_index[edge.to_node_id].append(edge.from_node_id)
        return in_nodes_index

    @cached_property
    def edge_index(self) -> dict[int, GraphEdge]:
        """Return a dictionary of edge id to edge object"""
        return {edge.id: edge for edge in self.edges}

    @cached_property
    def out_edges_index(self) -> defaultdict[int, list[GraphEdge]]:
        """Return a dictionary of node id to a list of ids of edges that are outgoing from the node"""
        out_edges_index = defaultdict(list)
        for edge in self.edges:
            out_edges_index[edge.from_node_id].append(edge)
        return out_edges_index

    @cached_property
    def in_edges_index(self) -> defaultdict[int, list[GraphEdge]]:
        """Return a dictionary of node id to a list of ids of edges that are incoming to the node"""
        in_edges_index = defaultdict(list)
        for edge in self.edges:
            in_edges_index[edge.to_node_id].append(edge)
        return in_edges_index

    def topological_sort(self, ignored_node_ids: set[int] | None = None) -> list[GraphNodeType]:
        """
        Perform topological sort on the graph

        Args:
            ignored_node_ids (set[int]): A set of node ids to ignore

        Returns:
            list[GraphNodeType]: A list of nodes in topological order

        Raises:
            ValueError: If the graph has a cycle
        """
        # NOTE: These nodes will be ignored during topological sort
        ignored_node_ids = ignored_node_ids or set()
        working_node_ids = set(self.node_index.keys()) - ignored_node_ids

        in_degrees: dict[int, int] = defaultdict(int)
        node_id_queue: deque[int] = deque(maxlen=len(working_node_ids))

        for node_id in working_node_ids:
            in_degrees[node_id] = len(self.in_nodes_index.get(node_id, []))
            if in_degrees[node_id] == 0:
                node_id_queue.append(node_id)

        topo_order: list[int] = []  # topological order of node ids
        while len(node_id_queue):
            curr_node_id: int = node_id_queue.popleft()
            topo_order.append(curr_node_id)

            for to_node_id in self.out_nodes_index.get(curr_node_id, []):
                in_degrees[to_node_id] -= 1
                if in_degrees[to_node_id] == 0:
                    node_id_queue.append(to_node_id)

        if len(topo_order) != (working_node_ids):
            raise ValueError("Graph has a cycle")

        return [self.node_index[node_id] for node_id in topo_order]
