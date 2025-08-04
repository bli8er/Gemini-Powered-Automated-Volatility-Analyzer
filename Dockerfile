# Use official Python image
FROM python:3.11-slim

# Set work directory
WORKDIR /app

# Install git and other system dependencies
RUN apt-get update && apt-get install -y git && apt-get clean

# Copy requirements first to leverage Docker caching
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
RUN git clone https://github.com/volatilityfoundation/volatility3.git /volatility3
WORKDIR /volatility3
RUN pip install --user -e ".[full]"
# Copy the rest of the app
WORKDIR /app
COPY . .

# Expose FastAPI port
EXPOSE 8000

# Default command
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
