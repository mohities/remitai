import azure.functions as func
import requests
import json
import os
import logging
import uuid
from datetime import datetime, timezone

def cors_headers() -> dict:
    return {
        'Access-Control-Allow-Origin':  '*',
        'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type, x-functions-key'
    }

def options_response() -> func.HttpResponse:
    return func.HttpResponse(
        status_code=200,
        headers=cors_headers()
    )

app = func.FunctionApp()

# ─────────────────────────────────────────────
# FUNCTION 1 — get_fx_rate
# ─────────────────────────────────────────────
@app.route(route="get_fx_rate", auth_level=func.AuthLevel.FUNCTION)
def get_fx_rate(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('get_fx_rate function triggered')

    try:
        req_body = req.get_json()
        amount_usd = float(req_body.get('amount_usd'))
        destination_country = req_body.get('destination_country')
    except Exception as e:
        return func.HttpResponse(
            json.dumps({"error": "Invalid input. Provide amount_usd and destination_country."}),
            status_code=400,
            mimetype="application/json",
            headers=cors_headers()
        )

    country_currency_map = {
        "mexico": "MXN",
        "philippines": "PHP",
        "india": "INR",
        "colombia": "COP",
        "nigeria": "NGN",
        "kenya": "KES",
        "pakistan": "PKR",
        "bangladesh": "BDT",
        "ghana": "GHS",
        "egypt": "EGP"
    }

    destination_lower = destination_country.lower()
    target_currency = country_currency_map.get(destination_lower)

    if not target_currency:
        return func.HttpResponse(
            json.dumps({"error": f"Country '{destination_country}' not supported yet."}),
            status_code=400,
            mimetype="application/json",
            headers=cors_headers()
        )

    try:
        fx_api_key = os.environ.get("FX_API_KEY")
        fx_api_url = os.environ.get("FX_API_URL")
        url = f"{fx_api_url}/{fx_api_key}/latest/USD"
        response = requests.get(url, timeout=10)
        data = response.json()

        if data.get("result") != "success":
            raise Exception("FX API returned error")

        exchange_rate = data["conversion_rates"][target_currency]
        local_amount = round(amount_usd * exchange_rate, 2)

        remitai_fee = round(amount_usd * 0.001, 2)
        remitai_fee = max(remitai_fee, 0.20)
        legacy_fee  = round(amount_usd * 0.065, 2)
        legacy_fee  = max(legacy_fee, 5.00)
        savings     = round(legacy_fee - remitai_fee, 2)

        result = {
            "amount_usd": amount_usd,
            "destination_country": destination_country,
            "target_currency": target_currency,
            "exchange_rate": exchange_rate,
            "local_amount": local_amount,
            "remitai_fee_usd": remitai_fee,
            "legacy_fee_usd": legacy_fee,
            "savings_usd": savings,
            "estimated_delivery": "Under 60 seconds"
        }

        return func.HttpResponse(
            json.dumps(result),
            status_code=200,
            mimetype="application/json",
            headers=cors_headers()
        )

    except Exception as e:
        logging.error(f"FX rate fetch failed: {str(e)}")
        return func.HttpResponse(
            json.dumps({"error": "Could not fetch exchange rate. Please try again."}),
            status_code=500,
            mimetype="application/json",
            headers=cors_headers()
        )


# ─────────────────────────────────────────────
# FUNCTION 2 — execute_transfer (coming next)
# ─────────────────────────────────────────────

@app.route(route="execute_transfer", auth_level=func.AuthLevel.FUNCTION)
def execute_transfer(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('execute_transfer function triggered')

    try:
        req_body            = req.get_json()
        amount_usd          = str(req_body.get('amount_usd'))
        recipient_phone     = req_body.get('recipient_phone')
        recipient_name      = req_body.get('recipient_name')
        destination_country = req_body.get('destination_country')
        sender_phone        = req_body.get('sender_phone')
        recipient_address   = req_body.get('recipient_address')
    except Exception:
        return func.HttpResponse(
            json.dumps({"error": "Invalid input. Check all required fields."}),
            status_code=400,
            mimetype="application/json",
            headers=cors_headers()
        )

    if not all([amount_usd, recipient_phone, recipient_name,
                destination_country, sender_phone, recipient_address]):
        return func.HttpResponse(
            json.dumps({"error": "Missing required fields."}),
            status_code=400,
            mimetype="application/json",
            headers=cors_headers()
        )

    transaction_id = f"REMITAI-{str(uuid.uuid4())[:8].upper()}"
    timestamp      = datetime.now(timezone.utc).isoformat()

    try:
        circle_api_key = os.environ.get("CIRCLE_API_KEY")
        circle_api_url = os.environ.get("CIRCLE_API_URL")
        wallet_id      = os.environ.get("CIRCLE_WALLET_ID")
        entity_secret  = os.environ.get("CIRCLE_ENTITY_SECRET")
        blockchain     = os.environ.get("CIRCLE_BLOCKCHAIN", "ETH-SEPOLIA")

        logging.info("Generating fresh entity secret ciphertext...")
        entity_secret_cipher = generate_entity_secret_ciphertext(entity_secret)
        logging.info(f"Ciphertext length: {len(entity_secret_cipher)}")

        headers = {
            "Authorization": f"Bearer {circle_api_key}",
            "Content-Type":  "application/json"
        }

        transfer_payload = {
            "idempotencyKey":         str(uuid.uuid4()),
            "walletId":               wallet_id,
            "entitySecretCiphertext": entity_secret_cipher,
            "amounts":                [str(amount_usd)],
            "destinationAddress":     recipient_address,
            "tokenAddress":           "0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238",
            "blockchain":             blockchain,
            "feeLevel":               "MEDIUM"
        }

        logging.info(f"Sending payload to Circle: {json.dumps(transfer_payload, indent=2)}")

        circle_response = requests.post(
            f"{circle_api_url}/developer/transactions/transfer",
            headers=headers,
            json=transfer_payload,
            timeout=30
        )

        circle_data = circle_response.json()
        logging.info(f"Circle status: {circle_response.status_code}")
        logging.info(f"Circle response: {json.dumps(circle_data, indent=2)}")

        if circle_response.status_code in [200, 201]:
            circle_tx_id  = circle_data.get("data", {}).get("id", transaction_id)
            circle_status = circle_data.get("data", {}).get("state", "INITIATED")
        else:
            error_msg  = circle_data.get("message", "Unknown error")
            error_code = circle_data.get("code", "unknown")
            logging.error(f"Circle error {error_code}: {error_msg}")
            return func.HttpResponse(
                json.dumps({
                    "error":              f"Transfer failed: {error_msg}",
                    "circle_error_code":  error_code,
                    "circle_message":     error_msg
                }),
                status_code=500,
                mimetype="application/json",
                xheaders=cors_headers()
            )

        result = {
            "transaction_id":      transaction_id,
            "circle_transfer_id":  circle_tx_id,
            "status":              circle_status,
            "amount_usd":          amount_usd,
            "recipient_name":      recipient_name,
            "recipient_phone":     recipient_phone,
            "destination_country": destination_country,
            "sender_phone":        sender_phone,
            "timestamp":           timestamp,
            "estimated_delivery":  "Under 60 seconds",
            "mode":                "live",
            "message": (
                f"Transfer of ${amount_usd} USDC to "
                f"{recipient_name} initiated successfully."
            )
        }

        save_to_cosmos(result)

        return func.HttpResponse(
            json.dumps(result),
            status_code=200,
            mimetype="application/json",

        )

    except Exception as e:
        logging.error(f"Transfer failed: {str(e)}")
        return func.HttpResponse(
            json.dumps({"error": f"Transfer failed: {str(e)}"}),
            status_code=500,
            mimetype="application/json",
            headers=cors_headers()
        )

def save_to_cosmos(transaction: dict):
    try:
        from azure.cosmos import CosmosClient

        conn_str = os.environ.get("COSMOS_DB_CONNECTION_STRING")
        if not conn_str:
            logging.warning("Cosmos DB connection string not set — skipping save")
            return

        client    = CosmosClient.from_connection_string(conn_str)
        database  = client.get_database_client("cognizant-remitai")
        container = database.get_container_client("transactions")

        transaction["id"] = transaction["transaction_id"]
        container.upsert_item(transaction)
        logging.info(f"Transaction saved to Cosmos DB: {transaction['id']}")

    except Exception as e:
        logging.error(f"Cosmos DB save failed: {str(e)}")


def generate_entity_secret_ciphertext(entity_secret_hex: str) -> str:
    """
    Dynamically generates a fresh entity secret ciphertext
    by fetching Circle's public key and encrypting with RSA-OAEP
    Must be called fresh for every Circle API request
    """
    import base64
    from cryptography.hazmat.primitives import serialization, hashes
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.backends import default_backend

    circle_api_key = os.environ.get("CIRCLE_API_KEY")

    response = requests.get(
        "https://api.circle.com/v1/w3s/config/entity/publicKey",
        headers={
            "Authorization": f"Bearer {circle_api_key}",
            "Content-Type": "application/json"
        },
        timeout=10
    )

    data = response.json()
    public_key_pem = data["data"]["publicKey"]

    entity_secret_bytes = bytes.fromhex(entity_secret_hex)

    public_key = serialization.load_pem_public_key(
        public_key_pem.encode(),
        backend=default_backend()
    )

    encrypted = public_key.encrypt(
        entity_secret_bytes,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )

    return base64.b64encode(encrypted).decode("utf-8")

def get_circle_token_id(api_key: str, blockchain: str, symbol: str) -> str:
    """
    Dynamically fetch the token ID from Circle API
    based on blockchain and token symbol
    """
    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        response = requests.get(
            f"https://api.circle.com/v1/w3s/tokens",
            headers=headers,
            params={
                "blockchain": blockchain,
                "pageSize": 50
            },
            timeout=10
        )

        data = response.json()
        logging.info(f"Token lookup response: {data}")

        if data.get("data") and data["data"].get("tokens"):
            for token in data["data"]["tokens"]:
                if (token.get("symbol", "").upper() == symbol.upper() and
                    token.get("blockchain", "").upper() == blockchain.upper()):
                    logging.info(f"Found token ID for {symbol} on {blockchain}: {token['id']}")
                    return token["id"]

        logging.warning(f"Token {symbol} not found on {blockchain} — using fallback")
        return None

    except Exception as e:
        logging.error(f"Token lookup failed: {str(e)}")
        return None


# ─────────────────────────────────────────────
# FUNCTION 3 — send_email_confirmation
# ─────────────────────────────────────────────
@app.route(route="send_email_confirmation", auth_level=func.AuthLevel.FUNCTION)
def send_email_confirmation(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('send_email_confirmation function triggered')

    try:
        req_body            = req.get_json()
        sender_email        = req_body.get('sender_email')
        recipient_email     = req_body.get('recipient_email')
        sender_name         = req_body.get('sender_name', 'Sender')
        recipient_name      = req_body.get('recipient_name', 'Recipient')
        amount_usd          = req_body.get('amount_usd')
        destination_country = req_body.get('destination_country')
        transaction_id      = req_body.get('transaction_id')
        local_amount        = req_body.get('local_amount', '')
        local_currency      = req_body.get('local_currency', '')
        remitai_fee         = req_body.get('remitai_fee', '0.20')
        legacy_fee          = req_body.get('legacy_fee', '')
    except Exception:
        return func.HttpResponse(
            json.dumps({"error": "Invalid input."}),
            status_code=400,
            mimetype="application/json",
            headers=cors_headers()
        )

    if not all([sender_email, recipient_email, amount_usd,
                transaction_id, destination_country]):
        return func.HttpResponse(
            json.dumps({"error": "Missing required fields."}),
            status_code=400,
            mimetype="application/json",
            headers=cors_headers()
        )

    try:
        from azure.communication.email import EmailClient

        conn_str     = os.environ.get("AZURE_EMAIL_CONNECTION_STRING")
        from_addr    = os.environ.get("AZURE_EMAIL_SENDER")

        if not conn_str or not from_addr:
            return func.HttpResponse(
                json.dumps({"error": "Email configuration missing."}),
                status_code=500,
                mimetype="application/json",
                headers=cors_headers()
            )

        email_client = EmailClient.from_connection_string(conn_str)

        sender_body = (
            "<html><body style='font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;'>"
            "<div style='background-color: #1a73e8; padding: 20px; text-align: center;'>"
            "<h1 style='color: white; margin: 0;'>RemitAI</h1>"
            "<p style='color: #e8f0fe; margin: 5px 0;'>Stablecoin Remittance</p>"
            "</div>"
            "<div style='padding: 30px; background-color: #f8f9fa;'>"
            "<h2 style='color: #1a73e8;'>Transfer Initiated Successfully</h2>"
            "<p>Hi " + sender_name + ", your transfer is on its way.</p>"
            "<div style='background: white; border-radius: 8px; padding: 20px; margin: 20px 0;'>"
            "<table style='width: 100%; border-collapse: collapse;'>"
            "<tr><td style='padding: 8px 0; color: #666;'>Amount sent</td>"
            "<td style='padding: 8px 0; font-weight: bold;'>$" + str(amount_usd) + " USDC</td></tr>"
            "<tr><td style='padding: 8px 0; color: #666;'>Recipient</td>"
            "<td style='padding: 8px 0; font-weight: bold;'>" + recipient_name + "</td></tr>"
            "<tr><td style='padding: 8px 0; color: #666;'>Destination</td>"
            "<td style='padding: 8px 0; font-weight: bold;'>" + destination_country.title() + "</td></tr>"
            "<tr><td style='padding: 8px 0; color: #666;'>Recipient receives</td>"
            "<td style='padding: 8px 0; font-weight: bold;'>" + str(local_amount) + " " + str(local_currency) + "</td></tr>"
            "<tr><td style='padding: 8px 0; color: #666;'>RemitAI fee</td>"
            "<td style='padding: 8px 0; font-weight: bold; color: #34a853;'>$" + str(remitai_fee) + "</td></tr>"
            "<tr><td style='padding: 8px 0; color: #666;'>You saved vs Western Union</td>"
            "<td style='padding: 8px 0; font-weight: bold; color: #34a853;'>$" + str(legacy_fee) + "</td></tr>"
            "<tr style='border-top: 1px solid #eee;'>"
            "<td style='padding: 8px 0; color: #666;'>Transaction ID</td>"
            "<td style='padding: 8px 0; font-size: 12px; color: #999;'>" + transaction_id + "</td></tr>"
            "<tr><td style='padding: 8px 0; color: #666;'>Estimated delivery</td>"
            "<td style='padding: 8px 0; font-weight: bold; color: #34a853;'>Under 60 seconds</td></tr>"
            "</table></div>"
            "<div style='background: #e8f5e9; border-radius: 8px; padding: 15px; margin: 20px 0;'>"
            "<p style='margin: 0; color: #2e7d32;'>"
            "<strong>You saved $" + str(legacy_fee) + " vs Western Union.</strong> "
            "Traditional services charge $" + str(legacy_fee) + ". "
            "RemitAI charged only $" + str(remitai_fee) + "."
            "</p></div></div>"
            "<div style='padding: 20px; text-align: center; color: #999; font-size: 12px;'>"
            "<p>Powered by Azure AI Foundry and USDC Stablecoin Technology</p>"
            "<p>Transaction ID: " + transaction_id + "</p>"
            "</div></body></html>"
        )

        recipient_body = (
            "<html><body style='font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;'>"
            "<div style='background-color: #1a73e8; padding: 20px; text-align: center;'>"
            "<h1 style='color: white; margin: 0;'>RemitAI</h1>"
            "<p style='color: #e8f0fe; margin: 5px 0;'>Stablecoin Remittance</p>"
            "</div>"
            "<div style='padding: 30px; background-color: #f8f9fa;'>"
            "<h2 style='color: #1a73e8;'>You have received money!</h2>"
            "<p>Hi " + recipient_name + ", " + sender_name + " has sent you money.</p>"
            "<div style='background: white; border-radius: 8px; padding: 20px; margin: 20px 0;'>"
            "<table style='width: 100%; border-collapse: collapse;'>"
            "<tr><td style='padding: 8px 0; color: #666;'>From</td>"
            "<td style='padding: 8px 0; font-weight: bold;'>" + sender_name + "</td></tr>"
            "<tr><td style='padding: 8px 0; color: #666;'>Amount received</td>"
            "<td style='padding: 8px 0; font-weight: bold; font-size: 24px; color: #1a73e8;'>"
            + str(local_amount) + " " + str(local_currency) + "</td></tr>"
            "<tr><td style='padding: 8px 0; color: #666;'>Equivalent in USD</td>"
            "<td style='padding: 8px 0; font-weight: bold;'>$" + str(amount_usd) + "</td></tr>"
            "<tr><td style='padding: 8px 0; color: #666;'>Status</td>"
            "<td style='padding: 8px 0; font-weight: bold; color: #34a853;'>Delivered</td></tr>"
            "<tr style='border-top: 1px solid #eee;'>"
            "<td style='padding: 8px 0; color: #666;'>Transaction ID</td>"
            "<td style='padding: 8px 0; font-size: 12px; color: #999;'>" + transaction_id + "</td></tr>"
            "</table></div></div>"
            "<div style='padding: 20px; text-align: center; color: #999; font-size: 12px;'>"
            "<p>Powered by Azure AI Foundry and USDC Stablecoin Technology</p>"
            "</div></body></html>"
        )

        sender_message = {
            "senderAddress": from_addr,
            "recipients": {
                "to": [{"address": sender_email}]
            },
            "content": {
                "subject": "RemitAI — Your transfer of $" + str(amount_usd) + " to " + recipient_name + " is on its way",
                "html": sender_body
            }
        }

        recipient_message = {
            "senderAddress": from_addr,
            "recipients": {
                "to": [{"address": recipient_email}]
            },
            "content": {
                "subject": "RemitAI — " + sender_name + " sent you " + str(local_amount) + " " + str(local_currency),
                "html": recipient_body
            }
        }

        logging.info(f"Sending sender confirmation to: {sender_email}")
        sender_poller   = email_client.begin_send(sender_message)
        sender_result   = sender_poller.result()
        logging.info(f"Sender email result: {sender_result}")

        logging.info(f"Sending recipient notification to: {recipient_email}")
        recipient_poller = email_client.begin_send(recipient_message)
        recipient_result = recipient_poller.result()
        logging.info(f"Recipient email result: {recipient_result}")

        result = {
            "status": "sent",
            "sender_email": sender_email,
            "recipient_email": recipient_email,
            "transaction_id": transaction_id,
            "message": "Confirmation emails sent to both sender and recipient"
        }

        return func.HttpResponse(
            json.dumps(result),
            status_code=200,
            mimetype="application/json",
            headers=cors_headers()
        )

    except Exception as e:
        logging.error(f"Email sending failed: {str(e)}")
        return func.HttpResponse(
            json.dumps({"error": f"Email sending failed: {str(e)}"}),
            status_code=500,
            mimetype="application/json",
            headers=cors_headers()
        )

# ─────────────────────────────────────────────
# FUNCTION 4 — chat_handler
# Bridges the web UI to the Foundry agent
# ─────────────────────────────────────────────

@app.route(route="create_thread", auth_level=func.AuthLevel.ANONYMOUS)
def create_thread(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('create_thread triggered')

    if req.method == 'OPTIONS':
        return options_response()

    try:
        from azure.ai.agents import AgentsClient
        from azure.identity import DefaultAzureCredential
        import traceback

        endpoint = os.environ.get("FOUNDRY_PROJECT_ENDPOINT")
        agent_id = os.environ.get("FOUNDRY_AGENT_ID")

        logging.info(f"Endpoint: {endpoint}")
        logging.info(f"Agent ID: {agent_id}")

        if not endpoint:
            return func.HttpResponse(
                json.dumps({"error": "FOUNDRY_PROJECT_ENDPOINT not configured"}),
                status_code=500,
                mimetype="application/json",
                headers=cors_headers()
            )

        credential = DefaultAzureCredential()
        client     = AgentsClient(
            endpoint=endpoint,
            credential=credential
        )

        logging.info("AgentsClient created — creating thread...")
        thread = client.threads.create()
        logging.info(f"Thread created: {thread.id}")

        return func.HttpResponse(
            json.dumps({"thread_id": thread.id}),
            status_code=200,
            mimetype="application/json",
            headers=cors_headers()
        )

    except Exception as e:
        error_detail = traceback.format_exc()
        logging.error(f"create_thread failed: {str(e)}")
        logging.error(f"Traceback: {error_detail}")
        return func.HttpResponse(
            json.dumps({
                "error":   str(e),
                "detail":  error_detail
            }),
            status_code=500,
            mimetype="application/json",
            headers=cors_headers()
        )


@app.route(route="chat_handler", auth_level=func.AuthLevel.ANONYMOUS)
def chat_handler(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('chat_handler triggered')

    if req.method == 'OPTIONS':
        return options_response()

    try:
        body      = req.get_json()
        user_msg  = body.get('message', '').strip()
        thread_id = body.get('thread_id', '').strip()

        if not user_msg or not thread_id:
            return func.HttpResponse(
                json.dumps({"error": "Missing message or thread_id"}),
                status_code=400,
                mimetype="application/json",
                headers=c
            )

    except Exception as e:
        return func.HttpResponse(
            json.dumps({"error": f"Invalid request: {str(e)}"}),
            status_code=400,
            mimetype="application/json",
            headers=cors_headers()
        )

    try:
        from azure.ai.agents import AgentsClient
        from azure.identity import DefaultAzureCredential

        endpoint = os.environ.get("FOUNDRY_PROJECT_ENDPOINT")
        agent_id = os.environ.get("FOUNDRY_AGENT_ID")
        func_url = os.environ.get("FUNCTION_BASE_URL")
        func_key = os.environ.get("FUNCTION_KEY")

        client = AgentsClient(
            endpoint=endpoint,
            credential=DefaultAzureCredential()
        )

        client.messages.create(
            thread_id=thread_id,
            role="user",
            content=user_msg
        )

        run = client.runs.create(
            thread_id=thread_id,
            agent_id=agent_id
        )

        all_tool_results = []

        while run.status in ["queued", "in_progress", "requires_action"]:
            time.sleep(1)
            run = client.runs.get(
                thread_id=thread_id,
                run_id=run.id
            )

            if run.status == "requires_action":
                tool_outputs = []

                for tool_call in run.required_action.submit_tool_outputs.tool_calls:
                    name      = tool_call.function.name
                    arguments = json.loads(tool_call.function.arguments)

                    logging.info(f"Tool called: {name}")
                    logging.info(f"Arguments: {json.dumps(arguments)}")

                    tool_url     = f"{func_url}/{name}"
                    tool_headers = {
                        "Content-Type":    "application/json",
                        "x-functions-key": func_key
                    }

                    try:
                        tool_response = requests.post(
                            tool_url,
                            headers=tool_headers,
                            json=arguments,
                            timeout=30
                        )
                        tool_result = tool_response.json()
                        tool_output = json.dumps(tool_result)
                    except Exception as e:
                        tool_output = json.dumps({"error": str(e)})
                        tool_result = {"error": str(e)}

                    tool_outputs.append({
                        "tool_call_id": tool_call.id,
                        "output":       tool_output
                    })

                    all_tool_results.append({
                        "name":   name,
                        "result": tool_result
                    })

                client.runs.submit_tool_outputs(
                    thread_id=thread_id,
                    run_id=run.id,
                    tool_outputs=tool_outputs
                )

        if run.status == "failed":
            error = getattr(run, 'last_error', 'Unknown error')
            logging.error(f"Run failed: {error}")
            return func.HttpResponse(
                json.dumps({
                    "response":     "I'm sorry, something went wrong. Please try again.",
                    "tool_results": []
                }),
                status_code=200,
                mimetype="application/json",
                headers={'Access-Control-Allow-Origin': '*'}
            )

        messages  = list(client.messages.list(thread_id=thread_id))
        last_msg  = messages[0]
        response  = last_msg.content[0].text.value

        logging.info(f"Agent response: {response[:100]}")

        return func.HttpResponse(
            json.dumps({
                "response":     response,
                "tool_results": all_tool_results
            }),
            status_code=200,
            mimetype="application/json",
            headers={'Access-Control-Allow-Origin': '*'}
        )

    except Exception as e:
        logging.error(f"chat_handler failed: {str(e)}")
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=500,
            mimetype="application/json",
            headers={'Access-Control-Allow-Origin': '*'}
        )