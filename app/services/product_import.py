import ipaddress
import socket
from html import unescape
from typing import Dict, List, Optional
from urllib.parse import urlparse
import re
import logging

import httpx

logger = logging.getLogger(__name__)


class ProductImportService:
    """Best-effort metadata extraction from third-party product pages with security and performance guardrails."""

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

    async def extract(self, product_url: str) -> Optional[Dict]:
        """Extract metadata if the URL is safe and reachable."""
        if not self._is_safe_url(product_url):
            logger.warning(f"Blocked unsafe or invalid product URL: {product_url}")
            return None

        try:
            async with httpx.AsyncClient(
                follow_redirects=True, 
                timeout=5.0,
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
            ) as client:
                response = await client.get(product_url, headers={"User-Agent": "AvokBot/1.0"})
                response.raise_for_status()
                
                # Double check redirected URL for SSRF
                if not self._is_safe_url(str(response.url)):
                    return None
        except Exception as e:
            logger.error(f"Failed to fetch product metadata for {product_url}: {str(e)}")
            return None

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

    def _is_safe_url(self, url: str) -> bool:
        """Validate that the URL is public, non-local, and uses safe schemes."""
        try:
            parsed = urlparse(url)
            if parsed.scheme not in ("http", "https"):
                return False
            
            hostname = parsed.hostname
            if not hostname:
                return False

            # Check for common local/private patterns in hostname
            if hostname.lower() in ("localhost", "internal", "metadata.google.internal"):
                return False

            # Resolve to IP to check for private ranges
            # This handles both IP literals and hostnames
            try:
                ip_address = socket.gethostbyname(hostname)
                ip = ipaddress.ip_address(ip_address)
                
                return not (
                    ip.is_private or 
                    ip.is_loopback or 
                    ip.is_link_local or 
                    ip.is_multicast or 
                    ip.is_unspecified or
                    str(ip) == "169.254.169.254" # AWS/Cloud metadata
                )
            except (socket.gaierror, ValueError):
                # If we cannot resolve it, it might be an invalid host
                return False
                
        except Exception:
            return False

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
