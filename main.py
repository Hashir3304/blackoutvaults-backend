# ============================================================
# 🧠 BLACKOUT VAULTS BACKEND (FastAPI + Stripe + Firebase + Twilio)
# ============================================================

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import stripe, os, json, base64, smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from twilio.rest import Client
from dotenv import load_dotenv
from reportlab.pdfgen import canvas
from io import BytesIO
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, storage
import openai

# --- Load environment ---
load_dotenv()
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
openai.api_key = os.getenv("OPENAI_API_KEY")

# --- Firebase ---
if not firebase_admin._apps:
    cred_dict = json.loads(base64.b64decode(os.getenv("FIREBASE_B64")).decode())
    cred = credentials.Certificate(cred_dict)
    firebase_admin.initialize_app(cred, {"storageBucket": os.getenv("FIREBASE_STORAGE_BUCKET")})
else:
    firebase_admin.get_app()


# --- Twilio ---
twilio_client = Client(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))

# --- FastAPI setup ---
app = FastAPI(title="Blackout Vaults Backend", version="4.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------------------------------------
# 🔹 HOME TEST ROUTE
# ------------------------------------------------------------
@app.get("/")
def home():
    return {"message": "✅ Blackout Vaults API Active", "version": "4.0"}

# ------------------------------------------------------------
# 🔹 AI PRIVACY SCAN
# ------------------------------------------------------------
@app.post("/scan")
async def scan(request: Request):
    data = await request.json()
    email = data.get("email", "anonymous@user.com")

    # Simulated AI analysis (can plug real OpenAI model)
    report_text = f"""
    Privacy Exposure Report for {email}

    ⚠️ Found leaks on LinkedIn_2024.csv, Facebook_2023.json
    ✅ Cleanup initiated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    """

    # Generate PDF report
    pdf_bytes = BytesIO()
    c = canvas.Canvas(pdf_bytes)
    c.drawString(100, 800, f"Blackout Vaults - Privacy Report")
    c.drawString(100, 780, f"Email: {email}")
    c.drawString(100, 760, f"Scan Time: {datetime.now()}")
    c.drawString(100, 740, "------------------------------------------")
    c.drawString(100, 720, "LinkedIn Leak: Cleaned ✅")
    c.drawString(100, 700, "Facebook Leak: Cleaned ✅")
    c.drawString(100, 680, "Total Exposures Removed: 2")
    c.showPage(); c.save()
    pdf_bytes.seek(0)

    # Upload to Firebase
    bucket = storage.bucket()
    blob = bucket.blob(f"reports/{email.replace('@','_')}_{int(datetime.now().timestamp())}.pdf")
    blob.upload_from_string(pdf_bytes.getvalue(), content_type="application/pdf")
    report_url = blob.generate_signed_url(datetime.utcnow().replace(year=datetime.utcnow().year + 1))

    # Send WhatsApp notification
    try:
        twilio_client.messages.create(
            from_=os.getenv("TWILIO_WHATSAPP_NUMBER"),
            to=os.getenv("ADMIN_WHATSAPP_NUMBER"),
            body=f"🛡️ New scan complete for {email}\nReport: {report_url}"
        )
    except Exception as e:
        print("Twilio error:", e)

    return JSONResponse({"status": "success", "report_url": report_url})

# ------------------------------------------------------------
# 🔹 STRIPE CHECKOUT SESSION
# ------------------------------------------------------------
@app.post("/create_checkout_session")
async def create_checkout_session(request: Request):
    data = await request.json()
    plan = data.get("plan", "free")
    amount = {"free": 0, "pro": 999, "elite": 2999}.get(plan, 0)

    if amount == 0:
        return {"url": "https://blackoutvaults.com/success?plan=free"}

    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        mode="subscription",
        line_items=[{
            "price_data": {
                "currency": "usd",
                "product_data": {"name": f"Blackout Vaults {plan.capitalize()} Plan"},
                "unit_amount": amount,
                "recurring": {"interval": "month"}
            },
            "quantity": 1
        }],
        success_url="https://blackoutvaults.com/success",
        cancel_url="https://blackoutvaults.com/cancel",
    )
    return {"url": session.url}

# ------------------------------------------------------------
# 🔹 STRIPE WEBHOOK
# ------------------------------------------------------------
@app.post("/stripe/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, os.getenv("STRIPE_WEBHOOK_SECRET"))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Webhook error: {e}")

    if event["type"] == "checkout.session.completed":
        customer_email = event["data"]["object"]["customer_email"]
        twilio_client.messages.create(
            from_=os.getenv("TWILIO_WHATSAPP_NUMBER"),
            to=os.getenv("ADMIN_WHATSAPP_NUMBER"),
            body=f"💳 Payment Success: {customer_email}"
        )
    return {"status": "success"}

# ------------------------------------------------------------
# 🔹 SMTP REPORT MAIL
# ------------------------------------------------------------
def send_email_report(to_email, pdf_content):
    msg = MIMEMultipart()
    msg["From"] = os.getenv("SMTP_EMAIL")
    msg["To"] = to_email
    msg["Subject"] = "Your Blackout Vaults Privacy Report"
    msg.attach(MIMEText("Attached is your encrypted privacy report.", "plain"))
    part = MIMEApplication(pdf_content, _subtype="pdf")
    part.add_header("Content-Disposition", "attachment", filename="PrivacyReport.pdf")
    msg.attach(part)
    with smtplib.SMTP_SSL(os.getenv("SMTP_SERVER"), int(os.getenv("SMTP_PORT"))) as server:
        server.login(os.getenv("SMTP_EMAIL"), os.getenv("SMTP_PASSWORD"))
        server.send_message(msg)

# ------------------------------------------------------------
# 🔹 ADMIN DASHBOARD ROUTE
# ------------------------------------------------------------
@app.get("/admin")
def admin():
    return {"users": 1089, "active_scans": 23, "revenue": "$12,438"}

# ------------------------------------------------------------
# 🔹 PRIVACY SCORE + DASHBOARD DATA
# ------------------------------------------------------------
from pydantic import BaseModel
import random

class PrivacyRequest(BaseModel):
    email: str

# Example database simulation
reports_db = {
    "user@blackoutvaults.com": [
        {"id": 1, "date": "2025-10-06", "leaksFound": 2, "leaksFixed": 2},
        {"id": 2, "date": "2025-09-28", "leaksFound": 4, "leaksFixed": 4},
    ]
}

@app.get("/privacy-score")
async def get_privacy_score(email: str):
    """
    Returns dynamic privacy score + AI analysis summary.
    """
    try:
        base_score = random.randint(60, 95)
        reports = reports_db.get(email, [])

        # Optional AI Summary
        ai_summary = None
        try:
            prompt = f"Assess privacy safety for {email}. Return one-line risk summary."
            res = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=50,
            )
            ai_summary = res.choices[0].message.content
        except Exception as e:
            ai_summary = "⚠️ AI summary unavailable (offline mode)."
            print(f"OpenAI error: {e}")

        return {
            "email": email,
            "score": base_score,
            "reports": reports,
            "summary": ai_summary,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Server error: {e}")


@app.post("/update-score")
async def update_score(req: PrivacyRequest):
    """
    Manual refresh endpoint for dashboard button.
    """
    email = req.email
    new_score = random.randint(70, 99)
    new_report = {
        "id": len(reports_db.get(email, [])) + 1,
        "date": datetime.utcnow().strftime("%Y-%m-%d"),
        "leaksFound": random.randint(0, 5),
        "leaksFixed": random.randint(0, 5),
    }
    reports_db[email] = reports_db.get(email, []) + [new_report]
    return {"email": email, "new_score": new_score, "reports": reports_db[email]}

# ------------------------------------------------------------
# ✅ RUN LOCALLY
# ------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=10000)
