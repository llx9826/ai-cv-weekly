"""LunaClaw Brief — Email sending.

LunaClaw Brief — 邮件发送
"""

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email.header import Header
from email import encoders
from pathlib import Path


class EmailSender:
    """SMTP 邮件发送（支持 HTML + PDF 附件）"""

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
        recipients = []
        if to_email:
            recipients = [to_email]
        else:
            recipients = self.config.get("to_emails", [])
        if not recipients:
            print("[Email] 未配置收件人")
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
                    print(f"⚠️ 附件添加失败：{e}")

            smtp_host = self.config["smtp_host"]
            smtp_port = self.config.get("smtp_port", 465)
            password = self.config.get("password") or os.getenv("EMAIL_PASSWORD", "")

            with smtplib.SMTP_SSL(smtp_host, smtp_port) as server:
                server.login(sender_email, password)
                server.sendmail(sender_email, recipients, msg.as_string())

            print(f"✅ 邮件已发送 → {', '.join(recipients)}")
            return True

        except Exception as e:
            print(f"❌ 邮件发送失败：{type(e).__name__}: {e}")
            return False
