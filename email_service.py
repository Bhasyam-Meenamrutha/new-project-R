import os
import smtplib

from email.message import EmailMessage

from dotenv import load_dotenv


load_dotenv()


EMAIL_SENDER = os.getenv(
    "EMAIL_SENDER"
)

EMAIL_PASSWORD = os.getenv(
    "EMAIL_PASSWORD"
)


def send_arrival_email(
    employee_name,
    employee_email,
    shift_start,
    first_in,
    status,
    minutes,
    sender_email=None
):
    """
    Send an early or late arrival notification.
    """

    if not EMAIL_SENDER or not EMAIL_PASSWORD:

        print(
            "Email configuration is missing."
        )

        return False

    message = EmailMessage()

    sender = sender_email or EMAIL_SENDER

    message["From"] = sender
    message["Reply-To"] = sender

    message["To"] = employee_email

    if status == "EARLY":

        message["Subject"] = (
            "Early Arrival Notification"
        )

        message.set_content(
            f"""
Hello {employee_name},

This is an automated attendance notification.

Your first arrival today was recorded earlier
than your scheduled shift.

Employee       : {employee_name}
Shift Start    : {shift_start}
First IN       : {first_in}
Arrival Status : EARLY
Early By       : {minutes} minutes

Please note that early arrival has been recorded
by the Employee Attendance System.

This is an automatically generated email.
Please do not reply to this email.

Regards,
Employee Attendance System
"""
        )

    elif status == "LATE":

        message["Subject"] = (
            "Late Arrival Notification"
        )

        message.set_content(
            f"""
Hello {employee_name},

This is an automated attendance notification.

Your first arrival today was recorded later
than your scheduled shift.

Employee       : {employee_name}
Shift Start    : {shift_start}
First IN       : {first_in}
Arrival Status : LATE
Late By        : {minutes} minutes

Please ensure that you follow your assigned
shift timings.

This is an automatically generated email.
Please do not reply to this email.

Regards,
Employee Attendance System
"""
        )

    else:

        print(
            "No arrival email required."
        )

        return False

    try:

        with smtplib.SMTP(
            "smtp.gmail.com",
            587
        ) as server:

            server.starttls()

            server.login(
                EMAIL_SENDER,
                EMAIL_PASSWORD
            )

            server.send_message(
                message,
                from_addr=EMAIL_SENDER
            )

        print(
            f"Arrival email sent to {employee_email}"
        )

        return True

    except Exception as error:

        print(
            "Failed to send arrival email:"
        )

        print(error)

        return False