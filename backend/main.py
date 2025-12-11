"""
SignalDock - Universal System Signal Router & Visual Pipeline Builder

Main FastAPI application entry point.
"""
import asyncio
import uuid
from contextlib import asynccontextmanager
from typing import Optional, List
from datetime import datetime
import logging

from fastapi import FastAPI, WebSocket, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import get_config, AppConfig
from database import init_db, get_db, Pipeline as PipelineModel, ActionLog, EventLog
from database.connection import get_db_session
from signals import (
    CPUSignalSource, BatterySignalSource, NetworkSignalSource,
    FilesystemSignalSource, WindowFocusSignalSource
)
from signals.base import SignalEvent
from signals.stubs import SensoryNetSignalSource, PulseMeshSignalSource
from actions import list_actions
from pipeline import PipelineExecutor
from websocket import WebSocketHandler, ConnectionManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global instances
config: AppConfig = get_config()
connection_manager = ConnectionManager()
ws_handler = WebSocketHandler(connection_manager)
pipeline_executor = PipelineExecutor()
signal_sources = []


async def start_signal_sources():
    """Initialize and start all signal sources"""
    global signal_sources
    
    # Create signal sources - Real system signals only
    signal_sources = [
        CPUSignalSource(),
        BatterySignalSource(),
        NetworkSignalSource(),
        WindowFocusSignalSource(),
    ]
    
    # Subscribe pipeline executor to events
    async def handle_event(event: SignalEvent):
        # Broadcast to WebSocket clients
        await ws_handler.broadcast_event(event)
        # Process through pipelines
        await pipeline_executor.process_event(event)
    
    # Start sources and subscribe
    for source in signal_sources:
        source.subscribe(handle_event)
        await source.start()
        logger.info(f"Started signal source: {source.name}")


async def stop_signal_sources():
    """Stop all signal sources"""
    for source in signal_sources:
        await source.stop()
        logger.info(f"Stopped signal source: {source.name}")


async def load_active_pipelines():
    """Load all active pipelines from database into executor"""
    from sqlalchemy import select
    
    async for session in get_db_session():
        try:
            result = await session.execute(
                select(PipelineModel).where(PipelineModel.is_active == True)
            )
            pipelines = result.scalars().all()
            
            for pipeline in pipelines:
                pipeline_executor.load_pipeline(
                    pipeline.id,
                    pipeline.name,
                    pipeline.nodes,
                    pipeline.edges
                )
                logger.info(f"Loaded active pipeline: {pipeline.name} (ID: {pipeline.id})")
            
            logger.info(f"Loaded {len(pipelines)} active pipelines from database")
        except Exception as e:
            logger.error(f"Error loading pipelines: {e}")
        break  # Only need one session iteration

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler"""
    # Startup
    logger.info("Starting SignalDock...")
    await init_db()
    
    # Load active pipelines from database
    await load_active_pipelines()
    
    await start_signal_sources()
    
    # Register pipeline executor callbacks
    pipeline_executor.on_action(
        lambda result, pid, nid: ws_handler.broadcast_action(result, pid, nid)
    )
    
    yield
    
    # Shutdown
    logger.info("Shutting down SignalDock...")
    await stop_signal_sources()


# Create FastAPI app
app = FastAPI(
    title="SignalDock",
    description="Universal System Signal Router & Visual Pipeline Builder",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============ Pydantic Models ============

class PipelineCreate(BaseModel):
    name: str
    description: Optional[str] = None
    nodes: list
    edges: list
    is_active: bool = True


class PipelineUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    nodes: Optional[list] = None
    edges: Optional[list] = None
    is_active: Optional[bool] = None


class PermissionUpdate(BaseModel):
    permission_type: str
    granted: bool


# ============ WebSocket Endpoint ============

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, client_id: Optional[str] = Query(None)):
    """WebSocket endpoint for real-time communication"""
    if not client_id:
        client_id = str(uuid.uuid4())
    
    await ws_handler.handle_connection(websocket, client_id)


# ============ Pipeline Endpoints ============

@app.get("/api/pipelines")
async def get_pipelines(db=Depends(get_db_session)):
    """Get all pipelines"""
    from sqlalchemy import select
    
    result = await db.execute(select(PipelineModel))
    pipelines = result.scalars().all()
    return [p.to_dict() for p in pipelines]


@app.post("/api/pipelines")
async def create_pipeline(pipeline: PipelineCreate, db=Depends(get_db_session)):
    """Create a new pipeline"""
    db_pipeline = PipelineModel(
        name=pipeline.name,
        description=pipeline.description,
        nodes=pipeline.nodes,
        edges=pipeline.edges,
        is_active=pipeline.is_active
    )
    db.add(db_pipeline)
    await db.commit()
    await db.refresh(db_pipeline)
    
    # Load into executor if active
    if pipeline.is_active:
        pipeline_executor.load_pipeline(
            db_pipeline.id,
            db_pipeline.name,
            db_pipeline.nodes,
            db_pipeline.edges
        )
    
    return db_pipeline.to_dict()


@app.get("/api/pipelines/{pipeline_id}")
async def get_pipeline(pipeline_id: int, db=Depends(get_db_session)):
    """Get a specific pipeline"""
    from sqlalchemy import select
    
    result = await db.execute(
        select(PipelineModel).where(PipelineModel.id == pipeline_id)
    )
    pipeline = result.scalar_one_or_none()
    
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    
    return pipeline.to_dict()


@app.put("/api/pipelines/{pipeline_id}")
async def update_pipeline(pipeline_id: int, update: PipelineUpdate, db=Depends(get_db_session)):
    """Update an existing pipeline"""
    from sqlalchemy import select
    
    result = await db.execute(
        select(PipelineModel).where(PipelineModel.id == pipeline_id)
    )
    pipeline = result.scalar_one_or_none()
    
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    
    # Update fields
    if update.name is not None:
        pipeline.name = update.name
    if update.description is not None:
        pipeline.description = update.description
    if update.nodes is not None:
        pipeline.nodes = update.nodes
    if update.edges is not None:
        pipeline.edges = update.edges
    if update.is_active is not None:
        pipeline.is_active = update.is_active
    
    pipeline.updated_at = datetime.utcnow()
    await db.commit()
    
    # Reload in executor
    pipeline_executor.unload_pipeline(pipeline_id)
    if pipeline.is_active:
        pipeline_executor.load_pipeline(
            pipeline.id,
            pipeline.name,
            pipeline.nodes,
            pipeline.edges
        )
    
    return pipeline.to_dict()


@app.delete("/api/pipelines/{pipeline_id}")
async def delete_pipeline(pipeline_id: int, db=Depends(get_db_session)):
    """Delete a pipeline"""
    from sqlalchemy import select, delete
    
    result = await db.execute(
        select(PipelineModel).where(PipelineModel.id == pipeline_id)
    )
    pipeline = result.scalar_one_or_none()
    
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    
    await db.execute(
        delete(PipelineModel).where(PipelineModel.id == pipeline_id)
    )
    await db.commit()
    
    pipeline_executor.unload_pipeline(pipeline_id)
    
    return {"message": "Pipeline deleted"}


@app.post("/api/pipelines/{pipeline_id}/toggle")
async def toggle_pipeline(pipeline_id: int, db=Depends(get_db_session)):
    """Toggle pipeline active state"""
    from sqlalchemy import select
    
    result = await db.execute(
        select(PipelineModel).where(PipelineModel.id == pipeline_id)
    )
    pipeline = result.scalar_one_or_none()
    
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    
    pipeline.is_active = not pipeline.is_active
    pipeline.updated_at = datetime.utcnow()
    await db.commit()
    
    # Update executor
    if pipeline.is_active:
        pipeline_executor.load_pipeline(
            pipeline.id,
            pipeline.name,
            pipeline.nodes,
            pipeline.edges
        )
    else:
        pipeline_executor.unload_pipeline(pipeline_id)
    
    return pipeline.to_dict()


# ============ Signal Source Endpoints ============

@app.get("/api/signals")
async def get_signal_sources():
    """Get all available signal sources"""
    from signals import list_signal_sources
    return list_signal_sources()


@app.get("/api/signals/status")
async def get_signal_status():
    """Get current status of all signal sources"""
    return [source.get_status() for source in signal_sources]


@app.get("/api/signals/{source_type}/current")
async def get_current_signal_values(source_type: str):
    """Get current values from a signal source"""
    for source in signal_sources:
        if source.source_type == source_type:
            if hasattr(source, 'get_current_values'):
                return source.get_current_values()
            else:
                return source.get_status()
    
    raise HTTPException(status_code=404, detail="Signal source not found")


# ============ Action Endpoints ============

@app.get("/api/actions")
async def get_actions():
    """Get all available actions"""
    return list_actions()


@app.get("/api/actions/logs")
async def get_action_logs(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db=Depends(get_db_session)
):
    """Get action execution logs"""
    from sqlalchemy import select
    
    result = await db.execute(
        select(ActionLog)
        .order_by(ActionLog.timestamp.desc())
        .limit(limit)
        .offset(offset)
    )
    logs = result.scalars().all()
    return [log.to_dict() for log in logs]


# ============ Event Endpoints ============

@app.get("/api/events/logs")
async def get_event_logs(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    source_type: Optional[str] = None,
    db=Depends(get_db_session)
):
    """Get signal event logs"""
    from sqlalchemy import select
    
    query = select(EventLog).order_by(EventLog.timestamp.desc())
    
    if source_type:
        query = query.where(EventLog.source_type == source_type)
    
    result = await db.execute(query.limit(limit).offset(offset))
    logs = result.scalars().all()
    return [log.to_dict() for log in logs]


# ============ Templates Endpoints ============

@app.get("/api/templates")
async def get_templates(db=Depends(get_db_session)):
    """Get pipeline templates"""
    from sqlalchemy import select
    
    result = await db.execute(
        select(PipelineModel).where(PipelineModel.is_template == True)
    )
    templates = result.scalars().all()
    return [t.to_dict() for t in templates]


@app.post("/api/templates/{template_id}/import")
async def import_template(template_id: int, db=Depends(get_db_session)):
    """Import a template as a new pipeline"""
    from sqlalchemy import select
    
    result = await db.execute(
        select(PipelineModel).where(
            PipelineModel.id == template_id,
            PipelineModel.is_template == True
        )
    )
    template = result.scalar_one_or_none()
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    # Create new pipeline from template
    new_pipeline = PipelineModel(
        name=f"{template.name} (copy)",
        description=template.description,
        nodes=template.nodes,
        edges=template.edges,
        is_active=False,
        is_template=False
    )
    db.add(new_pipeline)
    await db.commit()
    await db.refresh(new_pipeline)
    
    return new_pipeline.to_dict()


# ============ System Endpoints ============

@app.get("/api/system/status")
async def get_system_status():
    """Get overall system status"""
    return {
        "status": "running",
        "signal_sources": len(signal_sources),
        "active_pipelines": len(pipeline_executor.pipelines),
        "websocket_clients": connection_manager.get_connection_count(),
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/api/system/config")
async def get_system_config():
    """Get current configuration (non-sensitive)"""
    return {
        "app_name": config.app_name,
        "version": config.version,
        "signals": {
            "cpu_poll_interval": config.signals.cpu_poll_interval,
            "battery_poll_interval": config.signals.battery_poll_interval,
            "network_poll_interval": config.signals.network_poll_interval,
        },
        "permissions": {
            "clipboard_enabled": config.permissions.clipboard_enabled,
            "microphone_enabled": config.permissions.microphone_enabled,
            "shell_execution_enabled": config.permissions.shell_execution_enabled,
            "file_operations_enabled": config.permissions.file_operations_enabled,
            "process_control_enabled": config.permissions.process_control_enabled,
            "network_control_enabled": config.permissions.network_control_enabled,
        }
    }


@app.put("/api/system/permissions")
async def update_permission(update: PermissionUpdate):
    """Update a permission setting"""
    global config
    
    perm_map = {
        "clipboard": "clipboard_enabled",
        "microphone": "microphone_enabled",
        "shell_execution": "shell_execution_enabled",
        "file_operations": "file_operations_enabled",
        "process_control": "process_control_enabled",
        "network_control": "network_control_enabled",
    }
    
    attr_name = perm_map.get(update.permission_type)
    if not attr_name:
        raise HTTPException(status_code=400, detail="Unknown permission type")
    
    setattr(config.permissions, attr_name, update.granted)
    
    return {"message": f"Permission '{update.permission_type}' updated", "granted": update.granted}


# ============ Health Check ============

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=True
    )
