import logging
from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

TZ = ZoneInfo("America/Lima")

# Mapping Spanish day abbreviations → RRULE BYDAY codes
_DIA_MAP = {
    "lun": "MO", "mar": "TU", "mie": "WE", "mié": "WE",
    "jue": "TH", "vie": "FR", "sab": "SA", "sáb": "SA", "dom": "SU",
}


class GoogleService:
    def __init__(self, google_email_repo):
        self.email_repo = google_email_repo

    def is_quiet_hours(self) -> bool:
        """True entre 23:00 y 06:00 Lima."""
        hour = datetime.now(TZ).hour
        return hour >= 23 or hour < 6

    def classify_email(self, from_addr: str, subject: str, snippet: str) -> str:
        """Retorna: banco|migraciones|spam|otro."""
        from_l = from_addr.lower()
        subj_l = subject.lower()
        snip_l = (snippet or "").lower()
        text = f"{from_l} {subj_l} {snip_l}"

        # Bancos peruanos
        bank_domains = [
            "bbva", "bcp", "interbank", "scotiabank",
            "bn.com.pe", "cmac", "mibanco",
        ]
        if any(b in from_l for b in bank_domains):
            return "banco"

        # Migraciones
        migration_kw = [
            "migracion", "extranjeria", "carnet", "ptp",
            "superintendencia", "interpol", "permiso temporal",
        ]
        if any(k in text for k in migration_kw):
            return "migraciones"

        # Spam patterns
        spam_from = [
            "aliexpress", "temu", "shein", "wish.com",
            "noreply@statuspage", "marketing@", "promo@",
            "newsletter@", "offers@", "deals@",
        ]
        spam_kw = [
            "unsubscribe", "liquidacion", "oferta",
            "descuento exclusivo", "limited time", "act now",
            "click here", "ganaste",
        ]
        if any(s in from_l for s in spam_from) or any(k in text for k in spam_kw):
            return "spam"

        return "otro"

    async def check_inbox(self) -> dict:
        """Fetch unprocessed emails, classify, act on spam."""
        try:
            from plugins.google_services import get_credentials, _get_gmail_service
        except ImportError:
            logger.error("google_services plugin not available")
            return {"importantes": [], "spam_count": 0}

        service = _get_gmail_service()
        if not service:
            logger.debug("Gmail not authenticated, skipping check")
            return {"importantes": [], "spam_count": 0}

        try:
            # Fetch recent inbox messages (last 2 hours)
            two_hours_ago = datetime.now(TZ) - timedelta(hours=2)
            after_ts = int(two_hours_ago.timestamp())
            results = service.users().messages().list(
                userId="me", maxResults=20,
                q=f"in:inbox after:{after_ts}",
            ).execute()
            messages = results.get("messages", [])

            importantes = []
            spam_count = 0

            for msg in messages:
                msg_id = msg["id"]

                # Skip already processed
                if await self.email_repo.exists(msg_id):
                    continue

                # Get metadata
                m = service.users().messages().get(
                    userId="me", id=msg_id, format="metadata",
                    metadataHeaders=["Subject", "From", "Date"]
                ).execute()
                headers = {h["name"]: h["value"] for h in m["payload"]["headers"]}
                from_addr = headers.get("From", "")
                subject = headers.get("Subject", "")
                snippet = m.get("snippet", "")
                date_str = headers.get("Date", datetime.now(TZ).isoformat())
                thread_id = m.get("threadId", "")

                # Classify
                clasificacion = self.classify_email(from_addr, subject, snippet)
                accion = None

                if clasificacion == "spam":
                    # Move to spam
                    try:
                        service.users().messages().modify(
                            userId="me", id=msg_id,
                            body={"addLabelIds": ["SPAM"], "removeLabelIds": ["INBOX"]}
                        ).execute()
                        accion = "moved_to_spam"
                        spam_count += 1
                    except Exception as e:
                        logger.warning(f"Failed to spam {msg_id}: {e}")
                        accion = f"spam_failed: {e}"

                elif clasificacion in ("banco", "migraciones"):
                    importantes.append({
                        "from": from_addr,
                        "subject": subject,
                        "clasificacion": clasificacion,
                    })

                # Save to DB
                await self.email_repo.save(
                    message_id=msg_id,
                    thread_id=thread_id,
                    from_addr=from_addr,
                    subject=subject,
                    snippet=snippet,
                    date_received=date_str,
                    clasificacion=clasificacion,
                    accion=accion,
                )

            return {"importantes": importantes, "spam_count": spam_count}

        except Exception as e:
            logger.error(f"check_inbox error: {e}")
            return {"importantes": [], "spam_count": 0}

    # ---- Google Calendar sync ----

    def _build_recurrence(self, dias: str) -> list[str]:
        """Convert dias string to Google Calendar RRULE list."""
        dias = dias.strip().lower()
        if dias in ("hoy", "una_vez", ""):
            return []  # Single event, no recurrence
        if dias == "todos":
            return ["RRULE:FREQ=DAILY"]
        # Check if it's day-of-month numbers like "1,15"
        parts = [p.strip() for p in dias.split(",")]
        if all(p.isdigit() for p in parts):
            days_str = ",".join(parts)
            return [f"RRULE:FREQ=MONTHLY;BYMONTHDAY={days_str}"]
        # Otherwise treat as weekday abbreviations like "lun,mie,vie"
        byday = []
        for p in parts:
            code = _DIA_MAP.get(p)
            if code:
                byday.append(code)
        if byday:
            return [f"RRULE:FREQ=WEEKLY;BYDAY={','.join(byday)}"]
        return []

    def create_calendar_event(self, mensaje: str, hora: str, dias: str) -> str | None:
        """Create a Google Calendar event for a recordatorio. Returns event_id or None."""
        try:
            from plugins.google_services import _get_calendar_service
        except ImportError:
            logger.warning("google_services plugin not available for calendar")
            return None

        service = _get_calendar_service()
        if not service:
            logger.debug("Calendar not authenticated, skipping event creation")
            return None

        try:
            # Parse hora "HH:MM"
            h, m = hora.split(":")
            today = date.today()
            start_dt = datetime(today.year, today.month, today.day,
                                int(h), int(m), tzinfo=TZ)
            end_dt = start_dt + timedelta(minutes=15)

            event = {
                "summary": f"🔔 {mensaje}",
                "description": "Recordatorio de FinBot",
                "start": {"dateTime": start_dt.isoformat(), "timeZone": "America/Lima"},
                "end": {"dateTime": end_dt.isoformat(), "timeZone": "America/Lima"},
            }

            recurrence = self._build_recurrence(dias)
            if recurrence:
                event["recurrence"] = recurrence

            created = service.events().insert(calendarId="primary", body=event).execute()
            event_id = created.get("id")
            logger.info(f"Calendar event created: {event_id} for '{mensaje}'")
            return event_id
        except Exception as e:
            logger.error(f"Error creating calendar event: {e}")
            return None

    def delete_calendar_event(self, event_id: str) -> bool:
        """Delete a Google Calendar event. Returns True on success."""
        try:
            from plugins.google_services import _get_calendar_service
        except ImportError:
            return False

        service = _get_calendar_service()
        if not service:
            return False

        try:
            service.events().delete(calendarId="primary", eventId=event_id).execute()
            logger.info(f"Calendar event deleted: {event_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting calendar event {event_id}: {e}")
            return False

    def list_upcoming_events(self, max_results: int = 20) -> list[dict]:
        """List upcoming Calendar events for importing as recordatorios."""
        try:
            from plugins.google_services import _get_calendar_service
        except ImportError:
            return []

        service = _get_calendar_service()
        if not service:
            return []

        try:
            from datetime import timezone
            now = datetime.now(timezone.utc).isoformat()
            result = service.events().list(
                calendarId="primary", timeMin=now, maxResults=max_results,
                singleEvents=False, orderBy="updated",
            ).execute()
            events = result.get("items", [])
            output = []
            for ev in events:
                start = ev.get("start", {})
                dt_str = start.get("dateTime", start.get("date", ""))
                output.append({
                    "event_id": ev.get("id"),
                    "summary": ev.get("summary", ""),
                    "start": dt_str,
                    "recurrence": ev.get("recurrence", []),
                })
            return output
        except Exception as e:
            logger.error(f"Error listing calendar events: {e}")
            return []

    async def get_morning_summary(self) -> str:
        """Resumen de emails desde las 23:00 del dia anterior."""
        yesterday = datetime.now(TZ) - timedelta(days=1)
        since = yesterday.replace(hour=23, minute=0, second=0).isoformat()

        emails = await self.email_repo.get_since(since)
        if not emails:
            return ""

        # Group by classification
        groups: dict[str, list] = {}
        for e in emails:
            cls = e["clasificacion"]
            groups.setdefault(cls, []).append(e)

        lines = ["Resumen de correos de la noche:"]

        if "banco" in groups:
            lines.append(f"\nBancos ({len(groups['banco'])}):")
            for e in groups["banco"][:5]:
                lines.append(f"  - {e['from_addr']}: {e['subject']}")

        if "migraciones" in groups:
            lines.append(f"\nMigraciones ({len(groups['migraciones'])}):")
            for e in groups["migraciones"][:5]:
                lines.append(f"  - {e['subject']}")

        spam = groups.get("spam", [])
        if spam:
            lines.append(f"\nSpam movido: {len(spam)}")

        otros = groups.get("otro", [])
        if otros:
            lines.append(f"\nOtros ({len(otros)}):")
            for e in otros[:5]:
                lines.append(f"  - {e['from_addr']}: {e['subject']}")

        return "\n".join(lines)
