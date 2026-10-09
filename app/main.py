import json

from fastapi import FastAPI, HTTPException

from app.mock_hubble import router as mock_hubble_router

from app.employee_service import (
    enrich_employee,
    save_employee
)

from app.database import (
    employee_directory_collection,
    employees_collection
)


app = FastAPI(
    title="Hubble Employee API",
    description=(
        "Mock Hubble Employee Integration "
        "with MongoDB"
    ),
    version="1.0.0"
)


# ============================================================
# Register Mock Hubble Router
# ============================================================

app.include_router(
    mock_hubble_router
)
@app.get("/")
def home():

    return {
        "success": True,
        "message": "Hubble Employee API is running"
    }

@app.post("/api/directory/load")
def load_directory():

    try:

        with open(
            "data/employee_directory.json",
            "r",
            encoding="utf-8"
        ) as file:

            people = json.load(file)

        for person in people:

            employee_directory_collection.update_one(

                {
                    "name": person["name"]
                },

                {
                    "$set": person
                },

                upsert=True
            )

        return {
            "success": True,
            "message": "Employee directory loaded successfully",
            "count": len(people)
        }

    except FileNotFoundError:

        raise HTTPException(
            status_code=500,
            detail="employee_directory.json not found"
        )

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

@app.post("/api/employees/sync/{login_id}")
def sync_employee(login_id: str):

    try:

        # ----------------------------------------------------
        # Step 1: Read employee from Mock Hubble
        # ----------------------------------------------------

        with open(
            "data/mock_employees.json",
            "r",
            encoding="utf-8"
        ) as file:

            employees = json.load(file)


        hubble_employee = None


        for employee in employees:

            if (
                employee["loginId"].lower()
                == login_id.lower()
            ):

                hubble_employee = employee

                break


        if not hubble_employee:

            raise HTTPException(
                status_code=404,
                detail=(
                    f"Employee '{login_id}' "
                    "not found in Hubble"
                )
            )


        # ----------------------------------------------------
        # Step 2: Enrich employee
        #
        # Hubble provides:
        #
        # reportsTo
        # hrContact
        #
        # Employee Directory provides:
        #
        # reportsToMailId
        # hrEmail
        # ----------------------------------------------------

        employee = enrich_employee(
            hubble_employee
        )


        # ----------------------------------------------------
        # Step 3: Save final employee to MongoDB
        # ----------------------------------------------------

        saved_employee = save_employee(
            employee
        )


        return {
            "success": True,
            "message": (
                "Employee synchronized successfully"
            ),
            "data": saved_employee
        }


    except HTTPException:

        raise


    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# ============================================================
# Get Employee From MongoDB
# ============================================================

@app.get("/api/employees/{login_id}")
def get_employee(login_id: str):

    employee = (
        employees_collection.find_one(
            {
                "loginId": login_id
            },
            {
                "_id": 0
            }
        )
    )


    if not employee:

        raise HTTPException(
            status_code=404,
            detail=(
                f"Employee '{login_id}' "
                "not found in MongoDB"
            )
        )


    return {
        "success": True,
        "data": employee
    }