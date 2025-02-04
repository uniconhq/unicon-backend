from collections import Counter, defaultdict, deque
from functools import cached_property
from itertools import chain
from typing import Generic, Self, TypeVar

from pydantic import BaseModel, model_validator

from unicon_backend.lib.common import create_multi_index

IdType = TypeVar("IdType", bound=str)


class NodeSocket(BaseModel, Generic[IdType]):
    id: IdType


NodeSocketType = TypeVar("NodeSocketType", bound=NodeSocket[str])


class GraphNode(BaseModel, Generic[IdType, NodeSocketType]):
    id: IdType
    inputs: list[NodeSocketType]
    outputs: list[NodeSocketType]

    @model_validator(mode="after")
    def unique_socket_ids(self) -> Self:
        id_counter = Counter(map(lambda socket: socket.id, chain(self.inputs, self.outputs)))
        if len(id_counter) > 0 and id_counter.most_common(1)[0][1] > 1:
            raise ValueError("Socket ids must be unique")
        return self

    @cached_property
    def all_sockets(self) -> list[NodeSocketType]:
        """Return a list of all sockets"""
        return self.inputs + self.outputs

    @cached_property
    def socket_index(self) -> dict[str, NodeSocketType]:
        """Return a dictionary of socket id to socket object"""
        return {socket.id: socket for socket in chain(self.inputs, self.outputs)}

    def get_socket(self, socket_id: IdType) -> NodeSocketType | None:
        return self.socket_index.get(socket_id)


class GraphEdge(BaseModel, Generic[IdType]):
    id: IdType

    from_node_id: IdType
    from_socket_id: IdType

    to_node_id: IdType
    to_socket_id: IdType


GraphNodeType = TypeVar("GraphNodeType", bound=GraphNode[str, NodeSocket[str]])
GraphEdgeType = TypeVar("GraphEdgeType", bound=GraphEdge[str])


class Graph(BaseModel, Generic[GraphNodeType, GraphEdgeType]):
    nodes: list[GraphNodeType]
    edges: list[GraphEdgeType]

    @cached_property
    def node_index(self) -> dict[str, GraphNodeType]:
        """Return a map of node id to node object"""
        return {node.id: node for node in self.nodes}

    @cached_property
    def out_nodes_index(self) -> defaultdict[str, list[str]]:
        """Return a map of node id to a list of ids of nodes that are outgoing from the node"""
        return create_multi_index(self.edges, lambda e: e.from_node_id, lambda e: e.to_node_id)

    @cached_property
    def in_nodes_index(self) -> defaultdict[str, list[str]]:
        """Return a map of node id to a list of ids of nodes that are incoming to the node"""
        return create_multi_index(self.edges, lambda e: e.to_node_id, lambda e: e.from_node_id)

    @cached_property
    def out_edges_index(self) -> defaultdict[str, list[GraphEdgeType]]:
        """Return a map of node id to a list of ids of edges that are outgoing from the node"""
        return create_multi_index(self.edges, lambda e: e.from_node_id, lambda e: e)

    @cached_property
    def in_edges_index(self) -> defaultdict[str, list[GraphEdgeType]]:
        """Return a map of node id to a list of ids of edges that are incoming to the node"""
        return create_multi_index(self.edges, lambda e: e.to_node_id, lambda e: e)

    def topological_sort(self, ignored_node_ids: set[str] | None = None) -> list[GraphNodeType]:
        """
        Perform topological sort on the graph

        Args:
            ignored_node_ids (set[str]) A set of node ids to ignore

        Returns:
            list[GraphNodeType]: A list of nodes in topological order

        Raises:
            ValueError: If the graph has a cycle
        """
        # NOTE: These nodes will be ignored during topological sort
        ignored_node_ids = ignored_node_ids or set()
        working_node_ids = set(self.node_index.keys()) - ignored_node_ids

        in_degrees: dict[str, int] = defaultdict(int)
        node_id_queue: deque[str] = deque(maxlen=len(working_node_ids))

        for node_id in working_node_ids:
            in_degrees[node_id] = len(set(self.in_nodes_index.get(node_id, [])) - ignored_node_ids)
            if in_degrees[node_id] == 0:
                node_id_queue.append(node_id)

        topo_order_node_ids: list[str] = []
        while len(node_id_queue):
            curr_node_id = node_id_queue.popleft()
            topo_order_node_ids.append(curr_node_id)

            for to_node_id in self.out_nodes_index.get(curr_node_id, []):
                if to_node_id in ignored_node_ids:
                    continue

                in_degrees[to_node_id] -= 1
                if in_degrees[to_node_id] == 0:
                    node_id_queue.append(to_node_id)

        if len(topo_order_node_ids) != len(working_node_ids):
            raise ValueError("Graph has a cycle")

        return [self.node_index[node_id] for node_id in topo_order_node_ids]
