# Use Motia official Docker image as base
FROM motiadev/motia:latest

# Set working directory
WORKDIR /app

# Copy package files
COPY package*.json ./
COPY tsconfig.json ./
COPY motia.config.ts ./

# Install dependencies (including dev for motia dev mode)
RUN npm ci

# Copy application code and steps
COPY steps/ ./steps/

# Expose port
EXPOSE 3000

# Start Motia in dev mode to enable step discovery and hot reload
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
