"""Birth date setting service for Grok accounts."""

from __future__ import annotations

import datetime
import random
from typing import Any, Dict, Optional

from curl_cffi import requests

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


def _generate_random_birthdate() -> str:
    """Generate a random birth date (20-40 years old)."""
    today = datetime.date.today()
    age = random.randint(20, 40)
    birth_year = today.year - age
    birth_month = random.randint(1, 12)
    birth_day = random.randint(1, 28)  # Avoid month day count issues
    # Randomize time component to avoid fingerprinting
    hour = random.randint(0, 23)
    minute = random.randint(0, 59)
    second = random.randint(0, 59)
    ms = random.randint(0, 999)
    return f"{birth_year}-{birth_month:02d}-{birth_day:02d}T{hour:02d}:{minute:02d}:{second:02d}.{ms:03d}Z"


class BirthDateService:
    """Set birth date for Grok accounts (thread-safe, no global state)."""

    def __init__(self, cf_clearance: str = ""):
        self.cf_clearance = (cf_clearance or "").strip()

    def set_birth_date(
        self,
        sso: str,
        sso_rw: str,
        impersonate: str,
        user_agent: Optional[str] = None,
        cf_clearance: Optional[str] = None,
        timeout: int = 15,
        birth_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Set birth date for the account (required for NSFW).
        Returns: {
            ok: bool,
            status_code: int | None,
            error: str | None
        }
        """
        if not sso:
            return {
                "ok": False,
                "status_code": None,
                "error": "Missing sso",
            }
        if not sso_rw:
            return {
                "ok": False,
                "status_code": None,
                "error": "Missing sso-rw",
            }

        url = "https://grok.com/rest/auth/set-birth-date"

        cookies = {
            "sso": sso,
            "sso-rw": sso_rw,
        }
        clearance = (cf_clearance if cf_clearance is not None else self.cf_clearance).strip()
        if clearance:
            cookies["cf_clearance"] = clearance

        headers = {
            "content-type": "application/json",
            "origin": "https://grok.com",
            "referer": "https://grok.com/",
            "user-agent": user_agent or DEFAULT_USER_AGENT,
        }

        payload = {"birthDate": birth_date or _generate_random_birthdate()}

        try:
            response = requests.post(
                url,
                headers=headers,
                cookies=cookies,
                json=payload,
                impersonate=impersonate or "chrome120",
                timeout=timeout,
            )

            error = None
            ok = response.status_code == 200
            if response.status_code == 403:
                error = "403 Forbidden"
            elif response.status_code != 200:
                error = f"HTTP {response.status_code}"

            return {
                "ok": ok,
                "status_code": response.status_code,
                "error": error,
            }
        except Exception as e:
            return {
                "ok": False,
                "status_code": None,
                "error": str(e),
            }
