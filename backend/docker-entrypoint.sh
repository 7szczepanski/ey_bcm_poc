#!/bin/bash
set -e

echo "=== Running Docker entrypoint script ==="

# Show file system info
echo "=== File System Information ==="
df -h
ls -la /app
ls -la /app/data || echo "No /app/data directory"
ls -la /app/app/data || echo "No /app/app/data directory"

# Run the startup indexing check
echo "=== Running Startup Indexing ==="
python -m app.startup

# Start the FastAPI application
echo "=== Starting FastAPI Application ==="
exec "$@" 