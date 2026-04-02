"""
Async HTTP client for ECHA CHEM API.

Provides shared infrastructure for all ECHA API calls:
- JSON API endpoints (substance info, CLP classification, dossier list)
- HTML page downloads (dossier index, document pages)
- Automatic retry with exponential backoff
- Rate limiting
"""

import asyncio
import logging
from typing import Optional, Dict, Any

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://chem.echa.europa.eu"
DEFAULT_TIMEOUT = 60.0
MAX_RETRIES = 3
REQUEST_DELAY = 0.3  # seconds between requests
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


class ECHAClient:
    """Async HTTP client for ECHA CHEM API with retry and rate limiting."""

    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None
        self._last_request_time: float = 0

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            # Limit connection pool to avoid resource exhaustion
            limits = httpx.Limits(
                max_connections=10,
                max_keepalive_connections=5,
                keepalive_expiry=30.0,
            )
            self._client = httpx.AsyncClient(
                base_url=BASE_URL,
                headers={"User-Agent": USER_AGENT},
                timeout=DEFAULT_TIMEOUT,
                verify=False,  # Some ECHA endpoints have cert issues
                limits=limits,
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def _rate_limit(self):
        """Enforce minimum delay between requests."""
        now = asyncio.get_event_loop().time()
        elapsed = now - self._last_request_time
        if elapsed < REQUEST_DELAY:
            await asyncio.sleep(REQUEST_DELAY - elapsed)
        self._last_request_time = asyncio.get_event_loop().time()

    async def get_json(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        max_retries: int = MAX_RETRIES,
    ) -> Optional[Dict]:
        """GET request expecting JSON response. Returns None on failure."""
        client = await self._get_client()

        for attempt in range(max_retries):
            await self._rate_limit()
            try:
                response = await client.get(path, params=params)
                try:
                    if response.status_code == 200:
                        return response.json()
                    elif response.status_code == 404:
                        logger.warning("Resource not found: %s", path)
                        return None
                    else:
                        logger.warning(
                            "HTTP %d for %s (attempt %d/%d)",
                            response.status_code, path, attempt + 1, max_retries,
                        )
                finally:
                    await response.aclose()
            except (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError) as e:
                logger.warning(
                    "Request failed for %s (attempt %d/%d): %s",
                    path, attempt + 1, max_retries, e,
                )

            if attempt < max_retries - 1:
                await asyncio.sleep(1.0 * (attempt + 1))  # exponential backoff

        return None

    async def get_html(
        self,
        path: str,
        max_retries: int = MAX_RETRIES,
    ) -> Optional[str]:
        """GET request expecting HTML response. Returns None on failure."""
        client = await self._get_client()

        for attempt in range(max_retries):
            await self._rate_limit()
            try:
                response = await client.get(path)
                try:
                    if response.status_code == 200:
                        return response.text
                    elif response.status_code == 404:
                        logger.warning("Page not found: %s", path)
                        return None
                    else:
                        logger.warning(
                            "HTTP %d for %s (attempt %d/%d)",
                            response.status_code, path, attempt + 1, max_retries,
                        )
                finally:
                    await response.aclose()
            except (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError) as e:
                logger.warning(
                    "Request failed for %s (attempt %d/%d): %s",
                    path, attempt + 1, max_retries, e,
                )

            if attempt < max_retries - 1:
                await asyncio.sleep(1.0 * (attempt + 1))

        return None

    # ─── Substance API ────────────────────────────────────────────

    async def get_substance_info(self, substance_index: str) -> Optional[Dict]:
        """GET /api-substance/v1/substance/{substanceIndex}"""
        return await self.get_json(f"/api-substance/v1/substance/{substance_index}")

    # ─── Dossier API ──────────────────────────────────────────────

    async def get_dossier_list(
        self, substance_index: str, status: str = "Active"
    ) -> Optional[Dict]:
        """GET /api-dossier-list/v1/dossier"""
        return await self.get_json(
            "/api-dossier-list/v1/dossier",
            params={
                "rmlId": substance_index,
                "legislation": "REACH",
                "registrationStatuses": status,
                "pageIndex": 1,
                "pageSize": 100,
            },
        )

    # ─── CLP Industry (Notification) API ──────────────────────────

    async def get_clp_classifications(self, substance_index: str) -> Optional[Dict]:
        return await self.get_json(
            f"/api-cnl-inventory/industry/{substance_index}/classifications"
        )

    async def get_clp_classification_detail(self, cid: str) -> Optional[Dict]:
        return await self.get_json(f"/api-cnl-inventory/industry/classification/{cid}")

    async def get_clp_labelling(self, cid: str) -> Optional[Dict]:
        return await self.get_json(f"/api-cnl-inventory/industry/labelling/{cid}")

    async def get_clp_pictograms(self, cid: str) -> Optional[Dict]:
        return await self.get_json(f"/api-cnl-inventory/industry/pictograms/{cid}")

    async def get_clp_scl(self, cid: str) -> Optional[Dict]:
        return await self.get_json(
            f"/api-cnl-inventory/industry/specific-concentration-limits/{cid}"
        )

    async def get_clp_m_factors(self, cid: str) -> Optional[Dict]:
        return await self.get_json(f"/api-cnl-inventory/industry/m-factors/{cid}")

    # ─── Harmonised Classification API ────────────────────────────

    async def get_harmonised_classifications(self, substance_index: str) -> Optional[Dict]:
        return await self.get_json(
            f"/api-cnl-inventory/harmonized/{substance_index}/classifications"
        )

    async def get_harmonised_classification_detail(self, cid: str) -> Optional[Dict]:
        return await self.get_json(
            f"/api-cnl-inventory/harmonized/classification/{cid}"
        )

    async def get_harmonised_labelling(self, cid: str) -> Optional[Dict]:
        return await self.get_json(f"/api-cnl-inventory/harmonized/labelling/{cid}")

    async def get_harmonised_pictograms(self, cid: str) -> Optional[Dict]:
        return await self.get_json(f"/api-cnl-inventory/harmonized/pictograms/{cid}")

    async def get_harmonised_scl(self, cid: str) -> Optional[Dict]:
        return await self.get_json(
            f"/api-cnl-inventory/harmonized/specific-concentration-limits/{cid}"
        )

    async def get_harmonised_m_factors(self, cid: str) -> Optional[Dict]:
        return await self.get_json(f"/api-cnl-inventory/harmonized/m-factors/{cid}")

    async def get_harmonised_ate(self, cid: str) -> Optional[Dict]:
        return await self.get_json(
            f"/api-cnl-inventory/harmonized/acute-toxicity-estimates/{cid}"
        )

    async def get_harmonised_notes(self, cid: str) -> Optional[Dict]:
        return await self.get_json(f"/api-cnl-inventory/harmonized/notes/{cid}")

    # ─── HTML Pages ───────────────────────────────────────────────

    async def get_dossier_index(self, asset_id: str) -> Optional[str]:
        """Download dossier index.html."""
        return await self.get_html(f"/html-pages-prod/{asset_id}/index.html")

    async def get_document_html(self, asset_id: str, doc_id: str) -> Optional[str]:
        """Download a specific document page."""
        return await self.get_html(
            f"/html-pages-prod/{asset_id}/documents/{doc_id}.html"
        )


# Module-level singleton
_client: Optional[ECHAClient] = None


def get_client() -> ECHAClient:
    """Get or create the shared ECHA client singleton."""
    global _client
    if _client is None:
        _client = ECHAClient()
    return _client
