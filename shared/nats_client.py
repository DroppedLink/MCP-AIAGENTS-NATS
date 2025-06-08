import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional, Callable
import nats
from nats.js import JetStreamContext

logger = logging.getLogger(__name__)

class NATSClient:
    def __init__(self, url: str, agent_id: str):
        self.url = url
        self.agent_id = agent_id
        self.nc: Optional[nats.NATS] = None
        self.js: Optional[JetStreamContext] = None
        self.subscriptions = {}

    async def connect(self):
        """Connect to NATS server"""
        self.nc = await nats.connect(self.url)
        self.js = self.nc.jetstream()

        # Create streams if they don't exist
        await self._setup_streams()

        # Start heartbeat
        asyncio.create_task(self._heartbeat())

        logger.info(f"Agent {self.agent_id} connected to NATS")

    async def _setup_streams(self):
        """Set up JetStream streams"""
        streams = [
            {
                "name": "AI_EVENTS",
                "subjects": ["ai.events.>"],
                "retention": "limits",
                "max_age": 24 * 60 * 60 * 1000000000  # 24 hours in nanoseconds
            },
            {
                "name": "AI_WORKFLOWS",
                "subjects": ["ai.workflows.>"],
                "retention": "workqueue"
            },
            {
                "name": "AI_METRICS",
                "subjects": ["ai.metrics.>"],
                "retention": "limits",
                "max_age": 7 * 24 * 60 * 60 * 1000000000  # 7 days
            }
        ]

        for stream_config in streams:
            try:
                await self.js.add_stream(**stream_config)
                logger.info(f"Created stream: {stream_config['name']}")
            except Exception as e:
                if "stream name already in use" not in str(e).lower():
                    logger.error(f"Failed to create stream {stream_config['name']}: {e}")

    async def _heartbeat(self):
        """Send periodic heartbeat"""
        while True:
            try:
                await self.publish(f"ai.heartbeat.{self.agent_id}", {
                    "agent_id": self.agent_id,
                    "timestamp": datetime.utcnow().isoformat(),
                    "status": "active"
                })
                await asyncio.sleep(30)
            except Exception as e:
                logger.error(f"Heartbeat failed: {e}")
                await asyncio.sleep(5)

    async def publish(self, subject: str, data: Dict[str, Any]):
        """Publish message to NATS"""
        if not self.nc:
            raise RuntimeError("Not connected to NATS")

        message = json.dumps(data).encode()
        await self.nc.publish(subject, message)
        logger.debug(f"Published to {subject}: {data}")

    async def request(self, subject: str, data: Dict[str, Any], timeout: int = 5) -> Dict[str, Any]:
        """Send request and wait for reply"""
        if not self.nc:
            raise RuntimeError("Not connected to NATS")

        message = json.dumps(data).encode()
        response = await self.nc.request(subject, message, timeout=timeout)
        return json.loads(response.data.decode())

    async def subscribe(self, subject: str, callback: Callable):
        """Subscribe to subject"""
        if not self.nc:
            raise RuntimeError("Not connected to NATS")

        async def message_handler(msg):
            try:
                data = json.loads(msg.data.decode())
                await callback(msg.subject, data, msg)
            except Exception as e:
                logger.error(f"Error handling message on {subject}: {e}")

        sub = await self.nc.subscribe(subject, cb=message_handler)
        self.subscriptions[subject] = sub
        logger.info(f"Subscribed to {subject}")

    async def close(self):
        """Close NATS connection"""
        if self.nc:
            await self.nc.close()
            logger.info(f"Agent {self.agent_id} disconnected from NATS")
