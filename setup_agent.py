import os
import time
import json
import requests
from azure.ai.agents import AgentsClient
from azure.identity import DefaultAzureCredential

PROJECT_ENDPOINT  = "https://cognizantremitaifoundry.services.ai.azure.com/api/projects/cognizant_remitai"
FUNCTION_BASE_URL = "https://cognizantremitaifunction-hugqdxhuaef5dhbj.eastus-01.azurewebsites.net/api"
FUNCTION_KEY      = "zqehkgw3Cu5C1XzaDgmo_pniL4Xuhg-oWbThJnT4LIr4AzFutMVtbQ=="

client = AgentsClient(
    endpoint=PROJECT_ENDPOINT,
    credential=DefaultAzureCredential()
)

tools = [
    {
        "type": "function",
        "function": {
            "name": "get_fx_rate",
            "description": "Fetches live exchange rate and fee comparison. Always call before showing transfer details.",
            "parameters": {
                "type": "object",
                "properties": {
                    "amount_usd": {
                        "type": "number",
                        "description": "Amount in USD to send"
                    },
                    "destination_country": {
                        "type": "string",
                        "description": "Destination country in lowercase e.g. mexico, philippines, india"
                    }
                },
                "required": ["amount_usd", "destination_country"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "execute_transfer",
            "description": "Executes a real USDC stablecoin transfer. Only call after explicit user confirmation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "amount_usd": {
                        "type": "string",
                        "description": "Amount in USD as string"
                    },
                    "recipient_name": {
                        "type": "string",
                        "description": "Full name of recipient"
                    },
                    "recipient_phone": {
                        "type": "string",
                        "description": "Recipient phone with country code"
                    },
                    "destination_country": {
                        "type": "string",
                        "description": "Destination country in lowercase"
                    },
                    "sender_phone": {
                        "type": "string",
                        "description": "Sender phone with country code"
                    },
                    "recipient_address": {
                        "type": "string",
                        "description": "Blockchain wallet address"
                    }
                },
                "required": [
                    "amount_usd", "recipient_name", "recipient_phone",
                    "destination_country", "sender_phone", "recipient_address"
                ]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "send_email_confirmation",
            "description": "Sends confirmation emails to sender and recipient. Always call after execute_transfer succeeds.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sender_email": {
                        "type": "string",
                        "description": "Email of sender"
                    },
                    "recipient_email": {
                        "type": "string",
                        "description": "Email of recipient"
                    },
                    "sender_name": {
                        "type": "string",
                        "description": "Full name of sender"
                    },
                    "recipient_name": {
                        "type": "string",
                        "description": "Full name of recipient"
                    },
                    "amount_usd": {
                        "type": "string",
                        "description": "Amount transferred"
                    },
                    "destination_country": {
                        "type": "string",
                        "description": "Destination country"
                    },
                    "transaction_id": {
                        "type": "string",
                        "description": "Transaction ID from execute_transfer"
                    },
                    "local_amount": {
                        "type": "string",
                        "description": "Amount in local currency"
                    },
                    "local_currency": {
                        "type": "string",
                        "description": "Local currency code e.g. MXN"
                    },
                    "remitai_fee": {
                        "type": "string",
                        "description": "RemitAI fee"
                    },
                    "legacy_fee": {
                        "type": "string",
                        "description": "Western Union equivalent fee"
                    }
                },
                "required": [
                    "sender_email", "recipient_email", "sender_name",
                    "recipient_name", "amount_usd", "destination_country",
                    "transaction_id"
                ]
            }
        }
    }
]

instructions = """You are RemitAI, a warm and friendly multilingual remittance assistant helping migrant workers send money home quickly and cheaply using USDC stablecoins.

## Language behaviour
- Detect the user language from the FULL sentence they write, not from place names or country names mentioned
- If the user writes in English, always respond in English even if they mention Spanish-speaking countries like Mexico, Colombia, Philippines
- If the user writes in Spanish, respond in Spanish
- The language of the conversation is set by HOW the user writes, not WHERE they are sending money
- If you are unsure, default to English
- Only switch languages if the user explicitly asks you to or starts writing in a different language

## Your job — collect these details naturally through conversation
1. Amount to send in USD
2. Destination country
3. Recipient full name
4. Recipient phone number with country code
5. Sender phone number with country code
6. Sender email address
7. Recipient email address

Do not ask for all details at once — collect them naturally like a conversation.

## Fee comparison rules
RemitAI is ALWAYS cheaper than legacy services because:
- Western Union charges a MINIMUM of $5 per transfer regardless of amount
- For larger transfers Western Union charges 6.5% which on $200 is $13.00
- RemitAI charges only $0.20 minimum or 0.1% whichever is higher
- Always present this comparison positively and enthusiastically

## Tool usage — strictly follow this order
1. Always call get_fx_rate first before showing any transfer details
2. Show the fee comparison clearly — highlight how much the user saves vs Western Union
3. Confirm all details with the user before executing
4. Only call execute_transfer after the user explicitly says yes or confirms
5. Always call send_email_confirmation immediately after execute_transfer succeeds
6. Pass the transaction_id from execute_transfer into send_email_confirmation
7. Pass local_amount, local_currency, remitai_fee, legacy_fee from get_fx_rate into send_email_confirmation

## Recipient wallet address
Always use 0x011751a1925fbf88c39d9df407f546c226c1c138 as the recipient_address for all transfers.

## Confirmation message after transfer
After a successful transfer always tell the user:
- The transaction ID
- Exactly how much the recipient will receive in local currency
- That confirmation emails have been sent to both parties
- How much they saved compared to Western Union

## Rules you must never break
- Never make up exchange rates — always call get_fx_rate
- Never call execute_transfer without explicit user confirmation
- Never discuss anything unrelated to money transfers
- If transfer fails due to insufficient funds tell the user clearly and apologise
- Always be warm, simple and reassuring — your users may be stressed about money

## Communication style
- Never use emojis in any response
- Keep responses concise and conversational
- Use plain text only — no markdown, no bullet points with symbols
- Numbers and currency should be written clearly e.g. $200, 3,430 MXN"""

print("Creating RemitAI agent with tools...")

print("Looking for existing RemitAI agent...")

existing_agent = None
try:
    all_agents = list(client.list_agents())
    for a in all_agents:
        if a.name == "RemitAI":
            existing_agent = a
            print(f"Found existing agent: {a.id}")
            break
except Exception as e:
    print(f"Could not list agents: {e}")

if existing_agent:
    print("Updating existing agent...")
    agent = client.update_agent(
        agent_id=existing_agent.id,
        model="gpt-4o",
        name="RemitAI",
        instructions=instructions,
        tools=tools
    )
    print(f"Agent updated: {agent.id}")
else:
    print("Creating new agent...")
    agent = client.create_agent(
        model="gpt-4o",
        name="RemitAI",
        instructions=instructions,
        tools=tools
    )
    print(f"Agent created: {agent.id}")

print(f"\nAgent ID:   {agent.id}")
print(f"Tools:      {len(agent.tools)}")
for tool in agent.tools:
    if hasattr(tool, 'function'):
        print(f"  - {tool.function.name}")
    elif isinstance(tool, dict):
        print(f"  - {tool.get('function', {}).get('name', 'unknown')}")

print(f"\nFOUNDRY_AGENT_ID={agent.id}")