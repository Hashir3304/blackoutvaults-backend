import os
import json
import base64
import stripe
import firebase_admin
from firebase_admin import credentials, storage
from fastapi import FastAPI, Request, HTTPException
from twilio.rest import Client

# ---------------------------------
# FastAPI app
# ---------------------------------
app = FastAPI()

# ---------------------------------
# Stripe Setup
# ---------------------------------
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

# ---------------------------------
# Firebase Setup (Base64 JSON from ENV)
# ---------------------------------
firebase_b64 = os.getenv("FIREBASE_CREDENTIALS_BASE64")
if firebase_b64:
    try:
        firebase_json = base64.b64decode(firebase_b64).decode("utf-8")
        cred = credentials.Certificate(json.loads(firebase_json))
        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred, {
                "storageBucket": os.getenv("FIREBASE_STORAGE_BUCKET")
            })
    except Exception as e:
        print("❌ Firebase init failed:", str(e))

# ---------------------------------
# Twilio Setup
# ---------------------------------
TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP = os.getenv("TWILIO_WHATSAPP_NUMBER")  # e.g. whatsapp:+14155238886
ADMIN_WHATSAPP = os.getenv("ADMIN_WHATSAPP_NUMBER")    # e.g. whatsapp:+92333xxxxxxx
client = Client(TWILIO_SID, TWILIO_TOKEN)

# ---------------------------------
# Root Route
# ---------------------------------
@app.get("/")
def root():
    return {"message": "✅ Blackout Vault API is running"}

# ---------------------------------
# Stripe Webhook Route
# ---------------------------------
@app.post("/stripe/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid Stripe signature")

    # Handle events
    if event["type"] == "payment_intent.succeeded":
        payment_intent = event["data"]["object"]
        amount = payment_intent["amount_received"] / 100
        currency = payment_intent["currency"]

        # WhatsApp notify
        try:
            client.messages.create(
                from_=TWILIO_WHATSAPP,
                to=ADMIN_WHATSAPP,
                body=f"💳 Payment of {amount} {currency.upper()} succeeded ✅"
            )
        except Exception as e:
            print("❌ WhatsApp error:", e)

        return {"status": "success", "id": payment_intent["id"]}

    return {"status": "ignored"}

# ---------------------------------
# Test Firebase Upload
# ---------------------------------
@app.get("/test-firebase")
def test_firebase():
    try:
        bucket = storage.bucket()
        blob = bucket.blob("test.txt")
        blob.upload_from_string("Hello Firebase! Blackout Vault ✅")
        return {"message": "✅ Firebase upload successful"}
    except Exception as e:
        return {"error": str(e)}

# ---------------------------------
# Test WhatsApp Message
# ---------------------------------
@app.get("/test-whatsapp")
def test_whatsapp():
    try:
        message = client.messages.create(
            from_=TWILIO_WHATSAPP,
            to=ADMIN_WHATSAPP,
            body="✅ Blackout Vault WhatsApp integration is working!"
        )
        return {"sid": message.sid}
    except Exception as e:
        return {"error": str(e)}
