import os

import pickle

import shutil

import sqlite3



import cv2

import httpx

import numpy as np



from datetime import datetime



from fastapi import (

    FastAPI,

    HTTPException,

    UploadFile,

    File

)



from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse



from pydantic import BaseModel



from insightface.app import FaceAnalysis



from report_service import create_employee_report, create_all_employees_report


from attendance import (
    get_connection,
    add_employee,
    get_employee,
    delete_attendance_by_date,
    record_entry,
    record_exit,
    get_today_attendance,
    get_employee_events,
    get_daily_summary,
    get_attendance_by_date,
    get_employee_attendance_history,
    add_leave,
    delete_leave,
    get_leave
)





# ============================================================

# PROJECT PATHS

# ============================================================



BASE_DIR = os.path.dirname(

    os.path.abspath(__file__)

)



DATABASE = os.path.join(

    BASE_DIR,

    "attendance.db"

)



EMBEDDINGS_FILE = os.path.join(

    BASE_DIR,

    "data",

    "embeddings",

    "face_embeddings.pkl"

)



FACES_DIRECTORY = os.path.join(

    BASE_DIR,

    "data",

    "faces_v2"

)



HUBBLE_API_URL = os.getenv(

    "HUBBLE_API_URL",

    "http://127.0.0.1:8001"

).rstrip("/")





# ============================================================

# TWO CAMERA CONFIGURATION

# ============================================================



ENTRY_CAMERA = "/dev/video0"



EXIT_CAMERA = "/dev/video2"





# ============================================================

# INSIGHTFACE

# ============================================================



print("Loading InsightFace model...")



face_app = FaceAnalysis(

    name="buffalo_l"

)



face_app.prepare(

    ctx_id=-1,

    det_size=(320, 320)

)



print("InsightFace model loaded.")





# ============================================================

# FASTAPI

# ============================================================



app = FastAPI(

    title="Employee Attendance API",

    description=(

        "Backend API for the Employee Attendance System"

    ),

    version="6.1.0"

)





# ============================================================

# CORS

# ============================================================



app.add_middleware(

    CORSMiddleware,

    allow_origins=["*"],

    allow_credentials=True,

    allow_methods=["*"],

    allow_headers=["*"],

)





# ============================================================

# PYDANTIC MODELS

# ============================================================



class EmployeeCreate(BaseModel):



    employee_id: str = ""

    login_id: str = ""

    employee_name: str = ""

    shift_start: str

    shift_end: str = "22:00"

    email: str = ""


class EmployeeShiftUpdate(BaseModel):
    shift_start: str
    shift_end: str





class AttendanceEventCreate(BaseModel):



    employee_id: str





# ============================================================

# HOME

# ============================================================



@app.get("/")

def home():



    return {

        "message":

            "Employee Attendance API is running",



        "version":

            "6.1.0",



        "architecture":

            "two-camera"

    }





# ============================================================

# CAMERA STATUS

# ============================================================



@app.get("/cameras/status")

def cameras_status():



    entry_exists = os.path.exists(

        ENTRY_CAMERA

    )



    exit_exists = os.path.exists(

        EXIT_CAMERA

    )



    return {



        "architecture":

            "two-camera",



        "entry_camera": {



            "device":

                ENTRY_CAMERA,



            "mode":

                "ENTRY",



            "responsibility":

                "CHECK_IN",



            "device_exists":

                entry_exists

        },



        "exit_camera": {



            "device":

                EXIT_CAMERA,



            "mode":

                "EXIT",



            "responsibility":

                "CHECK_OUT",



            "device_exists":

                exit_exists

        }

    }





# ============================================================

# GET ALL EMPLOYEES

# ============================================================



@app.get("/employees")

def get_employees():



    connection = get_connection()



    cursor = connection.cursor()



    cursor.execute("""

        SELECT

            employee_id,

            employee_name,

            shift_start,

            shift_end,

            email,

            hr_contact,

            hr_email

        FROM employees

        ORDER BY employee_id

    """)



    employees = cursor.fetchall()



    connection.close()



    return [

        dict(employee)

        for employee in employees

    ]





# ============================================================
# UPDATE EMPLOYEE SHIFT
# ============================================================

@app.put("/employees/{employee_id}/shift")
def update_employee_shift(
    employee_id: str,
    shift: EmployeeShiftUpdate
):
    """Update an employee's shift timing in the SQLite database."""
    for field_name, value in (
        ("shift_start", shift.shift_start),
        ("shift_end", shift.shift_end),
    ):
        try:
            datetime.strptime(value, "%H:%M")
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=400,
                detail=f"{field_name} must use HH:MM format, for example 09:30",
            )

    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            UPDATE employees
            SET shift_start = ?, shift_end = ?
            WHERE employee_id = ?
            """,
            (shift.shift_start, shift.shift_end, employee_id),
        )

        if cursor.rowcount == 0:
            connection.rollback()
            raise HTTPException(
                status_code=404,
                detail=f"Employee '{employee_id}' not found",
            )

        connection.commit()
        cursor.execute(
            """
            SELECT employee_id, employee_name, shift_start, shift_end,
                   email, hr_contact, hr_email
            FROM employees
            WHERE employee_id = ?
            """,
            (employee_id,),
        )
        updated = cursor.fetchone()
        return {
            "success": True,
            "message": "Employee shift updated successfully",
            "employee": dict(updated),
        }
    finally:
        connection.close()


# ============================================================

# CREATE EMPLOYEE

# ============================================================



@app.post("/employees")

def create_employee(

    employee: EmployeeCreate

):



    login_id = (

        employee.login_id.strip()

        or employee.employee_id.strip()

    )



    if not login_id:



        raise HTTPException(

            status_code=400,

            detail="login_id is required"

        )



    # --------------------------------------------------------

    # VALIDATE SHIFT START

    # --------------------------------------------------------



    try:



        datetime.strptime(

            employee.shift_start,

            "%H:%M"

        )



    except ValueError:



        raise HTTPException(

            status_code=400,

            detail=(

                "shift_start must use "

                "HH:MM format, e.g. 14:00"

            )

        )



    # --------------------------------------------------------

    # VALIDATE SHIFT END

    # --------------------------------------------------------



    try:



        datetime.strptime(

            employee.shift_end,

            "%H:%M"

        )



    except ValueError:



        raise HTTPException(

            status_code=400,

            detail=(

                "shift_end must use "

                "HH:MM format, e.g. 22:00"

            )

        )



    # --------------------------------------------------------

    # CHECK EXISTING EMPLOYEE

    # --------------------------------------------------------



    existing_employee = get_employee(login_id)



    if existing_employee:



        raise HTTPException(

            status_code=409,

            detail="Employee already exists"

        )



    # --------------------------------------------------------

    # SYNC Hubble data before creating the local attendance row

    # --------------------------------------------------------



    try:



        hubble_response = httpx.post(

            f"{HUBBLE_API_URL}/api/employees/sync/"

            f"{login_id}",

            timeout=20.0

        )



    except httpx.HTTPError as exc:



        raise HTTPException(

            status_code=502,

            detail=(

                "Unable to connect to the Hubble employee API. "

                f"Start it or set HUBBLE_API_URL. ({exc})"

            )

        )



    if not hubble_response.is_success:



        try:

            hubble_detail = hubble_response.json().get(

                "detail",

                "Employee synchronization failed"

            )

        except ValueError:

            hubble_detail = (

                "Employee synchronization failed"

            )



        raise HTTPException(

            status_code=502,

            detail=str(hubble_detail)

        )



    hubble_data = hubble_response.json().get("data", {})



    employee_name = (

        hubble_data.get("name")

        or employee.employee_name.strip()

    )



    email = (

        hubble_data.get("mailId")

        or employee.email.strip()

    )



    if not employee_name or not email:



        raise HTTPException(

            status_code=502,

            detail=(

                "Hubble synchronization returned incomplete "

                "employee details"

            )

        )



    add_employee(

        employee_id=login_id,

        employee_name=employee_name,

        shift_start=employee.shift_start,

        shift_end=employee.shift_end,

        email=email,

        hr_contact=hubble_data.get("hrContact"),

        hr_email=hubble_data.get("hrEmail")

    )



    return {



        "message":

            "Employee created successfully",



        "employee": {



            "employee_id": login_id,



            "login_id": login_id,



            "employee_name":

                employee_name,



            "shift_start":

                employee.shift_start,



            "shift_end":

                employee.shift_end,



            "email":

                email,



            "hubble": hubble_data

        }

    }





# ============================================================

# DELETE EMPLOYEE COMPLETELY

# ============================================================



@app.delete(

    "/employees/{employee_id}"

)

def remove_employee(

    employee_id: str

):



    """

    Completely delete an employee.



    Deletes:



        - Employee record

        - Attendance events

        - Daily attendance

        - Face embedding

        - Face directory

    """



    # --------------------------------------------------------

    # OPEN THE ABSOLUTE DATABASE DIRECTLY

    # --------------------------------------------------------



    connection = sqlite3.connect(

        DATABASE

    )



    connection.row_factory = sqlite3.Row



    cursor = connection.cursor()



    # --------------------------------------------------------

    # CHECK EMPLOYEE

    # --------------------------------------------------------



    cursor.execute(

        """

        SELECT

            employee_id,

            employee_name,

            shift_start,

            shift_end,

            email

        FROM employees

        WHERE TRIM(employee_id) = TRIM(?)

        """,

        (

            employee_id,

        )

    )



    employee = cursor.fetchone()



    # --------------------------------------------------------

    # EMPLOYEE NOT FOUND

    # --------------------------------------------------------



    if employee is None:



        cursor.execute("""

            SELECT

                employee_id,

                employee_name

            FROM employees

            ORDER BY employee_id

        """)



        existing_employees = cursor.fetchall()



        connection.close()



        raise HTTPException(

            status_code=404,

            detail={



                "message":

                    (

                        f"Employee {employee_id} "

                        "was not found."

                    ),



                "database_used":

                    DATABASE,



                "employees_in_database": [



                    {

                        "employee_id":

                            row["employee_id"],



                        "employee_name":

                            row["employee_name"]

                    }



                    for row in existing_employees

                ]

            }

        )



    # --------------------------------------------------------

    # DELETE ATTENDANCE EVENTS

    # --------------------------------------------------------



    cursor.execute(

        """

        DELETE FROM attendance_events

        WHERE TRIM(employee_id) = TRIM(?)

        """,

        (

            employee_id,

        )

    )



    events_deleted = cursor.rowcount



    # --------------------------------------------------------

    # DELETE DAILY ATTENDANCE

    # --------------------------------------------------------



    cursor.execute(

        """

        DELETE FROM daily_attendance

        WHERE TRIM(employee_id) = TRIM(?)

        """,

        (

            employee_id,

        )

    )



    summaries_deleted = cursor.rowcount



    # --------------------------------------------------------
    # DELETE LEAVE RECORDS
    # --------------------------------------------------------

    cursor.execute(
        """
        DELETE FROM leave_records
        WHERE TRIM(employee_id) = TRIM(?)
        """,
        (
            employee_id,
        )
    )

    leave_records_deleted = cursor.rowcount



    # --------------------------------------------------------

    # DELETE EMPLOYEE

    # --------------------------------------------------------



    cursor.execute(

        """

        DELETE FROM employees

        WHERE TRIM(employee_id) = TRIM(?)

        """,

        (

            employee_id,

        )

    )



    employee_deleted = cursor.rowcount



    # --------------------------------------------------------

    # COMMIT DATABASE CHANGES

    # --------------------------------------------------------



    connection.commit()



    connection.close()



    # --------------------------------------------------------

    # DELETE FACE EMBEDDING

    # --------------------------------------------------------



    embedding_deleted = False



    if os.path.exists(

        EMBEDDINGS_FILE

    ):



        try:



            with open(

                EMBEDDINGS_FILE,

                "rb"

            ) as file_object:



                employee_embeddings = pickle.load(

                    file_object

                )



            if isinstance(

                employee_embeddings,

                dict

            ):



                matching_key = None



                # Exact match first

                if employee_id in employee_embeddings:



                    matching_key = employee_id



                else:



                    # Check for accidental whitespace

                    for key in employee_embeddings:



                        if (

                            str(key).strip()

                            == employee_id.strip()

                        ):



                            matching_key = key

                            break



                if matching_key is not None:



                    del employee_embeddings[

                        matching_key

                    ]



                    embedding_deleted = True



                    with open(

                        EMBEDDINGS_FILE,

                        "wb"

                    ) as file_object:



                        pickle.dump(

                            employee_embeddings,

                            file_object

                        )



        except Exception as error:



            raise HTTPException(

                status_code=500,

                detail=(

                    "Employee was deleted from the "

                    "database, but the face embedding "

                    "could not be updated: "

                    f"{error}"

                )

            )



    # --------------------------------------------------------

    # DELETE FACE DIRECTORY

    # --------------------------------------------------------



    face_directory = os.path.join(

        FACES_DIRECTORY,

        employee_id

    )



    face_directory_deleted = False



    if os.path.exists(

        face_directory

    ):



        try:



            shutil.rmtree(

                face_directory

            )



            face_directory_deleted = True



        except Exception as error:



            print(

                "Face directory deletion failed:",

                error

            )



    # --------------------------------------------------------

    # RESPONSE

    # --------------------------------------------------------



    return {



        "message":

            "Employee deleted completely",



        "employee_id":

            employee_id,



        "employee_name":

            employee["employee_name"],



        "database_used":

            DATABASE,



        "deleted": {



            "employee_record":

                employee_deleted,



            "attendance_events":

                events_deleted,



            "daily_attendance":

                summaries_deleted,



            "face_embedding":

                embedding_deleted,



            "face_directory":

                face_directory_deleted

        }

    }





# ============================================================

# RECORD ENTRY

# ============================================================



@app.post(

    "/attendance/entry"

)

def attendance_entry(

    attendance: AttendanceEventCreate

):



    employee = get_employee(

        attendance.employee_id

    )



    if employee is None:



        raise HTTPException(

            status_code=404,

            detail="Employee not found"

        )



    success = record_entry(

        attendance.employee_id

    )



    if not success:



        return {



            "message":

                "Entry was not recorded",



            "employee_id":

                attendance.employee_id,



            "status":

                "IGNORED"

        }



    summary = get_daily_summary(

        attendance.employee_id

    )



    return {



        "message":

            "Entry recorded successfully",



        "employee_id":

            attendance.employee_id,



        "event_type":

            "IN",



        "camera":

            ENTRY_CAMERA,



        "summary":

            summary

    }





# ============================================================

# RECORD EXIT

# ============================================================



@app.post(

    "/attendance/exit"

)

def attendance_exit(

    attendance: AttendanceEventCreate

):



    employee = get_employee(

        attendance.employee_id

    )



    if employee is None:



        raise HTTPException(

            status_code=404,

            detail="Employee not found"

        )



    success = record_exit(

        attendance.employee_id

    )



    if not success:



        return {



            "message":

                "Exit was not recorded",



            "employee_id":

                attendance.employee_id,



            "status":

                "IGNORED"

        }



    summary = get_daily_summary(

        attendance.employee_id

    )



    return {



        "message":

            "Exit recorded successfully",



        "employee_id":

            attendance.employee_id,



        "event_type":

            "OUT",



        "camera":

            EXIT_CAMERA,



        "summary":

            summary

    }





# ============================================================

# TODAY ATTENDANCE

# ============================================================



@app.get(

    "/attendance/today"

)

def today_attendance():



    return get_today_attendance()





# ============================================================

# HISTORICAL ATTENDANCE

# ============================================================



@app.get(

    "/attendance/date/{attendance_date}"

)

def attendance_by_date(

    attendance_date: str

):



    # --------------------------------------------------------

    # VALIDATE DATE

    # --------------------------------------------------------



    try:



        datetime.strptime(

            attendance_date,

            "%Y-%m-%d"

        )



    except ValueError:



        raise HTTPException(

            status_code=400,

            detail=(

                "Invalid date format. "

                "Use YYYY-MM-DD."

            )

        )



    # --------------------------------------------------------

    # GET ATTENDANCE

    # --------------------------------------------------------



    try:



        result = get_attendance_by_date(

            attendance_date

        )



    except ValueError as error:



        raise HTTPException(

            status_code=400,

            detail=str(error)

        )



    return result





# ============================================================

# DELETE ATTENDANCE FOR A PARTICULAR DATE

# ============================================================



@app.delete(

    "/attendance/date/{attendance_date}"

)

def remove_attendance_date(

    attendance_date: str

):



    """

    Delete attendance for a specific date.



    Deletes:

        - attendance_events

        - daily_attendance



    Keeps:

        - employees

        - face embeddings

        - employee face enrollment

    """



    # --------------------------------------------------------

    # VALIDATE DATE

    # --------------------------------------------------------



    try:



        datetime.strptime(

            attendance_date,

            "%Y-%m-%d"

        )



    except ValueError:



        raise HTTPException(

            status_code=400,

            detail=(

                "Invalid date format. "

                "Use YYYY-MM-DD."

            )

        )



    # --------------------------------------------------------

    # DELETE ATTENDANCE

    # --------------------------------------------------------



    try:



        result = delete_attendance_by_date(

            attendance_date

        )



    except ValueError as error:



        raise HTTPException(

            status_code=400,

            detail=str(error)

        )



    # --------------------------------------------------------

    # RESPONSE

    # --------------------------------------------------------



    return {



        "message":

            "Attendance deleted successfully",



        "date":

            attendance_date,



        "events_deleted":

            result["events_deleted"],



        "summaries_deleted":

            result["summaries_deleted"]

    }





# ============================================================

# EMPLOYEE DAILY SUMMARY

# ============================================================



@app.get(

    "/attendance/{employee_id}/summary"

)

def employee_daily_summary(

    employee_id: str

):



    employee = get_employee(

        employee_id

    )



    if employee is None:



        raise HTTPException(

            status_code=404,

            detail="Employee not found"

        )



    summary = get_daily_summary(

        employee_id

    )



    return summary





# ============================================================

# EMPLOYEE EVENTS

# ============================================================



@app.get(

    "/attendance/{employee_id}/events"

)

def employee_events(

    employee_id: str,

    attendance_date: str | None = None

):



    employee = get_employee(

        employee_id

    )



    if employee is None:



        raise HTTPException(

            status_code=404,

            detail="Employee not found"

        )



    # --------------------------------------------------------

    # VALIDATE DATE

    # --------------------------------------------------------



    if attendance_date is not None:



        try:



            datetime.strptime(

                attendance_date,

                "%Y-%m-%d"

            )



        except ValueError:



            raise HTTPException(

                status_code=400,

                detail=(

                    "attendance_date must use "

                    "YYYY-MM-DD format"

                )

            )



    events = get_employee_events(

        employee_id,

        attendance_date

    )



    return [

        dict(event)

        for event in events

    ]





# ============================================================


# ============================================================
# EMPLOYEE ATTENDANCE HISTORY CALENDAR
# ============================================================

@app.get("/employees/{employee_id}/attendance-history")
def employee_attendance_history(
    employee_id: str,
    year: int,
    month: int
):
    """Return calendar-ready attendance records for one employee/month."""

    employee = get_employee(employee_id)

    if employee is None:
        raise HTTPException(
            status_code=404,
            detail=f"Employee '{employee_id}' not found"
        )

    if month < 1 or month > 12:
        raise HTTPException(
            status_code=400,
            detail="month must be between 1 and 12"
        )

    if year < 2000 or year > 2100:
        raise HTTPException(
            status_code=400,
            detail="year must be between 2000 and 2100"
        )

    try:
        history = get_employee_attendance_history(
            employee_id,
            year,
            month
        )
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error)
        )
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Unable to load attendance history: {error}"
        )

    # get_employee_attendance_history() already returns a dictionary
    # containing the employee, year, month and the calendar list.
    # Do not wrap that whole dictionary inside another `attendance`
    # property; the React dashboard expects `attendance` to be a list.
    if not history:
        raise HTTPException(
            status_code=404,
            detail=f"Attendance history not found for employee '{employee_id}'"
        )

    attendance = history.get("attendance", [])

    return {
        "success": True,
        "employee_id": employee_id,
        "year": year,
        "month": month,
        "attendance": attendance
    }



# ============================================================
# EXCEL ATTENDANCE REPORTS
# ============================================================

@app.get("/reports/employee/{employee_id}")
def download_employee_report(
    employee_id: str,
    period: str = "monthly",
    date: str | None = None
):
    """Download one employee's weekly or monthly attendance Excel report."""
    normalized_period = period.strip().lower()

    if normalized_period not in {"weekly", "monthly"}:
        raise HTTPException(
            status_code=400,
            detail="period must be weekly or monthly"
        )

    try:
        content, filename = create_employee_report(
            employee_id,
            normalized_period,
            date
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error))
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Unable to create attendance report: {error}"
        )

    return StreamingResponse(
        iter([content]),
        media_type=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )


@app.get("/reports/attendance")
def download_all_employees_report(
    period: str = "monthly",
    date: str | None = None
):
    """Download all employees' weekly or monthly attendance Excel report."""
    normalized_period = period.strip().lower()

    if normalized_period not in {"weekly", "monthly"}:
        raise HTTPException(
            status_code=400,
            detail="period must be weekly or monthly"
        )

    try:
        content, filename = create_all_employees_report(
            normalized_period,
            date
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Unable to create attendance report: {error}"
        )

    return StreamingResponse(
        iter([content]),
        media_type=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )


# ============================================================
# LEAVE MANAGEMENT
# ============================================================

class LeaveCreate(BaseModel):
    employee_id: str
    leave_date: str
    leave_type: str = "Leave"
    reason: str | None = None


@app.post("/employees/{employee_id}/leave")
def create_employee_leave(
    employee_id: str,
    leave: LeaveCreate
):
    employee = get_employee(employee_id)

    if employee is None:
        raise HTTPException(
            status_code=404,
            detail="Employee not found"
        )

    if leave.employee_id.strip() != employee_id.strip():
        raise HTTPException(
            status_code=400,
            detail="employee_id in request body does not match URL"
        )

    try:
        datetime.strptime(leave.leave_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="leave_date must use YYYY-MM-DD format"
        )

    try:
        result = add_leave(
            employee_id=employee_id,
            leave_date=leave.leave_date,
            leave_type=leave.leave_type,
            reason=leave.reason
        )
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

    return {
        "success": True,
        "message": "Leave added successfully",
        "data": result
    }


@app.get("/employees/{employee_id}/leave/{leave_date}")
def employee_leave(
    employee_id: str,
    leave_date: str
):
    employee = get_employee(employee_id)

    if employee is None:
        raise HTTPException(
            status_code=404,
            detail="Employee not found"
        )

    try:
        datetime.strptime(leave_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="leave_date must use YYYY-MM-DD format"
        )

    leave = get_leave(employee_id, leave_date)

    return {
        "success": True,
        "data": leave
    }


@app.delete("/employees/{employee_id}/leave/{leave_date}")
def remove_employee_leave(
    employee_id: str,
    leave_date: str
):
    employee = get_employee(employee_id)

    if employee is None:
        raise HTTPException(
            status_code=404,
            detail="Employee not found"
        )

    try:
        datetime.strptime(leave_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="leave_date must use YYYY-MM-DD format"
        )

    try:
        result = delete_leave(employee_id, leave_date)
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

    return {
        "success": True,
        "message": "Leave deleted successfully",
        "data": result
    }


# EMPLOYEE ATTENDANCE

# ============================================================



@app.get(

    "/attendance/{employee_id}"

)

def employee_attendance(

    employee_id: str

):



    employee = get_employee(

        employee_id

    )



    if employee is None:



        raise HTTPException(

            status_code=404,

            detail="Employee not found"

        )



    events = get_employee_events(

        employee_id

    )



    return [

        dict(event)

        for event in events

    ]





# ============================================================

# ALL ATTENDANCE EVENTS

# ============================================================



@app.get(

    "/attendance"

)

def all_attendance():



    connection = get_connection()



    cursor = connection.cursor()



    cursor.execute("""

        SELECT

            attendance_events.id,

            attendance_events.employee_id,

            employees.employee_name,

            employees.shift_start,

            employees.shift_end,

            attendance_events.event_date,

            attendance_events.event_time,

            attendance_events.event_type,

            attendance_events.created_at

        FROM attendance_events

        LEFT JOIN employees

        ON attendance_events.employee_id =

           employees.employee_id

        ORDER BY

            attendance_events.event_date DESC,

            attendance_events.event_time DESC,

            attendance_events.id DESC

    """)



    records = cursor.fetchall()



    connection.close()



    return [

        dict(record)

        for record in records

    ]





# ============================================================

# MULTI-PHOTO FACE ENROLLMENT

# ============================================================



@app.post(

    "/employees/{employee_id}/enroll-face"

)

async def enroll_face(

    employee_id: str,

    files: list[UploadFile] = File(...)

):



    """

    Enroll multiple face images.



    Maximum:

        10 images



    Each image must contain:

        exactly one face.



    The final embedding is the normalized

    average of all valid embeddings.

    """



    # --------------------------------------------------------

    # CHECK EMPLOYEE

    # --------------------------------------------------------



    employee = get_employee(

        employee_id

    )



    if employee is None:



        raise HTTPException(

            status_code=404,

            detail="Employee not found"

        )



    # --------------------------------------------------------

    # CHECK FILE COUNT

    # --------------------------------------------------------



    if not files:



        raise HTTPException(

            status_code=400,

            detail=(

                "Please provide at least "

                "one face image."

            )

        )



    if len(files) > 10:



        raise HTTPException(

            status_code=400,

            detail=(

                "Maximum 10 face images "

                "can be uploaded at once."

            )

        )



    # --------------------------------------------------------

    # PROCESS IMAGES

    # --------------------------------------------------------



    embeddings = []



    processed_files = []



    rejected_files = []



    for file in files:



        # ----------------------------------------------------

        # VALIDATE FILE TYPE

        # ----------------------------------------------------



        if not file.content_type:



            rejected_files.append({



                "filename":

                    file.filename,



                "reason":

                    "File type could not be determined."

            })



            continue



        if not file.content_type.startswith(

            "image/"

        ):



            rejected_files.append({



                "filename":

                    file.filename,



                "reason":

                    "File is not an image."

            })



            continue



        # ----------------------------------------------------

        # READ IMAGE

        # ----------------------------------------------------



        image_bytes = await file.read()



        if not image_bytes:



            rejected_files.append({



                "filename":

                    file.filename,



                "reason":

                    "Empty image."

            })



            continue



        image_array = np.frombuffer(

            image_bytes,

            dtype=np.uint8

        )



        image = cv2.imdecode(

            image_array,

            cv2.IMREAD_COLOR

        )



        if image is None:



            rejected_files.append({



                "filename":

                    file.filename,



                "reason":

                    "Invalid image."

            })



            continue



        # ----------------------------------------------------

        # FACE DETECTION

        # ----------------------------------------------------



        faces = face_app.get(

            image

        )



        if len(faces) == 0:



            rejected_files.append({



                "filename":

                    file.filename,



                "reason":

                    "No face detected."

            })



            continue



        if len(faces) > 1:



            rejected_files.append({



                "filename":

                    file.filename,



                "reason": (

                    "Multiple faces detected. "

                    "Use an image containing "

                    "only the employee."

                )

            })



            continue



        # ----------------------------------------------------

        # GET EMBEDDING

        # ----------------------------------------------------



        embedding = (

            faces[0].normed_embedding

        )



        if embedding is None:



            rejected_files.append({



                "filename":

                    file.filename,



                "reason":

                    "Could not generate face embedding."

            })



            continue



        embedding = np.asarray(

            embedding,

            dtype=np.float32

        ).reshape(-1)



        # ----------------------------------------------------

        # VALIDATE EMBEDDING

        # ----------------------------------------------------



        if embedding.shape[0] != 512:



            rejected_files.append({



                "filename":

                    file.filename,



                "reason": (

                    "Unexpected embedding dimension: "

                    f"{embedding.shape[0]}"

                )

            })



            continue



        # ----------------------------------------------------

        # ACCEPT EMBEDDING

        # ----------------------------------------------------



        embeddings.append(

            embedding

        )



        processed_files.append(

            file.filename

        )



    # --------------------------------------------------------

    # REQUIRE VALID PHOTO

    # --------------------------------------------------------



    if len(embeddings) == 0:



        raise HTTPException(



            status_code=400,



            detail={



                "message":

                    "No valid face images were processed.",



                "processed_files":

                    [],



                "rejected_files":

                    rejected_files

            }

        )



    # --------------------------------------------------------

    # CONVERT TO ARRAY

    # --------------------------------------------------------



    embeddings_array = np.asarray(

        embeddings,

        dtype=np.float32

    )



    # --------------------------------------------------------

    # AVERAGE EMBEDDINGS

    # --------------------------------------------------------



    average_embedding = np.mean(

        embeddings_array,

        axis=0

    )



    # --------------------------------------------------------

    # NORMALIZE

    # --------------------------------------------------------



    norm = np.linalg.norm(

        average_embedding

    )



    if norm == 0:



        raise HTTPException(

            status_code=500,

            detail=(

                "Generated embedding "

                "has zero magnitude."

            )

        )



    average_embedding = (

        average_embedding / norm

    ).astype(np.float32)



    # --------------------------------------------------------

    # CREATE EMBEDDING DIRECTORY

    # --------------------------------------------------------



    embeddings_directory = os.path.dirname(

        EMBEDDINGS_FILE

    )



    os.makedirs(

        embeddings_directory,

        exist_ok=True

    )



    # --------------------------------------------------------

    # LOAD EXISTING EMBEDDINGS

    # --------------------------------------------------------



    employee_embeddings = {}



    if os.path.exists(

        EMBEDDINGS_FILE

    ):



        try:



            with open(

                EMBEDDINGS_FILE,

                "rb"

            ) as file_object:



                loaded_embeddings = pickle.load(

                    file_object

                )



            if isinstance(

                loaded_embeddings,

                dict

            ):



                employee_embeddings = (

                    loaded_embeddings

                )



        except (

            pickle.PickleError,

            EOFError,

            ValueError,

            TypeError

        ):



            employee_embeddings = {}



    # --------------------------------------------------------

    # SAVE FINAL EMBEDDING

    # --------------------------------------------------------



    employee_embeddings[

        employee_id

    ] = average_embedding



    with open(

        EMBEDDINGS_FILE,

        "wb"

    ) as file_object:



        pickle.dump(

            employee_embeddings,

            file_object

        )



    # --------------------------------------------------------

    # CREATE FACE DIRECTORY

    # --------------------------------------------------------



    employee_face_directory = os.path.join(

        FACES_DIRECTORY,

        employee_id

    )



    os.makedirs(

        employee_face_directory,

        exist_ok=True

    )



    # --------------------------------------------------------

    # RESPONSE

    # --------------------------------------------------------



    return {



        "message":

            "Face enrollment completed successfully",



        "employee_id":

            employee_id,



        "employee_name":

            employee["employee_name"],



        "photos_received":

            len(files),



        "photos_processed":

            len(processed_files),



        "photos_rejected":

            len(rejected_files),



        "embedding_dimension":

            int(

                average_embedding.shape[0]

            ),



        "embedding_file":

            EMBEDDINGS_FILE,



        "processed_files":

            processed_files,



        "rejected_files":

            rejected_files

    }

