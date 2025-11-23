FROM python:3.9-slim

WORKDIR /app

# Install Node.js for Hardhat
RUN apt-get update && apt-get install -y curl && \
    curl -fsSL https://deb.nodesource.com/setup_18.x | bash - && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Hardhat globally
RUN npm install -g hardhat

# Copy everything
COPY . .

# Install Node dependencies
WORKDIR /app/l1
RUN npm install
WORKDIR /app

# Expose ports
EXPOSE 3000 5000 8545

# Start script
CMD ["bash", "start.sh"]
