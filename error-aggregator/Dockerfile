FROM python:3.9-slim

WORKDIR /app

# Copy shared library first (if it's not installed as a package)
# This assumes 'shared' is in the build context one level up from 'error-aggregator'
COPY ./shared /app/shared

COPY ./error-aggregator/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ./error-aggregator/error_aggregator.py .

# Ensure the shared module can be imported
ENV PYTHONPATH "${PYTHONPATH}:/app"
ENV NATS_URL "nats://nats:4222" # Default, can be overridden
ENV HTTP_PORT "8081"
ENV MAX_ERRORS_STORED "100"


EXPOSE 8081

CMD ["python", "error_aggregator.py"]
