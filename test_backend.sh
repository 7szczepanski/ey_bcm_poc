#!/bin/bash

# Basic test script for the Business Combination Memo Generator Backend API

BASE_URL="http://localhost:8000/api"
COOKIE_JAR="cookies.txt"

# Clean up previous cookies
rm -f $COOKIE_JAR

echo "--- Testing Backend API: $BASE_URL ---"

# 1. Attempt Access without Login (should fail)
echo -e "\n[1] Checking /session endpoint (unauthenticated)..."
curl -s -b $COOKIE_JAR $BASE_URL/session
echo -e "\nExpected: 401 Unauthorized or similar error."

# 2. Login
echo -e "\n[2] Logging in as testuser..."
LOGIN_RESPONSE=$(curl -s -c $COOKIE_JAR -X POST $BASE_URL/login \
    -H "Content-Type: application/json" \
    -d '{"username": "testuser", "password": "password123"}')
echo "Login Response: $LOGIN_RESPONSE"
echo "Cookie jar contents:"
cat $COOKIE_JAR

if [ -s $COOKIE_JAR ]; then
    echo "Found cookies, continuing test..."
else
    echo "Login failed! No cookies received. Exiting." >&2
    exit 1
fi

# Wait a moment for the session to be created
sleep 2

# 3. Check Session (authenticated)
echo -e "\n[3] Checking /session endpoint (authenticated)..."
SESSION_RESPONSE=$(curl -s -b $COOKIE_JAR $BASE_URL/session)
echo "Session Response: $SESSION_RESPONSE"

# 4. Set Standard (IFRS)
echo -e "\n[4] Setting standard to IFRS..."
STANDARD_RESPONSE=$(curl -s -b $COOKIE_JAR -X POST $BASE_URL/set-standard \
    -H "Content-Type: application/json" \
    -d '{"standard": "ifrs"}')
echo "Standard Response: $STANDARD_RESPONSE"

# 5. Check if session has been updated with standard
echo -e "\n[5] Checking session for updates..."
SESSION_RESPONSE=$(curl -s -b $COOKIE_JAR $BASE_URL/session)
echo "Updated Session Response: $SESSION_RESPONSE"

# 6. Upload Agreement
REAL_PDF_TO_UPLOAD="backend/app/data/ifrs.pdf" # Use one of the actual PDFs

echo -e "\n[6] Uploading agreement ($REAL_PDF_TO_UPLOAD)..."
UPLOAD_RESPONSE=$(curl -s -b $COOKIE_JAR -X POST $BASE_URL/upload-agreement \
    -H "Expect:" \
    -F "file=@$REAL_PDF_TO_UPLOAD;type=application/pdf")
echo "Upload Response: $UPLOAD_RESPONSE"

# Wait for processing to complete
sleep 5

# 7. Check if session has been updated with agreement uploaded flag
echo -e "\n[7] Checking session after upload..."
SESSION_RESPONSE=$(curl -s -b $COOKIE_JAR $BASE_URL/session)
echo "Session after upload: $SESSION_RESPONSE"

# 8. Send a chat message
echo -e "\n[8] Sending a chat message..."
CHAT_RESPONSE=$(curl -s -b $COOKIE_JAR -X POST $BASE_URL/chatbot \
    -H "Content-Type: application/json" \
    -d '{"message": "What is the acquisition date mentioned?"}')
echo "Chat Response: $CHAT_RESPONSE"

# 9. Check if chat history has been saved in the session
echo -e "\n[9] Checking if chat history was saved..."
SESSION_RESPONSE=$(curl -s -b $COOKIE_JAR $BASE_URL/session)
echo "Session after chat: $SESSION_RESPONSE"

# 10. Send a second chat message to test continuity
echo -e "\n[10] Sending a second chat message for continuity..."
CHAT_RESPONSE=$(curl -s -b $COOKIE_JAR -X POST $BASE_URL/chatbot \
    -H "Content-Type: application/json" \
    -d '{"message": "Tell me more about the parties involved"}')
echo "Second Chat Response: $CHAT_RESPONSE"

# 11. Generate Memo
echo -e "\n[11] Generating memo..."
MEMO_RESPONSE=$(curl -s -b $COOKIE_JAR -X POST $BASE_URL/generate-memo)
echo "Memo Response: $MEMO_RESPONSE"

# 12. Logout
echo -e "\n[12] Logging out..."
LOGOUT_RESPONSE=$(curl -s -b $COOKIE_JAR -X POST $BASE_URL/logout)
echo "Logout Response: $LOGOUT_RESPONSE"

# 13. Attempt Access After Logout (should fail)
echo -e "\n[13] Checking /session endpoint (after logout)..."
curl -s -b $COOKIE_JAR $BASE_URL/session
echo -e "\nExpected: 401 Unauthorized or similar error."

# Clean up
rm -f $COOKIE_JAR

echo -e "\n--- Test script finished. ---" 