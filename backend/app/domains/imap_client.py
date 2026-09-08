"""Minimal IMAP/SMTP client for the CRM inbox.

Uses stdlib imaplib/smtplib (no new dependency) run in a worker thread
via asyncio.to_thread so the event loop isn't blocked. Read-only listing
+ single-message fetch + send. Not a full sync engine — fetches on demand
against the live mailbox, which is fine for the inbox volumes here.
"""
from __future__ import annotations

import asyncio
import email
import email.utils
import imaplib
import smtplib
import ssl
from email.header import decode_header, make_header
from email.message import EmailMessage
from typing import Any


class MailConnectionError(RuntimeError):
    pass


def _decode(value: str | None) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return value


def _list_inbox_sync(host: str, port: int, address: str, password: str,
                     folder: str, limit: int) -> list[dict[str, Any]]:
    try:
        M = imaplib.IMAP4_SSL(host, port, timeout=25)
        M.login(address, password)
    except imaplib.IMAP4.error as e:
        raise MailConnectionError(f"IMAP login failed: {e}")
    except Exception as e:
        raise MailConnectionError(f"IMAP connect failed: {e}")
    try:
        typ, _ = M.select(folder, readonly=True)
        if typ != "OK":
            raise MailConnectionError(f"Cannot open folder {folder}")
        typ, data = M.search(None, "ALL")
        ids = data[0].split() if data and data[0] else []
        ids = ids[-limit:][::-1]  # newest first
        out: list[dict[str, Any]] = []
        for mid in ids:
            typ, msg_data = M.fetch(mid, "(FLAGS BODY.PEEK[HEADER.FIELDS (FROM TO SUBJECT DATE MESSAGE-ID)])")
            if typ != "OK" or not msg_data or not msg_data[0]:
                continue
            raw = msg_data[0][1]
            flags = imaplib.ParseFlags(msg_data[0][0]) if msg_data[0][0] else ()
            hdr = email.message_from_bytes(raw)
            out.append({
                "uid": mid.decode(),
                "from": _decode(hdr.get("From")),
                "to": _decode(hdr.get("To")),
                "subject": _decode(hdr.get("Subject")) or "(no subject)",
                "date": _decode(hdr.get("Date")),
                "message_id": hdr.get("Message-ID", ""),
                "seen": b"\\Seen" in flags,
            })
        return out
    finally:
        try:
            M.logout()
        except Exception:
            pass


def _get_message_sync(host: str, port: int, address: str, password: str,
                      folder: str, uid: str) -> dict[str, Any]:
    try:
        M = imaplib.IMAP4_SSL(host, port, timeout=25)
        M.login(address, password)
    except Exception as e:
        raise MailConnectionError(f"IMAP connect failed: {e}")
    try:
        M.select(folder)  # not readonly — fetching marks \Seen, which we want
        typ, msg_data = M.fetch(uid.encode(), "(RFC822)")
        if typ != "OK" or not msg_data or not msg_data[0]:
            raise MailConnectionError("Message not found")
        msg = email.message_from_bytes(msg_data[0][1])
        text, html = "", ""
        if msg.is_multipart():
            for part in msg.walk():
                ctype = part.get_content_type()
                disp = str(part.get("Content-Disposition") or "")
                if "attachment" in disp:
                    continue
                if ctype == "text/plain" and not text:
                    text = part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", "replace")
                elif ctype == "text/html" and not html:
                    html = part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", "replace")
        else:
            payload = msg.get_payload(decode=True)
            body = payload.decode(msg.get_content_charset() or "utf-8", "replace") if payload else ""
            if msg.get_content_type() == "text/html":
                html = body
            else:
                text = body
        return {
            "uid": uid,
            "from": _decode(msg.get("From")),
            "to": _decode(msg.get("To")),
            "subject": _decode(msg.get("Subject")) or "(no subject)",
            "date": _decode(msg.get("Date")),
            "message_id": msg.get("Message-ID", ""),
            "text": text,
            "html": html,
        }
    finally:
        try:
            M.logout()
        except Exception:
            pass


def _send_sync(host: str, port: int, address: str, password: str, *,
               to: str, subject: str, body: str,
               in_reply_to: str | None = None) -> dict[str, Any]:
    msg = EmailMessage()
    msg["From"] = address
    msg["To"] = to
    msg["Subject"] = subject
    msg["Date"] = email.utils.formatdate(localtime=True)
    msg["Message-ID"] = email.utils.make_msgid()
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
        msg["References"] = in_reply_to
    msg.set_content(body)
    try:
        S = smtplib.SMTP_SSL(host, port, timeout=25, context=ssl.create_default_context())
        S.login(address, password)
        S.send_message(msg)
        S.quit()
    except smtplib.SMTPAuthenticationError as e:
        raise MailConnectionError(
            "SMTP login rejected — the domain may still be finishing "
            f"outbound verification with Migadu. ({e.smtp_code})"
        )
    except Exception as e:
        raise MailConnectionError(f"Send failed: {e}")
    return {"sent": True, "message_id": msg["Message-ID"]}


# Async wrappers -----------------------------------------------------------

async def list_inbox(host, port, address, password, *, folder="INBOX", limit=30):
    return await asyncio.to_thread(_list_inbox_sync, host, port, address, password, folder, limit)


async def get_message(host, port, address, password, uid, *, folder="INBOX"):
    return await asyncio.to_thread(_get_message_sync, host, port, address, password, folder, uid)


async def send_message(host, port, address, password, *, to, subject, body, in_reply_to=None):
    return await asyncio.to_thread(
        _send_sync, host, port, address, password,
        to=to, subject=subject, body=body, in_reply_to=in_reply_to,
    )
