import os
import json
import stripe
import firebase_admin
from firebase_admin import credentials
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from email.mime.text import MIMEText
import aiosmtplib
from twilio.rest import Client
import base64

app = FastAPI()

# -----------------------------
# Stripe Setup
# -----------------------------
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

# -----------------------------
# Firebase Setup (B64)
# -----------------------------
if not firebase_admin._apps:
    firebase_b64 = os.getenv("FIREBASE_B64")
    if firebase_b64:
        firebase_json = base64.b64decode(firebase_b64).decode("utf-8")
        cred = credentials.Certificate(json.loads(firebase_json))
        firebase_admin.initialize_app(cred)

# -----------------------------
# Twilio Setup
# -----------------------------
twilio_client = Client(
    os.getenv("TWILIO_ACCOUNT_SID"),
    os.getenv("TWILIO_AUTH_TOKEN")
)
TWILIO_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER")
ADMIN_NUMBER = os.getenv("ADMIN_WHATSAPP_NUMBER")

# -----------------------------
# SMTP Setup
# -----------------------------
SMTP_EMAIL = os.getenv("SMTP_EMAIL")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT"))
USE_SSL = os.getenv("SMTP_USE_SSL", "True").lower() == "true"

async def send_email(to_email: str, subject: str, body: str):
    message = MIMEText(body, "html")
    message["From"] = SMTP_EMAIL
    message["To"] = to_email
    message["Subject"] = subject

    if USE_SSL:
        await aiosmtplib.send(
            message,
            hostname=SMTP_SERVER,
            port=SMTP_PORT,
            username=SMTP_EMAIL,
            password=SMTP_PASSWORD,
            use_tls=True
        )
    else:
        await aiosmtplib.send(
            message,
            hostname=SMTP_SERVER,
            port=SMTP_PORT,
            username=SMTP_EMAIL,
            password=SMTP_PASSWORD,
            start_tls=True
        )

# -----------------------------
# Routes
# -----------------------------

@app.get("/")
async def root():
    return {"message": "✅ Blackout Vault API is running"}

@app.get("/test-email")
async def test_email():
    try:
        await send_email(
            to_email="blackoutvaults@gmail.com",
            subject="Test Email - Blackout Vaults",
            body="<h3>✅ SMTP setup works!</h3><p>This is a test email from your backend.</p>"
        )
        return {"message": "✅ Test email sent successfully"}
    except Exception as e:
        return {"error": str(e)}

@app.post("/stripe/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, WEBHOOK_SECRET
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    if event["type"] == "payment_intent.succeeded":
        intent = event["data"]["object"]
        amount = intent["amount_received"] / 100
        customer_email = intent.get("receipt_email", "blackoutvaults@gmail.com")

        # Send Email Receipt
        await send_email(
            to_email=customer_email,
            subject="🧾 Your Blackout Vaults Receipt",
            body=f"""
                <h2>Thank you for your payment!</h2>
                <p>We received <b>${amount:.2f}</b> successfully.</p>
                <p>Your purchase is being processed by Blackout Vaults.</p>
            """
        )

        # Send WhatsApp Admin Alert
        twilio_client.messages.create(
            from_=TWILIO_NUMBER,
            to=ADMIN_NUMBER,
            body=f"✅ New Stripe payment received: ${amount:.2f} from {customer_email}"
        )

    return {"message": "✅ Webhook received and processed"}
