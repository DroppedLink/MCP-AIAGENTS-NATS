# Error Logging and Monitoring System

This document describes the error logging and monitoring system implemented within the AI Agent Network. The system is designed to capture, aggregate, and expose critical errors from various services and agents.

## System Components

1.  **Standardized Error Message (`CriticalErrorEvent`):**
    *   Defined in `shared/message_types.py`.
    *   Ensures a consistent format for error reporting.
    *   Fields include:
        *   `event_id`: Unique ID for the error event (UUID).
        *   `timestamp`: ISO formatted UTC timestamp.
        *   `service_name`: Identifier of the service/agent reporting the error (e.g., `orchestrator-agent-xyz123`).
        *   `error_message`: A descriptive message of the error.
        *   `stack_trace`: Optional full stack trace.
        *   `severity`: Error severity (e.g., "ERROR", "CRITICAL").

2.  **Dedicated NATS Stream (`AI_CRITICAL_ERRORS`):**
    *   Configured in `shared/nats_client.py` during `_setup_streams`.
    *   NATS subject: `ai.critical_errors.>` (e.g., `ai.critical_errors.orchestrator-agent-xyz123`).
    *   Stores error events with a default retention of 7 days.
    *   Uses file storage for persistence.

3.  **Enhanced `NATSClient`:**
    *   Located in `shared/nats_client.py`.
    *   Includes a `publish_critical_error(service_name, error_message, stack_trace, severity)` method.
    *   Agents and services should use this method to report critical errors.
    *   The client itself also uses this method to report internal NATS communication issues.

4.  **Error Aggregator Service (`error-aggregator`):**
    *   Code: `error-aggregator/error_aggregator.py`.
    *   Dockerfile: `error-aggregator/Dockerfile`.
    *   Service in `docker-compose.yml`: `error-aggregator`.
    *   **Functionality:**
        *   Subscribes to the `ai.critical_errors.>` NATS subject.
        *   Stores a configurable number of recent error messages in memory (default: 200, configurable via `MAX_ERRORS_STORED` env var).
        *   Exposes an HTTP API to view these errors.
    *   **API Endpoints (default port 8081):**
        *   `GET /errors`: Returns a JSON array of stored `CriticalErrorEvent` objects.
            *   Supports filtering via query parameters:
                *   `?service_name=<name>`: Filter by service name.
                *   `?severity=<level>`: Filter by severity level.
                *   Example: `http://localhost:8081/errors?service_name=orchestrator-agent&severity=CRITICAL`
        *   `GET /health`: Returns the health status of the aggregator service, including the number of errors logged. Example: `http://localhost:8081/health`.

## How to Publish Errors

1.  Ensure your agent/service has an instance of `NATSClient`.
2.  When a critical error occurs (e.g., in a `try...except` block), call the `publish_critical_error` method:

    ```python
    import traceback
    # Assuming 'self.nats_client' is an instance of NATSClient
    # Assuming 'AGENT_ID' or 'SERVICE_NAME' is defined for your service

    try:
        # ... your critical operation ...
        raise ValueError("Something went wrong!")
    except Exception as e:
        error_msg = f"An error occurred: {e}"
        stack = traceback.format_exc()

        # Log it locally as well
        logger.error(error_msg, exc_info=True)

        # Publish to the central error stream
        asyncio.create_task(self.nats_client.publish_critical_error(
            service_name=AGENT_ID, # Or your specific service identifier
            error_message=error_msg,
            stack_trace=stack,
            severity="ERROR" # Or "CRITICAL"
        ))
    ```

## How to View Errors

1.  Ensure the `error-aggregator` service is running (e.g., via `docker-compose up -d`).
2.  Access the HTTP endpoints in your browser or via `curl`:
    *   All errors: `http://localhost:8081/errors`
    *   Filtered errors: `http://localhost:8081/errors?service_name=my-specific-agent`

## Future Enhancements

*   Persistent storage for the error aggregator (beyond in-memory).
*   More sophisticated UI for viewing/searching errors.
*   Integration with external alerting systems (e.g., PagerDuty, Opsgenie) based on error severity or frequency.
*   Distributed tracing integration to link errors with specific workflows.
