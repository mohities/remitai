import azure.functions as func
import requests
import json
import os
import logging
import uuid
from datetime import datetime, timezone

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
        recipient_address   = req_body.get('recipient_address')
    except Exception:
        return func.HttpResponse(
            json.dumps({"error": "Invalid input. Check all required fields."}),
            status_code=400,
            mimetype="application/json"
        )

    if not all([amount_usd, recipient_phone, recipient_name,
                destination_country, sender_phone, recipient_address]):
        return func.HttpResponse(
            json.dumps({"error": "Missing required fields."}),
            status_code=400,
            mimetype="application/json"
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
                mimetype="application/json"
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
# FUNCTION 3 — send_sms_confirmation (coming next)
# ─────────────────────────────────────────────