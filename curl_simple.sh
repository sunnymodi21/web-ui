#!/bin/bash

# Simple curl example for the browser agent
# This version polls for results instead of streaming

TASK="${1:-Go to example.com and tell me what you see}"
API_URL="http://127.0.0.1:7789/gradio_api"

echo "Task: $TASK"
echo ""

# Step 1: Submit the task
echo "[1/2] Submitting task..."
RESPONSE=$(curl -s -X POST "${API_URL}/call/predict" \
  -H "Content-Type: application/json" \
  -d "{\"data\":[\"${TASK}\"]}")

EVENT_ID=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['event_id'])" 2>/dev/null)

if [ -z "$EVENT_ID" ]; then
  echo "Error: Failed to get event ID"
  echo "$RESPONSE"
  exit 1
fi

echo "Event ID: $EVENT_ID"
echo ""

# Step 2: Poll for the result
echo "[2/2] Waiting for agent to complete..."
TIMEOUT=300  # 5 minutes
ELAPSED=0

while [ $ELAPSED -lt $TIMEOUT ]; do
  # Fetch the event stream and look for completion
  RESULT=$(curl -s -N "${API_URL}/call/predict/${EVENT_ID}" 2>/dev/null | \
    grep -m 1 'process_completed' | \
    sed 's/^data: //')

  if [ ! -z "$RESULT" ]; then
    echo ""
    echo "=========================================="
    echo "RESULT:"
    echo "=========================================="
    echo "$RESULT" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data['output']['data'][0])
except Exception as e:
    print('Error parsing result:', e, file=sys.stderr)
    print(data)
" 2>/dev/null
    echo "=========================================="
    exit 0
  fi

  echo -n "."
  sleep 2
  ELAPSED=$((ELAPSED + 2))
done

echo ""
echo "Timeout waiting for result"
exit 1
