import json
import os
import sys
from dotenv import load_dotenv
import httpx

# Load environment variables
load_dotenv()

BASE_URL = "https://api.meta.ai/v1"
MODEL_ID = "muse-spark-1.3"

# Retrieve API key
api_key = os.getenv("META_API_KEY") or os.getenv("MODEL_API_KEY")

if not api_key or not api_key.strip():
    print("Error: META_API_KEY not found or empty in environment / .env file.", file=sys.stderr)
    print("Please set META_API_KEY in .env before running this smoke test.", file=sys.stderr)
    sys.exit(1)

headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json",
}


def handle_http_error(response: httpx.Response):
    """Provide clear, actionable messages for common HTTP error statuses."""
    status = response.status_code
    try:
        body = response.json()
        error_msg = body.get("error", {}).get("message", response.text)
    except Exception:
        error_msg = response.text

    if status == 401:
        print(f"\n[ERROR 401] Authentication failed: Invalid or expired API key. Details: {error_msg}", file=sys.stderr)
    elif status == 429:
        print(f"\n[ERROR 429] Rate limit exceeded or quota exhausted. Details: {error_msg}", file=sys.stderr)
    elif 500 <= status < 600:
        print(f"\n[ERROR {status}] Meta Model API server error. Please retry later. Details: {error_msg}", file=sys.stderr)
    else:
        print(f"\n[ERROR {status}] Request failed: {error_msg}", file=sys.stderr)


def step1_plain_chat():
    print("=" * 60)
    print("STEP 1: Plain Chat Completion Call")
    print(f"Model: {MODEL_ID}")
    print(f"Endpoint: {BASE_URL}/chat/completions")
    print("=" * 60)

    payload = {
        "model": MODEL_ID,
        "messages": [
            {"role": "developer", "content": "You are Canary Analyst, an expert in geomechanical ground-subsidence monitoring."},
            {"role": "user", "content": "Briefly introduce yourself in two sentences."}
        ],
        "temperature": 0.2
    }

    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(f"{BASE_URL}/chat/completions", headers=headers, json=payload)
            if resp.status_code != 200:
                handle_http_error(resp)
                return False

            data = resp.json()
            message = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})

            print("\nResponse:")
            print(message.strip())
            print("\nToken Usage:")
            print(json.dumps(usage, indent=2))
            return True
    except httpx.RequestError as exc:
        print(f"\n[Network Error] Failed to connect to Meta Model API: {exc}", file=sys.stderr)
        return False


def dummy_get_weather(city: str) -> str:
    """Fake local tool implementation."""
    return json.dumps({"city": city, "temperature": "22 C", "condition": "Sunny", "status": "nominal"})


def step2_tool_calling():
    print("\n" + "=" * 60)
    print("STEP 2: Native Tool-Calling (Function Calling)")
    print(f"Model: {MODEL_ID}")
    print("=" * 60)

    # Define tool schema
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get current weather condition for a given city.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "city": {
                            "type": "string",
                            "description": "The city name, e.g. San Francisco"
                        }
                    },
                    "required": ["city"],
                    "additionalProperties": False
                }
            }
        }
    ]

    messages = [
        {"role": "user", "content": "What's the weather in Tokyo right now?"}
    ]

    payload = {
        "model": MODEL_ID,
        "messages": messages,
        "tools": tools,
        "tool_choice": "auto"
    }

    print("Sending prompt requiring tool call: 'What\\'s the weather in Tokyo right now?'")

    try:
        with httpx.Client(timeout=30.0) as client:
            # 1. Ask model, expecting a tool call
            resp = client.post(f"{BASE_URL}/chat/completions", headers=headers, json=payload)
            if resp.status_code != 200:
                handle_http_error(resp)
                return False

            data = resp.json()
            assistant_message = data["choices"][0]["message"]
            tool_calls = assistant_message.get("tool_calls", [])

            if not tool_calls:
                print("Model did not return tool_calls. Content:", assistant_message.get("content"))
                return False

            print(f"\nModel requested {len(tool_calls)} tool call(s):")
            for tc in tool_calls:
                print(f"- ID: {tc.get('id')}")
                print(f"  Function: {tc.get('function', {}).get('name')}")
                print(f"  Arguments: {tc.get('function', {}).get('arguments')}")

            # 2. Append assistant response to dialogue history
            messages.append(assistant_message)

            # 3. Execute dummy tool and append tool result message
            for tc in tool_calls:
                fn_name = tc["function"]["name"]
                args = json.loads(tc["function"]["arguments"])
                call_id = tc["id"]

                if fn_name == "get_weather":
                    result = dummy_get_weather(args.get("city", "Tokyo"))
                    print(f"\nExecuted fake tool '{fn_name}' with args {args} -> Result: {result}")
                    messages.append({
                        "role": "tool",
                        "tool_call_id": call_id,
                        "content": result
                    })

            # 4. Feed back to model for final answer
            followup_payload = {
                "model": MODEL_ID,
                "messages": messages,
                "tools": tools
            }

            resp2 = client.post(f"{BASE_URL}/chat/completions", headers=headers, json=followup_payload)
            if resp2.status_code != 200:
                handle_http_error(resp2)
                return False

            data2 = resp2.json()
            final_answer = data2["choices"][0]["message"]["content"]
            usage2 = data2.get("usage", {})

            print("\nFinal Assistant Answer:")
            print(final_answer.strip())
            print("\nToken Usage (Final turn):")
            print(json.dumps(usage2, indent=2))
            return True

    except httpx.RequestError as exc:
        print(f"\n[Network Error] Failed during tool calling execution: {exc}", file=sys.stderr)
        return False


def main():
    print("Running Canary Analyst Smoke Test (Muse Spark 1.3)...")
    s1 = step1_plain_chat()
    if not s1:
        print("\nStep 1 failed. Aborting Step 2.", file=sys.stderr)
        sys.exit(1)

    s2 = step2_tool_calling()
    if not s2:
        print("\nStep 2 failed.", file=sys.stderr)
        sys.exit(1)

    print("\n" + "=" * 60)
    print("ALL SMOKE TESTS COMPLETED SUCCESSFULLY.")
    print("=" * 60)


if __name__ == "__main__":
    main()

