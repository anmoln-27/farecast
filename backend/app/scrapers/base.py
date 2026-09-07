"""
backend/app/scrapers/base.py
----------------------------
Abstract Base Scraper for Indian Domestic Airlines & Aggregators.
Adheres to ethical web scraping best practices:
- robots.txt parsing & path compliance checking
- Desktop browser User-Agent & header rotation
- Configurable polite crawl delays & exponential backoff
- Standardised FareRecord schema transformation
"""
from __future__ import annotations

import abc
import logging
import random
import time
from datetime import date, datetime
from typing import Optional
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests

from backend.app.services.schema import FareRecord, normalise_city

logger = logging.getLogger(__name__)

# Modern desktop User-Agent pool for realistic HTTP requests
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_3_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
]


class BaseScraper(abc.ABC):
    """
    Abstract base class for airline scrapers.
    """

    def __init__(
        self,
        airline_code: str,
        airline_name: str,
        base_url: str,
        delay_seconds: float = 1.0,
        verify_robots: bool = True,
    ):
        self.airline_code = airline_code
        self.airline_name = airline_name
        self.base_url = base_url.rstrip("/")
        self.delay_seconds = delay_seconds
        self.verify_robots = verify_robots
        self._robot_parser: Optional[RobotFileParser] = None
        self._session = requests.Session()
        self._init_robots()

    def _init_robots(self) -> None:
        """Fetch and parse robots.txt for the domain with strict timeout."""
        if not self.verify_robots or not self.base_url:
            return
        try:
            parsed = urlparse(self.base_url)
            robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
            resp = self._session.get(robots_url, headers=self.get_headers(), timeout=3.0)
            if resp.status_code == 200:
                rp = RobotFileParser()
                rp.parse(resp.text.splitlines())
                self._robot_parser = rp
                logger.info("Loaded robots.txt for %s from %s", self.airline_name, robots_url)
            else:
                self._robot_parser = None
        except Exception as exc:
            logger.debug("Could not read robots.txt for %s: %s", self.airline_name, exc)
            self._robot_parser = None

    def is_allowed_by_robots(self, path: str, user_agent: str = "*") -> bool:
        """Check whether scraping path is permitted by robots.txt."""
        if not self.verify_robots or self._robot_parser is None:
            return True
        try:
            return self._robot_parser.can_fetch(user_agent, path)
        except Exception:
            return True

    def get_headers(self) -> dict[str, str]:
        """Generate browser-like headers with rotated User-Agent."""
        return {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,hi;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
        }

    def polite_sleep(self) -> None:
        """Sleep with random jitter to avoid aggressive burst request patterns."""
        jitter = random.uniform(0.1, 0.5)
        time.sleep(self.delay_seconds + jitter)

    def request_with_retry(
        self,
        url: str,
        method: str = "GET",
        max_retries: int = 3,
        **kwargs,
    ) -> Optional[requests.Response]:
        """
        Execute an HTTP request with exponential backoff and polite delay.
        """
        self.polite_sleep()
        headers = self.get_headers()
        if "headers" in kwargs:
            headers.update(kwargs.pop("headers"))

        backoff = 1.0
        for attempt in range(1, max_retries + 1):
            try:
                resp = self._session.request(method, url, headers=headers, timeout=10, **kwargs)
                if resp.status_code == 200:
                    return resp
                if resp.status_code in (429, 503):
                    logger.warning(
                        "[%s] Rate-limited or unavailable (%d) on %s. Retrying in %.1fs...",
                        self.airline_code,
                        resp.status_code,
                        url,
                        backoff,
                    )
                    time.sleep(backoff)
                    backoff *= 2
                    continue
                logger.warning("[%s] HTTP %d for %s", self.airline_code, resp.status_code, url)
                return resp
            except requests.RequestException as exc:
                logger.warning(
                    "[%s] Request failed (attempt %d/%d): %s",
                    self.airline_code,
                    attempt,
                    max_retries,
                    exc,
                )
                time.sleep(backoff)
                backoff *= 2
        return None

    def check_compliance_status(self, test_path: str = "/") -> dict:
        """
        Ethically audits robots.txt permissions and technical accessibility for this source.
        Detects anti-bot protections (Akamai, Cloudflare, etc.) without attempting bypass.
        Returns full transparency diagnostic.
        """
        parsed = urlparse(self.base_url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

        robots_allowed = self.is_allowed_by_robots(test_path)
        if not robots_allowed:
            return {
                "airline_code": self.airline_code,
                "airline_name": self.airline_name,
                "base_url": self.base_url,
                "robots_url": robots_url,
                "robots_allowed": False,
                "http_status": None,
                "access_state": "BLOCKED_BY_ROBOTS_TXT",
                "anti_bot_detected": None,
                "details": f"Path '{test_path}' explicitly disallowed by robots.txt.",
                "legal_compliance_rule": "Respects robots.txt directive strictly per SIH ethical scraping mandate.",
            }

        # Polite probe to check accessibility
        probe_url = f"{self.base_url}{test_path}"
        headers = {
            "User-Agent": "FARECAST-Research-Bot/1.0 (+https://farecast.gov.in/bot; research@farecast.gov.in)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

        try:
            resp = self._session.get(probe_url, headers=headers, timeout=3.5, allow_redirects=True)
            status = resp.status_code

            # Check for anti-bot signatures
            resp_headers_str = str(resp.headers).lower()
            text_snippet = resp.text[:2000].lower() if resp.text else ""

            anti_bot = None
            if "cf-ray" in resp_headers_str or "cloudflare" in resp_headers_str or "cf-chl-bypass" in text_snippet:
                anti_bot = "Cloudflare WAF / Turnstile"
            elif "akamai" in resp_headers_str or "akamai" in text_snippet:
                anti_bot = "Akamai Bot Manager"
            elif "datadome" in resp_headers_str or "datadome" in text_snippet:
                anti_bot = "DataDome Anti-Bot"
            elif "perimeterx" in resp_headers_str or "_px3" in text_snippet:
                anti_bot = "PerimeterX / HUMAN"

            if status == 200:
                if anti_bot and ("challenge" in text_snippet or "captcha" in text_snippet):
                    access_state = "RESTRICTED_BY_WAF_CHALLENGE"
                else:
                    access_state = "ACCESSIBLE_PERMITTED"
            elif status == 403:
                access_state = f"RESTRICTED_BY_WAF ({anti_bot})" if anti_bot else "RESTRICTED_BY_HTTP_403"
            elif status == 429:
                access_state = "RATE_LIMITED_HTTP_429"
            else:
                access_state = f"HTTP_{status}"

            return {
                "airline_code": self.airline_code,
                "airline_name": self.airline_name,
                "base_url": self.base_url,
                "robots_url": robots_url,
                "robots_allowed": True,
                "http_status": status,
                "access_state": access_state,
                "anti_bot_detected": anti_bot,
                "details": f"Probe to {probe_url} responded HTTP {status}.",
                "legal_compliance_rule": "Strict SIH ethical scraping mandate: anti-bot protections are not bypassed.",
            }
        except Exception as exc:
            return {
                "airline_code": self.airline_code,
                "airline_name": self.airline_name,
                "base_url": self.base_url,
                "robots_url": robots_url,
                "robots_allowed": robots_allowed,
                "http_status": None,
                "access_state": "UNREACHABLE",
                "anti_bot_detected": None,
                "details": f"Connection error: {type(exc).__name__}",
                "legal_compliance_rule": "Strict SIH ethical scraping mandate: connection failed; zero live data fabricated.",
            }

    @abc.abstractmethod
    def search_fares(
        self,
        origin: str,
        destination: str,
        travel_date: date,
        advance_window: str,
        simulate: bool = True,
    ) -> list[FareRecord]:
        """
        Search and extract flight fares for a given route and date.
        """
        pass
