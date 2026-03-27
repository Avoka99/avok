from html import unescape
from typing import Dict, List, Optional
from urllib.parse import urlparse
import re

import httpx


class ProductImportService:
    """Best-effort metadata extraction from third-party product pages."""

    META_PATTERNS = {
        "title": [
            r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+name=["\']twitter:title["\'][^>]+content=["\']([^"\']+)["\']',
            r"<title>(.*?)</title>",
        ],
        "description": [
            r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']',
        ],
        "image": [
            r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
            r'<img[^>]+src=["\']([^"\']+)["\']',
        ],
        "video": [
            r'<meta[^>]+property=["\']og:video["\'][^>]+content=["\']([^"\']+)["\']',
            r'<video[^>]+src=["\']([^"\']+)["\']',
        ],
    }

    async def extract(self, product_url: str) -> Dict:
        async with httpx.AsyncClient(follow_redirects=True, timeout=15.0) as client:
            response = await client.get(product_url, headers={"User-Agent": "AvokBot/1.0"})
            response.raise_for_status()

        html = response.text or ""
        parsed = urlparse(str(response.url))
        hostname = parsed.netloc.replace("www.", "")

        images = self._extract_many("image", html)
        videos = self._extract_many("video", html)

        return {
            "source_site_name": hostname or "Unknown site",
            "product_name": self._extract_one("title", html) or hostname,
            "product_description": self._extract_one("description", html),
            "product_url": str(response.url),
            "media": {
                "images": images[:6],
                "videos": videos[:3],
            },
            "snapshot": {
                "title": self._extract_one("title", html),
                "description": self._extract_one("description", html),
                "hostname": hostname,
            },
        }

    def _extract_one(self, key: str, html: str) -> Optional[str]:
        matches = self._extract_many(key, html)
        return matches[0] if matches else None

    def _extract_many(self, key: str, html: str) -> List[str]:
        values: List[str] = []
        for pattern in self.META_PATTERNS.get(key, []):
            matches = re.findall(pattern, html, flags=re.IGNORECASE | re.DOTALL)
            for match in matches:
                value = unescape(str(match)).strip()
                if value and value not in values:
                    values.append(value)
        return values
