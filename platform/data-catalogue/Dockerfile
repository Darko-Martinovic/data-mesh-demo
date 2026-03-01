FROM python:3.11-slim
WORKDIR /app
COPY platform/data-catalogue/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY platform/data-catalogue/ .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
