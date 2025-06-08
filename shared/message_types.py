from dataclasses import dataclass
from typing import Dict, Any, List, Optional
from datetime import datetime

@dataclass
class WorkflowRequest:
    workflow_id: str
    workflow_type: str
    parameters: Dict[str, Any]
    requester_id: str
    priority: int = 5
    timeout: int = 300

@dataclass
class WorkflowResponse:
    workflow_id: str
    status: str  # "completed", "failed", "in_progress"
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    agent_id: str = ""

@dataclass
class TaskAssignment:
    task_id: str
    task_type: str
    assigned_to: str
    parameters: Dict[str, Any]
    deadline: datetime
    dependencies: List[str] = None

@dataclass
class AgentCapability:
    agent_id: str
    capabilities: List[str]
    load: float  # 0.0 to 1.0
    status: str  # "available", "busy", "offline"

@dataclass
class MetricReport:
    agent_id: str
    timestamp: datetime
    metrics: Dict[str, float]
    tags: Dict[str, str] = None
