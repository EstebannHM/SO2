FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py monitor_common.py ./

EXPOSE 9099

CMD ["python", "server.py"]
