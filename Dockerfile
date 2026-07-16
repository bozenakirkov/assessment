FROM python:3.14-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY python_service ./python_service
COPY node_worker ./node_worker
COPY tests ./tests

EXPOSE 5000

CMD ["python", "app.py"]