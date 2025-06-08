# AI Agent Network Implementation Guide

## Quick Start Implementation Order

### Phase 1: Foundation (Day 1)
1. **NATS Infrastructure**
   - Set up NATS server with JetStream
   - Create shared NATS client library
   - Test basic pub/sub functionality

2. **Shared Libraries**
   - Implement message types and protocols
   - Create base agent class
   - Set up logging and monitoring

### Phase 2: MCP Integration (Day 2)
1. **Proxmox MCP Enhancement**
   - Add NATS communication to existing Proxmox MCP
   - Implement service registration
   - Add workflow support

2. **Additional MCP Servers**
   - Build filesystem MCP server
   - Build cloud provider MCP server
   - Test MCP-to-NATS bridge

### Phase 3: AI Agents (Day 3-4)
1. **Orchestrator Agent**
   - Workflow coordination logic
   - Task distribution algorithms
   - Service discovery

2. **Specialist Agents**
   - Domain-specific intelligence
   - Task execution engines
   - Result aggregation

3. **Monitor Agent**
   - Health checking
   - Metric collection
   - Alert generation

### Phase 4: Dashboard & Testing (Day 5)
1. **Web Dashboard**
   - Real-time monitoring
   - Workflow visualization
   - Agent management

2. **Integration Testing**
   - End-to-end workflows
   - Failure scenarios
   - Performance testing

## Key Implementation Files

### agents/orchestrator/agent.py
```python
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import sys
import os
sys.path.append('/app/shared')

from nats_client import NATSClient
from message_types import WorkflowRequest, WorkflowResponse, TaskAssignment

logger = logging.getLogger(__name__)

class OrchestratorAgent:
    def __init__(self, agent_id: str, nats_url: str):
        self.agent_id = agent_id
        self.nats = NATSClient(nats_url, agent_id)
        self.active_workflows = {}
        self.available_agents = {}
        self.mcp_services = {}
        
    async def start(self):
        """Start the orchestrator agent"""
        await self.nats.connect()
        
        # Subscribe to workflow requests
        await self.nats.subscribe("ai.workflows.request", self.handle_workflow_request)
        
        # Subscribe to agent registrations
        await self.nats.subscribe("ai.agents.register", self.handle_agent_registration)
        
        # Subscribe to MCP service registrations
        await self.nats.subscribe("ai.mcp.register", self.handle_mcp_registration)
        
        # Subscribe to task completions
        await self.nats.subscribe("ai.tasks.complete", self.handle_task_completion)
        
        # Start service discovery
        asyncio.create_task(self.discover_services())
        
        logger.info(f"Orchestrator {self.agent_id} started")
        
    async def discover_services(self):
        """Discover available agents and MCP services"""
        while True:
            # Request agent capabilities
            await self.nats.publish("ai.agents.discovery.request", {
                "requester": self.agent_id,
                "timestamp": datetime.utcnow().isoformat()
            })
            
            # Request MCP service capabilities
            await self.nats.publish("ai.mcp.discovery.request", {
                "requester": self.agent_id,
                "timestamp": datetime.utcnow().isoformat()
            })
            
            await asyncio.sleep(60)  # Discover every minute
            
    async def handle_workflow_request(self, subject: str, data: Dict, msg):
        """Handle incoming workflow requests"""
        try:
            request = WorkflowRequest(**data)
            logger.info(f"Received workflow request: {request.workflow_id}")
            
            # Plan workflow execution
            execution_plan = await self.plan_workflow(request)
            
            if execution_plan:
                # Store workflow
                self.active_workflows[request.workflow_id] = {
                    "request": request,
                    "plan": execution_plan,
                    "status": "in_progress",
                    "start_time": datetime.utcnow()
                }
                
                # Execute workflow
                await self.execute_workflow(request.workflow_id)
                
                # Send acknowledgment
                response = WorkflowResponse(
                    workflow_id=request.workflow_id,
                    status="accepted",
                    agent_id=self.agent_id
                )
            else:
                # Reject workflow
                response = WorkflowResponse(
                    workflow_id=request.workflow_id,
                    status="rejected",
                    error="Unable to plan workflow execution",
                    agent_id=self.agent_id
                )
            
            await self.nats.publish("ai.workflows.response", response.__dict__)
            
        except Exception as e:
            logger.error(f"Error handling workflow request: {e}")
            
    async def plan_workflow(self, request: WorkflowRequest) -> Optional[List[TaskAssignment]]:
        """Plan workflow execution based on available resources"""
        if request.workflow_type == "vm_deployment":
            return await self.plan_vm_deployment(request)
        elif request.workflow_type == "health_check":
            return await self.plan_health_check(request)
        elif request.workflow_type == "resource_optimization":
            return await self.plan_resource_optimization(request)
        else:
            logger.warning(f"Unknown workflow type: {request.workflow_type}")
            return None
            
    async def plan_vm_deployment(self, request: WorkflowRequest) -> List[TaskAssignment]:
        """Plan VM deployment workflow"""
        tasks = []
        
        # Task 1: Validate parameters
        tasks.append(TaskAssignment(
            task_id=f"{request.workflow_id}_validate",
            task_type="validate_vm_parameters",
            assigned_to="specialist-001",  # TODO: Select based on load
            parameters=request.parameters,
            deadline=datetime.utcnow() + timedelta(minutes=5)
        ))
        
        # Task 2: Create VM
        tasks.append(TaskAssignment(
            task_id=f"{request.workflow_id}_create",
            task_type="create_vm",
            assigned_to="mcp-proxmox",
            parameters=request.parameters,
            deadline=datetime.utcnow() + timedelta(minutes=15),
            dependencies=[f"{request.workflow_id}_validate"]
        ))
        
        # Task 3: Configure VM
        tasks.append(TaskAssignment(
            task_id=f"{request.workflow_id}_configure",
            task_type="configure_vm",
            assigned_to="specialist-001",
            parameters=request.parameters,
            deadline=datetime.utcnow() + timedelta(minutes=10),
            dependencies=[f"{request.workflow_id}_create"]
        ))
        
        return tasks
        
    async def execute_workflow(self, workflow_id: str):
        """Execute workflow tasks"""
        workflow = self.active_workflows[workflow_id]
        
        for task in workflow["plan"]:
            # Check dependencies
            if task.dependencies:
                deps_complete = await self.check_dependencies(task.dependencies)
                if not deps_complete:
                    logger.warning(f"Dependencies not met for task {task.task_id}")
                    continue
            
            # Assign task
            await self.nats.publish(f"ai.tasks.assign.{task.assigned_to}", task.__dict__)
            
    async def check_dependencies(self, dependencies: List[str]) -> bool:
        """Check if task dependencies are complete"""
        # Implementation would check completed tasks
        return True  # Simplified for example
        
    async def handle_agent_registration(self, subject: str, data: Dict, msg):
        """Handle agent capability registrations"""
        self.available_agents[data["agent_id"]] = {
            "capabilities": data["capabilities"],
            "load": data.get("load", 0.0),
            "status": data.get("status", "available"),
            "last_seen": datetime.utcnow()
        }
        logger.info(f"Registered agent: {data['agent_id']}")
        
    async def handle_mcp_registration(self, subject: str, data: Dict, msg):
        """Handle MCP service registrations"""
        self.mcp_services[data["service_id"]] = {
            "capabilities": data["capabilities"],
            "endpoint": data["endpoint"],
            "status": data.get("status", "available"),
            "last_seen": datetime.utcnow()
        }
        logger.info(f"Registered MCP service: {data['service_id']}")
        
    async def handle_task_completion(self, subject: str, data: Dict, msg):
        """Handle task completion notifications"""
        task_id = data["task_id"]
        status = data["status"]
        
        # Update workflow progress
        for workflow_id, workflow in self.active_workflows.items():
            for task in workflow["plan"]:
                if task.task_id == task_id:
                    task.status = status
                    if status == "completed":
                        logger.info(f"Task {task_id} completed successfully")
                    elif status == "failed":
                        logger.error(f"Task {task_id} failed: {data.get('error')}")
                    break

if __name__ == "__main__":
    import os
    
    agent = OrchestratorAgent(
        agent_id=os.getenv("AGENT_ID", "orchestrator-001"),
        nats_url=os.getenv("NATS_URL", "nats://localhost:4222")
    )
    
    asyncio.run(agent.start())
```

### mcp-servers/proxmox/enhanced_server.py
```python
import asyncio
import json
import logging
from datetime import datetime
import sys
import os

# Add existing proxmox MCP imports
sys.path.append('/app')
from mcp_server import *  # Import existing MCP server code
sys.path.append('/app/shared')
from nats_client import NATSClient

logger = logging.getLogger(__name__)

class ProxmoxMCPWithNATS:
    def __init__(self, nats_url: str, service_id: str = "mcp-proxmox"):
        self.service_id = service_id
        self.nats = NATSClient(nats_url, service_id)
        self.capabilities = [
            "vm_management",
            "container_management", 
            "storage_management",
            "backup_management",
            "user_management"
        ]
        
    async def start(self):
        """Start the enhanced MCP server with NATS integration"""
        # Connect to NATS
        await self.nats.connect()
        
        # Register service capabilities
        await self.register_service()
        
        # Subscribe to task assignments
        await self.nats.subscribe(f"ai.tasks.assign.{self.service_id}", self.handle_task_assignment)
        
        # Subscribe to discovery requests
        await self.nats.subscribe("ai.mcp.discovery.request", self.handle_discovery_request)
        
        # Start the original MCP server
        await self.start_mcp_server()
        
        logger.info(f"Proxmox MCP with NATS started: {self.service_id}")
        
    async def register_service(self):
        """Register this MCP service with the network"""
        registration = {
            "service_id": self.service_id,
            "service_type": "mcp_server",
            "capabilities": self.capabilities,
            "endpoint": f"http://{self.service_id}:8001",
            "status": "available",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await self.nats.publish("ai.mcp.register", registration)
        
    async def handle_discovery_request(self, subject: str, data: Dict, msg):
        """Respond to service discovery requests"""
        await self.register_service()
        
    async def handle_task_assignment(self, subject: str, data: Dict, msg):
        """Handle task assignments from orchestrator"""
        try:
            task_id = data["task_id"]
            task_type = data["task_type"]
            parameters = data["parameters"]
            
            logger.info(f"Received task assignment: {task_id} ({task_type})")
            
            # Execute task based on type
            if task_type == "create_vm":
                result = await self.create_vm_task(parameters)
            elif task_type == "list_vms":
                result = await self.list_vms_task()
            elif task_type == "backup_vm":
                result = await self.backup_vm_task(parameters)
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
            # Report failure
            failure = {
                "task_id": data.get("task_id", "unknown"),
                "status": "failed",
                "error": str(e),
                "service_id": self.service_id,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            await self.nats.publish("ai.tasks.complete", failure)
            logger.error(f"Task execution failed: {e}")
            
    async def create_vm_task(self, parameters: Dict) -> Dict:
        """Execute VM creation task using existing MCP tools"""
        # Use existing create_vm function from MCP server
        # This integrates with the existing Proxmox MCP codebase
        vmid = parameters.get("vmid")
        name = parameters.get("name")
        node = parameters.get("node", "pve")
        
        # Call existing MCP function
        result = await create_vm_tool(vmid=vmid, name=name, node=node, **parameters)
        
        return {
            "vmid": vmid,
            "name": name,
            "status": "created",
            "details": result
        }
        
    async def start_mcp_server(self):
        """Start the existing MCP server alongside NATS"""
        # Import and start existing MCP server code
        # This runs the original SSE-based MCP server in parallel
        pass

if __name__ == "__main__":
    server = ProxmoxMCPWithNATS(
        nats_url=os.getenv("NATS_URL", "nats://localhost:4222"),
        service_id=os.getenv("SERVICE_ID", "mcp-proxmox")
    )
    
    asyncio.run(server.start())
```

### dashboard/app.py
```python
from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO
import asyncio
import json
import logging
from datetime import datetime
import sys
import os
sys.path.append('/app/shared')

from nats_client import NATSClient

app = Flask(__name__)
app.config['SECRET_KEY'] = 'ai-agent-dashboard'
socketio = SocketIO(app, cors_allowed_origins="*")

logger = logging.getLogger(__name__)

class DashboardMonitor:
    def __init__(self, nats_url: str):
        self.nats = NATSClient(nats_url, "dashboard-monitor")
        self.agents = {}
        self.workflows = {}
        self.metrics = {}
        
    async def start(self):
        """Start monitoring NATS for dashboard updates"""
        await self.nats.connect()
        
        # Subscribe to all relevant streams
        await self.nats.subscribe("ai.heartbeat.>", self.handle_heartbeat)
        await self.nats.subscribe("ai.workflows.>", self.handle_workflow_event)
        await self.nats.subscribe("ai.metrics.>", self.handle_metrics)
        await self.nats.subscribe("ai.tasks.>", self.handle_task_event)
        
    async def handle_heartbeat(self, subject: str, data: Dict, msg):
        """Handle agent heartbeat messages"""
        agent_id = data["agent_id"]
        self.agents[agent_id] = {
            "last_seen": datetime.utcnow(),
            "status": data["status"],
            "timestamp": data["timestamp"]
        }
        
        # Emit to web clients
        socketio.emit('agent_update', {
            'agent_id': agent_id,
            'status': data["status"],
            'last_seen': data["timestamp"]
        })
        
    async def handle_workflow_event(self, subject: str, data: Dict, msg):
        """Handle workflow events"""
        if "workflow_id" in data:
            workflow_id = data["workflow_id"]
            self.workflows[workflow_id] = data
            
            socketio.emit('workflow_update', data)
            
    async def handle_metrics(self, subject: str, data: Dict, msg):
        """Handle metric reports"""
        agent_id = data.get("agent_id", "unknown")
        self.metrics[agent_id] = data
        
        socketio.emit('metrics_update', data)
        
    async def handle_task_event(self, subject: str, data: Dict, msg):
        """Handle task events"""
        socketio.emit('task_update', data)

# Global monitor instance
monitor = DashboardMonitor(os.getenv("NATS_URL", "nats://localhost:4222"))

@app.route('/')
def dashboard():
    return render_template('dashboard.html')

@app.route('/api/agents')
def api_agents():
    return jsonify(monitor.agents)

@app.route('/api/workflows')
def api_workflows():
    return jsonify(monitor.workflows)

@app.route('/api/metrics')
def api_metrics():
    return jsonify(monitor.metrics)

if __name__ == '__main__':
    # Start NATS monitoring in background
    import threading
    import asyncio
    
    def start_monitor():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(monitor.start())
        loop.run_forever()
        
    monitor_thread = threading.Thread(target=start_monitor)
    monitor_thread.daemon = True
    monitor_thread.start()
    
    # Start Flask app
    socketio.run(app, host='0.0.0.0', port=8080, debug=True)
```

## Build Commands

```bash
# Create all directories
mkdir -p ai-agent-network/{nats,agents/{orchestrator,specialist,monitor},mcp-servers/{proxmox,filesystem,cloud},dashboard,shared}

# Copy shared libraries
cp NATS_FOR_AI_AGENTS_SETUP.md ai-agent-network/
cp NATS_FOR_AI_AGENTS_IMPLEMENTATION.md ai-agent-network/

# Build and start the network
cd ai-agent-network
docker-compose up --build -d

# Monitor logs
docker-compose logs -f

# Access dashboard
curl http://localhost:8080
```

This implementation guide provides the foundation for building a complete AI agent network with NATS communication. 