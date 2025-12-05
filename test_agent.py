"""
Test script for the simple agent endpoint
"""
from gradio_client import Client

# Simple test task
task = "Go to google.com and tell me what you see"

print(f"Testing agent with task: {task}")
print("Connecting to agent...")

try:
    # Connect to the Gradio interface
    client = Client("http://127.0.0.1:7789")

    print("Sending task to agent (this may take a while)...")

    # Call the predict function
    result = client.predict(
        task,
        api_name="/predict"
    )

    print("\n" + "="*60)
    print("AGENT RESPONSE:")
    print("="*60)
    print(result)
    print("="*60)

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
