import asyncio
import logging
import os
import uuid
import traceback # For stack trace

# Attempt to import NATSClient from shared, assuming PYTHONPATH is set up or it's installed
try:
    from shared.nats_client import NATSClient
    from shared.message_types import WorkflowRequest # Example message type
except ImportError:
    import sys
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))) # Adjust path to reach 'shared'
    from shared.nats_client import NATSClient
    from shared.message_types import WorkflowRequest


# Configuration
NATS_URL = os.getenv("NATS_URL", "nats://localhost:4222")
AGENT_ID = os.getenv("AGENT_ID", f"orchestrator-agent-{uuid.uuid4().hex[:6]}")

# Basic logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class OrchestratorAgent:
    def __init__(self):
        self.nats_client = NATSClient(url=NATS_URL, agent_id=AGENT_ID)

    async def connect(self):
        await self.nats_client.connect()
        logger.info(f"Orchestrator Agent {AGENT_ID} connected to NATS.")

    async def handle_workflow_request(self, subject: str, data: dict, msg_obj):
        try:
            logger.info(f"Received workflow request on {subject}: {data}")
            request = WorkflowRequest(**data) # Assuming data matches WorkflowRequest fields

            # Simulate processing the workflow
            if request.workflow_type == "critical_operation":
                # Simulate a failing operation
                if request.parameters.get("cause_error", False):
                    raise ValueError("Simulated error during critical_operation workflow!")

                logger.info(f"Successfully processed workflow: {request.workflow_id}")
                # Normally, you would publish a response here

            else:
                logger.info(f"Ignoring unknown workflow type: {request.workflow_type}")


        except ValueError as ve: # More specific exception
            error_message = f"ValueError during workflow '{data.get('workflow_id', 'unknown_workflow')}': {ve}"
            logger.error(error_message)
            # Publish this error to the critical error stream
            # The NATSClient's agent_id will be used as service_name if not overridden here
            await self.nats_client.publish_critical_error(
                service_name=AGENT_ID, # Explicitly state the service name
                error_message=error_message,
                stack_trace=traceback.format_exc(), # Include stack trace
                severity="ERROR"
            )
            # Potentially publish a WorkflowResponse with status "failed"

        except Exception as e:
            # Catch-all for other unexpected errors
            error_message = f"Unexpected error processing workflow '{data.get('workflow_id', 'unknown_workflow')}': {e}"
            logger.error(error_message, exc_info=True) # Log with stack trace locally

            await self.nats_client.publish_critical_error(
                service_name=AGENT_ID,
                error_message=error_message,
                stack_trace=traceback.format_exc(),
                severity="CRITICAL" # More severe as it's unexpected
            )
            # Potentially publish a WorkflowResponse with status "failed"


    async def start(self):
        await self.connect()
        # Example: Subscribe to workflow requests
        # The subject would be specific to this agent or a group it belongs to
        await self.nats_client.subscribe(f"ai.workflows.orchestrator.{AGENT_ID}", self.handle_workflow_request)
        logger.info(f"Orchestrator Agent {AGENT_ID} started and subscribed to workflow requests.")

        # Keep the agent running
        while True:
            await asyncio.sleep(1)

async def main():
    agent = OrchestratorAgent()
    try:
        await agent.start()
    except KeyboardInterrupt:
        logger.info("Orchestrator Agent shutting down...")
    except Exception as e:
        logger.critical(f"Orchestrator Agent failed critically: {e}", exc_info=True)
        # If NATS client is initialized in agent, it might try to publish this too
        # This depends on whether agent.nats_client is available and connected here
        if agent.nats_client and agent.nats_client.js: # Check if NATS is usable
             await agent.nats_client.publish_critical_error(
                service_name=AGENT_ID, # or a more generic "orchestrator-bootstrap"
                error_message=f"Orchestrator Agent failed critically during startup/runtime: {e}",
                stack_trace=traceback.format_exc(),
                severity="CRITICAL"
            )
    finally:
        if agent.nats_client:
            await agent.nats_client.close()
        logger.info("Orchestrator Agent shutdown complete.")


if __name__ == "__main__":
    asyncio.run(main())
