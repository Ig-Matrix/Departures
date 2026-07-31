"""Builds and sends the digest email over plain SMTP (free with any Gmail
account, using an App Password). No third-party service required."""

import os
import smtplib
from email.message import EmailMessage
from html import escape

AMBER, GREEN, INK, MUTE = "#B26A00", "#0F7A5A", "#12182A", "#6B7689"
LABEL = {"automation": "Automation", "frontend": "Frontend", "backend": "Backend"}


def build_html(alerts, new_count, total, health, board_url=None):
    groups = {"automation": [], "frontend": [], "backend": []}
    for j in alerts:
        groups[j["category"]].append(j)

    body = ""
    for key in ("automation", "frontend", "backend"):
        rows = groups[key]
        if not rows:
            continue
        body += (
            f'<tr><td style="padding:22px 0 8px;font:600 12px/1 -apple-system,sans-serif;'
            f'letter-spacing:.16em;text-transform:uppercase;color:{MUTE}">'
            f'{LABEL[key]} &middot; {len(rows)}</td></tr>'
        )
        for j in rows:
            is_visa = j["mode"] == "visa"
            col = AMBER if is_visa else GREEN
            sub = " &middot; " + ", ".join(j["subtracks"]) if j["subtracks"] else ""
            body += f'''<tr><td style="padding:10px 0;border-bottom:1px solid #E6E9EF">
  <a href="{escape(j["url"] or "")}" style="font:600 16px/1.35 -apple-system,sans-serif;
    color:{INK};text-decoration:none">{escape(j["title"] or "")}</a>
  <div style="font:400 13px/1.5 -apple-system,sans-serif;color:{MUTE};margin-top:3px">
    {escape(j["company"] or "")} &middot; {escape(j["loc"] or "")}{sub}
  </div>
  <div style="margin-top:7px">
    <span style="font:600 10px/1 ui-monospace,monospace;letter-spacing:.1em;color:{col};
      border:1px solid {col};border-radius:4px;padding:4px 7px">
      {"VISA" if is_visa else "REMOTE"} &middot; {j["score"]}
    </span>
    <span style="font:400 11px/1 ui-monospace,monospace;color:{MUTE};margin-left:8px">
      {escape("  ".join(j["reasons"]))} &middot; {escape(j["source"])}
    </span>
  </div>
</td></tr>'''

    health_line = "  ".join(f"{k}:{v}" for k, v in sorted(health.items())) or "no sources responded"
    board_link = (
        f'<a href="{escape(board_url)}" style="color:{MUTE}">Open the full board</a><br>'
        if board_url else ""
    )
    plural = "" if len(alerts) == 1 else "s"

    return f'''<!doctype html><html><body style="margin:0;background:#F7F8FA;padding:26px 14px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"
  style="max-width:600px;margin:0 auto;background:#fff;border:1px solid #E6E9EF;
  border-radius:12px;padding:26px">
  <tr><td style="font:600 20px/1 ui-monospace,monospace;letter-spacing:.3em;color:{INK}">
    DEPARTURES</td></tr>
  <tr><td style="font:400 14px/1.6 -apple-system,sans-serif;color:{MUTE};padding-top:8px">
    {len(alerts)} new role{plural} worth a look
    ({new_count} new overall, {total} on the board).
  </td></tr>
  {body}
  <tr><td style="padding-top:22px;font:400 11px/1.6 ui-monospace,monospace;color:#9AA3B2">
    {board_link}Board health: {escape(health_line)}<br>
    Score is eligibility from Nigeria, not job quality. Read the fine print
    before applying, and never pay a fee to apply.
  </td></tr>
</table></body></html>'''


def send(subject, html_body):
    """Reads SMTP settings from environment. Returns True if sent."""
    host = os.environ.get("SMTP_HOST")
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASS")
    to_addr = os.environ.get("MAIL_TO") or user
    port = int(os.environ.get("SMTP_PORT", "465"))

    if not (host and user and password and to_addr):
        print("  ! SMTP not configured, skipping email "
              "(set SMTP_HOST, SMTP_USER, SMTP_PASS, MAIL_TO)")
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = to_addr
    msg.set_content("This digest is HTML. Open it in an HTML-capable client.")
    msg.add_alternative(html_body, subtype="html")

    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=30) as s:
                s.login(user, password)
                s.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=30) as s:
                s.starttls()
                s.login(user, password)
                s.send_message(msg)
        print(f"  > digest sent to {to_addr}")
        return True
    except Exception as e:
        print(f"  ! email failed: {e}")
        return False
