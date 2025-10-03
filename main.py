import os
import json
import base64
import stripe
from fastapi import FastAPI, Request, Header
from fastapi.responses import JSONResponse
from twilio.rest import Client
import firebase_admin
from firebase_admin import credentials, firestore

app = FastAPI()

# -------------------------------
# Stripe Setup
# -------------------------------
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
endpoint_secret = os.getenv("STRIPE_WEBHOOK_SECRET")

# -------------------------------
# Firebase Setup
# -------------------------------
firebase_initialized = False
if not firebase_admin._apps:
    firebase_b64 = os.getenv("FIREBASE_B64")
    if firebase_b64:
        try:
            firebase_json = base64.b64decode(firebase_b64).decode("utf-8")
            cred_dict = json.loads(firebase_json)
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
            firebase_initialized = True
            print("✅ Firebase initialized")
        except Exception as e:
            print("⚠️ Firebase init failed:", e)
else:
    firebase_initialized = True

db = firestore.client() if firebase_initialized else None

# -------------------------------
# Twilio Setup
# -------------------------------
twilio_sid = os.getenv("TWILIO_ACCOUNT_SID")
twilio_token = os.getenv("TWILIO_AUTH_TOKEN")
twilio_number = os.getenv("TWILIO_WHATSAPP_NUMBER")
admin_number = os.getenv("ADMIN_WHATSAPP_NUMBER")

twilio_client = None
if twilio_sid and twilio_token:
    try:
        twilio_client = Client(twilio_sid, twilio_token)
        print("✅ Twilio client ready")
    except Exception as e:
        print("⚠️ Twilio init failed:", e)

# -------------------------------
# Routes
# -------------------------------
@app.get("/")
async def root():
    return {"message": "✅ Blackout Vault API is running"}

@app.post("/stripe/webhook")
async def stripe_webhook(request: Request, stripe_signature: str = Header(None)):
    payload = await request.body()

    try:
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, endpoint_secret
        )
    except stripe.error.SignatureVerificationError:
        return JSONResponse(status_code=400, content={"error": "Invalid signature"})
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": str(e)})

    # -------------------------------
    # Handle Stripe Events
    # -------------------------------
    if event["type"] == "payment_intent.succeeded":
        payment_intent = event["data"]["object"]
        print("✅ Payment succeeded:", payment_intent["id"])

        if db:
            db.collection("payments").add(payment_intent)

        if twilio_client:
            try:
                twilio_client.messages.create(
                    from_=twilio_number,
                    body=f"✅ Payment succeeded! ID: {payment_intent['id']}",
                    to=admin_number
                )
            except Exception as e:
                print("⚠️ Twilio send failed:", e)

    elif event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        print("✅ Checkout completed:", session["id"])

    elif event["type"] == "checkout.session.expired":
        print("⚠️ Checkout session expired")

    else:
        print("Unhandled event type:", event["type"])

    return {"status": "success"}
