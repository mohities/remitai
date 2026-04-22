from dotenv import load_dotenv
load_dotenv()

import os
import json
import time
import requests
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from azure.ai.agents import AgentsClient
from azure.identity import DefaultAzureCredential

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIR  = os.path.join(BASE_DIR, 'web')

app = Flask(__name__, static_folder=WEB_DIR, static_url_path='')
CORS(app)

PROJECT_ENDPOINT  = os.environ.get("FOUNDRY_PROJECT_ENDPOINT")
AGENT_ID          = os.environ.get("FOUNDRY_AGENT_ID")
FUNCTION_BASE_URL = os.environ.get("FUNCTION_BASE_URL")
FUNCTION_KEY      = os.environ.get("FUNCTION_KEY")

print(f"PROJECT_ENDPOINT:  {PROJECT_ENDPOINT}")
print(f"AGENT_ID:          {AGENT_ID}")
print(f"FUNCTION_BASE_URL: {FUNCTION_BASE_URL}")
print(f"WEB_DIR:           {WEB_DIR}")
print(f"index.html exists: {os.path.exists(os.path.join(WEB_DIR, 'index.html'))}")

agents_client = AgentsClient(
    endpoint=PROJECT_ENDPOINT,
    credential=DefaultAzureCredential()
)


@app.after_request
def after_request(response):
    response.headers['Access-Control-Allow-Origin']  = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    return response


def call_function(name: str, arguments: dict) -> str:
    url     = f"{FUNCTION_BASE_URL}/{name}"
    headers = {
        "Content-Type":    "application/json",
        "x-functions-key": FUNCTION_KEY
    }
    try:
        response = requests.post(
            url,
            headers=headers,
            json=arguments,
            timeout=30
        )
        return json.dumps(response.json())
    except Exception as e:
        print(f"Function call error: {str(e)}")
        return json.dumps({"error": str(e)})


def handle_tool_calls(run, thread_id: str):
    if not run.required_action:
        return []

    tool_outputs = []
    tool_results = []

    for tool_call in run.required_action.submit_tool_outputs.tool_calls:
        name      = tool_call.function.name
        arguments = json.loads(tool_call.function.arguments)

        print(f"\n  Tool called: {name}")
        print(f"  Arguments:   {json.dumps(arguments, indent=2)}")

        result     = call_function(name, arguments)
        result_obj = json.loads(result)

        print(f"  Result:      {result[:200]}")

        tool_outputs.append({
            "tool_call_id": tool_call.id,
            "output":       result
        })
        tool_results.append({
            "name":   name,
            "result": result_obj
        })

    agents_client.runs.submit_tool_outputs(
        thread_id=thread_id,
        run_id=run.id,
        tool_outputs=tool_outputs
    )

    return tool_results


@app.route('/')
def index():
    return send_from_directory(WEB_DIR, 'index.html')


@app.route('/<path:filename>')
def static_files(filename):
    return send_from_directory(WEB_DIR, filename)


@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({
        "status":   "ok",
        "agent_id": AGENT_ID
    })


@app.route('/api/thread', methods=['POST', 'OPTIONS'])
def create_thread():
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    try:
        thread = agents_client.threads.create()
        print(f"Thread created: {thread.id}")
        return jsonify({"thread_id": thread.id})
    except Exception as e:
        print(f"Thread error: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/chat', methods=['POST', 'OPTIONS'])
def chat():
    if request.method == 'OPTIONS':
        return jsonify({}), 200

    data      = request.json
    user_msg  = data.get('message', '').strip()
    thread_id = data.get('thread_id', '').strip()

    if not user_msg or not thread_id:
        return jsonify({"error": "Missing message or thread_id"}), 400

    print(f"\nUser [{thread_id[:8]}]: {user_msg}")

    try:
        agents_client.messages.create(
            thread_id=thread_id,
            role="user",
            content=user_msg
        )

        run = agents_client.runs.create(
            thread_id=thread_id,
            agent_id=AGENT_ID
        )

        all_tool_results = []

        while run.status in ["queued", "in_progress", "requires_action"]:
            time.sleep(1)
            run = agents_client.runs.get(
                thread_id=thread_id,
                run_id=run.id
            )
            if run.status == "requires_action":
                results = handle_tool_calls(run, thread_id)
                if results:
                    all_tool_results.extend(results)

        if run.status == "failed":
            error = getattr(run, 'last_error', 'Unknown error')
            print(f"Run failed: {error}")
            return jsonify({
                "response":     "I'm sorry, something went wrong. Please try again.",
                "tool_results": []
            })

        messages  = list(agents_client.messages.list(thread_id=thread_id))
        last_msg  = messages[0]
        response  = last_msg.content[0].text.value

        print(f"Agent: {response[:100]}")

        return jsonify({
            "response":     response,
            "tool_results": all_tool_results
        })

    except Exception as e:
        print(f"Chat error: {str(e)}")
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    print("\n" + "="*50)
    print("   RemitAI Web Server")
    print("="*50)
    print(f"Agent ID:  {AGENT_ID}")
    print(f"Web dir:   {WEB_DIR}")
    print(f"HTML file: {'FOUND' if os.path.exists(os.path.join(WEB_DIR, 'index.html')) else 'NOT FOUND'}")
    print("\nOpen http://localhost:5000 in Chrome")
    print("="*50 + "\n")
    app.run(
        debug=False,
        port=5000,
        host='0.0.0.0',
        threaded=True
    )