"""
shared/email_sender.py
======================
Sends automated reports and alerts via email.

WHY THIS EXISTS:
  The scheduler generates weekly reports every Monday.
  This module delivers them directly to your manager's inbox
  automatically — no manual forwarding needed.

SUPPORTED:
  - Gmail (default)
  - Any SMTP server (Outlook, company mail server)

USAGE:
  from shared.email_sender import EmailSender
  sender = EmailSender(config)
  sender.send_weekly_report(report_content, hours_saved, total_runs)
"""

import smtplib
import ssl
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path

from shared.logger import get_logger

logger = get_logger("email_sender")


class EmailSender:

    def __init__(self, config: dict):
        self.sender     = config.get("email_sender", "")
        self.password   = config.get("email_password", "")
        self.recipient  = config.get("email_recipient", "")
        self.smtp_host  = config.get("email_smtp_host", "smtp.gmail.com")
        self.smtp_port  = config.get("email_smtp_port", 587)

        self.enabled = bool(self.sender and self.password and self.recipient)

        if self.enabled:
            logger.info(
                f"EmailSender ready | "
                f"from={self.sender} | "
                f"to={self.recipient}"
            )
        else:
            logger.warning(
                "EmailSender disabled — "
                "EMAIL_SENDER, EMAIL_PASSWORD, or EMAIL_RECIPIENT "
                "missing from .env"
            )

    def send(
        self,
        subject: str,
        body_html: str,
        body_text: str = "",
        attachment_path: str = None
    ) -> bool:
        """
        Send an email with optional file attachment.
        Returns True if sent successfully, False if failed.
        """
        if not self.enabled:
            logger.warning("Email not sent — sender not configured")
            return False

        try:
            # Build the email
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"]    = self.sender
            msg["To"]      = self.recipient

            # Add plain text version
            if body_text:
                msg.attach(MIMEText(body_text, "plain"))

            # Add HTML version
            msg.attach(MIMEText(body_html, "html"))

            # Add attachment if provided
            if attachment_path:
                path = Path(attachment_path)
                if path.exists():
                    with open(path, "rb") as f:
                        part = MIMEBase("application", "octet-stream")
                        part.set_payload(f.read())
                    encoders.encode_base64(part)
                    part.add_header(
                        "Content-Disposition",
                        f"attachment; filename={path.name}"
                    )
                    msg.attach(part)

            # Send via SMTP
            context = ssl.create_default_context()
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.ehlo()
                server.starttls(context=context)
                server.login(self.sender, self.password)
                server.sendmail(self.sender, self.recipient, msg.as_string())

            logger.info(f"Email sent: '{subject}' to {self.recipient}")
            return True

        except smtplib.SMTPAuthenticationError:
            logger.error(
                "Email authentication failed. "
                "Check EMAIL_PASSWORD in .env — "
                "use Gmail App Password, not your regular password."
            )
            return False
        except smtplib.SMTPException as e:
            logger.error(f"SMTP error: {e}")
            return False
        except Exception as e:
            logger.error(f"Email send failed: {e}")
            return False

    def send_weekly_report(
        self,
        report_content: str,
        hours_saved: float,
        total_runs: int,
        cumulative_hours: float,
        attachment_path: str = None
    ) -> bool:
        """
        Send the formatted weekly leadership report email.
        Called automatically by the scheduler every Monday at 7am.
        """
        date_str = datetime.now().strftime("%B %d, %Y")
        value = hours_saved * 50  # estimated at $50/hr

        subject = (
            f"AI Automation Weekly Update — "
            f"Week of {date_str} | "
            f"{hours_saved:.1f}hrs saved"
        )

        # HTML version — looks professional in Outlook and Gmail
        body_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; color: #333; max-width: 600px;">

            <div style="background: #1B2A4A; padding: 20px; border-radius: 8px 8px 0 0;">
                <h2 style="color: white; margin: 0;">
                    AI Automation Weekly Update
                </h2>
                <p style="color: #94a3b8; margin: 5px 0 0 0;">
                    {date_str} &nbsp;|&nbsp; Application Support Automation
                </p>
            </div>

            <div style="background: #f8fafc; padding: 20px; border: 1px solid #e2e8f0;">

                <h3 style="color: #1B2A4A;">Headline This Week</h3>
                <table width="100%" cellpadding="0" cellspacing="8">
                    <tr>
                        <td style="background: #2E5FA3; color: white; padding: 16px;
                                   border-radius: 6px; text-align: center; width: 30%;">
                            <div style="font-size: 28px; font-weight: bold;">
                                {hours_saved:.1f}h
                            </div>
                            <div style="font-size: 12px;">Hours Saved This Week</div>
                        </td>
                        <td width="4%"></td>
                        <td style="background: #1A7A6E; color: white; padding: 16px;
                                   border-radius: 6px; text-align: center; width: 30%;">
                            <div style="font-size: 28px; font-weight: bold;">
                                {cumulative_hours:.1f}h
                            </div>
                            <div style="font-size: 12px;">Total Hours Saved</div>
                        </td>
                        <td width="4%"></td>
                        <td style="background: #166534; color: white; padding: 16px;
                                   border-radius: 6px; text-align: center; width: 30%;">
                            <div style="font-size: 28px; font-weight: bold;">
                                ${value:,.0f}
                            </div>
                            <div style="font-size: 12px;">Est. Value (@$50/hr)</div>
                        </td>
                    </tr>
                </table>

                <h3 style="color: #1B2A4A; margin-top: 24px;">Agent Activity</h3>
                <table width="100%" cellpadding="8" cellspacing="0"
                       style="border-collapse: collapse;">
                    <tr style="background: #1B2A4A; color: white;">
                        <th style="padding: 10px; text-align: left;">Agent</th>
                        <th style="padding: 10px; text-align: left;">Status</th>
                        <th style="padding: 10px; text-align: left;">Time Saved</th>
                    </tr>
                    <tr style="border-bottom: 1px solid #e2e8f0;">
                        <td style="padding: 10px;">Ticket Auto-Classifier</td>
                        <td style="padding: 10px; color: #166534;">&#x2705; Live</td>
                        <td style="padding: 10px;">4 min per ticket</td>
                    </tr>
                    <tr style="border-bottom: 1px solid #e2e8f0; background: #f8fafc;">
                        <td style="padding: 10px;">Log Harvester</td>
                        <td style="padding: 10px; color: #166534;">&#x2705; Live</td>
                        <td style="padding: 10px;">18 min per P1/P2</td>
                    </tr>
                </table>

                <h3 style="color: #1B2A4A; margin-top: 24px;">What Is Next</h3>
                <ul style="color: #374151; line-height: 1.8;">
                    <li>Agent #3: SQL Query Bot — analysts ask data questions
                        in plain English</li>
                    <li>Dynatrace integration — real monitoring data
                        replaces synthetic logs</li>
                    <li>Self-Healing Agent — auto-fixes known failure patterns</li>
                </ul>

                <div style="background: #D6E4F7; border-left: 4px solid #2E5FA3;
                            padding: 12px 16px; margin-top: 20px; border-radius: 4px;">
                    <strong>Total agent runs this week: {total_runs}</strong><br>
                    All P1 tickets require human confirmation before any
                    auto-classification is applied.
                </div>

            </div>

            <div style="background: #e2e8f0; padding: 12px 20px;
                        border-radius: 0 0 8px 8px; font-size: 12px; color: #64748b;">
                This report was generated automatically every Monday at 7am
                by the AI Automation Platform.<br>
                Full report attached as markdown file.
            </div>

        </body>
        </html>
        """

        # Plain text fallback
        body_text = f"""
AI Automation Weekly Update — {date_str}

HEADLINE METRICS:
  Hours saved this week:  {hours_saved:.1f}h
  Total hours saved:      {cumulative_hours:.1f}h
  Estimated value:        ${value:,.0f} (@$50/hr)
  Total agent runs:       {total_runs}

AGENTS LIVE:
  - Ticket Auto-Classifier: 4 min saved per ticket
  - Log Harvester: 18 min saved per P1/P2 incident

WHAT IS NEXT:
  - Agent #3: SQL Query Bot
  - Dynatrace integration
  - Self-Healing Agent

Full report attached.
        """

        return self.send(
            subject=subject,
            body_html=body_html,
            body_text=body_text,
            attachment_path=attachment_path
        )

    def send_test_email(self) -> bool:
        """
        Send a test email to verify configuration works.
        Run this before relying on automated delivery.
        """
        return self.send(
            subject="AI Automation — Email Test",
            body_html="""
            <html><body style="font-family: Arial, sans-serif;">
            <h2 style="color: #1B2A4A;">Email Configuration Test</h2>
            <p>This is a test email from your AI Automation Platform.</p>
            <p style="color: #166534; font-weight: bold;">
                If you received this, email delivery is working correctly.
            </p>
            <p>Weekly reports will be delivered every Monday at 7am.</p>
            </body></html>
            """,
            body_text=(
                "AI Automation Email Test\n\n"
                "If you received this, email delivery is working correctly.\n"
                "Weekly reports will be delivered every Monday at 7am."
            )
        )