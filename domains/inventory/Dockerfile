FROM python:3.11-slim
WORKDIR /app
COPY domains/inventory/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY platform/event_bus/ ./event_bus/
COPY domains/inventory/ .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8003"]
