from typing import List, Dict, Set, Tuple, Any, Optional
from collections import defaultdict, deque
import logging

logger = logging.getLogger(__name__)

class CircularDependencyError(Exception):
    """Raised when circular dependencies are detected in the flow graph."""
    pass

class DependencyResolver:
    """
    Resolves dependencies in a flow graph and determines execution order.
    
    This class implements topological sorting with cycle detection to determine
    the optimal execution order for nodes in a flow graph.
    """
    
    def __init__(self, nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]]):
        """
        Initialize the dependency resolver.
        
        Args:
            nodes: List of node configurations from React Flow
            edges: List of edge configurations from React Flow
        """
        self.nodes = {node['id']: node for node in nodes}
        self.edges = edges
        self.dependency_graph = defaultdict(list)  # node_id -> [dependent_nodes]
        self.reverse_graph = defaultdict(list)     # node_id -> [prerequisite_nodes]
        self.execution_levels = []
        self.total_order = []
        
        self._build_dependency_graph()
    
    def _build_dependency_graph(self) -> None:
        """
        Build dependency graphs from the flow edges.
        """
        # Initialize all nodes in the graphs
        for node_id in self.nodes.keys():
            self.dependency_graph[node_id] = []
            self.reverse_graph[node_id] = []
        
        # Build edges
        for edge in self.edges:
            source = edge['source']
            target = edge['target']
            
            # Forward dependency: source -> target
            self.dependency_graph[source].append(target)
            
            # Reverse dependency: target depends on source
            self.reverse_graph[target].append(source)
    
    def detect_cycles(self) -> Tuple[bool, List[str]]:
        """
        Detect cycles in the dependency graph using DFS.
        
        Returns:
            Tuple of (has_cycles, cycle_nodes)
        """
        WHITE, GRAY, BLACK = 0, 1, 2
        colors = {node_id: WHITE for node_id in self.nodes.keys()}
        cycle_nodes = []
        
        def dfs(node_id: str, path: List[str]) -> bool:
            if colors[node_id] == GRAY:
                # Found a back edge - cycle detected
                cycle_start = path.index(node_id)
                cycle_nodes.extend(path[cycle_start:])
                return True
            
            if colors[node_id] == BLACK:
                return False
            
            colors[node_id] = GRAY
            path.append(node_id)
            
            for neighbor in self.dependency_graph[node_id]:
                if dfs(neighbor, path):
                    return True
            
            path.pop()
            colors[node_id] = BLACK
            return False
        
        for node_id in self.nodes.keys():
            if colors[node_id] == WHITE:
                if dfs(node_id, []):
                    return True, cycle_nodes
        
        return False, []
    
    def resolve_dependencies(self) -> List[List[str]]:
        """
        Resolve dependencies and return execution levels.
        
        Returns:
            List of execution levels, where each level contains nodes
            that can be executed in parallel.
            
        Raises:
            CircularDependencyError: If cycles are detected
        """
        # Check for cycles first
        has_cycles, cycle_nodes = self.detect_cycles()
        if has_cycles:
            raise CircularDependencyError(
                f"Circular dependency detected involving nodes: {cycle_nodes}"
            )
        
        # Perform topological sort using Kahn's algorithm
        self.execution_levels = self._topological_sort()
        
        # Create total order for sequential execution
        self.total_order = []
        for level in self.execution_levels:
            self.total_order.extend(level)
        
        logger.info(f"Resolved dependencies: {len(self.execution_levels)} levels")
        logger.debug(f"Execution levels: {self.execution_levels}")
        
        return self.execution_levels
    
    def _topological_sort(self) -> List[List[str]]:
        """
        Perform topological sorting using Kahn's algorithm.
        
        Returns:
            List of execution levels
        """
        # Calculate in-degrees for each node
        in_degree = {node_id: len(self.reverse_graph[node_id]) 
                    for node_id in self.nodes.keys()}
        
        # Initialize queue with nodes having no dependencies
        queue = deque([node_id for node_id, degree in in_degree.items() 
                      if degree == 0])
        
        execution_levels = []
        
        while queue:
            # Process all nodes at the current level
            current_level = list(queue)
            queue.clear()
            execution_levels.append(current_level)
            
            # Process each node in the current level
            for node_id in current_level:
                # Reduce in-degree for all dependent nodes
                for dependent_node in self.dependency_graph[node_id]:
                    in_degree[dependent_node] -= 1
                    
                    # If dependent node has no more dependencies, add to queue
                    if in_degree[dependent_node] == 0:
                        queue.append(dependent_node)
        
        # Verify all nodes were processed
        processed_nodes = sum(len(level) for level in execution_levels)
        if processed_nodes != len(self.nodes):
            unprocessed = [node_id for node_id in self.nodes.keys() 
                          if not any(node_id in level for level in execution_levels)]
            raise CircularDependencyError(
                f"Unable to process all nodes. Unprocessed: {unprocessed}"
            )
        
        return execution_levels
    
    def get_node_dependencies(self, node_id: str) -> List[str]:
        """
        Get direct dependencies for a specific node.
        
        Args:
            node_id: Node ID to get dependencies for
            
        Returns:
            List of node IDs that this node depends on
        """
        return self.reverse_graph.get(node_id, [])
    
    def get_node_dependents(self, node_id: str) -> List[str]:
        """
        Get nodes that depend on a specific node.
        
        Args:
            node_id: Node ID to get dependents for
            
        Returns:
            List of node IDs that depend on this node
        """
        return self.dependency_graph.get(node_id, [])
    
    def get_execution_level(self, node_id: str) -> int:
        """
        Get the execution level for a specific node.
        
        Args:
            node_id: Node ID to get level for
            
        Returns:
            Execution level (0-indexed), or -1 if node not found
        """
        for level_idx, level in enumerate(self.execution_levels):
            if node_id in level:
                return level_idx
        return -1
    
    def get_critical_path(self) -> List[str]:
        """
        Calculate the critical path through the flow graph.
        
        Returns:
            List of node IDs representing the longest path
        """
        if not self.execution_levels:
            return []
        
        # Find paths from each starting node to each ending node
        start_nodes = self.execution_levels[0] if self.execution_levels else []
        end_nodes = self.execution_levels[-1] if self.execution_levels else []
        
        longest_path = []
        max_length = 0
        
        for start_node in start_nodes:
            for end_node in end_nodes:
                path = self._find_path(start_node, end_node)
                if len(path) > max_length:
                    max_length = len(path)
                    longest_path = path
        
        return longest_path
    
    def _find_path(self, start: str, end: str) -> List[str]:
        """
        Find a path from start node to end node.
        
        Args:
            start: Starting node ID
            end: Ending node ID
            
        Returns:
            List of node IDs representing the path
        """
        if start == end:
            return [start]
        
        visited = set()
        queue = deque([(start, [start])])
        
        while queue:
            node, path = queue.popleft()
            
            if node in visited:
                continue
            
            visited.add(node)
            
            for neighbor in self.dependency_graph[node]:
                new_path = path + [neighbor]
                
                if neighbor == end:
                    return new_path
                
                if neighbor not in visited:
                    queue.append((neighbor, new_path))
        
        return []  # No path found
    
    def analyze_parallelism(self) -> Dict[str, int]:
        """
        Analyze parallelism opportunities in the flow.
        
        Returns:
            Dictionary with parallelism metrics
        """
        total_nodes = len(self.nodes)
        max_parallel = max(len(level) for level in self.execution_levels) if self.execution_levels else 0
        avg_parallel = (sum(len(level) for level in self.execution_levels) / 
                       len(self.execution_levels)) if self.execution_levels else 0
        
        return {
            'total_nodes': total_nodes,
            'execution_levels': len(self.execution_levels),
            'max_parallel_nodes': max_parallel,
            'avg_parallel_nodes': avg_parallel,
            'parallelism_factor': max_parallel / total_nodes if total_nodes > 0 else 0
        }
    
    def get_dependency_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the dependency analysis.
        
        Returns:
            Dictionary with dependency information
        """
        has_cycles, cycle_nodes = self.detect_cycles()
        parallelism = self.analyze_parallelism()
        critical_path = self.get_critical_path()
        
        return {
            'total_nodes': len(self.nodes),
            'total_edges': len(self.edges),
            'has_cycles': has_cycles,
            'cycle_nodes': cycle_nodes,
            'execution_levels': self.execution_levels,
            'total_order': self.total_order,
            'critical_path': critical_path,
            'critical_path_length': len(critical_path),
            'parallelism': parallelism
        }
