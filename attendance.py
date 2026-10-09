import sqlite3

import os

from datetime import datetime

import httpx

from email_service import send_arrival_email

DATABASE = os.path.join(

    os.path.dirname(

        os.path.abspath(__file__)

    ),

    "attendance.db"

)

HUBBLE_API_URL = os.getenv(

    "HUBBLE_API_URL",

    "http://127.0.0.1:8001"

).rstrip("/")

# ============================================================

# DATABASE

# ============================================================

def get_connection():

    connection = sqlite3.connect(DATABASE)

    connection.row_factory = sqlite3.Row

    return connection

def create_database():

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("""

        CREATE TABLE IF NOT EXISTS employees (

            employee_id TEXT PRIMARY KEY,

            employee_name TEXT NOT NULL,

            shift_start TEXT NOT NULL,

            shift_end TEXT DEFAULT '22:00',

            email TEXT,

            hr_contact TEXT,

            hr_email TEXT

        )

    """)

    cursor.execute("""

        CREATE TABLE IF NOT EXISTS attendance_events (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            employee_id TEXT NOT NULL,

            event_date TEXT NOT NULL,

            event_time TEXT NOT NULL,

            event_type TEXT NOT NULL

                CHECK(event_type IN ('IN', 'OUT')),

            created_at TEXT NOT NULL

        )

    """)

    cursor.execute("""

        CREATE TABLE IF NOT EXISTS daily_attendance (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            employee_id TEXT NOT NULL,

            attendance_date TEXT NOT NULL,

            first_in TEXT,

            last_out TEXT,

            arrival_status TEXT,

            early_minutes INTEGER DEFAULT 0,

            late_minutes INTEGER DEFAULT 0,

            worked_minutes INTEGER DEFAULT 0,

            email_sent INTEGER DEFAULT 0,

            UNIQUE(employee_id, attendance_date)

        )

    """)

    cursor.execute("""

        CREATE TABLE IF NOT EXISTS leave_records (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            employee_id TEXT NOT NULL,

            leave_date TEXT NOT NULL,

            leave_type TEXT DEFAULT 'Leave',

            reason TEXT,

            created_at TEXT NOT NULL,

            UNIQUE(employee_id, leave_date)

        )

    """)


    cursor.execute("""

        CREATE INDEX IF NOT EXISTS idx_leave_employee_date

        ON leave_records(employee_id, leave_date)

    """)


    cursor.execute("""

        CREATE INDEX IF NOT EXISTS idx_events_employee_date

        ON attendance_events(employee_id, event_date)

    """)

    cursor.execute("""

        CREATE INDEX IF NOT EXISTS idx_events_date

        ON attendance_events(event_date)

    """)

    connection.commit()

    cursor.execute("PRAGMA table_info(employees)")

    employee_columns = [

        column["name"]

        for column in cursor.fetchall()

    ]

    if "shift_end" not in employee_columns:

        cursor.execute("""

            ALTER TABLE employees

            ADD COLUMN shift_end TEXT DEFAULT '22:00'

        """)

    if "hr_contact" not in employee_columns:

        cursor.execute("""

            ALTER TABLE employees

            ADD COLUMN hr_contact TEXT

        """)

    if "hr_email" not in employee_columns:

        cursor.execute("""

            ALTER TABLE employees

            ADD COLUMN hr_email TEXT

        """)

    connection.commit()

    connection.close()

# ============================================================

# EMPLOYEE MANAGEMENT

# ============================================================

def add_employee(

    employee_id,

    employee_name,

    shift_start,

    email,

    shift_end="22:00",

    hr_contact=None,

    hr_email=None

):

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("""

        INSERT OR REPLACE INTO employees

        (

            employee_id,

            employee_name,

            shift_start,

            shift_end,

            email,

            hr_contact,

            hr_email

        )

        VALUES (?, ?, ?, ?, ?, ?, ?)

    """, (

        employee_id,

        employee_name,

        shift_start,

        shift_end,

        email,

        hr_contact,

        hr_email

    ))

    connection.commit()

    connection.close()

    print(

        f"Employee {employee_id} added successfully."

    )

def get_employee(employee_id):

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

        WHERE employee_id = ?

    """, (employee_id,))

    employee = cursor.fetchone()

    connection.close()

    return employee

# ============================================================

# DELETE EMPLOYEE COMPLETELY

# ============================================================

def delete_employee(employee_id):

    """

    Delete employee and all related attendance data.

    """

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("""

        SELECT employee_id

        FROM employees

        WHERE employee_id = ?

    """, (employee_id,))

    employee = cursor.fetchone()

    if employee is None:

        connection.close()

        return False

    cursor.execute("""

        DELETE FROM attendance_events

        WHERE employee_id = ?

    """, (employee_id,))

    cursor.execute("""

        DELETE FROM leave_records

        WHERE employee_id = ?

    """, (employee_id,))


    cursor.execute("""

        DELETE FROM daily_attendance

        WHERE employee_id = ?

    """, (employee_id,))

    cursor.execute("""

        DELETE FROM employees

        WHERE employee_id = ?

    """, (employee_id,))

    connection.commit()

    connection.close()

    return True

# ============================================================

# DELETE ATTENDANCE BY DATE

# ============================================================

def delete_attendance_by_date(attendance_date):

    """

    Delete attendance events and summaries for one date.

    Employee details are NOT deleted.

    Face embeddings are NOT deleted.

    """

    try:

        datetime.strptime(

            attendance_date,

            "%Y-%m-%d"

        )

    except ValueError:

        raise ValueError(

            "Invalid date format. Use YYYY-MM-DD."

        )

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("""

        DELETE FROM attendance_events

        WHERE event_date = ?

    """, (attendance_date,))

    cursor.execute("""

        DELETE FROM leave_records

        WHERE leave_date = ?

    """, (attendance_date,))


    events_deleted = cursor.rowcount

    cursor.execute("""

        DELETE FROM daily_attendance

        WHERE attendance_date = ?

    """, (attendance_date,))

    summaries_deleted = cursor.rowcount

    connection.commit()

    connection.close()

    return {

        "date": attendance_date,

        "events_deleted": events_deleted,

        "summaries_deleted": summaries_deleted

    }

# ============================================================

# TIME HELPERS

# ============================================================

def get_today():

    return datetime.now().strftime("%Y-%m-%d")

def get_current_time():

    return datetime.now().strftime("%H:%M:%S")

def time_to_minutes(time_string):

    parts = time_string.split(":")

    hour = int(parts[0])

    minute = int(parts[1])

    return hour * 60 + minute

def calculate_time_difference(

    start_time,

    end_time

):

    start = time_to_minutes(start_time)

    end = time_to_minutes(end_time)

    difference = end - start

    if difference < 0:

        difference = 0

    return difference

# ============================================================

# ARRIVAL STATUS

# ============================================================

def calculate_arrival_status(

    first_in,

    shift_start

):

    arrival_minutes = time_to_minutes(

        first_in

    )

    shift_minutes = time_to_minutes(

        shift_start

    )

    difference = arrival_minutes - shift_minutes

    if difference < 0:

        return (

            "EARLY",

            abs(difference),

            0

        )

    if difference > 0:

        return (

            "LATE",

            0,

            difference

        )

    return (

        "ON_TIME",

        0,

        0

    )

# ============================================================

# EVENTS

# ============================================================

def get_today_events(employee_id):

    today = get_today()

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("""

        SELECT

            id,

            employee_id,

            event_date,

            event_time,

            event_type,

            created_at

        FROM attendance_events

        WHERE employee_id = ?

        AND event_date = ?

        ORDER BY event_time ASC, id ASC

    """, (

        employee_id,

        today

    ))

    events = cursor.fetchall()

    connection.close()

    return events

def get_events_by_date(

    employee_id,

    attendance_date

):

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("""

        SELECT

            id,

            employee_id,

            event_date,

            event_time,

            event_type,

            created_at

        FROM attendance_events

        WHERE employee_id = ?

        AND event_date = ?

        ORDER BY event_time ASC, id ASC

    """, (

        employee_id,

        attendance_date

    ))

    events = cursor.fetchall()

    connection.close()

    return events

def get_employee_events(

    employee_id,

    attendance_date=None

):

    connection = get_connection()

    cursor = connection.cursor()

    if attendance_date:

        cursor.execute("""

            SELECT

                id,

                employee_id,

                event_date,

                event_time,

                event_type,

                created_at

            FROM attendance_events

            WHERE employee_id = ?

            AND event_date = ?

            ORDER BY event_time ASC, id ASC

        """, (

            employee_id,

            attendance_date

        ))

    else:

        cursor.execute("""

            SELECT

                id,

                employee_id,

                event_date,

                event_time,

                event_type,

                created_at

            FROM attendance_events

            WHERE employee_id = ?

            ORDER BY

                event_date DESC,

                event_time DESC,

                id DESC

        """, (

            employee_id,

        ))

    events = cursor.fetchall()

    connection.close()

    return events

# ============================================================

# CURRENT STATE

# ============================================================

def get_current_state(employee_id):

    events = get_today_events(

        employee_id

    )

    if not events:

        return "OUTSIDE"

    last_event = events[-1]

    if last_event["event_type"] == "IN":

        return "INSIDE"

    return "OUTSIDE"

def get_first_in(employee_id):

    events = get_today_events(

        employee_id

    )

    for event in events:

        if event["event_type"] == "IN":

            return event["event_time"]

    return None

# ============================================================

# EMAIL

# ============================================================

def resolve_hr_email(employee_id, stored_hr_email=None):

    if stored_hr_email:

        return stored_hr_email

    try:

        response = httpx.get(

            f"{HUBBLE_API_URL}/api/employees/"

            f"{employee_id}",

            timeout=5.0

        )

        if response.is_success:

            return response.json().get("data", {}).get("hrEmail")

    except httpx.HTTPError as error:

        print(

            f"Unable to resolve HR email for {employee_id}: {error}"

        )

    return None

def send_arrival_notification(

    employee,

    first_in,

    status,

    early_minutes,

    late_minutes

):

    hr_email = resolve_hr_email(

        employee["employee_id"],

        employee["hr_email"]

    )

    if not employee["email"]:

        print(

            "Employee email is not configured."

        )

        return False

    if status == "EARLY":

        return send_arrival_email(

            employee_name=employee["employee_name"],

            employee_email=employee["email"],

            shift_start=employee["shift_start"],

            first_in=first_in,

            status="EARLY",

            minutes=early_minutes,

            sender_email=hr_email

        )

    if status == "LATE":

        return send_arrival_email(

            employee_name=employee["employee_name"],

            employee_email=employee["email"],

            shift_start=employee["shift_start"],

            first_in=first_in,

            status="LATE",

            minutes=late_minutes,

            sender_email=hr_email

        )

    return False

# ============================================================

# RECORD ENTRY

# ============================================================

def record_entry(

    employee_id,

    event_time=None

):

    employee = get_employee(

        employee_id

    )

    if employee is None:

        print(

            "Employee not found."

        )

        return False

    if event_time is None:

        event_time = get_current_time()

    today = get_today()

    current_state = get_current_state(

        employee_id

    )

    if current_state == "INSIDE":

        print()

        print("ENTRY IGNORED")

        print("-------------")

        print(

            f"Employee : {employee['employee_name']}"

        )

        print(

            "Reason   : Employee is already inside."

        )

        return False

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("""

        INSERT INTO attendance_events

        (

            employee_id,

            event_date,

            event_time,

            event_type,

            created_at

        )

        VALUES (?, ?, ?, ?, ?)

    """, (

        employee_id,

        today,

        event_time,

        "IN",

        datetime.now().isoformat()

    ))

    connection.commit()

    connection.close()

    first_in = get_first_in(

        employee_id

    )

    is_first_arrival = (

        first_in == event_time

    )

    print()

    print("ENTRY RECORDED")

    print("--------------")

    print(

        f"Employee : {employee['employee_name']}"

    )

    print(

        f"ID       : {employee_id}"

    )

    print(

        f"Time     : {event_time}"

    )

    if is_first_arrival:

        (

            status,

            early_minutes,

            late_minutes

        ) = calculate_arrival_status(

            first_in,

            employee["shift_start"]

        )

        print(

            f"Shift    : {employee['shift_start']}"

        )

        print(

            f"Status   : {status}"

        )

        if status == "EARLY":

            print(

                f"Early by : {early_minutes} minutes"

            )

        elif status == "LATE":

            print(

                f"Late by  : {late_minutes} minutes"

            )

        connection = get_connection()

        cursor = connection.cursor()

        cursor.execute("""

            INSERT INTO daily_attendance

            (

                employee_id,

                attendance_date,

                first_in,

                arrival_status,

                early_minutes,

                late_minutes

            )

            VALUES (?, ?, ?, ?, ?, ?)

            ON CONFLICT(employee_id, attendance_date)

            DO UPDATE SET

                first_in = excluded.first_in,

                arrival_status = excluded.arrival_status,

                early_minutes = excluded.early_minutes,

                late_minutes = excluded.late_minutes

        """, (

            employee_id,

            today,

            first_in,

            status,

            early_minutes,

            late_minutes

        ))

        connection.commit()

        connection.close()

        if status in ("EARLY", "LATE"):

            print()

            print(

                "Sending arrival notification..."

            )

            email_sent = send_arrival_notification(

                employee,

                first_in,

                status,

                early_minutes,

                late_minutes

            )

            if email_sent:

                connection = get_connection()

                cursor = connection.cursor()

                cursor.execute("""

                    UPDATE daily_attendance

                    SET email_sent = 1

                    WHERE employee_id = ?

                    AND attendance_date = ?

                """, (

                    employee_id,

                    today

                ))

                connection.commit()

                connection.close()

                print(

                    "Arrival notification sent."

                )

    return True

# ============================================================

# RECORD EXIT

# ============================================================

def record_exit(

    employee_id,

    event_time=None

):

    employee = get_employee(

        employee_id

    )

    if employee is None:

        print(

            "Employee not found."

        )

        return False

    if event_time is None:

        event_time = get_current_time()

    today = get_today()

    current_state = get_current_state(

        employee_id

    )

    if current_state == "OUTSIDE":

        print()

        print("EXIT IGNORED")

        print("------------")

        print(

            f"Employee : {employee['employee_name']}"

        )

        print(

            "Reason   : Employee is already outside."

        )

        return False

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("""

        INSERT INTO attendance_events

        (

            employee_id,

            event_date,

            event_time,

            event_type,

            created_at

        )

        VALUES (?, ?, ?, ?, ?)

    """, (

        employee_id,

        today,

        event_time,

        "OUT",

        datetime.now().isoformat()

    ))

    connection.commit()

    connection.close()

    print()

    print("EXIT RECORDED")

    print("-------------")

    print(

        f"Employee : {employee['employee_name']}"

    )

    print(

        f"ID       : {employee_id}"

    )

    print(

        f"Time     : {event_time}"

    )

    summary = calculate_daily_summary(

        employee_id

    )

    print(

        f"Worked today : "

        f"{summary['worked_hours']}"

    )

    return True

# ============================================================

# WORK SESSIONS

# ============================================================

def calculate_sessions(employee_id):

    events = get_today_events(

        employee_id

    )

    return calculate_sessions_from_events(

        events

    )

def calculate_sessions_from_events(events):

    sessions = []

    open_in = None

    for event in events:

        if event["event_type"] == "IN":

            if open_in is None:

                open_in = event["event_time"]

        elif event["event_type"] == "OUT":

            if open_in is not None:

                minutes = calculate_time_difference(

                    open_in,

                    event["event_time"]

                )

                sessions.append({

                    "check_in": open_in,

                    "check_out": event["event_time"],

                    "worked_minutes": minutes

                })

                open_in = None

    open_session = None

    if open_in is not None:

        open_session = {

            "check_in": open_in,

            "check_out": None

        }

    return sessions, open_session

def calculate_worked_minutes(

    sessions,

    open_session=None

):

    worked_minutes = sum(

        session["worked_minutes"]

        for session in sessions

    )

    if open_session and open_session.get("check_in"):

        worked_minutes += calculate_time_difference(

            open_session["check_in"],

            get_current_time()

        )

    return worked_minutes

# ============================================================

# DAILY SUMMARY

# ============================================================

def calculate_daily_summary(employee_id):

    employee = get_employee(

        employee_id

    )

    if employee is None:

        return None

    events = get_today_events(

        employee_id

    )

    sessions, open_session = calculate_sessions(

        employee_id

    )

    total_worked_minutes = calculate_worked_minutes(

        sessions,

        open_session

    )

    first_in = None

    for event in events:

        if event["event_type"] == "IN":

            first_in = event["event_time"]

            break

    last_out = None

    for event in reversed(events):

        if event["event_type"] == "OUT":

            last_out = event["event_time"]

            break

    arrival_status = None

    early_minutes = 0

    late_minutes = 0

    if first_in:

        (

            arrival_status,

            early_minutes,

            late_minutes

        ) = calculate_arrival_status(

            first_in,

            employee["shift_start"]

        )

    worked_hours = (

        f"{total_worked_minutes // 60}h "

        f"{total_worked_minutes % 60}m"

    )

    return {

        "employee_id": employee_id,

        "employee_name": employee["employee_name"],

        "date": get_today(),

        "shift_start": employee["shift_start"],

        "shift_end": employee["shift_end"],

        "first_in": first_in,

        "last_out": last_out,

        "arrival_status": arrival_status,

        "early_minutes": early_minutes,

        "late_minutes": late_minutes,

        "worked_minutes": total_worked_minutes,

        "worked_hours": worked_hours,

        "sessions": sessions,

        "open_session": open_session,

        "current_state": get_current_state(

            employee_id

        ),

        "event_count": len(events)

    }

def get_daily_summary(employee_id):

    summary = calculate_daily_summary(

        employee_id

    )

    if summary is None:

        return None

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("""

        INSERT INTO daily_attendance

        (

            employee_id,

            attendance_date,

            first_in,

            last_out,

            arrival_status,

            early_minutes,

            late_minutes,

            worked_minutes

        )

        VALUES (?, ?, ?, ?, ?, ?, ?, ?)

        ON CONFLICT(employee_id, attendance_date)

        DO UPDATE SET

            first_in = excluded.first_in,

            last_out = excluded.last_out,

            arrival_status = excluded.arrival_status,

            early_minutes = excluded.early_minutes,

            late_minutes = excluded.late_minutes,

            worked_minutes = excluded.worked_minutes

    """, (

        employee_id,

        summary["date"],

        summary["first_in"],

        summary["last_out"],

        summary["arrival_status"],

        summary["early_minutes"],

        summary["late_minutes"],

        summary["worked_minutes"]

    ))

    connection.commit()

    connection.close()

    return summary

# ============================================================

# TODAY ATTENDANCE

# ============================================================

def get_today_attendance():

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("""

        SELECT

            employee_id,

            employee_name,

            shift_start,

            shift_end,

            email

        FROM employees

        ORDER BY employee_id

    """)

    employees = cursor.fetchall()

    connection.close()

    results = []

    for employee in employees:

        summary = calculate_daily_summary(

            employee["employee_id"]

        )

        results.append(summary)

    return results

# ============================================================

# HISTORICAL ATTENDANCE

# ============================================================

def get_attendance_by_date(

    attendance_date

):

    try:

        datetime.strptime(

            attendance_date,

            "%Y-%m-%d"

        )

    except ValueError:

        raise ValueError(

            "Invalid date format. Use YYYY-MM-DD."

        )

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("""

        SELECT

            employee_id,

            employee_name,

            shift_start,

            shift_end,

            email

        FROM employees

        ORDER BY employee_id

    """)

    employees = cursor.fetchall()

    connection.close()

    results = []

    for employee in employees:

        events = get_events_by_date(

            employee["employee_id"],

            attendance_date

        )

        sessions, open_session = (

            calculate_sessions_from_events(

                events

            )

        )

        worked_minutes = calculate_worked_minutes(

            sessions,

            open_session if attendance_date == get_today() else None

        )

        worked_hours = (

            f"{worked_minutes // 60}h "

            f"{worked_minutes % 60}m"

        )

        first_in = None

        for event in events:

            if event["event_type"] == "IN":

                first_in = event["event_time"]

                break

        last_out = None

        for event in reversed(events):

            if event["event_type"] == "OUT":

                last_out = event["event_time"]

                break

        arrival_status = None

        early_minutes = 0

        late_minutes = 0

        if first_in:

            (

                arrival_status,

                early_minutes,

                late_minutes

            ) = calculate_arrival_status(

                first_in,

                employee["shift_start"]

            )

        current_state = "OUTSIDE"

        if events:

            last_event = events[-1]

            if last_event["event_type"] == "IN":

                current_state = "INSIDE"

        results.append({

            "employee_id": employee["employee_id"],

            "employee_name": employee["employee_name"],

            "date": attendance_date,

            "shift_start": employee["shift_start"],

            "shift_end": employee["shift_end"],

            "first_in": first_in,

            "last_out": last_out,

            "arrival_status": arrival_status,

            "early_minutes": early_minutes,

            "late_minutes": late_minutes,

            "worked_minutes": worked_minutes,

            "worked_hours": worked_hours,

            "sessions": sessions,

            "open_session": open_session,

            "current_state": current_state,

            "event_count": len(events)

        })

    return results


# ============================================================
# EMPLOYEE MONTHLY ATTENDANCE HISTORY
# ============================================================

def _format_worked_minutes(worked_minutes):
    return f"{worked_minutes // 60}h {worked_minutes % 60}m"


def _calculate_shift_minutes(shift_start, shift_end):
    start = time_to_minutes(shift_start)
    end = time_to_minutes(shift_end)

    if end <= start:
        end += 24 * 60

    return end - start


def get_employee_attendance_history(
    employee_id,
    year,
    month
):
    """
    Return a complete calendar month for one employee.

    Status values:
        FULL_DAY
        HALF_DAY
        LEAVE
        ABSENT
        WEEKEND
    """
    if month < 1 or month > 12:
        raise ValueError("Month must be between 1 and 12.")

    if year < 2000 or year > 2100:
        raise ValueError("Invalid year.")

    employee = get_employee(employee_id)

    if employee is None:
        return None

    import calendar
    from datetime import date

    connection = get_connection()
    cursor = connection.cursor()

    first_date = f"{year:04d}-{month:02d}-01"
    last_day = calendar.monthrange(year, month)[1]
    last_date = f"{year:04d}-{month:02d}-{last_day:02d}"

    cursor.execute("""
        SELECT
            id,
            employee_id,
            event_date,
            event_time,
            event_type,
            created_at
        FROM attendance_events
        WHERE employee_id = ?
        AND event_date BETWEEN ? AND ?
        ORDER BY event_date ASC, event_time ASC, id ASC
    """, (employee_id, first_date, last_date))

    event_rows = cursor.fetchall()

    cursor.execute("""
        SELECT
            leave_date,
            leave_type,
            reason
        FROM leave_records
        WHERE employee_id = ?
        AND leave_date BETWEEN ? AND ?
        ORDER BY leave_date ASC
    """, (employee_id, first_date, last_date))

    leave_rows = cursor.fetchall()
    connection.close()

    events_by_date = {}

    for row in event_rows:
        event = dict(row)
        events_by_date.setdefault(
            event["event_date"],
            []
        ).append(event)

    leaves_by_date = {}

    for row in leave_rows:
        leave = dict(row)
        leaves_by_date[leave["leave_date"]] = leave

    expected_minutes = _calculate_shift_minutes(
        employee["shift_start"],
        employee["shift_end"]
    )

    if expected_minutes <= 0:
        expected_minutes = 480

    today = get_today()
    attendance = []

    for day_number in range(1, last_day + 1):
        current_date = date(
            year,
            month,
            day_number
        )

        date_string = current_date.isoformat()
        events = events_by_date.get(date_string, [])
        leave = leaves_by_date.get(date_string)

        # Saturday / Sunday.
        if current_date.weekday() >= 5:
            attendance.append({
                "date": date_string,
                "day": day_number,
                "weekday": current_date.strftime("%A"),
                "status": "WEEKEND",
                "first_in": None,
                "last_out": None,
                "worked_minutes": 0,
                "worked_hours": "0h 0m",
                "arrival_status": None,
                "early_minutes": 0,
                "late_minutes": 0,
                "leave_type": None,
                "reason": None,
                "events": [],
                "sessions": [],
                "open_session": None
            })
            continue

        # Leave takes priority over attendance.
        if leave:
            attendance.append({
                "date": date_string,
                "day": day_number,
                "weekday": current_date.strftime("%A"),
                "status": "LEAVE",
                "first_in": None,
                "last_out": None,
                "worked_minutes": 0,
                "worked_hours": "0h 0m",
                "arrival_status": None,
                "early_minutes": 0,
                "late_minutes": 0,
                "leave_type": leave["leave_type"],
                "reason": leave["reason"],
                "events": [],
                "sessions": [],
                "open_session": None
            })
            continue

        # No events on a working day.
        if not events:
            attendance.append({
                "date": date_string,
                "day": day_number,
                "weekday": current_date.strftime("%A"),
                "status": "ABSENT",
                "first_in": None,
                "last_out": None,
                "worked_minutes": 0,
                "worked_hours": "0h 0m",
                "arrival_status": None,
                "early_minutes": 0,
                "late_minutes": 0,
                "leave_type": None,
                "reason": None,
                "events": [],
                "sessions": [],
                "open_session": None
            })
            continue

        sessions, open_session = calculate_sessions_from_events(
            events
        )

        worked_minutes = sum(
            session["worked_minutes"]
            for session in sessions
        )

        # If employee is still inside today, count time until now.
        if date_string == today and open_session:
            worked_minutes += calculate_time_difference(
                open_session["check_in"],
                get_current_time()
            )

        first_in = None
        last_out = None

        for event in events:
            if (
                event["event_type"] == "IN"
                and first_in is None
            ):
                first_in = event["event_time"]

            if event["event_type"] == "OUT":
                last_out = event["event_time"]

        arrival_status = None
        early_minutes = 0
        late_minutes = 0

        if first_in:
            (
                arrival_status,
                early_minutes,
                late_minutes
            ) = calculate_arrival_status(
                first_in,
                employee["shift_start"]
            )

        # 75% or more of scheduled shift = full day.
        if worked_minutes >= expected_minutes * 0.75:
            status = "FULL_DAY"
        else:
            status = "HALF_DAY"

        attendance.append({
            "date": date_string,
            "day": day_number,
            "weekday": current_date.strftime("%A"),
            "status": status,
            "first_in": first_in,
            "last_out": last_out,
            "worked_minutes": worked_minutes,
            "worked_hours": _format_worked_minutes(worked_minutes),
            "arrival_status": arrival_status,
            "early_minutes": early_minutes,
            "late_minutes": late_minutes,
            "leave_type": None,
            "reason": None,
            "events": events,
            "sessions": sessions,
            "open_session": open_session
        })

    return {
        "employee": {
            "employee_id": employee["employee_id"],
            "employee_name": employee["employee_name"],
            "email": employee["email"],
            "shift_start": employee["shift_start"],
            "shift_end": employee["shift_end"]
        },
        "year": year,
        "month": month,
        "attendance": attendance
    }


def add_leave(
    employee_id,
    leave_date,
    leave_type="Leave",
    reason=None
):
    """Add or update a leave record."""
    if get_employee(employee_id) is None:
        return False

    try:
        datetime.strptime(
            leave_date,
            "%Y-%m-%d"
        )
    except ValueError:
        raise ValueError(
            "Invalid leave date. Use YYYY-MM-DD."
        )

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        INSERT INTO leave_records
        (
            employee_id,
            leave_date,
            leave_type,
            reason,
            created_at
        )
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(employee_id, leave_date)
        DO UPDATE SET
            leave_type = excluded.leave_type,
            reason = excluded.reason
    """, (
        employee_id,
        leave_date,
        leave_type or "Leave",
        reason,
        datetime.now().isoformat()
    ))

    connection.commit()
    connection.close()

    return True


def delete_leave(employee_id, leave_date):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        DELETE FROM leave_records
        WHERE employee_id = ?
        AND leave_date = ?
    """, (employee_id, leave_date))

    deleted = cursor.rowcount > 0

    connection.commit()
    connection.close()

    return deleted


def get_leave(employee_id, leave_date):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            id,
            employee_id,
            leave_date,
            leave_type,
            reason,
            created_at
        FROM leave_records
        WHERE employee_id = ?
        AND leave_date = ?
    """, (employee_id, leave_date))

    leave = cursor.fetchone()

    connection.close()

    return leave


# ============================================================

# BACKWARD COMPATIBILITY

# ============================================================

def check_employee_attendance(employee_id):

    return record_entry(

        employee_id

    )

# ============================================================

# INITIALIZE DATABASE

# ============================================================

create_database()

# ============================================================

# DIRECT TEST

# ============================================================

if __name__ == "__main__":

    print()

    print("======================================")

    print("Event-Based Attendance System")

    print("======================================")

    print()

    print("Database initialized.")

    print()

    print("Available functions:")

    print("record_entry(employee_id)")

    print("record_exit(employee_id)")

    print("get_current_state(employee_id)")

    print("calculate_sessions(employee_id)")

    print("calculate_daily_summary(employee_id)")

    print("get_today_attendance()")

    print("get_attendance_by_date('YYYY-MM-DD')")

    print("get_employee_events(employee_id)")

    print("delete_employee(employee_id)")

    print("delete_attendance_by_date('YYYY-MM-DD')")