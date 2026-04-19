import azure.functions as func
import requests
import json
import os
import logging

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
            mimetype="application/json"
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
            mimetype="application/json"
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
        legacy_fee = round(amount_usd * 0.065, 2)
        savings = round(legacy_fee - remitai_fee, 2)

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
            mimetype="application/json"
        )

    except Exception as e:
        logging.error(f"FX rate fetch failed: {str(e)}")
        return func.HttpResponse(
            json.dumps({"error": "Could not fetch exchange rate. Please try again."}),
            status_code=500,
            mimetype="application/json"
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
        recipient_address   = req_body.get(
            'recipient_address',
            '0x0000000000000000000000000000000000000002'
        )
    except Exception:
        return func.HttpResponse(
            json.dumps({"error": "Invalid input. Check all required fields."}),
            status_code=400,
            mimetype="application/json"
        )

    if not all([amount_usd, recipient_phone, recipient_name,
                destination_country, sender_phone]):
        return func.HttpResponse(
            json.dumps({"error": "Missing required fields."}),
            status_code=400,
            mimetype="application/json"
        )

    transaction_id = f"REMITAI-{str(uuid.uuid4())[:8].upper()}"
    timestamp      = datetime.now(timezone.utc).isoformat()

    try:
        circle_api_key       = os.environ.get("CIRCLE_API_KEY")
        circle_api_url       = os.environ.get("CIRCLE_API_URL")
        wallet_id            = os.environ.get("CIRCLE_WALLET_ID")
        entity_secret_cipher = os.environ.get("CIRCLE_ENTITY_SECRET_CIPHERTEXT")

        headers = {
            "Authorization": f"Bearer {circle_api_key}",
            "Content-Type":  "application/json"
        }

        transfer_payload = {
            "idempotencyKey": str(uuid.uuid4()),
            "walletId": wallet_id,
            "entitySecretCiphertext": entity_secret_cipher,
            "amounts": [amount_usd],
            "destinationAddress": recipient_address,
            "tokenId": "7adb2b7d-c9cd-5164-b2d4-b73b088274dc",
            "fee": {
                "type": "level",
                "config": {
                    "feeLevel": "MEDIUM"
                }
            }
        }

        logging.info(f"Calling Circle API: {circle_api_url}/developer/transactions/transfer")

        circle_response = requests.post(
            f"{circle_api_url}/developer/transactions/transfer",
            headers=headers,
            json=transfer_payload,
            timeout=30
        )

        circle_data = circle_response.json()
        logging.info(f"Circle response status: {circle_response.status_code}")
        logging.info(f"Circle response data: {circle_data}")

        if circle_response.status_code in [200, 201]:
            circle_tx_id  = circle_data.get("data", {}).get("id", transaction_id)
            circle_status = circle_data.get("data", {}).get("state", "INITIATED")
        else:
            error_msg = circle_data.get("message", "Unknown Circle error")
            logging.error(f"Circle API error: {error_msg}")
            return func.HttpResponse(
                json.dumps({"error": f"Transfer failed: {error_msg}"}),
                status_code=500,
                mimetype="application/json"
            )

        result = {
            "transaction_id": transaction_id,
            "circle_transfer_id": circle_tx_id,
            "status": circle_status,
            "amount_usd": amount_usd,
            "recipient_name": recipient_name,
            "recipient_phone": recipient_phone,
            "destination_country": destination_country,
            "sender_phone": sender_phone,
            "timestamp": timestamp,
            "estimated_delivery": "Under 60 seconds",
            "mode": "live",
            "message": (
                f"Transfer of ${amount_usd} USDC to "
                f"{recipient_name} initiated successfully."
            )
        }

        save_to_cosmos(result)

        return func.HttpResponse(
            json.dumps(result),
            status_code=200,
            mimetype="application/json"
        )

    except Exception as e:
        logging.error(f"Transfer failed: {str(e)}")
        return func.HttpResponse(
            json.dumps({"error": f"Transfer failed: {str(e)}"}),
            status_code=500,
            mimetype="application/json"
        )


def save_to_cosmos(transaction: dict):
    try:
        from azure.cosmos import CosmosClient

        conn_str = os.environ.get("COSMOS_DB_CONNECTION_STRING")
        if not conn_str:
            logging.warning("Cosmos DB connection string not set — skipping save")
            return

        client    = CosmosClient.from_connection_string(conn_str)
        database  = client.get_database_client("remitai")
        container = database.get_container_client("transactions")

        transaction["id"] = transaction["transaction_id"]
        container.upsert_item(transaction)
        logging.info(f"Transaction saved to Cosmos DB: {transaction['id']}")

    except Exception as e:
        logging.error(f"Cosmos DB save failed: {str(e)}")
# ─────────────────────────────────────────────
# FUNCTION 3 — send_sms_confirmation (coming next)
# ─────────────────────────────────────────────