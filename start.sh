#!/bin/bash

# This script fetches secrets from Google Cloud Secret Manager,
# sets them as environment variables, and starts the motia services.

set -e

GCLOUD_PATH="/root/google-cloud-sdk/bin/gcloud"
PROJECT_ID="speedy-carver-477302-p1"

# Function to fetch a secret from GCP Secret Manager
fetch_secret() {
  local secret_name="$1"
  sudo "$GCLOUD_PATH" secrets versions access latest --secret="$secret_name" --project="$PROJECT_ID"
}

# Fetch secrets and export them as environment variables
export MOTIA_REDIS_PASSWORD=$(fetch_secret "organism-redis-password")
# export DAYTONA_API_KEY=$(fetch_secret "organism-ollama-api-key")

# Start the services
docker compose up -d --remove-orphans
