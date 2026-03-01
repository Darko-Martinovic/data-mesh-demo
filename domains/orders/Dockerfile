FROM python:3.11-slim
WORKDIR /app
COPY domains/orders/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY platform/event_bus/ ./event_bus/
COPY domains/orders/ .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"]
