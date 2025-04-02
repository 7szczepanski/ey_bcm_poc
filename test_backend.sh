#!/bin/bash

# Enhanced test script for the Business Combination Memo Generator Backend API with iterative memo generation

BASE_URL="http://localhost:8000/api"
COOKIE_JAR="cookies.txt"
AGREEMENT_PDF="/Users/mateuszs/Downloads/1-Model-Merger-Agreement.pdf"

# Verify the agreement PDF file exists
if [ ! -f "$AGREEMENT_PDF" ]; then
    echo "Error: Agreement PDF file not found at $AGREEMENT_PDF"
    echo "Please provide the correct path to the agreement PDF."
    exit 1
fi

# Clean up previous cookies
rm -f $COOKIE_JAR

echo "--- Testing Backend API Iterative Memo Generation Pipeline: $BASE_URL ---"

# 1. Attempt Access without Login (should fail)
echo -e "\n[1] Checking /session endpoint (unauthenticated)..."
curl -s -b $COOKIE_JAR $BASE_URL/session
echo -e "\nExpected: 401 Unauthorized or similar error."

# 2. Login with verbose output to debug cookie handling
echo -e "\n[2] Logging in as testuser (with verbose output)..."
LOGIN_RESPONSE=$(curl -v -c $COOKIE_JAR -X POST $BASE_URL/login \
    -H "Content-Type: application/json" \
    -d '{"username": "testuser", "password": "password123"}' 2>&1)
echo "Login Response Headers and Body: $LOGIN_RESPONSE"
echo "Cookie jar contents:"
cat $COOKIE_JAR

# Check if cookie jar is empty
if [ -s $COOKIE_JAR ]; then
    echo "Found cookies, continuing test..."
else
    echo "Login failed! No cookies received. Exiting." >&2
    exit 1
fi

# Wait a moment for the session to be created
sleep 2

# 3. Check Session with verbose output (authenticated)
echo -e "\n[3] Checking /session endpoint (authenticated) with verbose output..."
SESSION_RESPONSE=$(curl -v -b $COOKIE_JAR $BASE_URL/session 2>&1)
echo "Session Response with Headers: $SESSION_RESPONSE"

# Continue with verbose curl calls to debug
# 4. Set Standard (IFRS)
echo -e "\n[4] Setting standard to IFRS..."
STANDARD_RESPONSE=$(curl -v -b $COOKIE_JAR -X POST $BASE_URL/set-standard \
    -H "Content-Type: application/json" \
    -d '{"standard": "ifrs"}' 2>&1)
echo "Standard Response with Headers: $STANDARD_RESPONSE"

# Check if session has been updated with standard
echo -e "\n[5] Checking session for updates..."
SESSION_RESPONSE=$(curl -v -b $COOKIE_JAR $BASE_URL/session 2>&1)
echo "Updated Session Response: $SESSION_RESPONSE"

# 6. Upload Agreement
echo -e "\n[6] Uploading agreement ($AGREEMENT_PDF)..."
UPLOAD_RESPONSE=$(curl -v -b $COOKIE_JAR -X POST $BASE_URL/upload-agreement \
    -H "Expect:" \
    -F "file=@$AGREEMENT_PDF;type=application/pdf" 2>&1)
echo "Upload Response with Headers: $UPLOAD_RESPONSE"

# Wait for processing to complete
echo "Waiting 10 seconds for agreement indexing to complete..."
sleep 10

# 7. Check if session has been updated with agreement uploaded flag
echo -e "\n[7] Checking session after upload..."
SESSION_RESPONSE=$(curl -v -b $COOKIE_JAR $BASE_URL/session 2>&1)
echo "Session after upload: $SESSION_RESPONSE"

# 8. Generate initial memo - NOTE: Pass the parameter as a query parameter instead of in the body
echo -e "\n[8] Generating initial memo..."
MEMO_RESPONSE=$(curl -v -b $COOKIE_JAR -X POST "$BASE_URL/generate-memo?force_regenerate=true" 2>&1)
echo "Memo generation response headers: $MEMO_RESPONSE"

# Extract and print a more manageable portion of the memo response
MEMO_CONTENT=$(echo "$MEMO_RESPONSE" | grep -o '{.*}' | tail -1)
echo "Memo content (partial): ${MEMO_CONTENT:0:300}..."

# 8a. Validate Evidence Snippets
echo -e "\n[8a] Validating memo evidence snippets..."
# Extract information about evidence snippets
EVIDENCE_COUNT=$(echo "$MEMO_CONTENT" | grep -o '"evidence"\s*:\s*\[' | wc -l)
SNIPPET_COUNT=$(echo "$MEMO_CONTENT" | grep -o '"snippet"\s*:\s*"' | wc -l)
STANDARD_COUNT=$(echo "$MEMO_CONTENT" | grep -o '"source_type"\s*:\s*"standard"' | wc -l)
AGREEMENT_COUNT=$(echo "$MEMO_CONTENT" | grep -o '"source_type"\s*:\s*"agreement"' | wc -l)

echo "Evidence validation results:"
echo "- Total evidence sections: $EVIDENCE_COUNT"
echo "- Total snippets found: $SNIPPET_COUNT"
echo "- Standard references: $STANDARD_COUNT"
echo "- Agreement references: $AGREEMENT_COUNT"

# Check if snippets contain expected content
if echo "$MEMO_CONTENT" | grep -q "COOPERATION; REGULATORY APPROVALS"; then
    echo "✅ Found expected agreement content in snippets"
else
    echo "❌ Expected agreement content not found in snippets"
fi

if echo "$MEMO_CONTENT" | grep -q "IFRS"; then
    echo "✅ Found expected standard content in snippets"
else
    echo "❌ Expected standard content not found in snippets"
fi

# Check that there's at least some evidence
if [ "$SNIPPET_COUNT" -gt 0 ] && [ "$STANDARD_COUNT" -gt 0 ] && [ "$AGREEMENT_COUNT" -gt 0 ]; then
    echo "✅ Evidence snippets validation passed"
else
    echo "❌ Evidence snippets validation failed - missing expected evidence types"
fi

# 9. Seed questions from initial memo
echo -e "\n[9] Seeding questions from initial memo..."
SEED_RESPONSE=$(curl -v -b $COOKIE_JAR -X POST $BASE_URL/seed-questions 2>&1)
echo "Seed Response: $SEED_RESPONSE"

# 10. Check session after seeding
echo -e "\n[10] Checking session after seeding questions..."
SESSION_RESPONSE=$(curl -v -b $COOKIE_JAR $BASE_URL/session 2>&1)
SESSION_CONTENT=$(echo "$SESSION_RESPONSE" | grep -o '{.*}' | tail -1)
echo "Session after seeding (partial): ${SESSION_CONTENT:0:300}..."

# 11. Send a response to the seeded questions
echo -e "\n[11] Responding to seeded questions with sample information..."
CHAT_RESPONSE=$(curl -v -b $COOKIE_JAR -X POST $BASE_URL/chatbot \
    -H "Content-Type: application/json" \
    -d '{"message": "The acquisition date is January 15, 2023. The acquirer is Acme Corp and the target is Target Inc. The deal consideration is 500 million USD paid in cash."}' 2>&1)
CHAT_CONTENT=$(echo "$CHAT_RESPONSE" | grep -o '{.*}' | tail -1)
echo "Chat Response (partial): ${CHAT_CONTENT:0:300}..."

# Test structured data extraction and regeneration decision
echo -e "\n[11a] Testing structured data extraction from chat response..."
# Extract structured_output field from the chat response
STRUCTURED_DATA=$(echo "$CHAT_CONTENT" | grep -o '"structured_output":{[^}]*}' | head -1)
echo "Extracted structured data: $STRUCTURED_DATA"

# Check if structured data was extracted and should trigger regeneration
if [[ "$STRUCTURED_DATA" == *"acquisition_date"* || "$STRUCTURED_DATA" == *"acquirer"* || "$STRUCTURED_DATA" == *"consideration"* ]]; then
    echo "✅ Structured data detected - this should trigger memo regeneration"
    SHOULD_REGENERATE=true
else
    echo "❌ No relevant structured data detected - no regeneration needed"
    SHOULD_REGENERATE=false
fi

# 12. Generate updated memo with the new information - Using query parameter
echo -e "\n[12] Generating updated memo with new information..."
UPDATED_MEMO_RESPONSE=$(curl -v -b $COOKIE_JAR -X POST "$BASE_URL/generate-memo?force_regenerate=true" 2>&1)
UPDATED_MEMO_CONTENT=$(echo "$UPDATED_MEMO_RESPONSE" | grep -o '{.*}' | tail -1)
echo "Updated memo (partial): ${UPDATED_MEMO_CONTENT:0:300}..."

# Test message without structured data
echo -e "\n[12a] Testing message without extractable structured data..."
NO_STRUCT_RESPONSE=$(curl -v -b $COOKIE_JAR -X POST $BASE_URL/chatbot \
    -H "Content-Type: application/json" \
    -d '{"message": "I think this looks good so far, please continue."}' 2>&1)
NO_STRUCT_CONTENT=$(echo "$NO_STRUCT_RESPONSE" | grep -o '{.*}' | tail -1)
echo "Chat response for non-structured message (partial): ${NO_STRUCT_CONTENT:0:300}..."

# Check if structured data was extracted from the non-structured message
STRUCTURED_DATA=$(echo "$NO_STRUCT_CONTENT" | grep -o '"structured_output":{[^}]*}' | head -1)
if [[ -z "$STRUCTURED_DATA" || "$STRUCTURED_DATA" == *"{}"* ]]; then
    echo "✅ No structured data detected - should not trigger regeneration"
else
    echo "❓ Unexpected structured data detected: $STRUCTURED_DATA"
fi

# Test message with specific structured data
echo -e "\n[12b] Testing message with specific extractable data..."
SPECIFIC_RESPONSE=$(curl -v -b $COOKIE_JAR -X POST $BASE_URL/chatbot \
    -H "Content-Type: application/json" \
    -d '{"message": "The goodwill value was calculated as 125 million USD, representing the excess of consideration over net identifiable assets."}' 2>&1)
SPECIFIC_CONTENT=$(echo "$SPECIFIC_RESPONSE" | grep -o '{.*}' | tail -1)
echo "Chat response for specific structured message (partial): ${SPECIFIC_CONTENT:0:300}..."

# Check if structured data was extracted from the specific message
STRUCTURED_DATA=$(echo "$SPECIFIC_CONTENT" | grep -o '"structured_output":{[^}]*}' | head -1)
if [[ "$STRUCTURED_DATA" == *"goodwill"* || "$STRUCTURED_DATA" == *"125"* ]]; then
    echo "✅ Structured data about goodwill detected - should trigger regeneration"
else
    echo "❌ Expected structured data about goodwill not detected"
fi

# 13. Accept the memo if satisfied
echo -e "\n[13] Accepting the memo..."
ACCEPT_RESPONSE=$(curl -v -b $COOKIE_JAR -X POST $BASE_URL/accept-memo 2>&1)
echo "Accept Response: $ACCEPT_RESPONSE"

# 14. Check final session state
echo -e "\n[14] Checking final session state..."
FINAL_SESSION=$(curl -v -b $COOKIE_JAR $BASE_URL/session 2>&1)
FINAL_SESSION_CONTENT=$(echo "$FINAL_SESSION" | grep -o '{.*}' | tail -1)
echo "Final Session (partial): ${FINAL_SESSION_CONTENT:0:300}..."

# 15. Test evaluate-message endpoint (if implemented)
echo -e "\n[15] Testing evaluate-message endpoint..."
EVAL_RESPONSE=$(curl -v -b $COOKIE_JAR -X POST $BASE_URL/evaluate-message \
    -H "Content-Type: application/json" \
    -d '{"message": "The fair value of intangible assets recognized was 75 million USD, including customer relationships, technology, and brand."}' 2>&1)
echo "Evaluation Response: $EVAL_RESPONSE"

# 16. Test PDF serving endpoints
echo -e "\n[16] Testing PDF serving endpoints..."
# Try to access standard PDF
STANDARD_PDF_RESPONSE=$(curl -v -b $COOKIE_JAR -o /dev/null -s -w "%{http_code}" $BASE_URL/standard-pdf/ifrs 2>&1)
echo "Standard PDF response code: $STANDARD_PDF_RESPONSE"
if [[ "$STANDARD_PDF_RESPONSE" == "200" ]]; then
    echo "✅ Successfully accessed standard PDF"
else
    echo "❌ Failed to access standard PDF"
fi

# Try to access agreement PDF
SESSION_ID=$(echo "$SESSION_CONTENT" | grep -o '"session_id":"[^"]*"' | sed 's/"session_id":"//g' | sed 's/"//g')
if [[ -n "$SESSION_ID" ]]; then
    AGREEMENT_PDF_RESPONSE=$(curl -v -b $COOKIE_JAR -o /dev/null -s -w "%{http_code}" $BASE_URL/agreement-pdf/$SESSION_ID 2>&1)
    echo "Agreement PDF response code: $AGREEMENT_PDF_RESPONSE"
    if [[ "$AGREEMENT_PDF_RESPONSE" == "200" ]]; then
        echo "✅ Successfully accessed agreement PDF"
    else
        echo "❌ Failed to access agreement PDF"
    fi
else
    echo "❌ Could not extract session ID for agreement PDF test"
fi

# 17. Logout
echo -e "\n[17] Logging out..."
LOGOUT_RESPONSE=$(curl -v -b $COOKIE_JAR -X POST $BASE_URL/logout 2>&1)
echo "Logout Response: $LOGOUT_RESPONSE"

# 18. Attempt Access After Logout (should fail)
echo -e "\n[18] Checking /session endpoint (after logout)..."
curl -s -b $COOKIE_JAR $BASE_URL/session
echo -e "\nExpected: 401 Unauthorized or similar error."

# Clean up
rm -f $COOKIE_JAR

echo -e "\n--- Test script finished. ---" 