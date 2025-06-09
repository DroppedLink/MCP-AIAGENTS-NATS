import asyncio
import json
import logging
from collections import deque
from datetime import datetime
from typing import Deque, List, Dict, Any
import os
import uuid

from http.server import BaseHTTPRequestHandler, HTTPServer
import threading

# Attempt to import NATSClient from shared, assuming PYTHONPATH is set up or it's installed
# For local development, you might need to adjust sys.path
try:
    from shared.nats_client import NATSClient
    from shared.message_types import CriticalErrorEvent # Ensure this is available
except ImportError:
    # This is a fallback if 'shared' is not directly in PYTHONPATH
    # This might happen depending on how the subtask executes or if it's run in isolation
    import sys
    # Assuming the script is run from ai-agent-network/ or similar root where 'shared' is a subdir
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from shared.nats_client import NATSClient
    from shared.message_types import CriticalErrorEvent


# Configuration
NATS_URL = os.getenv("NATS_URL", "nats://localhost:4222")
SERVICE_ID = f"error-aggregator-{uuid.uuid4().hex[:6]}"
ERROR_SUBJECT = "ai.critical_errors.>"
MAX_ERRORS_STORED = int(os.getenv("MAX_ERRORS_STORED", 100))
HTTP_PORT = int(os.getenv("HTTP_PORT", 8081))
HTTP_HOST = "0.0.0.0"

# In-memory store for errors
# Using deque for efficient appends and pops from either end if needed
error_log: Deque[Dict[str, Any]] = deque(maxlen=MAX_ERRORS_STORED)

# Basic logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ErrorRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/errors"): # Modified to handle query parameters
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()

            errors_to_send = list(error_log)

            query_components = {}
            if '?' in self.path:
                query_string = self.path.split('?', 1)[1] # Split only on the first '?'
                query_components = dict(qc.split("=") for qc in query_string.split("&") if "=" in qc) # Ensure key=value pairs

            if "service_name" in query_components:
                errors_to_send = [e for e in errors_to_send if e.get("service_name") == query_components["service_name"]]
            if "severity" in query_components:
                errors_to_send = [e for e in errors_to_send if e.get("severity") == query_components["severity"]]

            self.wfile.write(json.dumps(errors_to_send).encode('utf-8'))
        elif self.path == "/health":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "service_id": SERVICE_ID, "errors_logged": len(error_log)}).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Not Found"}).encode('utf-8'))

async def nats_message_handler(subject: str, data: Dict[str, Any], msg_obj): # msg_obj is 'msg' from NATS
    logger.info(f"Received error on {subject}: {data.get('error_message', 'Unknown error')[:100]}")
    # Data is already a dict due to NATSClient's message_handler
    error_log.append(data)
    # No manual ack needed for core NATS nc.subscribe as used in NATSClient

async def main():
    logger.info(f"Starting Error Aggregator Service (ID: {SERVICE_ID})")
    logger.info(f"Max errors stored: {MAX_ERRORS_STORED}")
    logger.info(f"NATS URL: {NATS_URL}")
    logger.info(f"HTTP server on port: {HTTP_PORT}")

    nats_client = NATSClient(url=NATS_URL, agent_id=SERVICE_ID)

    try:
        await nats_client.connect()
        logger.info("Connected to NATS")

        # Subscribe to the critical error subject.
        await nats_client.subscribe(ERROR_SUBJECT, nats_message_handler)
        logger.info(f"Subscribed to NATS subject: {ERROR_SUBJECT}")

        # Start HTTP server in a separate thread
        http_server = HTTPServer((HTTP_HOST, HTTP_PORT), ErrorRequestHandler)
        http_thread = threading.Thread(target=http_server.serve_forever, daemon=True)
        http_thread.start()
        logger.info(f"HTTP server started on {HTTP_HOST}:{HTTP_PORT}")

        # Keep the main coroutine running
        while True:
            await asyncio.sleep(1)
    except Exception as e:
        logger.error(f"Error Aggregator Service failed: {e}", exc_info=True)
    finally:
        if nats_client:
            await nats_client.close()
        logger.info("Error Aggregator Service stopped.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Service interrupted by user.")
    except Exception as e:
        logger.critical(f"Unhandled exception in main: {e}", exc_info=True)
