"""
SignalDock Database Models
"""
from datetime import datetime
from typing import Optional, List, Any
from sqlalchemy import String, Boolean, DateTime, Text, ForeignKey, Float, JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all models"""
    pass


class Pipeline(Base):
    """Pipeline storage model"""
    __tablename__ = "pipelines"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    nodes: Mapped[List[Any]] = mapped_column(JSON, nullable=False, default=list)
    edges: Mapped[List[Any]] = mapped_column(JSON, nullable=False, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_template: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    action_logs: Mapped[List["ActionLog"]] = relationship(back_populates="pipeline", cascade="all, delete-orphan")
    
    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "nodes": self.nodes,
            "edges": self.edges,
            "is_active": self.is_active,
            "is_template": self.is_template,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class ActionLog(Base):
    """Action execution log model"""
    __tablename__ = "action_logs"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    pipeline_id: Mapped[Optional[int]] = mapped_column(ForeignKey("pipelines.id"), nullable=True)
    action_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    action_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    result: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    execution_time_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    trigger_event_id: Mapped[Optional[int]] = mapped_column(ForeignKey("event_logs.id"), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    pipeline: Mapped[Optional["Pipeline"]] = relationship(back_populates="action_logs")
    trigger_event: Mapped[Optional["EventLog"]] = relationship(back_populates="triggered_actions")
    
    def to_dict(self):
        return {
            "id": self.id,
            "pipeline_id": self.pipeline_id,
            "action_type": self.action_type,
            "action_name": self.action_name,
            "status": self.status,
            "result": self.result,
            "error_message": self.error_message,
            "execution_time_ms": self.execution_time_ms,
            "trigger_event_id": self.trigger_event_id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None
        }


class EventLog(Base):
    """Signal event log model"""
    __tablename__ = "event_logs"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    source_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    event_data: Mapped[Any] = mapped_column(JSON, nullable=False)
    event_metadata: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    triggered_actions: Mapped[List["ActionLog"]] = relationship(back_populates="trigger_event")
    
    def to_dict(self):
        return {
            "id": self.id,
            "source_type": self.source_type,
            "source_name": self.source_name,
            "event_type": self.event_type,
            "event_data": self.event_data,
            "event_metadata": self.event_metadata,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None
        }


class Permission(Base):
    """Permission grants model"""
    __tablename__ = "permissions"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    permission_type: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    granted: Mapped[bool] = mapped_column(Boolean, default=False)
    granted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Permission types
    SHELL_EXECUTION = "shell_execution"
    FILE_OPERATIONS = "file_operations"
    PROCESS_CONTROL = "process_control"
    NETWORK_CONTROL = "network_control"
    CLIPBOARD_ACCESS = "clipboard_access"
    MICROPHONE_ACCESS = "microphone_access"
    
    def to_dict(self):
        return {
            "id": self.id,
            "permission_type": self.permission_type,
            "description": self.description,
            "granted": self.granted,
            "granted_at": self.granted_at.isoformat() if self.granted_at else None,
            "revoked_at": self.revoked_at.isoformat() if self.revoked_at else None
        }


class Setting(Base):
    """Application settings storage"""
    __tablename__ = "settings"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    value: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            "id": self.id,
            "key": self.key,
            "value": self.value,
            "description": self.description,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
