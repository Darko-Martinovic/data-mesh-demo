FROM python:3.11-slim
WORKDIR /app
COPY domains/customer/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Copy shared event_bus so it is importable as `from event_bus.bus import EventBus`
COPY platform/event_bus/ ./event_bus/
COPY domains/customer/ .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
