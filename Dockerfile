FROM python:3.9.6-slim

WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy the rest of the application
COPY . .

# Copy the real .env file (make sure to create it from .env.example)
COPY .env .

CMD ["python", "telegram_bot.py"]
