from fastapi import APIRouter, HTTPException
from app.models.schemas import MerchantProfile
from app.services import merchant_registry

router = APIRouter()


@router.post("/register", summary="Register or update a merchant profile")
def register_merchant(profile: MerchantProfile):
    saved = merchant_registry.register(profile)
    return {"registered": True, "merchant_id": saved.merchant_id}


@router.get("/{merchant_id}", summary="Get merchant risk profile")
def get_merchant(merchant_id: str):
    profile = merchant_registry.get(merchant_id)
    if not profile:
        raise HTTPException(status_code=404, detail=f"Merchant '{merchant_id}' not found")
    return profile


@router.get("/", summary="List all merchants")
def list_merchants():
    return merchant_registry.all_merchants()
