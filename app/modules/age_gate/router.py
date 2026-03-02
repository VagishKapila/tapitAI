from fastapi import APIRouter
from pydantic import BaseModel
from datetime import date

router = APIRouter(prefix="/v1/age", tags=["age"])


class AgeCheckRequest(BaseModel):
    birth_year: int


@router.post("/check")
def check_age(payload: AgeCheckRequest):
    current_year = date.today().year
    age = current_year - payload.birth_year

    if age < 18:
        return {
            "allowed": False,
            "message": "Sorry, TapIn is 18+ only."
        }

    return {
        "allowed": True,
        "age": age
    }
