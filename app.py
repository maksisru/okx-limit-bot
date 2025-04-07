import os
import time
from datetime import datetime, timezone
import json
import base64
import hmac
import hashlib
import requests
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

    url = BASE_URL + endpoint
    print(f"\n🌐 Sending {method} request to {url}")
    print("🕒 Timestamp:", timestamp)
    print("📦 Payload:", body)
    print("🧾 Headers:", json.dumps(headers, indent=2))

    try:
        response = requests.request(method, url, headers=headers, data=body)
        print("📨 Raw Response Text:", response.text)
        return response.json()
    except Exception as e:
        print("🚨 Request failed:", str(e))
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
    print("📩 Received payload:", data)

    if data.get("secret") != WEBHOOK_SECRET:
        return jsonify({"error": "Invalid secret"}), 403

    symbol = data["symbol"]
    price = data["limit_price"]
    tp_price = data["take_profit"]
    quantity = data.get("quantity", "0.01")
    leverage = data.get("leverage", "20")

    print(f"⚙️ Params — symbol: {symbol}, price: {price}, TP: {tp_price}, qty: {quantity}, lev: {leverage}")

    # Установка плеча
    leverage_result = send_okx_request("POST", "/api/v5/account/set-leverage", {
        "instId": symbol,
        "lever": leverage,
        "mgnMode": "isolated"
    })
    print("📶 Leverage response:", leverage_result)

    # Отмена предыдущего ордера
    prev_order = load_order()
    if prev_order:
        cancel_result = send_okx_request("POST", "/api/v5/trade/cancel-order", {
            "instId": symbol,
            "ordId": prev_order
        })
        print("❌ Cancel previous order response:", cancel_result)
        clear_order()

    # Новый ордер
    order_payload = {
        "instId": symbol,
        "tdMode": "isolated",
        "side": "buy",
        "posSide": "long",
        "ordType": "limit",
        "px": price,
        "sz": quantity,
        "tpTriggerPx": tp_price,
        "tpOrdPx": tp_price
    }
    print("📦 Sending order payload:", order_payload)

    result = send_okx_request("POST", "/api/v5/trade/order", order_payload)
    print("📨 Order response from OKX:", result)

    try:
        order_id = result["data"][_
