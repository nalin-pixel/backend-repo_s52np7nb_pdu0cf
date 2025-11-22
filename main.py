import os
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database import db, create_document, get_documents
from schemas import User, Workspace, Transaction, Notification

app = FastAPI(title="Elitemoney Pro Manager API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Elitemoney Pro Manager API running"}

@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = db.name
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️ Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️ Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    return response

# --------- Helper functions ---------

def compute_cash_flow(transactions: List[dict]) -> Dict[str, float]:
    income = sum(t.get("amount", 0) for t in transactions if t.get("direction") == "income")
    expense = sum(t.get("amount", 0) for t in transactions if t.get("direction") == "expense")
    return {"income": income, "expense": expense, "net": income - expense}


def compute_social_balances(transactions: List[dict]) -> Dict[str, float]:
    balances: Dict[str, float] = {}
    for t in transactions:
        if t.get("type") != "social":
            continue
        payer = t.get("payer_id")
        amount = float(t.get("amount", 0))
        beneficiaries = t.get("beneficiaries") or []
        if not payer or amount <= 0 or not beneficiaries:
            continue
        # Initialize
        balances[payer] = balances.get(payer, 0.0)
        if t.get("split_method") == "percentage":
            for b in beneficiaries:
                uid = b.get("user_id")
                share_pct = float(b.get("share", 0))
                share_amt = amount * share_pct
                balances[uid] = balances.get(uid, 0.0) - share_amt
            balances[payer] += amount
        else:  # equal
            per_head = amount / len(beneficiaries)
            for b in beneficiaries:
                uid = b.get("user_id")
                balances[uid] = balances.get(uid, 0.0) - per_head
            balances[payer] += amount
    # Net: positive means user should receive money; negative means owes
    return balances

# --------- Schemas for requests ---------

class CreateUser(BaseModel):
    name: str
    email: str
    default_workspace_id: Optional[str] = None

class CreateWorkspace(BaseModel):
    name: str
    type: str  # company|home|social
    members: List[str] = []

class CreateTransaction(BaseModel):
    workspace_id: str
    type: str  # company|home|social
    amount: float
    date: Optional[datetime] = None
    category: Optional[str] = "General"
    status: Optional[str] = "Pending"
    direction: Optional[str] = None
    payer_id: Optional[str] = None
    split_method: Optional[str] = None
    beneficiaries: Optional[List[Dict[str, Any]]] = None

# --------- CRUD Endpoints (minimal) ---------

@app.post("/api/users")
def create_user(payload: CreateUser):
    uid = create_document("user", payload)
    return {"id": uid}

@app.post("/api/workspaces")
def create_workspace(payload: CreateWorkspace):
    if payload.type not in ("company", "home", "social"):
        raise HTTPException(status_code=400, detail="Invalid workspace type")
    wid = create_document("workspace", payload)
    return {"id": wid}

@app.post("/api/transactions")
def create_transaction(payload: CreateTransaction):
    if payload.type not in ("company", "home", "social"):
        raise HTTPException(status_code=400, detail="Invalid transaction type")
    tid = create_document("transaction", payload)
    return {"id": tid}

@app.get("/api/workspaces/{workspace_id}/summary")
def workspace_summary(workspace_id: str, mode: Optional[str] = None):
    # fetch latest transactions for this workspace
    txns = get_documents("transaction", {"workspace_id": workspace_id})
    if not mode and txns:
        mode = txns[0].get("type")

    mode = (mode or "home").lower()
    if mode == "company":
        cash = compute_cash_flow(txns)
        pending = sum(t.get("amount", 0) for t in txns if t.get("status") == "Pending")
        return {"mode": "company", "cash_flow": cash, "invoices": {"pending": pending}}
    elif mode == "social":
        balances = compute_social_balances(txns)
        return {"mode": "social", "balances": balances}
    else:  # home
        cash = compute_cash_flow(txns)
        return {"mode": "home", "budget": cash}

# --------- AI-like endpoints with fail-safe ---------

@app.post("/api/ai/receipt-scan")
async def receipt_scan(file: UploadFile = File(...)):
    try:
        # Simulate a call to external AI service using environment flag
        simulate_quota = os.getenv("SIMULATE_AI_QUOTA", "false").lower() == "true"
        if simulate_quota:
            raise HTTPException(status_code=429, detail="Quota Exceeded")
        # Here you'd integrate with a real OCR/LLM API
        content = await file.read()
        # naive mock success extraction
        return {
            "merchant": "Parsed Merchant",
            "amount": 42.5,
            "date": datetime.utcnow().date().isoformat(),
            "demo": False
        }
    except HTTPException as e:
        if e.status_code == 429:
            return {
                "merchant": "Demo Store",
                "amount": 50.00,
                "date": datetime.utcnow().date().isoformat(),
                "demo": True,
                "message": "Quota exceeded - using demo data"
            }
        raise
    except Exception:
        return {
            "merchant": "Demo Store",
            "amount": 50.00,
            "date": datetime.utcnow().date().isoformat(),
            "demo": True,
            "message": "AI unavailable - using demo data"
        }

@app.get("/api/ai/advisor")
def financial_advisor(workspace_id: Optional[str] = None):
    try:
        simulate_quota = os.getenv("SIMULATE_AI_QUOTA", "false").lower() == "true"
        if simulate_quota:
            raise HTTPException(status_code=429, detail="Quota Exceeded")
        # simple heuristic based on last 30 days transactions
        filter_q = {"workspace_id": workspace_id} if workspace_id else {}
        since = datetime.utcnow() - timedelta(days=30)
        txns = [t for t in get_documents("transaction", filter_q) if t.get("date", since) >= since]
        cash = compute_cash_flow(txns)
        insight = "You're on track. Keep expenses under 80% of income." if cash["net"] >= 0 else "Spending exceeds income. Consider cutting non-essentials."
        return {"demo": False, "advice": insight, "net30": cash["net"]}
    except HTTPException as e:
        if e.status_code == 429:
            return {"demo": True, "advice": "Limit Reached: Try to save 20% of your income this month."}
        raise
    except Exception:
        return {"demo": True, "advice": "Limit Reached: Try to save 20% of your income this month."}
