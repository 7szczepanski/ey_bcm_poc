#!/bin/bash

# Test script for Docker container indexing
echo "=== Testing Docker Container Indexing ==="

# 1. Rebuild and start the backend container
echo -e "\n[1] Rebuilding and starting backend container..."
docker-compose up --build backend -d

# 2. Wait for the container to initialize
echo -e "\n[2] Waiting for container to initialize (30 seconds)..."
sleep 30

# 3. Check the logs to see if indexing happened
echo -e "\n[3] Checking container logs for indexing activity..."
docker-compose logs backend | grep -i "index"

# 4. Verify standard endpoints work with the indexed data
echo -e "\n[4] Testing standard endpoints..."

BASE_URL="http://localhost:8000/api"
COOKIE_JAR="cookies.txt"

# Clean up previous cookies
rm -f $COOKIE_JAR

# Login
echo -e "\n[4.1] Logging in as testuser..."
LOGIN_RESPONSE=$(curl -s -c $COOKIE_JAR -X POST $BASE_URL/login \
    -H "Content-Type: application/json" \
    -d '{"username": "testuser", "password": "password123"}')
echo "Login Response: $LOGIN_RESPONSE"

# Set Standard
echo -e "\n[4.2] Setting standard to IFRS..."
STANDARD_RESPONSE=$(curl -s -b $COOKIE_JAR -X POST $BASE_URL/set-standard \
    -H "Content-Type: application/json" \
    -d '{"standard": "ifrs"}')
echo "Standard Response: $STANDARD_RESPONSE"

# 5. Stop the container
echo -e "\n[5] Stopping container..."
docker-compose stop backend

# 6. Start the container again
echo -e "\n[6] Restarting container..."
docker-compose up backend -d

# 7. Wait for the container to initialize
echo -e "\n[7] Waiting for container to initialize (10 seconds)..."
sleep 10

# 8. Check the logs to see if indices were loaded from volume
echo -e "\n[8] Checking container logs for index loading from volume..."
docker-compose logs backend | grep -i "index"

# 9. Clean up
echo -e "\n[9] Cleaning up..."
rm -f $COOKIE_JAR

echo -e "\n=== Test completed ===" 