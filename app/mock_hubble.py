import json

from pathlib import Path

from fastapi import APIRouter, HTTPException


router = APIRouter(
    prefix="/mock-hubble",
    tags=["Mock Hubble"]
)


DATA_FILE = Path(
    "data/mock_employees.json"
)


def load_employees():

    with open(
        DATA_FILE,
        "r",
        encoding="utf-8"
    ) as file:

        return json.load(file)


@router.get("/employee/{login_id}")
def get_employee(login_id: str):

    employees = load_employees()

    for employee in employees:

        if (
            employee["loginId"].lower()
            == login_id.lower()
        ):

            return employee

    raise HTTPException(
        status_code=404,
        detail="Employee not found"
    )