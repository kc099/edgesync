from typing import List, Dict, Any, Optional, Callable
from enum import Enum
import asyncio
import threading
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from .execution_context import ExecutionContext, ExecutionStatus
from ..processors.factory import ProcessorFactory
from ..processors.base_processor import BaseProcessor, ExecutionError

logger = logging.getLogger(__name__)

class ExecutionStrategy(Enum):
    """Execution strategy enumeration."""
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    HYBRID = "hybrid"

class NodeScheduler:
    """
    Schedules and executes nodes based on dependency resolution.
    
    This class manages the execution of nodes in the correct order,
    handling both sequential and parallel execution strategies.
    """
    
    def __init__(self, 
                 execution_levels: List[List[str]],
                 nodes: Dict[str, Dict[str, Any]],
                 dependency_graph: Dict[str, List[str]],
                 execution_context: ExecutionContext,
                 strategy: ExecutionStrategy = ExecutionStrategy.HYBRID,
                 max_workers: int = 4):
        """
        Initialize the node scheduler.
        
        Args:
            execution_levels: List of execution levels from dependency resolver
            nodes: Dictionary of node configurations
            dependency_graph: Reverse dependency graph (node -> prerequisites)
            execution_context: Execution context for this flow run
            strategy: Execution strategy to use
            max_workers: Maximum number of worker threads for parallel execution
        """
        self.execution_levels = execution_levels
        self.nodes = nodes
        self.dependency_graph = dependency_graph
        self.execution_context = execution_context
        self.strategy = strategy
        self.max_workers = max_workers
        
        # Create processors for all nodes
        self.processors = self._create_processors()
        
        # Event callbacks
        self.on_node_start: Optional[Callable[[str], None]] = None
        self.on_node_complete: Optional[Callable[[str, Dict[str, Any]], None]] = None
        self.on_node_error: Optional[Callable[[str, Exception], None]] = None
        self.on_level_complete: Optional[Callable[[int, List[str]], None]] = None
    
    def _create_processors(self) -> Dict[str, BaseProcessor]:
        """
        Create processor instances for all nodes.
        
        Returns:
            Dictionary mapping node IDs to processor instances
        """
        processors = {}
        flow_context = {
            'execution_id': self.execution_context.execution_id,
            'flow_id': self.execution_context.flow_id,
            'variables': self.execution_context.get_all_variables()
        }
        
        for node_id, node_config in self.nodes.items():
            try:
                processor = ProcessorFactory.create_processor(node_config, flow_context)
                processors[node_id] = processor
                logger.debug(f"Created processor for node {node_id}: {type(processor).__name__}")
            except Exception as e:
                logger.error(f"Failed to create processor for node {node_id}: {e}")
                raise
        
        return processors
    
    def execute_flow(self) -> Dict[str, Any]:
        """
        Execute the entire flow based on the configured strategy.
        
        Returns:
            Dictionary with execution results
        """
        logger.info(f"Starting flow execution with strategy: {self.strategy.value}")
        
        try:
            self.execution_context.start_execution()
            
            if self.strategy == ExecutionStrategy.SEQUENTIAL:
                return self._execute_sequential()
            elif self.strategy == ExecutionStrategy.PARALLEL:
                return self._execute_parallel()
            elif self.strategy == ExecutionStrategy.HYBRID:
                return self._execute_hybrid()
            else:
                raise ValueError(f"Unknown execution strategy: {self.strategy}")
                
        except Exception as e:
            logger.error(f"Flow execution failed: {e}")
            self.execution_context.complete_execution(success=False, error=str(e))
            raise
    
    def _execute_sequential(self) -> Dict[str, Any]:
        """
        Execute nodes sequentially level by level.
        
        Returns:
            Dictionary with execution results
        """
        logger.info("Executing flow sequentially")
        
        for level_idx, level_nodes in enumerate(self.execution_levels):
            logger.info(f"Executing level {level_idx} with {len(level_nodes)} nodes")
            
            for node_id in level_nodes:
                if not self.execution_context.is_running():
                    logger.info("Execution stopped by user")
                    break
                
                self._execute_single_node(node_id)
            
            if self.on_level_complete:
                self.on_level_complete(level_idx, level_nodes)
            
            # Check if execution should continue
            if not self.execution_context.is_running():
                break
        
        self.execution_context.complete_execution(success=True)
        return self._get_execution_results()
    
    def _execute_parallel(self) -> Dict[str, Any]:
        """
        Execute nodes in parallel within each level.
        
        Returns:
            Dictionary with execution results
        """
        logger.info(f"Executing flow in parallel with {self.max_workers} workers")
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            for level_idx, level_nodes in enumerate(self.execution_levels):
                logger.info(f"Executing level {level_idx} with {len(level_nodes)} nodes in parallel")
                
                # Submit all nodes in this level for parallel execution
                future_to_node = {
                    executor.submit(self._execute_single_node, node_id): node_id
                    for node_id in level_nodes
                    if self.execution_context.is_running()
                }
                
                # Wait for all nodes in this level to complete
                for future in as_completed(future_to_node):
                    node_id = future_to_node[future]
                    try:
                        future.result()  # This will raise any exception from node execution
                    except Exception as e:
                        logger.error(f"Node {node_id} failed in parallel execution: {e}")
                        # Continue with other nodes unless it's a critical failure
                
                if self.on_level_complete:
                    self.on_level_complete(level_idx, level_nodes)
                
                # Check if execution should continue
                if not self.execution_context.is_running():
                    break
        
        self.execution_context.complete_execution(success=True)
        return self._get_execution_results()
    
    def _execute_hybrid(self) -> Dict[str, Any]:
        """
        Execute nodes using hybrid strategy (mix of sequential and parallel).
        
        Returns:
            Dictionary with execution results
        """
        logger.info("Executing flow with hybrid strategy")
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            for level_idx, level_nodes in enumerate(self.execution_levels):
                logger.info(f"Executing level {level_idx} with {len(level_nodes)} nodes")
                
                # Categorize nodes for parallel vs sequential execution
                parallel_nodes = []
                sequential_nodes = []
                
                for node_id in level_nodes:
                    processor = self.processors[node_id]
                    if self._should_execute_parallel(processor):
                        parallel_nodes.append(node_id)
                    else:
                        sequential_nodes.append(node_id)
                
                # Execute parallel nodes concurrently
                if parallel_nodes:
                    logger.debug(f"Executing {len(parallel_nodes)} nodes in parallel")
                    future_to_node = {
                        executor.submit(self._execute_single_node, node_id): node_id
                        for node_id in parallel_nodes
                        if self.execution_context.is_running()
                    }
                    
                    for future in as_completed(future_to_node):
                        node_id = future_to_node[future]
                        try:
                            future.result()
                        except Exception as e:
                            logger.error(f"Parallel node {node_id} failed: {e}")
                
                # Execute sequential nodes one by one
                if sequential_nodes:
                    logger.debug(f"Executing {len(sequential_nodes)} nodes sequentially")
                    for node_id in sequential_nodes:
                        if not self.execution_context.is_running():
                            break
                        self._execute_single_node(node_id)
                
                if self.on_level_complete:
                    self.on_level_complete(level_idx, level_nodes)
                
                # Check if execution should continue
                if not self.execution_context.is_running():
                    break
        
        self.execution_context.complete_execution(success=True)
        return self._get_execution_results()
    
    def _should_execute_parallel(self, processor: BaseProcessor) -> bool:
        """
        Determine if a processor should be executed in parallel.
        
        Args:
            processor: Processor instance to check
            
        Returns:
            True if processor can be executed in parallel
        """
        # I/O bound operations can typically run in parallel
        parallel_types = [
            'device',           # Device operations
            'display',          # Display updates
            'debug',            # Debug logging
            'comment'           # Comment nodes (no-op)
        ]
        
        processor_type = processor.node_type
        return processor_type in parallel_types
    
    def _execute_single_node(self, node_id: str) -> None:
        """
        Execute a single node.
        
        Args:
            node_id: ID of the node to execute
        """
        processor = self.processors[node_id]
        
        try:
            # Check if node can be executed
            if not self.execution_context.can_execute_node(node_id, self.dependency_graph):
                logger.warning(f"Node {node_id} cannot be executed at this time")
                return
            
            # Set node status to running
            self.execution_context.set_node_status(node_id, ExecutionStatus.RUNNING)
            
            # Fire node start callback
            if self.on_node_start:
                self.on_node_start(node_id)
            
            logger.debug(f"Executing node {node_id}")
            
            # Get input data from predecessor nodes
            input_data = self.execution_context.get_node_input_data(node_id, self.dependency_graph)
            
            # Execute the processor
            start_time = datetime.now()
            result = processor.safe_execute(input_data)
            end_time = datetime.now()
            
            # Store execution result
            execution_result = {
                **result,
                'execution_time_ms': (end_time - start_time).total_seconds() * 1000,
                'node_id': node_id,
                'node_type': processor.node_type
            }
            
            self.execution_context.set_node_result(node_id, execution_result)
            self.execution_context.set_node_status(node_id, ExecutionStatus.COMPLETED)
            
            # Fire node complete callback
            if self.on_node_complete:
                self.on_node_complete(node_id, execution_result)
            
            logger.debug(f"Node {node_id} completed successfully")
            
        except ExecutionError as e:
            logger.error(f"Node {node_id} execution failed: {e}")
            self.execution_context.set_node_status(node_id, ExecutionStatus.FAILED)
            
            # Store error information
            error_result = {
                'error': str(e),
                'node_id': node_id,
                'node_type': processor.node_type,
                'timestamp': datetime.now().isoformat()
            }
            self.execution_context.set_node_result(node_id, error_result)
            
            # Fire node error callback
            if self.on_node_error:
                self.on_node_error(node_id, e)
            
            # Decide whether to continue or stop execution
            if self._should_stop_on_error(node_id, e):
                self.execution_context.stop_execution(f"Critical node {node_id} failed: {e}")
        
        except Exception as e:
            logger.error(f"Unexpected error in node {node_id}: {e}")
            self.execution_context.set_node_status(node_id, ExecutionStatus.FAILED)
            
            # Fire node error callback
            if self.on_node_error:
                self.on_node_error(node_id, e)
            
            # Stop execution on unexpected errors
            self.execution_context.stop_execution(f"Unexpected error in node {node_id}: {e}")
    
    def _should_stop_on_error(self, node_id: str, error: Exception) -> bool:
        """
        Determine if execution should stop when a node fails.
        
        Args:
            node_id: ID of the failed node
            error: The exception that occurred
            
        Returns:
            True if execution should stop
        """
        # For now, continue execution unless it's a critical node
        # In the future, this could be configurable per node
        critical_node_types = ['device', 'custom-function']
        processor = self.processors[node_id]
        
        return processor.node_type in critical_node_types
    
    def _get_execution_results(self) -> Dict[str, Any]:
        """
        Get the final execution results.
        
        Returns:
            Dictionary with execution results and summary
        """
        summary = self.execution_context.get_execution_summary()
        
        # Get all node results
        node_results = {}
        for node_id in self.nodes.keys():
            result = self.execution_context.get_node_result(node_id)
            if result:
                node_results[node_id] = result
        
        return {
            'execution_summary': summary,
            'node_results': node_results,
            'variables': self.execution_context.get_all_variables(),
            'execution_log': self.execution_context.get_execution_log(limit=100)
        }
    
    def pause_execution(self) -> None:
        """
        Pause the execution.
        """
        self.execution_context.pause_execution()
        logger.info("Flow execution paused")
    
    def resume_execution(self) -> None:
        """
        Resume the execution.
        """
        self.execution_context.resume_execution()
        logger.info("Flow execution resumed")
    
    def stop_execution(self, reason: str = "User requested stop") -> None:
        """
        Stop the execution.
        
        Args:
            reason: Reason for stopping
        """
        self.execution_context.stop_execution(reason)
        logger.info(f"Flow execution stopped: {reason}")
