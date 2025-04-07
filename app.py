import os
import json
import base64
import hmac
import hashlib
import requests
from datetime import datetime, timezone
from flask import Flask, request, jsonify
from dotenv import load_dotenv

load_dotenv("/etc/secrets/.env.example")
app = Flask(__name__)

API_KEY = os.getenv("OKX_API_KEY")
API_SECRET = os.getenv("OKX_API_SECRET")
PASSPHRASE = os.getenv("OKX_PASSPHRASE")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")
BASE_URL = "https://www.okx.com"
ORDER_FILE = "current_order.json"

def generate_signature(timestamp, method, request_path, body=""):
    message = f"{timestamp}{method.upper()}{request_path}{body}"
    mac = hmac.new(API_SECRET.encode(), message.encode(), hashlib.sha256)
    return base64.b64encode(mac.digest()).decode()

def get_iso_timestamp():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")

def send_okx_request(method, endpoint, payload=None):
    timestamp = get_iso_timestamp()
    body = json.dumps(payload) if payload else ""
    headers = {
        "OK-ACCESS-KEY": API_KEY,
        "OK-ACCESS-SIGN": generate_signature(timestamp, method, endpoint, body),
        "OK-ACCESS-TIMESTAMP": timestamp,
        "OK-ACCESS-PASSPHRASE": PASSPHRASE,
        "Content-Type": "application/json"
    }
    try:
        response = requests.request(method, BASE_URL + endpoint, headers=headers, data=body)
        return response.json()
    except Exception as e:
        return {"error": str(e)}

def save_order(order_id):
    with open(ORDER_FILE, "w") as f:
        json.dump({"ordId": order_id}, f)

def load_order():
    if os.path.exists(ORDER_FILE):
        with open(ORDER_FILE, "r") as f:
            return json.load(f).get("ordId")
    return None

def clear_order():
    if os.path.exists(ORDER_FILE):
        os.remove(ORDER_FILE)

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    if data.get("secret") != WEBHOOK_SECRET:
        return jsonify({"error": "Invalid secret"}), 403

    symbol = data.get("symbol")
    price = data.get("limit_price")
    tp_price = data.get("take_profit")
    quantity = data.get("sz", "1")
    leverage = data.get("leverage", "10")
    side = data.get("side", "buy")
    pos_side = data.get("posSide", "long")

    print("📩 Webhook received:", data)

    # Установка плеча
    send_okx_request("POST", "/api/v5/account/set-leverage", {
        "instId": symbol,
        "lever": leverage,
        "mgnMode": "isolated"
    })

    # Отмена предыдущего ордера
    prev_order = load_order()
    if prev_order:
        send_okx_request("POST", "/api/v5/trade/cancel-order", {
            "instId": symbol,
            "ordId": prev_order
        })
        clear_order()

    # Создание нового ордера
    order_payload = {
        "instId": symbol,
        "tdMode": "isolated",
        "side": side,
        "posSide": pos_side,
        "ordType": "limit",
        "px": price,
        "sz": quantity,
        "tpTriggerPx": tp_price,
        "tpOrdPx": tp_price
    }

    print("📦 Order payload:", order_payload)

    result = send_okx_request("POST", "/api/v5/trade/order", order_payload)
    print("🧾 OKX Response:", result)

    try:
        order_id = result["data"][0]["ordId"]
        save_order(order_id)
        return jsonify({"status": "order placed", "order_id": order_id})
    except Exception as e:
        return jsonify({"error": str(e), "response": result}), 400


@app.route("/")
def index():
    return "✅ OKX limit bot is running."

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

