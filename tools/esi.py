from tools.http_client import get, post, batch_gather

ESI_BASE = "https://esi.evetech.net/latest"

# Known eviction corps/alliances by ID
KNOWN_EVICTION_ENTITIES = {
    # Add known eviction corp IDs here as you encounter them
    "corps": set(),
    "alliances": set()
}

async def get_character_id(name: str) -> int | None:
    url = f"{ESI_BASE}/universe/ids/"
    res = await post(url, json=[name])
    if res.status_code != 200:
        return None
    data = res.json()
    characters = data.get("characters", [])
    return characters[0]["id"] if characters else None

async def get_character_info(character_id: int) -> dict:
    url = f"{ESI_BASE}/characters/{character_id}/"
    res = await get(url)
    return res.json() if res.status_code == 200 else {}

async def get_corporation_info(corp_id: int) -> dict:
    url = f"{ESI_BASE}/corporations/{corp_id}/"
    res = await get(url)
    return res.json() if res.status_code == 200 else {}

async def get_alliance_info(alliance_id: int) -> dict:
    url = f"{ESI_BASE}/alliances/{alliance_id}/"
    res = await get(url)
    return res.json() if res.status_code == 200 else {}

async def _fetch_type(type_id: int) -> tuple[int, str]:
    """Fetch a single type name from ESI. Returns (type_id, name)."""
    try:
        r = await get(f"{ESI_BASE}/universe/types/{type_id}/", timeout=5.0)
        if r.status_code == 200:
            return type_id, r.json().get("name", f"Unknown [{type_id}]")
    except Exception:
        pass
    return type_id, f"Unknown [{type_id}]"

async def resolve_type_names(type_ids: list) -> dict:
    """Resolve type IDs to names via ESI — concurrent batched requests."""
    if not type_ids:
        return {}
    coros = [_fetch_type(tid) for tid in type_ids]
    results = await batch_gather(coros, batch_size=15)
    return {
        tid: name
        for item in results
        if not isinstance(item, Exception)
        for tid, name in [item]
    }

async def get_full_pilot_profile(name: str) -> dict | None:
    character_id = await get_character_id(name)
    if not character_id:
        return None

    char_info = await get_character_info(character_id)
    if not char_info:
        return None

    corp_id = char_info.get("corporation_id")
    alliance_id = char_info.get("alliance_id")

    corp_info = await get_corporation_info(corp_id) if corp_id else {}
    alliance_info = await get_alliance_info(alliance_id) if alliance_id else {}

    return {
        "character_id": character_id,
        "name": name,
        "security_status": round(char_info.get("security_status", 0), 2),
        "birthday": char_info.get("birthday", "Unknown"),
        "corporation_id": corp_id,
        "corporation_name": corp_info.get("name", "Unknown"),
        "corporation_ticker": corp_info.get("ticker", ""),
        "member_count": corp_info.get("member_count", 0),
        "alliance_id": alliance_id,
        "alliance_name": alliance_info.get("name", "No Alliance"),
        "alliance_ticker": alliance_info.get("ticker", "")
    }

async def search_corporation(name: str) -> dict | None:
    url = f"{ESI_BASE}/universe/ids/"
    res = await post(url, json=[name])
    if res.status_code != 200:
        return None
    data = res.json()
    corporations = data.get("corporations", [])
    if not corporations:
        return None
    corp_id = corporations[0]["id"]
    corp_info = await get_corporation_info(corp_id)
    alliance_info = {}
    if corp_info.get("alliance_id"):
        alliance_info = await get_alliance_info(corp_info["alliance_id"])
    return {
        "corporation_id": corp_id,
        "name": corp_info.get("name", "Unknown"),
        "ticker": corp_info.get("ticker", ""),
        "member_count": corp_info.get("member_count", 0),
        "alliance_name": alliance_info.get("name", "No Alliance"),
        "alliance_ticker": alliance_info.get("ticker", "")
    }
