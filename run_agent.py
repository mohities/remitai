import os
import json
import time
import requests
from azure.ai.agents import AgentsClient
from azure.identity import DefaultAzureCredential


AGENT_ID          = "asst_iPi4o4bFyWc9uRhFZm98e4ma"
PROJECT_ENDPOINT  = "https://cognizantremitaifoundry.services.ai.azure.com/api/projects/cognizant_remitai"
FUNCTION_BASE_URL = "https://cognizantremitaifunction-hugqdxhuaef5dhbj.eastus-01.azurewebsites.net/api"
FUNCTION_KEY      = "zqehkgw3Cu5C1XzaDgmo_pniL4Xuhg-oWbThJnT4LIr4AzFutMVtbQ=="

client = AgentsClient(
    endpoint=PROJECT_ENDPOINT,
    credential=DefaultAzureCredential()
)

def call_azure_function(function_name: str, arguments: dict) -> str:
    url     = f"{FUNCTION_BASE_URL}/{function_name}"
    headers = {
        "Content-Type":    "application/json",
        "x-functions-key": FUNCTION_KEY
    }
    try:
        response = requests.post(
            url, headers=headers, json=arguments, timeout=30
        )
        return json.dumps(response.json())
    except Exception as e:
        return json.dumps({"error": str(e)})

def process_tool_calls(run, thread_id):
    if not run.required_action:
        return

    tool_outputs = []
    for tool_call in run.required_action.submit_tool_outputs.tool_calls:
        name      = tool_call.function.name
        arguments = json.loads(tool_call.function.arguments)

        print(f"\n  Calling tool: {name}")
        print(f"  Arguments:    {json.dumps(arguments, indent=2)}")

        result = call_azure_function(name, arguments)
        print(f"  Result:       {result[:300]}")

        tool_outputs.append({
            "tool_call_id": tool_call.id,
            "output":       result
        })

    client.runs.submit_tool_outputs(
        thread_id=thread_id,
        run_id=run.id,
        tool_outputs=tool_outputs
    )

def chat(user_message: str, thread_id: str = None):
    if not thread_id:
        thread    = client.threads.create()
        thread_id = thread.id
        print(f"Thread created: {thread_id}")

    client.messages.create(
        thread_id=thread_id,
        role="user",
        content=user_message
    )

    run = client.runs.create(
        thread_id=thread_id,
        agent_id=AGENT_ID
    )

    while run.status in ["queued", "in_progress", "requires_action"]:
        time.sleep(1)
        run = client.runs.get(
            thread_id=thread_id,
            run_id=run.id
        )

        if run.status == "requires_action":
            process_tool_calls(run, thread_id)

    if run.status == "failed":
        print(f"Run failed: {run.last_error}")
        return "Sorry something went wrong. Please try again.", thread_id

    messages     = client.messages.list(thread_id=thread_id)
    messages_list = list(messages)
    last_msg     = messages_list[0]
    response     = last_msg.content[0].text.value

    return response, thread_id

if __name__ == "__main__":
    print("RemitAI Agent — type 'quit' to exit\n")
    thread_id = None

    while True:
        user_input = input("You: ").strip()
        if user_input.lower() == "quit":
            break
        if not user_input:
            continue

        print("\nThinking...")
        response, thread_id = chat(user_input, thread_id)
        print(f"\nRemitAI: {response}\n")