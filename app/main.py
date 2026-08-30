from fastapi import FastAPI
from app.routers import fraud, merchant

app = FastAPI(
    title="Razorpay Fraud Guard Agent — Problem #2",
    description="""
Pre-authorization fraud detector for agentic e-commerce.
Runs three detectors in parallel before UPI Reserve Pay fires:
  1. Prompt injection    — intent vs basket mismatch
  2. Counterfeit merchant — real-time merchant risk scoring
  3. Agent impersonation  — JWT identity verification + velocity detection
""",
    version="1.0.0"
)

app.include_router(fraud.router, prefix="/fraud", tags=["Fraud Detection"])
app.include_router(merchant.router, prefix="/merchant", tags=["Merchant Registry"])

@app.get("/health")
def health():
    return {"status": "ok", "agent": "fraud-guard", "version": "1.0.0"}
