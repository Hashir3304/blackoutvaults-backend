import os, stripe, json, smtplib, ssl, base64
from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from twilio.rest import Client
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
import firebase_admin
from firebase_admin import credentials, storage
from reportlab.pdfgen import canvas
from datetime import datetime
from io import BytesIO
from dotenv import load_dotenv

# =========================================================
# 🔹 LOAD ENV
# =========================================================
load_dotenv()

# =========================================================
# 🔹 FASTAPI APP SETUP
# =========================================================
app = FastAPI(title="Blackout Vaults API", version="3.0.0")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Allow CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================================================
# 🔹 STRIPE CONFIGURATION
# =========================================================
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
endpoint_secret = os.getenv("STRIPE_WEBHOOK_SECRET")

# =========================================================
# 🔹 FIREBASE CONFIGURATION
# =========================================================
try:
    firebase_b64 = os.getenv("FIREBASE_B64")
    if firebase_b64:
        decoded = base64.b64decode(firebase_b64)
        cred = credentials.Certificate(json.loads(decoded))
        firebase_admin.initialize_app(cred, {
            "storageBucket": f"{os.getenv('FIREBASE_PROJECT_ID')}.appspot.com"
        })
        print("🔥 Firebase connected successfully.")
    else:
        print("⚠️ FIREBASE_B64 not found.")
except Exception as e:
    print("⚠️ Firebase initialization failed:", e)

# =========================================================
# 🔹 SMTP CONFIG (Professional Mail)
# =========================================================
SMTP_EMAIL = os.getenv("SMTP_EMAIL", "support@blackoutvaults.com")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "Blackoutvaults2025")
SMTP_SERVER = os.getenv("SMTP_SERVER", "mail.blackoutvaults.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))

# =========================================================
# 🔹 TWILIO CONFIG
# =========================================================
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER")
ADMIN_WHATSAPP_NUMBER = os.getenv("ADMIN_WHATSAPP_NUMBER")

# =========================================================
# 🔹 BASIC ROUTES
# =========================================================
@app.get("/")
def home():
    return {"message": "✅ Blackout Vaults Automation Running", "version": "3.0"}

@app.get("/health")
def health():
    return {"status": "ok", "message": "Server and Database Connected"}

# =========================================================
# 🔹 STRIPE WEBHOOK
# =========================================================
@app.post("/stripe/webhook")
async def stripe_webhook(request: Request, stripe_signature: str = Header(None)):
    payload = await request.body()
    try:
        event = stripe.Webhook.construct_event(payload, stripe_signature, endpoint_secret)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        email = session.get("customer_details", {}).get("email", "Unknown")
        amount = session.get("amount_total", 0) / 100
        payment_id = session.get("payment_intent", "Unknown")

        # 1️⃣ Create receipt PDF
        receipt_path = create_receipt_pdf(email, amount, payment_id)

        # 2️⃣ Send Email Receipt
        send_email_with_receipt(email, amount, receipt_path)

        # 3️⃣ WhatsApp notification
        send_whatsapp(f"💸 New Payment from {email} — ${amount:.2f}")

        # 4️⃣ Upload to Firebase
        upload_to_firebase(receipt_path, f"receipts/{payment_id}.pdf")

    return {"status": "Webhook Received"}

# =========================================================
# 🔹 PDF RECEIPT GENERATOR
# =========================================================
def create_receipt_pdf(email, amount, payment_id):
    try:
        os.makedirs("receipts", exist_ok=True)
        path = f"receipts/receipt_{payment_id}.pdf"

        buffer = BytesIO()
        c = canvas.Canvas(buffer)
        c.setTitle("Blackout Vaults Receipt")

        # --- Theme ---
        c.setFillColorRGB(0.95, 0.85, 0.2)  # yellow header
        c.rect(0, 780, 600, 30, fill=True, stroke=False)
        c.setFillColorRGB(0, 0, 0)
        c.setFont("Helvetica-Bold", 18)
        c.drawString(150, 785, "BLACKOUT VAULTS - RECEIPT")

        # --- Logo ---
        logo_path = "static/logo.png"
        if os.path.exists(logo_path):
            c.drawImage(logo_path, 40, 700, width=100, height=100, mask='auto')

        # --- Details ---
        c.setFont("Helvetica", 12)
        c.drawString(50, 660, f"Customer Email: {email}")
        c.drawString(50, 640, f"Amount Paid: ${amount:.2f}")
        c.drawString(50, 620, f"Payment ID: {payment_id}")
        c.drawString(50, 600, f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # --- Footer ---
        c.setFont("Helvetica-Oblique", 10)
        c.drawString(50, 560, "Thank you for trusting Blackout Vaults.")
        c.drawString(50, 545, "Your Privacy. Professionally Handled.")

        c.showPage()
        c.save()

        with open(path, "wb") as f:
            f.write(buffer.getvalue())

        print(f"📄 Receipt PDF created at {path}")
        return path
    except Exception as e:
        print("⚠️ PDF generation failed:", e)
        return None

# =========================================================
# 🔹 EMAIL RECEIPT SENDER
# =========================================================
def send_email_with_receipt(to_email, amount, receipt_path):
    try:
        msg = MIMEMultipart()
        msg["From"] = f"Blackout Vaults <{SMTP_EMAIL}>"
        msg["To"] = to_email
        msg["Subject"] = f"🧾 Payment Receipt - ${amount:.2f}"

        body = f"""
Hello,

Thank you for your payment of ${amount:.2f}.
Your privacy protection plan has been successfully activated.

Best regards,  
**Blackout Vaults Team**  
support@blackoutvaults.com
"""
        msg.attach(MIMEText(body, "plain"))

        if receipt_path and os.path.exists(receipt_path):
            with open(receipt_path, "rb") as f:
                part = MIMEApplication(f.read(), Name=os.path.basename(receipt_path))
            part['Content-Disposition'] = f'attachment; filename="{os.path.basename(receipt_path)}"'
            msg.attach(part)

        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, context=context) as server:
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.sendmail(SMTP_EMAIL, to_email, msg.as_string())

        print(f"📧 Receipt sent to {to_email}")
    except Exception as e:
        print("⚠️ Email sending failed:", e)

# =========================================================
# 🔹 WHATSAPP NOTIFIER
# =========================================================
def send_whatsapp(message):
    try:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        client.messages.create(
            from_=TWILIO_WHATSAPP_NUMBER,
            to=ADMIN_WHATSAPP_NUMBER,
            body=message
        )
        print("💬 WhatsApp notification sent.")
    except Exception as e:
        print("⚠️ WhatsApp send failed:", e)

# =========================================================
# 🔹 FIREBASE UPLOAD
# =========================================================
def upload_to_firebase(local_path, cloud_path):
    try:
        bucket = storage.bucket()
        blob = bucket.blob(cloud_path)
        blob.upload_from_filename(local_path)
        blob.make_public()
        print(f"☁️ Uploaded to Firebase: {blob.public_url}")
    except Exception as e:
        print("⚠️ Firebase upload failed:", e)
