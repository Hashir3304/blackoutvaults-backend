import os
import stripe
import json
import base64
from fastapi import FastAPI, Request, Header
from fastapi.responses import JSONResponse
from email.mime.text import MIMEText
import aiosmtplib
from twilio.rest import Client
import firebase_admin
from firebase_admin import credentials, storage

# --- Initialize FastAPI ---
app = FastAPI()

# --- Stripe Setup ---
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

# --- Twilio Setup ---
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER")
ADMIN_WHATSAPP_NUMBER = os.getenv("ADMIN_WHATSAPP_NUMBER")
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# --- Firebase Setup (from Base64 env) ---
firebase_b64 = os.getenv("FIREBASE_CREDENTIALS_B64")
if firebase_b64:
    cred_json = base64.b64decode(firebase_b64).decode("utf-8")
    cred_dict = json.loads(cred_json)
    cred = credentials.Certificate(cred_dict)
    firebase_admin.initialize_app(cred, {"storageBucket": os.getenv("FIREBASE_STORAGE_BUCKET")})

# --- Root Route ---
@app.get("/")
async def root():
    return {"message": "✅ Blackout Vault API is running"}

# --- Email Helper ---
async def send_email(to_email: str, subject: str, body: str):
    sender = os.getenv("SMTP_EMAIL")
    password = os.getenv("SMTP_PASSWORD")
    smtp_server = os.getenv("SMTP_SERVER", "mail.blackoutvaults.com")
    smtp_port = int(os.getenv("SMTP_PORT", "465"))

    message = MIMEText(body, "html")
    message["From"] = sender
    message["To"] = to_email
    message["Subject"] = subject

    await aiosmtplib.send(
        message,
        hostname=smtp_server,
        port=smtp_port,
        username=sender,
        password=password,
        use_tls=True
    )

# --- Test Email Route ---
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

# --- Stripe Webhook ---
@app.post("/stripe/webhook")
async def stripe_webhook(request: Request, stripe_signature: str = Header(None)):
    payload = await request.body()
    try:
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, STRIPE_WEBHOOK_SECRET
        )
    except stripe.error.SignatureVerificationError:
        return JSONResponse({"error": "Invalid Stripe signature"}, status_code=400)

    # Handle events
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        customer_email = session.get("customer_email")

        # Send Email Receipt
        if customer_email:
            await send_email(
                to_email=customer_email,
                subject="🧾 Blackout Vaults Receipt",
                body=f"""
                <h2>Thank you for your purchase!</h2>
                <p>Your payment of <b>{session.get('amount_total',0)/100:.2f} {session.get('currency','').upper()}</b> was successful.</p>
                <p>- Blackout Vaults Team</p>
                """
            )

        # Send WhatsApp Alert
        if ADMIN_WHATSAPP_NUMBER:
            twilio_client.messages.create(
                from_=TWILIO_WHATSAPP_NUMBER,
                body=f"✅ New Stripe Checkout completed!\nCustomer: {customer_email}",
                to=ADMIN_WHATSAPP_NUMBER
            )

    return {"status": "success"}

# --- Firebase Upload Example ---
@app.post("/upload")
async def upload_file(request: Request):
    data = await request.json()
    filename = data.get("filename", "test.txt")
    content = data.get("content", "Hello from Blackout Vaults")

    bucket = storage.bucket()
    blob = bucket.blob(filename)
    blob.upload_from_string(content)

    return {"message": f"✅ Uploaded {filename} to Firebase"}

# --- Firebase Download Example ---
@app.get("/download/{filename}")
async def download_file(filename: str):
    bucket = storage.bucket()
    blob = bucket.blob(filename)

    if not blob.exists():
        return {"error": "File not found"}

    content = blob.download_as_text()
    return {"filename": filename, "content": content}
