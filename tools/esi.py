import httpx

ESI_BASE = "https://esi.evetech.net/latest"

async def get_character_id(name: str) -> int | None:
    """Look up a character ID by name."""
    url = f"{ESI_BASE}/universe/ids/"
    async with httpx.AsyncClient() as client:
        res = await client.post(url, json=[name])
        if res.status_code != 200:
            return None
        data = res.json()
        characters = data.get("characters", [])
        return characters[0]["id"] if characters else None

async def get_character_info(character_id: int) -> dict:
    """Get character details by ID."""
    url = f"{ESI_BASE}/characters/{character_id}/"
    async with httpx.AsyncClient() as client:
        res = await client.get(url)
        if res.status_code != 200:
            return {}
        return res.json()

async def get_corporation_info(corp_id: int) -> dict:
    """Get corporation details by ID."""
    url = f"{ESI_BASE}/corporations/{corp_id}/"
    async with httpx.AsyncClient() as client:
        res = await client.get(url)
        if res.status_code != 200:
            return {}
        return res.json()

async def get_alliance_info(alliance_id: int) -> dict:
    """Get alliance details by ID."""
    url = f"{ESI_BASE}/alliances/{alliance_id}/"
    async with httpx.AsyncClient() as client:
        res = await client.get(url)
        if res.status_code != 200:
            return {}
        return res.json()

async def get_full_pilot_profile(name: str) -> dict | None:
    """Get complete pilot profile including corp and alliance."""
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
    """Search for a corporation by name and return full info."""
    url = f"{ESI_BASE}/universe/ids/"
    async with httpx.AsyncClient() as client:
        res = await client.post(url, json=[name])
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