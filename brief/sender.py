"""LunaClaw Brief — Delivery (Email + Webhook)

Supports two delivery channels:
  - EmailSender:   SMTP-based email with HTML + PDF attachment
  - WebhookSender: HTTP POST to arbitrary webhook URLs (Slack, DingTalk, etc.)
"""

import json
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email.header import Header
from email import encoders
from pathlib import Path

import requests


class EmailSender:
    """SMTP email sender supporting HTML content and PDF attachments."""

    def __init__(self, email_config: dict):
        self.config = email_config

    def send(
        self,
        subject: str,
        html_content: str,
        text_content: str = "",
        to_email: str | None = None,
        attachment_path: str | None = None,
    ) -> bool:
        """Send an email with optional PDF attachment. Returns True on success."""
        recipients = []
        if to_email:
            recipients = [to_email]
        else:
            recipients = self.config.get("to_emails", [])
        if not recipients:
            print("[Email] No recipients configured")
            return False

        try:
            msg = MIMEMultipart("mixed")
            msg["Subject"] = Header(subject, "utf-8")
            sender_email = self.config["sender_email"]
            msg["From"] = f"LunaClaw Brief <{sender_email}>"
            msg["To"] = ", ".join(recipients)

            alt = MIMEMultipart("alternative")
            if text_content:
                alt.attach(MIMEText(text_content, "plain", "utf-8"))
            alt.attach(MIMEText(html_content, "html", "utf-8"))
            msg.attach(alt)

            if attachment_path and Path(attachment_path).exists():
                try:
                    with open(attachment_path, "rb") as f:
                        part = MIMEBase("application", "pdf")
                        part.set_payload(f.read())
                    encoders.encode_base64(part)
                    filename = os.path.basename(attachment_path)
                    part.add_header("Content-Disposition", f'attachment; filename="{filename}"')
                    msg.attach(part)
                except Exception as e:
                    print(f"[Email] Attachment failed: {e}")

            smtp_host = self.config["smtp_host"]
            smtp_port = self.config.get("smtp_port", 465)
            password = self.config.get("password") or os.getenv("EMAIL_PASSWORD", "")

            with smtplib.SMTP_SSL(smtp_host, smtp_port) as server:
                server.login(sender_email, password)
                server.sendmail(sender_email, recipients, msg.as_string())

            print(f"✅ Email sent → {', '.join(recipients)}")
            return True

        except Exception as e:
            print(f"❌ Email failed: {type(e).__name__}: {e}")
            return False


class WebhookSender:
    """HTTP webhook delivery for Slack, DingTalk, Feishu, custom endpoints."""

    def __init__(self, webhook_config: dict):
        self.url = webhook_config.get("url", "")
        self.webhook_type = webhook_config.get("type", "generic")
        self.timeout = webhook_config.get("timeout", 30)

    def send(self, subject: str, text_content: str, html_path: str = "") -> bool:
        """POST report summary to the webhook endpoint."""
        if not self.url:
            print("[Webhook] No URL configured")
            return False

        try:
            payload = self._build_payload(subject, text_content, html_path)
            resp = requests.post(
                self.url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=self.timeout,
            )
            if resp.status_code in (200, 201, 204):
                print(f"✅ Webhook delivered → {self.webhook_type}")
                return True
            print(f"❌ Webhook failed: {resp.status_code} - {resp.text[:100]}")
            return False
        except Exception as e:
            print(f"❌ Webhook error: {type(e).__name__}: {e}")
            return False

    def _build_payload(self, subject: str, text_content: str, html_path: str) -> dict:
        truncated = text_content[:2000]

        if self.webhook_type == "slack":
            return {
                "text": f"*{subject}*\n\n{truncated}",
            }
        elif self.webhook_type == "dingtalk":
            return {
                "msgtype": "markdown",
                "markdown": {
                    "title": subject,
                    "text": f"## {subject}\n\n{truncated}",
                },
            }
        elif self.webhook_type == "feishu":
            return {
                "msg_type": "interactive",
                "card": {
                    "header": {"title": {"content": subject, "tag": "plain_text"}},
                    "elements": [{"tag": "div", "text": {"content": truncated, "tag": "plain_text"}}],
                },
            }
        else:
            return {
                "subject": subject,
                "content": truncated,
                "html_path": html_path,
            }
