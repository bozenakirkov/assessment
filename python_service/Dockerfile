FROM python:3.14-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY state_machine.py .
COPY init.sql .
COPY tests ./tests

EXPOSE 5000

CMD ["python", "app.py"]