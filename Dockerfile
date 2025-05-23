FROM python:3.11-slim

WORKDIR /MVP

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . /MVP

CMD ["uvicorn", "main:app", "--host", "localhost", "--port", "8000"]