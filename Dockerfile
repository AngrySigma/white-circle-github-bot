FROM python:3.9-slim

# Set working directory
RUN apt-get update && apt-get install -y git && apt-get clean
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the bot code
COPY main.py .

# Run the bot
ENTRYPOINT ["python", "/app/main.py"]