"""
SignalDock Pipeline Executor

The core engine that processes events through pipeline graphs.
"""
import asyncio
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
import logging
import json

from .filters import Filter, create_filter
from .transformers import Transformer, create_transformer
from .policies import ExecutionPolicy, create_policy
from signals.base import SignalEvent
from actions.base import Action, ActionResult

logger = logging.getLogger(__name__)


class PipelineNode:
    """Represents a node in the pipeline graph"""
    
    def __init__(self, node_id: str, node_type: str, config: dict):
        self.id = node_id
        self.type = node_type  # "source", "filter", "transformer", "action"
        self.config = config
        self.data = config.get("data", {})
        self.position = config.get("position", {"x": 0, "y": 0})
        
        # Runtime components
        self.filter: Optional[Filter] = None
        self.transformer: Optional[Transformer] = None
        self.action: Optional[Action] = None
        self.policy: Optional[ExecutionPolicy] = None
        
        self._initialize_component()
    
    def _initialize_component(self):
        """Initialize the node's runtime component based on type"""
        try:
            if self.type == "filter":
                filter_config = self.data.get("filter", {})
                self.filter = create_filter(filter_config)
            
            elif self.type == "transformer":
                transformer_config = self.data.get("transformer", {})
                self.transformer = create_transformer(transformer_config)
            
            elif self.type == "action":
                action_type = self.data.get("action_type", "notification")
                action_params = self.data.get("params", {})
                
                from actions import get_action
                action_class = get_action(action_type)
                self.action = action_class(params=action_params)
                
                # Initialize execution policy
                policy_config = self.data.get("policy", {"type": "none"})
                self.policy = create_policy(policy_config)
                
        except Exception as e:
            logger.error(f"Error initializing node {self.id}: {e}")


class PipelineEdge:
    """Represents an edge connecting two nodes"""
    
    def __init__(self, edge_id: str, source: str, target: str, config: dict = None):
        self.id = edge_id
        self.source = source  # Source node ID
        self.target = target  # Target node ID
        self.source_handle = config.get("sourceHandle") if config else None
        self.target_handle = config.get("targetHandle") if config else None


class Pipeline:
    """A complete pipeline with nodes and edges"""
    
    def __init__(self, pipeline_id: int, name: str, nodes: list, edges: list):
        self.id = pipeline_id
        self.name = name
        self.is_active = True
        
        # Parse nodes and edges
        self.nodes: Dict[str, PipelineNode] = {}
        self.edges: List[PipelineEdge] = []
        
        for node_config in nodes:
            node = PipelineNode(
                node_id=node_config["id"],
                node_type=node_config.get("type", "source"),
                config=node_config
            )
            self.nodes[node.id] = node
        
        for edge_config in edges:
            edge = PipelineEdge(
                edge_id=edge_config["id"],
                source=edge_config["source"],
                target=edge_config["target"],
                config=edge_config
            )
            self.edges.append(edge)
        
        # Build adjacency list for traversal
        self.adjacency: Dict[str, List[str]] = {}
        for edge in self.edges:
            if edge.source not in self.adjacency:
                self.adjacency[edge.source] = []
            self.adjacency[edge.source].append(edge.target)
    
    def get_source_nodes(self) -> List[PipelineNode]:
        """Get all source nodes (entry points)"""
        return [n for n in self.nodes.values() if n.type == "source"]
    
    def get_connected_nodes(self, node_id: str) -> List[PipelineNode]:
        """Get nodes connected to the given node"""
        target_ids = self.adjacency.get(node_id, [])
        return [self.nodes[tid] for tid in target_ids if tid in self.nodes]


class PipelineExecutor:
    """
    Executes pipelines by routing events through the node graph.
    """
    
    def __init__(self):
        self.pipelines: Dict[int, Pipeline] = {}
        self.source_subscriptions: Dict[str, List[int]] = {}  # source_type -> [pipeline_ids]
        self._event_handlers: List[Callable] = []
        self._action_handlers: List[Callable] = []
        self.logger = logging.getLogger(f"{__name__}.PipelineExecutor")
    
    def load_pipeline(self, pipeline_id: int, name: str, nodes: list, edges: list) -> Pipeline:
        """Load a pipeline from configuration"""
        pipeline = Pipeline(pipeline_id, name, nodes, edges)
        self.pipelines[pipeline_id] = pipeline
        
        # Register source subscriptions
        for node in pipeline.get_source_nodes():
            source_type = node.data.get("source_type", "")
            if source_type:
                if source_type not in self.source_subscriptions:
                    self.source_subscriptions[source_type] = []
                if pipeline_id not in self.source_subscriptions[source_type]:
                    self.source_subscriptions[source_type].append(pipeline_id)
        
        self.logger.info(f"Loaded pipeline: {name} (ID: {pipeline_id})")
        return pipeline
    
    def unload_pipeline(self, pipeline_id: int) -> bool:
        """Unload a pipeline"""
        if pipeline_id not in self.pipelines:
            return False
        
        # Remove source subscriptions
        for source_type, pipeline_ids in self.source_subscriptions.items():
            if pipeline_id in pipeline_ids:
                pipeline_ids.remove(pipeline_id)
        
        del self.pipelines[pipeline_id]
        self.logger.info(f"Unloaded pipeline ID: {pipeline_id}")
        return True
    
    def on_event(self, callback: Callable) -> None:
        """Register callback for event notifications"""
        self._event_handlers.append(callback)
    
    def on_action(self, callback: Callable) -> None:
        """Register callback for action notifications"""
        self._action_handlers.append(callback)
    
    async def _notify_event(self, event: SignalEvent, pipeline_id: int, node_id: str) -> None:
        """Notify handlers of event processing"""
        for handler in self._event_handlers:
            try:
                result = handler(event, pipeline_id, node_id)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                self.logger.error(f"Error in event handler: {e}")
    
    async def _notify_action(self, result: ActionResult, pipeline_id: int, node_id: str) -> None:
        """Notify handlers of action execution"""
        for handler in self._action_handlers:
            try:
                callback_result = handler(result, pipeline_id, node_id)
                if asyncio.iscoroutine(callback_result):
                    await callback_result
            except Exception as e:
                self.logger.error(f"Error in action handler: {e}")
    
    async def process_event(self, event: SignalEvent) -> List[ActionResult]:
        """
        Process an event through all relevant pipelines.
        
        Args:
            event: The signal event to process
        
        Returns:
            List of action results from all executed actions
        """
        results = []
        
        # Find pipelines subscribed to this event source
        source_type = event.source_type
        pipeline_ids = self.source_subscriptions.get(source_type, [])
        
        self.logger.info(f"[PIPELINE] Processing event: {source_type}, subscriptions: {self.source_subscriptions}, pipelines loaded: {list(self.pipelines.keys())}")
        
        for pipeline_id in pipeline_ids:
            pipeline = self.pipelines.get(pipeline_id)
            if not pipeline or not pipeline.is_active:
                self.logger.info(f"[PIPELINE] Skipping pipeline {pipeline_id}: exists={pipeline is not None}, active={pipeline.is_active if pipeline else 'N/A'}")
                continue
            
            self.logger.info(f"[PIPELINE] Processing through pipeline {pipeline_id}: {pipeline.name}")
            
            # Find matching source nodes
            for source_node in pipeline.get_source_nodes():
                node_source_type = source_node.data.get("source_type", "")
                self.logger.info(f"[PIPELINE] Source node {source_node.id} has source_type: {node_source_type}")
                if node_source_type == source_type:
                    # Process through this pipeline starting from source
                    pipeline_results = await self._process_pipeline(
                        pipeline, source_node.id, event
                    )
                    results.extend(pipeline_results)
        
        return results
    
    async def _process_pipeline(
        self, 
        pipeline: Pipeline, 
        start_node_id: str, 
        event: SignalEvent
    ) -> List[ActionResult]:
        """Process event through a single pipeline from start node"""
        results = []
        
        # BFS through the pipeline graph
        queue = [(start_node_id, event.to_dict())]
        
        while queue:
            current_node_id, event_data = queue.pop(0)
            current_node = pipeline.nodes.get(current_node_id)
            
            if not current_node:
                continue
            
            # Notify event processing
            await self._notify_event(event, pipeline.id, current_node_id)
            
            self.logger.info(f"[PIPELINE-TRACE] Visiting node {current_node_id} (Type: {current_node.type})")
            
            # Process based on node type
            if current_node.type == "source":
                # Source nodes just pass through
                pass
            
            elif current_node.type == "filter":
                # Apply filter
                if current_node.filter:
                    if not current_node.filter.evaluate(event_data):
                        self.logger.info(f"[PIPELINE-TRACE] Filter blocked event at node {current_node_id}")
                        # Event filtered out, don't continue this path
                        continue
                    else:
                        self.logger.info(f"[PIPELINE-TRACE] Filter passed event at node {current_node_id}")
            
            elif current_node.type == "transformer":
                # Apply transformation
                if current_node.transformer:
                    event_data = current_node.transformer.transform(event_data)
            
            elif current_node.type == "action":
                # Execute action
                if current_node.action:
                    self.logger.info(f"[PIPELINE-TRACE] Executing action at node {current_node_id}")
                    context = {
                        "event": event_data,
                        "pipeline_id": pipeline.id,
                        "node_id": current_node_id,
                        "params": current_node.data.get("params", {})
                    }
                    
                    # Check execution policy
                    if current_node.policy:
                        should_execute = await current_node.policy.should_execute(
                            f"{pipeline.id}_{current_node_id}",
                            context
                        )
                        if not should_execute:
                            self.logger.debug(f"Action skipped by policy: {current_node_id}")
                            continue
                    
                    # Execute action
                    result = await current_node.action.safe_execute(context)
                    self.logger.info(f"[PIPELINE-TRACE] Action Result: status={result.status}, message='{result.message}', error='{result.error}'")
                    results.append(result)
                    
                    # Update policy state
                    if current_node.policy:
                        await current_node.policy.on_execute(
                            f"{pipeline.id}_{current_node_id}",
                            context
                        )
                    
                    # Notify action execution
                    await self._notify_action(result, pipeline.id, current_node_id)
            
            # Add connected nodes to queue
            connected_nodes = pipeline.get_connected_nodes(current_node_id)
            self.logger.info(f"[PIPELINE-TRACE] Node {current_node_id} has {len(connected_nodes)} connections: {[n.id for n in connected_nodes]}")
            
            for next_node in connected_nodes:
                queue.append((next_node.id, event_data.copy()))
        
        return results
    
    def get_pipeline_status(self, pipeline_id: int) -> Optional[dict]:
        """Get status of a pipeline"""
        pipeline = self.pipelines.get(pipeline_id)
        if not pipeline:
            return None
        
        return {
            "id": pipeline.id,
            "name": pipeline.name,
            "is_active": pipeline.is_active,
            "node_count": len(pipeline.nodes),
            "edge_count": len(pipeline.edges),
            "source_types": [
                n.data.get("source_type") 
                for n in pipeline.get_source_nodes()
            ]
        }
    
    def set_pipeline_active(self, pipeline_id: int, active: bool) -> bool:
        """Enable or disable a pipeline"""
        pipeline = self.pipelines.get(pipeline_id)
        if not pipeline:
            return False
        
        pipeline.is_active = active
        return True
    
    def get_all_pipelines(self) -> List[dict]:
        """Get status of all pipelines"""
        return [
            self.get_pipeline_status(pid) 
            for pid in self.pipelines.keys()
        ]
