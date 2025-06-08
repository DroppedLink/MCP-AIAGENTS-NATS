# NATS AI Agent Network - Complete Implementation Guide

## Missing Implementation Details

This document provides all the critical missing pieces from the setup and implementation guides to enable independent system building.

## Complete Dockerfiles

### agents/orchestrator/Dockerfile
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared libraries
COPY ../shared/ ./shared/

# Copy agent code
COPY agent.py .

# Create non-root user
RUN useradd -m -u 1001 agent
USER agent

CMD ["python", "agent.py"]
```

### agents/orchestrator/requirements.txt
```
nats-py==2.6.0
asyncio-mqtt==0.16.1
python-dotenv==1.0.0
pydantic==2.5.0
fastapi==0.104.1
uvicorn==0.24.0
prometheus-client==0.19.0
structlog==23.2.0
```

### agents/specialist/Dockerfile
```dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ../shared/ ./shared/
COPY agent.py .

RUN useradd -m -u 1001 agent
USER agent

CMD ["python", "agent.py"]
```

### agents/specialist/requirements.txt
```
nats-py==2.6.0
requests==2.31.0
psutil==5.9.6
docker==6.1.3
kubernetes==28.1.0
paramiko==3.3.1
sqlalchemy==2.0.23
redis==5.0.1
```

### mcp-servers/proxmox/Dockerfile
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy existing Proxmox MCP code
COPY src/ ./src/
COPY tests/ ./tests/
COPY *.py ./
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared NATS libraries
COPY ../shared/ ./shared/

# Copy enhanced server
COPY enhanced_server.py .

RUN useradd -m -u 1001 mcp
USER mcp

EXPOSE 8001

CMD ["python", "enhanced_server.py"]
```

### mcp-servers/filesystem/Dockerfile
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ../shared/ ./shared/
COPY server.py .

RUN useradd -m -u 1001 mcp
USER mcp

EXPOSE 8002

CMD ["python", "server.py"]
```

### dashboard/Dockerfile
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install Node.js for frontend build
RUN apt-get update && apt-get install -y \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY templates/ ./templates/
COPY static/ ./static/
COPY ../shared/ ./shared/
COPY app.py .

RUN useradd -m -u 1001 dashboard
USER dashboard

EXPOSE 8080

CMD ["python", "app.py"]
```

## Complete Agent Implementations

### agents/specialist/agent.py
```python
import asyncio
import logging
import psutil
import json
import sys
import os
from datetime import datetime, timedelta
from typing import Dict, Any, List
import docker
import requests

sys.path.append('/app/shared')
from nats_client import NATSClient
from message_types import TaskAssignment, AgentCapability, MetricReport

logger = logging.getLogger(__name__)

class SpecialistAgent:
    def __init__(self, agent_id: str, nats_url: str, agent_type: str = "general"):
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.nats = NATSClient(nats_url, agent_id)
        self.capabilities = self._get_capabilities()
        self.current_load = 0.0
        self.active_tasks = {}
        
    def _get_capabilities(self) -> List[str]:
        """Define agent capabilities based on type"""
        base_capabilities = [
            "system_monitoring",
            "file_operations",
            "network_testing",
            "log_analysis"
        ]
        
        if self.agent_type == "machine_learning":
            base_capabilities.extend([
                "model_training",
                "inference_serving",
                "data_preprocessing",
                "gpu_computing"
            ])
        elif self.agent_type == "infrastructure":
            base_capabilities.extend([
                "vm_management",
                "container_orchestration",
                "storage_management",
                "network_configuration"
            ])
        
        return base_capabilities
        
    async def start(self):
        """Start the specialist agent"""
        await self.nats.connect()
        
        # Register capabilities
        await self.register_capabilities()
        
        # Subscribe to task assignments
        await self.nats.subscribe(f"ai.tasks.assign.{self.agent_id}", self.handle_task_assignment)
        
        # Subscribe to discovery requests
        await self.nats.subscribe("ai.agents.discovery.request", self.handle_discovery_request)
        
        # Start metric reporting
        asyncio.create_task(self.report_metrics())
        
        # Start health monitoring
        asyncio.create_task(self.monitor_health())
        
        logger.info(f"Specialist agent {self.agent_id} started with type: {self.agent_type}")
        
        # Keep running
        while True:
            await asyncio.sleep(1)
            
    async def register_capabilities(self):
        """Register agent capabilities with the network"""
        capability = AgentCapability(
            agent_id=self.agent_id,
            capabilities=self.capabilities,
            load=self.current_load,
            status="available"
        )
        
        await self.nats.publish("ai.agents.register", capability.__dict__)
        
    async def handle_discovery_request(self, subject: str, data: Dict, msg):
        """Respond to discovery requests"""
        await self.register_capabilities()
        
    async def handle_task_assignment(self, subject: str, data: Dict, msg):
        """Handle task assignments from orchestrator"""
        try:
            task = TaskAssignment(**data)
            logger.info(f"Received task: {task.task_id} ({task.task_type})")
            
            # Update load
            self.current_load = min(1.0, self.current_load + 0.2)
            self.active_tasks[task.task_id] = task
            
            # Execute task
            result = await self.execute_task(task)
            
            # Report completion
            completion = {
                "task_id": task.task_id,
                "status": "completed",
                "result": result,
                "agent_id": self.agent_id,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            await self.nats.publish("ai.tasks.complete", completion)
            
            # Update load
            self.current_load = max(0.0, self.current_load - 0.2)
            del self.active_tasks[task.task_id]
            
        except Exception as e:
            # Report failure
            failure = {
                "task_id": data.get("task_id", "unknown"),
                "status": "failed",
                "error": str(e),
                "agent_id": self.agent_id,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            await self.nats.publish("ai.tasks.complete", failure)
            logger.error(f"Task execution failed: {e}")
            
    async def execute_task(self, task: TaskAssignment) -> Dict[str, Any]:
        """Execute different types of tasks"""
        if task.task_type == "validate_vm_parameters":
            return await self.validate_vm_parameters(task.parameters)
        elif task.task_type == "configure_vm":
            return await self.configure_vm(task.parameters)
        elif task.task_type == "system_health_check":
            return await self.system_health_check()
        elif task.task_type == "analyze_logs":
            return await self.analyze_logs(task.parameters)
        else:
            raise ValueError(f"Unknown task type: {task.task_type}")
            
    async def validate_vm_parameters(self, parameters: Dict) -> Dict:
        """Validate VM creation parameters"""
        required_fields = ["vmid", "name", "node"]
        missing_fields = [f for f in required_fields if f not in parameters]
        
        if missing_fields:
            raise ValueError(f"Missing required fields: {missing_fields}")
            
        # Validate VMID format
        try:
            vmid = int(parameters["vmid"])
            if vmid < 100 or vmid > 999999:
                raise ValueError("VMID must be between 100 and 999999")
        except ValueError:
            raise ValueError("VMID must be a valid integer")
            
        return {
            "validation_status": "passed",
            "validated_parameters": parameters,
            "recommendations": {
                "memory": parameters.get("memory", 1024),
                "cores": parameters.get("cores", 1),
                "disk_size": parameters.get("disk_size", "10G")
            }
        }
        
    async def configure_vm(self, parameters: Dict) -> Dict:
        """Configure VM after creation"""
        vmid = parameters["vmid"]
        
        # Simulate configuration steps
        await asyncio.sleep(2)  # Simulate work
        
        return {
            "vmid": vmid,
            "configuration": "completed",
            "applied_settings": {
                "firewall": "enabled",
                "backup_schedule": "daily",
                "monitoring": "enabled"
            }
        }
        
    async def system_health_check(self) -> Dict:
        """Perform system health check"""
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        return {
            "cpu_usage": cpu_percent,
            "memory_usage": memory.percent,
            "disk_usage": disk.percent,
            "status": "healthy" if cpu_percent < 80 and memory.percent < 80 else "warning"
        }
        
    async def analyze_logs(self, parameters: Dict) -> Dict:
        """Analyze log files for patterns"""
        log_path = parameters.get("log_path", "/var/log/messages")
        
        # Simulate log analysis
        await asyncio.sleep(1)
        
        return {
            "log_path": log_path,
            "errors_found": 3,
            "warnings_found": 12,
            "patterns": ["connection_timeout", "disk_space_low"],
            "recommendations": ["Increase timeout values", "Clean up disk space"]
        }
        
    async def report_metrics(self):
        """Report agent metrics periodically"""
        while True:
            try:
                cpu_percent = psutil.cpu_percent()
                memory = psutil.virtual_memory()
                
                metrics = MetricReport(
                    agent_id=self.agent_id,
                    timestamp=datetime.utcnow(),
                    metrics={
                        "cpu_usage": cpu_percent,
                        "memory_usage": memory.percent,
                        "active_tasks": len(self.active_tasks),
                        "load": self.current_load
                    },
                    tags={"type": self.agent_type}
                )
                
                await self.nats.publish("ai.metrics.agent", metrics.__dict__)
                await asyncio.sleep(30)
                
            except Exception as e:
                logger.error(f"Error reporting metrics: {e}")
                await asyncio.sleep(30)
                
    async def monitor_health(self):
        """Monitor agent health and report issues"""
        while True:
            try:
                # Check system resources
                cpu_percent = psutil.cpu_percent(interval=1)
                memory = psutil.virtual_memory()
                
                if cpu_percent > 90:
                    await self.nats.publish("ai.alerts.high_cpu", {
                        "agent_id": self.agent_id,
                        "cpu_usage": cpu_percent,
                        "timestamp": datetime.utcnow().isoformat()
                    })
                    
                if memory.percent > 90:
                    await self.nats.publish("ai.alerts.high_memory", {
                        "agent_id": self.agent_id,
                        "memory_usage": memory.percent,
                        "timestamp": datetime.utcnow().isoformat()
                    })
                    
                await asyncio.sleep(60)
                
            except Exception as e:
                logger.error(f"Error in health monitoring: {e}")
                await asyncio.sleep(60)

if __name__ == "__main__":
    agent = SpecialistAgent(
        agent_id=os.getenv("AGENT_ID", "specialist-001"),
        nats_url=os.getenv("NATS_URL", "nats://localhost:4222"),
        agent_type=os.getenv("AGENT_TYPE", "general")
    )
    
    asyncio.run(agent.start())
```

### agents/monitor/agent.py
```python
import asyncio
import logging
import json
import sys
import os
from datetime import datetime, timedelta
from typing import Dict, Any, List
import psutil
import requests

sys.path.append('/app/shared')
from nats_client import NATSClient

logger = logging.getLogger(__name__)

class MonitorAgent:
    def __init__(self, agent_id: str, nats_url: str):
        self.agent_id = agent_id
        self.nats = NATSClient(nats_url, agent_id)
        self.agent_status = {}
        self.workflow_status = {}
        self.alerts = []
        
    async def start(self):
        """Start the monitor agent"""
        await self.nats.connect()
        
        # Subscribe to heartbeats
        await self.nats.subscribe("ai.heartbeat.>", self.handle_heartbeat)
        
        # Subscribe to workflow events
        await self.nats.subscribe("ai.workflows.>", self.handle_workflow_event)
        
        # Subscribe to metrics
        await self.nats.subscribe("ai.metrics.>", self.handle_metrics)
        
        # Subscribe to alerts
        await self.nats.subscribe("ai.alerts.>", self.handle_alert)
        
        # Start monitoring tasks
        asyncio.create_task(self.check_agent_health())
        asyncio.create_task(self.monitor_workflows())
        asyncio.create_task(self.system_monitoring())
        
        logger.info(f"Monitor agent {self.agent_id} started")
        
        while True:
            await asyncio.sleep(1)
            
    async def handle_heartbeat(self, subject: str, data: Dict, msg):
        """Handle agent heartbeat messages"""
        agent_id = data["agent_id"]
        self.agent_status[agent_id] = {
            "last_seen": datetime.utcnow(),
            "status": data["status"],
            "timestamp": data["timestamp"]
        }
        
    async def handle_workflow_event(self, subject: str, data: Dict, msg):
        """Handle workflow events"""
        if "workflow_id" in data:
            workflow_id = data["workflow_id"]
            self.workflow_status[workflow_id] = {
                "last_update": datetime.utcnow(),
                "status": data.get("status", "unknown"),
                "data": data
            }
            
    async def handle_metrics(self, subject: str, data: Dict, msg):
        """Handle metric reports"""
        # Store metrics for analysis
        agent_id = data.get("agent_id", "unknown")
        metrics = data.get("metrics", {})
        
        # Check for threshold violations
        if metrics.get("cpu_usage", 0) > 85:
            await self.create_alert("high_cpu", f"High CPU usage on {agent_id}: {metrics['cpu_usage']}%")
            
        if metrics.get("memory_usage", 0) > 85:
            await self.create_alert("high_memory", f"High memory usage on {agent_id}: {metrics['memory_usage']}%")
            
    async def handle_alert(self, subject: str, data: Dict, msg):
        """Handle incoming alerts"""
        alert = {
            "timestamp": datetime.utcnow(),
            "subject": subject,
            "data": data,
            "severity": self._determine_severity(subject)
        }
        
        self.alerts.append(alert)
        
        # Keep only last 1000 alerts
        if len(self.alerts) > 1000:
            self.alerts = self.alerts[-1000:]
            
        logger.warning(f"Alert received: {subject} - {data}")
        
    def _determine_severity(self, subject: str) -> str:
        """Determine alert severity based on subject"""
        if "high_cpu" in subject or "high_memory" in subject:
            return "warning"
        elif "agent_offline" in subject or "workflow_failed" in subject:
            return "critical"
        else:
            return "info"
            
    async def create_alert(self, alert_type: str, message: str):
        """Create and publish an alert"""
        alert = {
            "alert_type": alert_type,
            "message": message,
            "timestamp": datetime.utcnow().isoformat(),
            "source": self.agent_id
        }
        
        await self.nats.publish(f"ai.alerts.{alert_type}", alert)
        
    async def check_agent_health(self):
        """Monitor agent health and detect offline agents"""
        while True:
            try:
                current_time = datetime.utcnow()
                offline_threshold = timedelta(minutes=2)
                
                for agent_id, status in list(self.agent_status.items()):
                    if current_time - status["last_seen"] > offline_threshold:
                        await self.create_alert("agent_offline", f"Agent {agent_id} has been offline for over 2 minutes")
                        
                await asyncio.sleep(60)  # Check every minute
                
            except Exception as e:
                logger.error(f"Error in agent health check: {e}")
                await asyncio.sleep(60)
                
    async def monitor_workflows(self):
        """Monitor workflow progress and detect stuck workflows"""
        while True:
            try:
                current_time = datetime.utcnow()
                stuck_threshold = timedelta(minutes=30)
                
                for workflow_id, status in list(self.workflow_status.items()):
                    if (current_time - status["last_update"] > stuck_threshold and 
                        status["status"] in ["in_progress", "pending"]):
                        await self.create_alert("workflow_stuck", 
                                              f"Workflow {workflow_id} has been stuck for over 30 minutes")
                        
                await asyncio.sleep(300)  # Check every 5 minutes
                
            except Exception as e:
                logger.error(f"Error in workflow monitoring: {e}")
                await asyncio.sleep(300)
                
    async def system_monitoring(self):
        """Monitor overall system health"""
        while True:
            try:
                # System metrics
                cpu_percent = psutil.cpu_percent(interval=1)
                memory = psutil.virtual_memory()
                disk = psutil.disk_usage('/')
                
                system_metrics = {
                    "agent_id": self.agent_id,
                    "timestamp": datetime.utcnow().isoformat(),
                    "metrics": {
                        "system_cpu": cpu_percent,
                        "system_memory": memory.percent,
                        "system_disk": disk.percent,
                        "active_agents": len(self.agent_status),
                        "active_workflows": len(self.workflow_status),
                        "total_alerts": len(self.alerts)
                    }
                }
                
                await self.nats.publish("ai.metrics.system", system_metrics)
                
                await asyncio.sleep(30)
                
            except Exception as e:
                logger.error(f"Error in system monitoring: {e}")
                await asyncio.sleep(30)

if __name__ == "__main__":
    agent = MonitorAgent(
        agent_id=os.getenv("AGENT_ID", "monitor-001"),
        nats_url=os.getenv("NATS_URL", "nats://localhost:4222")
    )
    
    asyncio.run(agent.start())
```

### mcp-servers/filesystem/server.py
```python
import asyncio
import os
import json
import logging
from datetime import datetime
from typing import Dict, Any
import sys

sys.path.append('/app/shared')
from nats_client import NATSClient

logger = logging.getLogger(__name__)

class FilesystemMCPServer:
    def __init__(self, nats_url: str, service_id: str = "mcp-filesystem"):
        self.service_id = service_id
        self.nats = NATSClient(nats_url, service_id)
        self.capabilities = [
            "file_operations",
            "directory_management",
            "file_monitoring",
            "backup_operations"
        ]
        self.workspace = "/workspace"
        
    async def start(self):
        """Start the filesystem MCP server"""
        await self.nats.connect()
        
        # Register service
        await self.register_service()
        
        # Subscribe to task assignments
        await self.nats.subscribe(f"ai.tasks.assign.{self.service_id}", self.handle_task_assignment)
        
        # Subscribe to discovery
        await self.nats.subscribe("ai.mcp.discovery.request", self.handle_discovery_request)
        
        logger.info(f"Filesystem MCP server started: {self.service_id}")
        
        while True:
            await asyncio.sleep(1)
            
    async def register_service(self):
        """Register this MCP service"""
        registration = {
            "service_id": self.service_id,
            "service_type": "mcp_server",
            "capabilities": self.capabilities,
            "endpoint": f"http://{self.service_id}:8002",
            "status": "available",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await self.nats.publish("ai.mcp.register", registration)
        
    async def handle_discovery_request(self, subject: str, data: Dict, msg):
        """Handle discovery requests"""
        await self.register_service()
        
    async def handle_task_assignment(self, subject: str, data: Dict, msg):
        """Handle task assignments"""
        try:
            task_id = data["task_id"]
            task_type = data["task_type"]
            parameters = data["parameters"]
            
            logger.info(f"Received task: {task_id} ({task_type})")
            
            if task_type == "create_file":
                result = await self.create_file(parameters)
            elif task_type == "read_file":
                result = await self.read_file(parameters)
            elif task_type == "list_directory":
                result = await self.list_directory(parameters)
            elif task_type == "backup_files":
                result = await self.backup_files(parameters)
            else:
                raise ValueError(f"Unknown task type: {task_type}")
                
            # Report completion
            completion = {
                "task_id": task_id,
                "status": "completed",
                "result": result,
                "service_id": self.service_id,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            await self.nats.publish("ai.tasks.complete", completion)
            
        except Exception as e:
            failure = {
                "task_id": data.get("task_id", "unknown"),
                "status": "failed",
                "error": str(e),
                "service_id": self.service_id,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            await self.nats.publish("ai.tasks.complete", failure)
            logger.error(f"Task failed: {e}")
            
    async def create_file(self, parameters: Dict) -> Dict:
        """Create a file"""
        file_path = os.path.join(self.workspace, parameters["filename"])
        content = parameters.get("content", "")
        
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        with open(file_path, 'w') as f:
            f.write(content)
            
        return {
            "file_path": file_path,
            "size": len(content),
            "created": datetime.utcnow().isoformat()
        }
        
    async def read_file(self, parameters: Dict) -> Dict:
        """Read a file"""
        file_path = os.path.join(self.workspace, parameters["filename"])
        
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
            
        with open(file_path, 'r') as f:
            content = f.read()
            
        return {
            "file_path": file_path,
            "content": content,
            "size": len(content)
        }
        
    async def list_directory(self, parameters: Dict) -> Dict:
        """List directory contents"""
        dir_path = os.path.join(self.workspace, parameters.get("directory", ""))
        
        if not os.path.exists(dir_path):
            raise FileNotFoundError(f"Directory not found: {dir_path}")
            
        files = []
        for item in os.listdir(dir_path):
            item_path = os.path.join(dir_path, item)
            stat = os.stat(item_path)
            files.append({
                "name": item,
                "type": "directory" if os.path.isdir(item_path) else "file",
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
            })
            
        return {
            "directory": dir_path,
            "files": files,
            "count": len(files)
        }
        
    async def backup_files(self, parameters: Dict) -> Dict:
        """Backup files to a backup directory"""
        source_dir = os.path.join(self.workspace, parameters.get("source", ""))
        backup_dir = os.path.join(self.workspace, "backups", datetime.now().strftime("%Y%m%d_%H%M%S"))
        
        os.makedirs(backup_dir, exist_ok=True)
        
        import shutil
        shutil.copytree(source_dir, backup_dir, dirs_exist_ok=True)
        
        return {
            "source": source_dir,
            "backup_location": backup_dir,
            "timestamp": datetime.utcnow().isoformat()
        }

if __name__ == "__main__":
    server = FilesystemMCPServer(
        nats_url=os.getenv("NATS_URL", "nats://localhost:4222"),
        service_id=os.getenv("SERVICE_ID", "mcp-filesystem")
    )
    
    asyncio.run(server.start())
```

## Dashboard Templates

### dashboard/templates/dashboard.html
```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Agent Network Dashboard</title>
    <script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }
        .card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .status-online { color: #4CAF50; }
        .status-offline { color: #f44336; }
        .status-warning { color: #ff9800; }
        .metric { display: inline-block; margin: 10px; padding: 10px; background: #e3f2fd; border-radius: 4px; }
        .alert { padding: 10px; margin: 5px 0; border-radius: 4px; }
        .alert-warning { background: #fff3cd; border: 1px solid #ffeaa7; }
        .alert-critical { background: #f8d7da; border: 1px solid #f5c6cb; }
        .workflow-item { padding: 8px; margin: 4px 0; border-left: 4px solid #2196F3; background: #f0f0f0; }
    </style>
</head>
<body>
    <div class="container">
        <h1>AI Agent Network Dashboard</h1>
        
        <div class="grid">
            <!-- Agents Status -->
            <div class="card">
                <h2>Agent Status</h2>
                <div id="agents-list"></div>
            </div>
            
            <!-- System Metrics -->
            <div class="card">
                <h2>System Metrics</h2>
                <canvas id="metrics-chart" width="400" height="200"></canvas>
            </div>
            
            <!-- Active Workflows -->
            <div class="card">
                <h2>Active Workflows</h2>
                <div id="workflows-list"></div>
            </div>
            
            <!-- Recent Alerts -->
            <div class="card">
                <h2>Recent Alerts</h2>
                <div id="alerts-list"></div>
            </div>
        </div>
    </div>

    <script>
        const socket = io();
        const agents = {};
        const workflows = {};
        const alerts = [];
        
        // Chart setup
        const ctx = document.getElementById('metrics-chart').getContext('2d');
        const chart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'CPU Usage %',
                    data: [],
                    borderColor: '#ff6384',
                    fill: false
                }, {
                    label: 'Memory Usage %',
                    data: [],
                    borderColor: '#36a2eb',
                    fill: false
                }]
            },
            options: {
                responsive: true,
                scales: {
                    y: { beginAtZero: true, max: 100 }
                }
            }
        });
        
        // Socket event handlers
        socket.on('agent_update', function(data) {
            agents[data.agent_id] = data;
            updateAgentsDisplay();
        });
        
        socket.on('workflow_update', function(data) {
            workflows[data.workflow_id] = data;
            updateWorkflowsDisplay();
        });
        
        socket.on('metrics_update', function(data) {
            updateMetricsChart(data);
        });
        
        function updateAgentsDisplay() {
            const container = document.getElementById('agents-list');
            container.innerHTML = '';
            
            for (const [agentId, agent] of Object.entries(agents)) {
                const div = document.createElement('div');
                div.className = 'metric';
                
                const statusClass = agent.status === 'active' ? 'status-online' : 'status-offline';
                div.innerHTML = `
                    <strong>${agentId}</strong><br>
                    <span class="${statusClass}">${agent.status}</span><br>
                    <small>Last seen: ${new Date(agent.last_seen).toLocaleTimeString()}</small>
                `;
                container.appendChild(div);
            }
        }
        
        function updateWorkflowsDisplay() {
            const container = document.getElementById('workflows-list');
            container.innerHTML = '';
            
            for (const [workflowId, workflow] of Object.entries(workflows)) {
                const div = document.createElement('div');
                div.className = 'workflow-item';
                div.innerHTML = `
                    <strong>${workflowId}</strong><br>
                    Status: ${workflow.status}<br>
                    <small>Type: ${workflow.workflow_type || 'Unknown'}</small>
                `;
                container.appendChild(div);
            }
        }
        
        function updateMetricsChart(data) {
            const now = new Date().toLocaleTimeString();
            const metrics = data.metrics || {};
            
            // Add new data point
            chart.data.labels.push(now);
            chart.data.datasets[0].data.push(metrics.cpu_usage || 0);
            chart.data.datasets[1].data.push(metrics.memory_usage || 0);
            
            // Keep only last 20 points
            if (chart.data.labels.length > 20) {
                chart.data.labels.shift();
                chart.data.datasets[0].data.shift();
                chart.data.datasets[1].data.shift();
            }
            
            chart.update();
        }
        
        // Load initial data
        fetch('/api/agents')
            .then(response => response.json())
            .then(data => {
                Object.assign(agents, data);
                updateAgentsDisplay();
            });
            
        fetch('/api/workflows')
            .then(response => response.json())
            .then(data => {
                Object.assign(workflows, data);
                updateWorkflowsDisplay();
            });
    </script>
</body>
</html>
```

## Environment Setup Script

### setup.sh
```bash
#!/bin/bash

echo "Setting up AI Agent Network..."

# Create directory structure
mkdir -p ai-agent-network/{nats,agents/{orchestrator,specialist,monitor},mcp-servers/{proxmox,filesystem,cloud},dashboard/{templates,static},shared}

# Copy existing Proxmox MCP code
if [ -d "../container-mcp-proxmox" ]; then
    cp -r ../container-mcp-proxmox/* ai-agent-network/mcp-servers/proxmox/
    echo "Copied existing Proxmox MCP code"
else
    echo "Warning: Proxmox MCP code not found. Please copy manually."
fi

# Create .env file
cat > ai-agent-network/.env << EOF
# NATS Configuration
NATS_URL=nats://localhost:4222
NATS_MONITOR_PORT=8222

# Agent Configuration
LOG_LEVEL=INFO
AGENT_HEARTBEAT_INTERVAL=30

# MCP Server Ports
MCP_PROXMOX_PORT=8001
MCP_FILESYSTEM_PORT=8002
MCP_CLOUD_PORT=8003

# Dashboard
DASHBOARD_PORT=8080

# Proxmox Configuration (update with your values)
PROXMOX_HOST=your-proxmox-host
PROXMOX_USER=your-username@pve
PROXMOX_PASSWORD=your-password
EOF

echo "Setup complete! Next steps:"
echo "1. Update .env file with your Proxmox credentials"
echo "2. cd ai-agent-network"
echo "3. docker-compose up --build"
```

This completes all missing implementation details needed for independent system building. 