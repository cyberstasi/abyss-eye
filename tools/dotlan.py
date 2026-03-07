import httpx

ESI_BASE = "https://esi.evetech.net/latest"

async def get_system_id(system_name: str) -> int | None:
    """Look up a system ID by name using ESI."""
    url = f"{ESI_BASE}/universe/ids/"
    async with httpx.AsyncClient() as client:
        res = await client.post(url, json=[system_name])
        if res.status_code != 200:
            return None
        data = res.json()
        systems = data.get("systems", [])
        return systems[0]["id"] if systems else None

async def get_system_info(system_id: int) -> dict:
    """Get system details from ESI."""
    url = f"{ESI_BASE}/universe/systems/{system_id}/"
    async with httpx.AsyncClient() as client:
        res = await client.get(url)
        return res.json() if res.status_code == 200 else {}

async def get_system_kills(system_id: int) -> dict:
    """Get kill activity for a system from ESI."""
    url = f"{ESI_BASE}/universe/system_kills/"
    async with httpx.AsyncClient() as client:
        res = await client.get(url)
        if res.status_code != 200:
            return {}
        all_systems = res.json()
        for system in all_systems:
            if system.get("system_id") == system_id:
                return system
        return {"ship_kills": 0, "pod_kills": 0, "npc_kills": 0}

async def get_system_jumps(system_id: int) -> int:
    """Get jump count for a system from ESI."""
    url = f"{ESI_BASE}/universe/system_jumps/"
    async with httpx.AsyncClient() as client:
        res = await client.get(url)
        if res.status_code != 200:
            return 0
        all_systems = res.json()
        for system in all_systems:
            if system.get("system_id") == system_id:
                return system.get("ship_jumps", 0)
        return 0

async def get_full_system_intel(system_name: str) -> dict | None:
    """Get complete intel on a system."""
    system_id = await get_system_id(system_name)
    if not system_id:
        return None

    system_info = await get_system_info(system_id)
    kill_data = await get_system_kills(system_id)
    jumps = await get_system_jumps(system_id)

    ship_kills = kill_data.get("ship_kills", 0)
    pod_kills = kill_data.get("pod_kills", 0)
    npc_kills = kill_data.get("npc_kills", 0)

    # Determine security class
    security = system_info.get("security_status", 0)
    if security >= 0.5:
        sec_class = "Highsec"
    elif security > 0:
        sec_class = "Lowsec"
    elif security == -1:
        sec_class = "Wormhole"
    else:
        sec_class = "Nullsec"

    # Wormhole check by system ID range
    is_wormhole = system_id >= 31000000

    if is_wormhole:
        sec_class = "Wormhole"

    # Activity rating based on PvP kills
    total_pvp = ship_kills + pod_kills
    if total_pvp == 0:
        activity = "⚪ QUIET — No recent PvP activity"
    elif total_pvp <= 3:
        activity = "🟡 LOW — Light activity"
    elif total_pvp <= 10:
        activity = "🟠 MODERATE — Active system"
    else:
        activity = "🔴 HOT — Heavy PvP activity"

    return {
        "system_id": system_id,
        "name": system_name,
        "security_status": round(security, 2),
        "security_class": sec_class,
        "ship_kills_1hr": ship_kills,
        "pod_kills_1hr": pod_kills,
        "npc_kills_1hr": npc_kills,
        "jumps_1hr": jumps,
        "activity_rating": activity,
        "is_wormhole": is_wormhole
    }