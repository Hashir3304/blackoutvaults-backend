# main.py
import os
import json
import base64
import stripe
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from twilio.rest import Client as TwilioClient
import firebase_admin
from firebase_admin import credentials, firestore

# --- Load Environment Variables ---
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER")
ADMIN_WHATSAPP_NUMBER = os.getenv("ADMIN_WHATSAPP_NUMBER")

# Firebase Base64 (from Render ENV)
FIREBASE_B64 = os.getenv("FIREBASE_B64")

# --- Stripe Setup ---
stripe.api_key = STRIPE_SECRET_KEY

# --- Firebase Setup ---
if not firebase_admin._apps and FIREBASE_B64:
    try:
        decoded_json = base64.b64decode(FIREBASE_B64).decode("utf-8")
        firebase_credentials = json.loads(decoded_json)
        cred = credentials.Certificate(firebase_credentials)
        firebase_admin.initialize_app(cred)
        db = firestore.client()
    except Exception as e:
        print("Firebase init error:", e)
        db = None
else:
    db = None

# --- Twilio Setup ---
twilio_client = None
if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
    try:
        twilio_client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    except Exception as e:
        print("Twilio init error:", e)

# --- FastAPI ---
app = FastAPI()

@app.get("/")
async def root():
    return {"message": "✅ Blackout Vault API is running"}

# --- Stripe Webhook ---
@app.post("/stripe/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": str(e)})

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        customer_email = session.get("customer_email")
        session_id = session.get("id")
        amount_total = session.get("amount_total", 0) / 100

        # ✅ Save to Firebase
        if db:
            db.collection("payments").document(session_id).set({
                "email": customer_email,
                "amount": amount_total,
                "status": "paid"
            })

        # ✅ WhatsApp message
        message = f"""
        ✅ Blackout Vault Payment Confirmed
        💳 Amount: ${amount_total}
        📧 Email: {customer_email}

        🔗 Dashboard: https://blackoutvaults.com/dashboard?session_id={session_id}
        """

        if twilio_client:
            try:
                twilio_client.messages.create(
                    from_=TWILIO_WHATSAPP_NUMBER,
                    body=message,
                    to=ADMIN_WHATSAPP_NUMBER
                )
            except Exception as e:
                print("Twilio error:", e)

    return {"status": "success"}

# --- Stripe Test Endpoint ---
@app.get("/test-stripe")
async def test_stripe():
    return {"status": "Stripe connected", "key": STRIPE_SECRET_KEY[:6] + "****"}

# --- Firebase Test Endpoint ---
@app.get("/test-firebase")
async def test_firebase():
    if not db:
        return {"error": "Firebase not initialized"}
    return {"status": "Firebase connected"}
