"""
Excel attendance report generation.

Main report format:

Date | Emp ID | Emp Name | Shift In | Shift Out | No. of Hrs Working

For All Employees:
Every date contains every employee.

Example:

01-10-2026 | vyasa       | Vikansha Yasa       | 17:35:25 | 23:01:57 | 5h 25m
01-10-2026 | isanapathi  | Indhu Sanapathi     | 10:49:40 |           | 1h 28m
01-10-2026 | mbhasyam    | Meenamrutha Bhasyam | 10:51:00 | 12:19:00 | 1h 28m

02-10-2026 | vyasa       | Vikansha Yasa       |           |           | 0h 0m
02-10-2026 | isanapathi  | Indhu Sanapathi     |           |           | 0h 0m
02-10-2026 | mbhasyam    | Meenamrutha Bhasyam |           |           | 0h 0m
"""

from datetime import date as date_type, datetime, timedelta
from io import BytesIO
import calendar

from openpyxl import Workbook
from openpyxl.styles import (
    Alignment,
    Font,
    PatternFill,
    Border,
    Side,
)
from openpyxl.utils import get_column_letter

from attendance import (
    get_connection,
    get_employee,
    get_employee_attendance_history,
)


XLSX_MEDIA_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)


# ============================================================
# Excel styles
# ============================================================

HEADER_FILL = PatternFill(
    "solid",
    fgColor="1F2937"
)

SUBHEADER_FILL = PatternFill(
    "solid",
    fgColor="EEF2FF"
)

WHITE_FONT = Font(
    color="FFFFFF",
    bold=True
)

BOLD_FONT = Font(
    bold=True
)

TITLE_FONT = Font(
    size=16,
    bold=True
)

THIN_BORDER = Border(
    bottom=Side(
        style="thin",
        color="D0D5DD"
    )
)


# ============================================================
# Date helpers
# ============================================================

def _parse_date(value):
    """
    Convert YYYY-MM-DD string to date.
    """
    if value:
        try:
            return datetime.strptime(
                value,
                "%Y-%m-%d"
            ).date()

        except ValueError as exc:
            raise ValueError(
                "date must use YYYY-MM-DD format"
            ) from exc

    return date_type.today()


def _period_dates(period, selected_date):
    """
    Return start and end date for weekly/monthly report.
    """

    selected = _parse_date(selected_date)

    if period == "monthly":

        first = selected.replace(
            day=1
        )

        last = selected.replace(
            day=calendar.monthrange(
                selected.year,
                selected.month
            )[1]
        )

        return first, last

    if period == "weekly":

        # Monday -> Sunday
        start = (
            selected
            - timedelta(
                days=selected.weekday()
            )
        )

        end = start + timedelta(
            days=6
        )

        return start, end

    raise ValueError(
        "period must be weekly or monthly"
    )


# ============================================================
# Attendance data
# ============================================================

def _month_history(
    employee_id,
    year,
    month
):
    """
    Get attendance history for one employee/month.
    """

    history = get_employee_attendance_history(
        employee_id,
        year,
        month
    )

    if history is None:
        raise LookupError(
            f"Employee '{employee_id}' not found"
        )

    return {
        row["date"]: row
        for row in history.get(
            "attendance",
            []
        )
    }


def _history_for_range(
    employee_id,
    start_date,
    end_date
):
    """
    Get attendance records between start_date and end_date.
    """

    result = {}

    # Start from first day of the first month.
    cursor = start_date.replace(
        day=1
    )

    while cursor <= end_date:

        month_data = _month_history(
            employee_id,
            cursor.year,
            cursor.month
        )

        result.update(
            month_data
        )

        if cursor.month == 12:

            cursor = cursor.replace(
                year=cursor.year + 1,
                month=1
            )

        else:

            cursor = cursor.replace(
                month=cursor.month + 1
            )

    return {
        key: value
        for key, value in result.items()
        if (
            start_date.isoformat()
            <= key
            <= end_date.isoformat()
        )
    }


def _employee_rows():
    """
    Get all employees from SQLite.
    """

    connection = get_connection()

    try:

        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                employee_id,
                employee_name,
                shift_start,
                shift_end,
                email,
                hr_contact,
                hr_email
            FROM employees
            ORDER BY employee_name COLLATE NOCASE
            """
        )

        return [
            dict(row)
            for row in cursor.fetchall()
        ]

    finally:
        connection.close()


def _format_minutes(minutes):
    """
    Convert minutes to 'Xh Ym'.
    """

    minutes = int(
        minutes or 0
    )

    hours = minutes // 60
    remaining = minutes % 60

    return f"{hours}h {remaining}m"


# ============================================================
# Excel helpers
# ============================================================

def _set_header(
    ws,
    row,
    columns
):
    """
    Create Excel header row.
    """

    for column_number, value in enumerate(
        columns,
        start=1
    ):

        cell = ws.cell(
            row=row,
            column=column_number,
            value=value
        )

        cell.fill = HEADER_FILL
        cell.font = WHITE_FONT

        cell.alignment = Alignment(
            horizontal="center",
            vertical="center"
        )

        cell.border = THIN_BORDER

    ws.freeze_panes = (
        f"A{row + 1}"
    )

    ws.auto_filter.ref = (
        f"A{row}:"
        f"{get_column_letter(len(columns))}"
        f"{row}"
    )


def _style_sheet(
    ws,
    widths
):
    """
    Apply common Excel formatting.
    """

    for index, width in enumerate(
        widths,
        start=1
    ):

        ws.column_dimensions[
            get_column_letter(index)
        ].width = width

    for row in ws.iter_rows():

        for cell in row:

            cell.alignment = Alignment(
                vertical="top",
                wrap_text=True
            )

    ws.sheet_view.showGridLines = False


# ============================================================
# Main employee report
# ============================================================

def _add_employee_attendance_sheet(
    wb,
    employee,
    rows,
    period,
    start_date,
    end_date
):
    """
    Create individual employee report.

    Format:

    Date
    Emp ID
    Emp Name
    Shift In
    Shift Out
    No. of Hrs Working
    """

    ws = wb.active

    ws.title = "Attendance Report"

    # --------------------------------------------------------
    # Title
    # --------------------------------------------------------

    ws["A1"] = (
        "Employee Attendance Report"
    )

    ws["A1"].font = TITLE_FONT

    ws.merge_cells(
        "A1:F1"
    )

    # --------------------------------------------------------
    # Employee information
    # --------------------------------------------------------

    information = [

        (
            "Employee ID",
            employee.get(
                "employee_id"
            ) or ""
        ),

        (
            "Employee Name",
            employee.get(
                "employee_name"
            ) or ""
        ),

        (
            "Email",
            employee.get(
                "email"
            ) or ""
        ),

        (
            "Shift",
            (
                f"{employee.get('shift_start') or ''}"
                f" - "
                f"{employee.get('shift_end') or ''}"
            )
        ),

        (
            "Report Type",
            period.title()
        ),

        (
            "Report Period",
            (
                f"{start_date.strftime('%d-%m-%Y')}"
                f" to "
                f"{end_date.strftime('%d-%m-%Y')}"
            )
        ),
    ]

    for row_number, (
        label,
        value
    ) in enumerate(
        information,
        start=3
    ):

        label_cell = ws.cell(
            row=row_number,
            column=1,
            value=label
        )

        label_cell.font = BOLD_FONT
        label_cell.fill = SUBHEADER_FILL

        ws.merge_cells(
            start_row=row_number,
            start_column=2,
            end_row=row_number,
            end_column=6
        )

        ws.cell(
            row=row_number,
            column=2,
            value=value
        )

    # --------------------------------------------------------
    # Main table
    # --------------------------------------------------------

    header_row = 10

    columns = [
        "Date",
        "Emp ID",
        "Emp Name",
        "Shift In",
        "Shift Out",
        "No. of Hrs Working",
    ]

    _set_header(
        ws,
        header_row,
        columns
    )

    output_row = (
        header_row + 1
    )

    for row in rows:

        attendance = row[
            "attendance"
        ]

        values = [

            datetime.strptime(
                attendance["date"],
                "%Y-%m-%d"
            ).date(),

            employee.get(
                "employee_id"
            ) or "",

            employee.get(
                "employee_name"
            ) or "",

            attendance.get(
                "first_in"
            ) or "",

            attendance.get(
                "last_out"
            ) or "",

            attendance.get(
                "worked_hours"
            ) or "0h 0m",
        ]

        for column_number, value in enumerate(
            values,
            start=1
        ):

            cell = ws.cell(
                row=output_row,
                column=column_number,
                value=value
            )

            if column_number == 1:

                cell.number_format = (
                    "dd-mm-yyyy"
                )

        output_row += 1

    # --------------------------------------------------------
    # Total
    # --------------------------------------------------------

    total_minutes = sum(
        int(
            row["attendance"].get(
                "worked_minutes"
            ) or 0
        )
        for row in rows
    )

    total_row = (
        output_row + 1
    )

    ws.cell(
        row=total_row,
        column=1,
        value="Total Working Hours"
    ).font = BOLD_FONT

    ws.cell(
        row=total_row,
        column=2,
        value=_format_minutes(
            total_minutes
        )
    ).font = BOLD_FONT

    ws.cell(
        row=total_row,
        column=1
    ).fill = SUBHEADER_FILL

    # --------------------------------------------------------
    # Formatting
    # --------------------------------------------------------

    _style_sheet(
        ws,
        [
            15,
            16,
            30,
            16,
            16,
            22,
        ]
    )

    ws.freeze_panes = (
        f"A{header_row + 1}"
    )

    ws.auto_filter.ref = (
        f"A{header_row}:"
        f"F{header_row + len(rows)}"
    )

    ws.row_dimensions[1].height = 25


# ============================================================
# Session history sheet
# ============================================================

def _add_sessions_sheet(
    wb,
    rows
):
    """
    Session history for individual employee.
    """

    ws = wb.create_sheet(
        "Session History"
    )

    columns = [
        "Date",
        "Emp ID",
        "Emp Name",
        "Session #",
        "Check In",
        "Check Out",
        "Hours Worked",
        "Worked Minutes",
    ]

    _set_header(
        ws,
        1,
        columns
    )

    output_row = 2

    for row in rows:

        employee = row[
            "employee"
        ]

        attendance = row[
            "attendance"
        ]

        sessions = (
            attendance.get(
                "sessions"
            ) or []
        )

        for index, session in enumerate(
            sessions,
            start=1
        ):

            minutes = int(
                session.get(
                    "worked_minutes"
                ) or 0
            )

            values = [

                datetime.strptime(
                    attendance["date"],
                    "%Y-%m-%d"
                ).date(),

                employee.get(
                    "employee_id"
                ) or "",

                employee.get(
                    "employee_name"
                ) or "",

                index,

                session.get(
                    "check_in"
                ) or "",

                session.get(
                    "check_out"
                ) or "",

                _format_minutes(
                    minutes
                ),

                minutes,
            ]

            for column_number, value in enumerate(
                values,
                start=1
            ):

                cell = ws.cell(
                    row=output_row,
                    column=column_number,
                    value=value
                )

                if column_number == 1:

                    cell.number_format = (
                        "dd-mm-yyyy"
                    )

            output_row += 1

        # Open session
        open_session = attendance.get(
            "open_session"
        )

        if open_session:

            values = [

                datetime.strptime(
                    attendance["date"],
                    "%Y-%m-%d"
                ).date(),

                employee.get(
                    "employee_id"
                ) or "",

                employee.get(
                    "employee_name"
                ) or "",

                len(sessions) + 1,

                open_session.get(
                    "check_in"
                ) or "",

                "OPEN",

                "Open session",

                "",
            ]

            for column_number, value in enumerate(
                values,
                start=1
            ):

                cell = ws.cell(
                    row=output_row,
                    column=column_number,
                    value=value
                )

                if column_number == 1:

                    cell.number_format = (
                        "dd-mm-yyyy"
                    )

            output_row += 1

    _style_sheet(
        ws,
        [
            15,
            16,
            30,
            12,
            16,
            16,
            18,
            18,
        ]
    )


# ============================================================
# All employee report
# ============================================================

def _add_all_employees_attendance_sheet(
    wb,
    report_rows,
    period,
    start_date,
    end_date
):
    """
    Create ALL EMPLOYEE report.

    EXACT MAIN FORMAT:

    Date | Emp ID | Emp Name | Shift In | Shift Out |
    No. of Hrs Working

    IMPORTANT:
    Rows are ordered by DATE first and then EMPLOYEE.

    Example:

    01-10-2026 | employee1
    01-10-2026 | employee2
    01-10-2026 | employee3

    02-10-2026 | employee1
    02-10-2026 | employee2
    02-10-2026 | employee3
    """

    ws = wb.active

    ws.title = "Attendance Report"

    # --------------------------------------------------------
    # Title
    # --------------------------------------------------------

    ws["A1"] = (
        "All Employees Attendance Report"
    )

    ws["A1"].font = TITLE_FONT

    ws.merge_cells(
        "A1:F1"
    )

    # --------------------------------------------------------
    # Report information
    # --------------------------------------------------------

    ws["A3"] = "Report Type"
    ws["B3"] = period.title()

    ws["A4"] = "Report Period"

    ws["B4"] = (
        f"{start_date.strftime('%d-%m-%Y')}"
        f" to "
        f"{end_date.strftime('%d-%m-%Y')}"
    )

    ws["A3"].font = BOLD_FONT
    ws["A4"].font = BOLD_FONT

    ws["A3"].fill = SUBHEADER_FILL
    ws["A4"].fill = SUBHEADER_FILL

    # --------------------------------------------------------
    # Header
    # --------------------------------------------------------

    header_row = 6

    columns = [
        "Date",
        "Emp ID",
        "Emp Name",
        "Shift In",
        "Shift Out",
        "No. of Hrs Working",
    ]

    _set_header(
        ws,
        header_row,
        columns
    )

    # --------------------------------------------------------
    # Data
    # --------------------------------------------------------

    output_row = (
        header_row + 1
    )

    for row in report_rows:

        employee = row[
            "employee"
        ]

        attendance = row[
            "attendance"
        ]

        values = [

            datetime.strptime(
                attendance["date"],
                "%Y-%m-%d"
            ).date(),

            employee.get(
                "employee_id"
            ) or "",

            employee.get(
                "employee_name"
            ) or "",

            attendance.get(
                "first_in"
            ) or "",

            attendance.get(
                "last_out"
            ) or "",

            attendance.get(
                "worked_hours"
            ) or "0h 0m",
        ]

        for column_number, value in enumerate(
            values,
            start=1
        ):

            cell = ws.cell(
                row=output_row,
                column=column_number,
                value=value
            )

            if column_number == 1:

                cell.number_format = (
                    "dd-mm-yyyy"
                )

        output_row += 1

    # --------------------------------------------------------
    # Formatting
    # --------------------------------------------------------

    _style_sheet(
        ws,
        [
            15,  # Date
            16,  # Emp ID
            30,  # Emp Name
            16,  # Shift In
            16,  # Shift Out
            22,  # Hours
        ]
    )

    ws.freeze_panes = (
        f"A{header_row + 1}"
    )

    if report_rows:

        ws.auto_filter.ref = (
            f"A{header_row}:"
            f"F{header_row + len(report_rows)}"
        )

    ws.row_dimensions[1].height = 25


# ============================================================
# All employee session history
# ============================================================

def _add_all_employee_sessions_sheet(
    wb,
    report_rows
):
    """
    Session history for all employees.
    """

    ws = wb.create_sheet(
        "Session History"
    )

    columns = [
        "Date",
        "Emp ID",
        "Emp Name",
        "Session #",
        "Check In",
        "Check Out",
        "Hours Worked",
        "Worked Minutes",
    ]

    _set_header(
        ws,
        1,
        columns
    )

    output_row = 2

    for row in report_rows:

        employee = row[
            "employee"
        ]

        attendance = row[
            "attendance"
        ]

        sessions = (
            attendance.get(
                "sessions"
            ) or []
        )

        for index, session in enumerate(
            sessions,
            start=1
        ):

            minutes = int(
                session.get(
                    "worked_minutes"
                ) or 0
            )

            values = [

                datetime.strptime(
                    attendance["date"],
                    "%Y-%m-%d"
                ).date(),

                employee.get(
                    "employee_id"
                ) or "",

                employee.get(
                    "employee_name"
                ) or "",

                index,

                session.get(
                    "check_in"
                ) or "",

                session.get(
                    "check_out"
                ) or "",

                _format_minutes(
                    minutes
                ),

                minutes,
            ]

            for column_number, value in enumerate(
                values,
                start=1
            ):

                cell = ws.cell(
                    row=output_row,
                    column=column_number,
                    value=value
                )

                if column_number == 1:

                    cell.number_format = (
                        "dd-mm-yyyy"
                    )

            output_row += 1

        # Open session
        open_session = attendance.get(
            "open_session"
        )

        if open_session:

            values = [

                datetime.strptime(
                    attendance["date"],
                    "%Y-%m-%d"
                ).date(),

                employee.get(
                    "employee_id"
                ) or "",

                employee.get(
                    "employee_name"
                ) or "",

                len(sessions) + 1,

                open_session.get(
                    "check_in"
                ) or "",

                "OPEN",

                "Open session",

                "",
            ]

            for column_number, value in enumerate(
                values,
                start=1
            ):

                cell = ws.cell(
                    row=output_row,
                    column=column_number,
                    value=value
                )

                if column_number == 1:

                    cell.number_format = (
                        "dd-mm-yyyy"
                    )

            output_row += 1

    _style_sheet(
        ws,
        [
            15,
            16,
            30,
            12,
            16,
            16,
            18,
            18,
        ]
    )


# ============================================================
# Workbook creation
# ============================================================

def _build_workbook(
    report_rows,
    employee_details=None,
    period="monthly",
    start_date=None,
    end_date=None
):
    """
    Build workbook.
    """

    wb = Workbook()

    if employee_details:

        # Individual employee
        _add_employee_attendance_sheet(
            wb,
            employee_details,
            report_rows,
            period,
            start_date,
            end_date
        )

        _add_sessions_sheet(
            wb,
            report_rows
        )

    else:

        # All employees
        _add_all_employees_attendance_sheet(
            wb,
            report_rows,
            period,
            start_date,
            end_date
        )

        _add_all_employee_sessions_sheet(
            wb,
            report_rows
        )

    return wb


def _save_workbook(wb):
    """
    Convert workbook to bytes.
    """

    buffer = BytesIO()

    wb.save(buffer)

    buffer.seek(0)

    return buffer.getvalue()


# ============================================================
# Individual employee rows
# ============================================================

def _employee_report_rows(
    employee,
    start_date,
    end_date
):
    """
    Create rows for one employee.
    """

    history = _history_for_range(
        employee["employee_id"],
        start_date,
        end_date
    )

    rows = []

    current_date = start_date

    while current_date <= end_date:

        date_key = current_date.isoformat()

        attendance = history.get(
            date_key
        )

        # Safety fallback.
        # Normally get_employee_attendance_history()
        # already returns every date.
        if attendance is None:

            attendance = {
                "date": date_key,
                "first_in": None,
                "last_out": None,
                "worked_minutes": 0,
                "worked_hours": "0h 0m",
                "sessions": [],
                "events": [],
                "open_session": None,
            }

        rows.append(
            {
                "employee": employee,
                "attendance": attendance,
            }
        )

        current_date += timedelta(
            days=1
        )

    return rows


# ============================================================
# Individual employee report
# ============================================================

def create_employee_report(
    employee_id,
    period,
    selected_date=None
):
    """
    Create weekly/monthly report for one employee.
    """

    if period not in {
        "weekly",
        "monthly"
    }:

        raise ValueError(
            "period must be weekly or monthly"
        )

    employee = get_employee(
        employee_id
    )

    if employee is None:

        raise LookupError(
            f"Employee '{employee_id}' not found"
        )

    employee = dict(
        employee
    )

    start_date, end_date = _period_dates(
        period,
        selected_date
    )

    rows = _employee_report_rows(
        employee,
        start_date,
        end_date
    )

    workbook = _build_workbook(
        rows,
        employee_details=employee,
        period=period,
        start_date=start_date,
        end_date=end_date
    )

    filename = (
        f"{employee['employee_id']}_attendance_"
        f"{period}_"
        f"{start_date.isoformat()}_to_"
        f"{end_date.isoformat()}.xlsx"
    )

    return (
        _save_workbook(workbook),
        filename
    )


# ============================================================
# ALL EMPLOYEES REPORT
# ============================================================

def create_all_employees_report(
    period,
    selected_date=None
):
    """
    Create weekly/monthly report for ALL employees.

    IMPORTANT:

    The order is:

    Date 1
        Employee 1
        Employee 2
        Employee 3

    Date 2
        Employee 1
        Employee 2
        Employee 3

    ...

    This matches the requested notebook format.
    """

    if period not in {
        "weekly",
        "monthly"
    }:

        raise ValueError(
            "period must be weekly or monthly"
        )

    start_date, end_date = _period_dates(
        period,
        selected_date
    )

    # --------------------------------------------------------
    # Load employees once.
    # --------------------------------------------------------

    employees = _employee_rows()

    # --------------------------------------------------------
    # Build history for every employee.
    # --------------------------------------------------------

    employee_histories = {}

    for employee in employees:

        employee_id = employee[
            "employee_id"
        ]

        employee_histories[
            employee_id
        ] = _history_for_range(
            employee_id,
            start_date,
            end_date
        )

    # --------------------------------------------------------
    # IMPORTANT:
    #
    # Date first -> employees second.
    #
    # This gives the notebook format.
    # --------------------------------------------------------

    report_rows = []

    current_date = start_date

    while current_date <= end_date:

        date_key = current_date.isoformat()

        for employee in employees:

            employee_id = employee[
                "employee_id"
            ]

            history = employee_histories[
                employee_id
            ]

            attendance = history.get(
                date_key
            )

            # Safety fallback.
            if attendance is None:

                attendance = {
                    "date": date_key,
                    "first_in": None,
                    "last_out": None,
                    "worked_minutes": 0,
                    "worked_hours": "0h 0m",
                    "sessions": [],
                    "events": [],
                    "open_session": None,
                }

            report_rows.append(
                {
                    "employee": employee,
                    "attendance": attendance,
                }
            )

        current_date += timedelta(
            days=1
        )

    # --------------------------------------------------------
    # Build workbook
    # --------------------------------------------------------

    workbook = _build_workbook(
        report_rows,
        employee_details=None,
        period=period,
        start_date=start_date,
        end_date=end_date
    )

    filename = (
        f"all_employees_attendance_"
        f"{period}_"
        f"{start_date.isoformat()}_to_"
        f"{end_date.isoformat()}.xlsx"
    )

    return (
        _save_workbook(workbook),
        filename
    )