import os
import json
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from okx.v5 import Trade

load_dotenv()
app = Flask(__name__)

tradeAPI = Trade(
    api_key=os.getenv("OKX_API_KEY"),
    api_secret_key=os.getenv("OKX_API_SECRET"),
    passphrase=os.getenv("OKX_PASSPHRASE"),
    use_server_time=True,
    flag='1'  # '1' — реальный счёт, '0' — демо
)

ORDER_FILE = "current_order.json"

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

@app.route("/", methods=["GET"])
def home():
    return "OKX Bot is running!"

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json

    if data.get("secret") != os.getenv("WEBHOOK_SECRET"):
        return jsonify({"error": "Invalid secret"}), 403

    symbol = data["symbol"]
    price = data["limit_price"]
    tp_price = data["take_profit"]
    quantity = data.get("quantity", "0.01")
    leverage = data.get("leverage", "20")

    tradeAPI.set_leverage(instId=symbol, lever=leverage, mgnMode="isolated")

    prev_order = load_order()
    if prev_order:
        try:
            tradeAPI.cancel_order(instId=symbol, ordId=prev_order)
        except Exception as e:
            print(f"Ошибка при отмене ордера: {e}")
        clear_order()

    order = tradeAPI.place_order(
        instId=symbol,
        tdMode="isolated",
        side="buy",
        posSide="long",
        ordType="limit",
        orderPx=price,
        sz=quantity,
        tpTriggerPx=tp_price,
        tpOrdPx=tp_price
    )

    order_id = order['data'][0]['ordId']
    save_order(order_id)
    return jsonify({"status": "order placed", "order_id": order_id})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)