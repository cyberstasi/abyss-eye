"""
Shared httpx client for all AURA tool modules.

- One connection pool reused across all requests
- Retry with exponential backoff on transient errors (429, 502, 503, 504, timeouts)
- zKillboard-specific semaphore (max 3 concurrent) + User-Agent enforcement
- Graceful shutdown via lifespan hook in main.py
"""

import asyncio
import httpx

# User-Agent sent with every request
USER_AGENT = "AURA-EVE-Agent/1.0 (github.com/cyberstasi/abyss-eye)"

# Transient HTTP status codes worth retrying
RETRY_STATUSES = {429, 502, 503, 504}

# zKill concurrency limit — they rate-limit hard
_zkill_semaphore = asyncio.Semaphore(3)

# Module-level shared client (initialised on first use)
_client: httpx.AsyncClient | None = None


def get_client() -> httpx.AsyncClient:
    """Return the shared AsyncClient, creating it if needed."""
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            headers={"User-Agent": USER_AGENT},
            timeout=httpx.Timeout(10.0, connect=5.0),
            limits=httpx.Limits(max_connections=50, max_keepalive_connections=20),
        )
    return _client


async def close_client() -> None:
    """Close the shared client. Call this on app shutdown."""
    global _client
    if _client and not _client.is_closed:
        await _client.aclose()
        _client = None


async def _request_with_retry(
    method: str,
    url: str,
    max_retries: int = 3,
    **kwargs,
) -> httpx.Response:
    """Send a request with exponential backoff on transient failures."""
    client = get_client()
    delay = 1.0
    last_exc: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            response = await client.request(method, url, **kwargs)
            if response.status_code not in RETRY_STATUSES:
                return response
            # Transient HTTP error — wait then retry
            if attempt < max_retries:
                await asyncio.sleep(delay)
                delay *= 2
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            last_exc = exc
            if attempt < max_retries:
                await asyncio.sleep(delay)
                delay *= 2

    # All retries exhausted
    if last_exc:
        raise last_exc
    # Return the last bad response rather than raising
    return response  # type: ignore[return-value]


async def get(url: str, **kwargs) -> httpx.Response:
    return await _request_with_retry("GET", url, **kwargs)


async def post(url: str, **kwargs) -> httpx.Response:
    return await _request_with_retry("POST", url, **kwargs)


async def zkill_get(url: str, **kwargs) -> httpx.Response:
    """GET wrapper with zKillboard concurrency limit."""
    async with _zkill_semaphore:
        response = await _request_with_retry("GET", url, **kwargs)
        # Small fixed delay to stay well under their rate limit
        await asyncio.sleep(0.25)
        return response


async def batch_gather(coros: list, batch_size: int = 15) -> list:
    """
    Run a list of coroutines in batches using asyncio.gather.
    Prevents hammering ESI with hundreds of concurrent requests.
    """
    results = []
    for i in range(0, len(coros), batch_size):
        batch = coros[i : i + batch_size]
        batch_results = await asyncio.gather(*batch, return_exceptions=True)
        results.extend(batch_results)
    return results
