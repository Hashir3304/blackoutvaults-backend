import os
import json
import base64
import stripe
import smtplib
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from firebase_admin import credentials, initialize_app, storage
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders

# --- Load ENV ---
from dotenv import load_dotenv
load_dotenv()

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

# --- SMTP Email ---
SMTP_EMAIL = os.getenv("SMTP_EMAIL")  # support@blackoutvaults.com
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")  # hosting password
SMTP_SERVER = os.getenv("SMTP_SERVER")  # mail.blackoutvaults.com
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))

ADMIN_EMAIL = "support@blackoutvaults.com"

# --- Firebase ---
firebase_b64 = os.getenv("FIREBASE_SERVICE_ACCOUNT_B64")
if firebase_b64:
    temp_path = "temp-firebase.json"
    with open(temp_path, "w") as f:
        f.write(base64.b64decode(firebase_b64).decode("utf-8"))
    cred = credentials.Certificate(temp_path)
    initialize_app(cred, {"storageBucket": os.getenv("FIREBASE_STORAGE_BUCKET")})

# --- Stripe ---
stripe.api_key = STRIPE_SECRET_KEY

# --- FastAPI app ---
app = FastAPI()

@app.get("/")
async def root():
    return {"message": "✅ Blackout Vault API is running with receipts + SMTP"}

# === PDF GENERATION ===
def generate_receipt(session):
    receipt_path = f"receipt_{session['id']}.pdf"
    c = canvas.Canvas(receipt_path, pagesize=letter)
    width, height = letter

    # Colors
    black = colors.black
    yellow = colors.Color(1, 0.85, 0)  # Blackout Vaults Yellow

    # Logo
    logo_path = "assets/logo.png"
    if os.path.exists(logo_path):
        logo = ImageReader(logo_path)
        c.drawImage(logo, 40, height - 100, width=100, height=60, mask='auto')

    # Header
    c.setFillColor(yellow)
    c.setFont("Helvetica-Bold", 22)
    c.drawString(160, height - 70, "Blackout Vaults")

    c.setFillColor(black)
    c.setFont("Helvetica", 12)
    c.drawString(160, height - 90, "Your Privacy. Professionally Handled.")

    # Divider
    c.setStrokeColor(yellow)
    c.setLineWidth(2)
    c.line(40, height - 110, width - 40, height - 110)

    # Receipt Info
    c.setFillColor(black)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, height - 140, "Payment Receipt")

    c.setFont("Helvetica", 12)
    c.drawString(40, height - 170, f"Customer Email: {session.get('customer_email', 'N/A')}")
    c.drawString(40, height - 190, f"Amount Paid: ${session['amount_total']/100:.2f}")
    c.drawString(40, height - 210, f"Currency: {session['currency'].upper()}")
    c.drawString(40, height - 230, f"Payment Status: {session['payment_status']}")
    c.drawString(40, height - 250, f"Session ID: {session['id']}")

    # Footer
    c.setFont("Helvetica-Oblique", 10)
    c.setFillColor(black)
    c.drawString(40, 40, "Thank you for trusting Blackout Vaults.")

    c.save()
    return receipt_path

# === SEND EMAIL ===
def send_email(to_email, subject, body, attachment_path=None):
    msg = MIMEMultipart()
    msg["From"] = SMTP_EMAIL
    msg["To"] = to_email
    msg["Cc"] = ADMIN_EMAIL
    msg["Subject"] = subject

    msg.attach(MIMEText(body, "plain"))

    if attachment_path:
        with open(attachment_path, "rb") as f:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f"attachment; filename={os.path.basename(attachment_path)}")
            msg.attach(part)

    server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT)
    server.login(SMTP_EMAIL, SMTP_PASSWORD)
    server.sendmail(SMTP_EMAIL, [to_email, ADMIN_EMAIL], msg.as_string())
    server.quit()

# === STRIPE WEBHOOK ===
@app.post("/stripe/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]

        receipt = generate_receipt(session)
        send_email(
            session.get("customer_email", ADMIN_EMAIL),
            "Your Blackout Vaults Receipt",
            "Attached is your official receipt. Thank you for choosing Blackout Vaults.",
            receipt
        )
        return JSONResponse({"status": "✅ Receipt sent"})

    return JSONResponse({"status": "ignored"})
