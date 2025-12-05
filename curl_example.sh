#!/bin/bash

# Simple curl example for the browser agent endpoint
# Usage: ./curl_example.sh "Your task here"

TASK="${1:-Go to example.com and tell me what you see}"
API_URL="http://127.0.0.1:7789"

echo "Submitting task: $TASK"
echo ""

# Step 1: Join the queue and get event_id
echo "Step 1: Joining queue..."
RESPONSE=$(curl -s -X POST "${API_URL}/gradio_api/call/predict" \
  -H "Content-Type: application/json" \
  -d "{\"data\":[\"${TASK}\"]}")

EVENT_ID=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['event_id'])")
echo "Event ID: $EVENT_ID"
echo ""

# Step 2: Stream the results
echo "Step 2: Waiting for results (this may take a minute)..."
echo ""

curl -s -N "${API_URL}/gradio_api/call/predict/${EVENT_ID}" | while IFS= read -r line; do
  # Skip empty lines and heartbeat messages
  if [[ -z "$line" ]] || [[ "$line" == "event: heartbeat" ]]; then
    continue
  fi

  # Parse data lines
  if [[ "$line" == data:* ]]; then
    # Extract JSON after "data: "
    json_data="${line#data: }"

    # Check if it's the complete message
    if echo "$json_data" | grep -q '"msg":"process_completed"'; then
      echo "=========================================="
      echo "RESULT:"
      echo "=========================================="
      echo "$json_data" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data['output']['data'][0])" 2>/dev/null || echo "$json_data"
      echo "=========================================="
      break
    fi

    # Show progress
    if echo "$json_data" | grep -q '"msg":"process_generating"'; then
      echo -n "."
    fi
  fi
done

echo ""
echo "Done!"
