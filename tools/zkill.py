import httpx

ZKILL_BASE = "https://zkillboard.com/api"

async def get_pilot_kills(character_id: int, limit: int = 25) -> list:
    """Get recent kills for a pilot."""
    url = f"{ZKILL_BASE}/kills/characterID/{character_id}/"
    async with httpx.AsyncClient(headers={"User-Agent": "AURA-EVE-Agent/1.0"}) as client:
        res = await client.get(url)
        return res.json()[:limit] if res.status_code == 200 else []

async def get_pilot_losses(character_id: int, limit: int = 25) -> list:
    """Get recent losses for a pilot."""
    url = f"{ZKILL_BASE}/losses/characterID/{character_id}/"
    async with httpx.AsyncClient(headers={"User-Agent": "AURA-EVE-Agent/1.0"}) as client:
        res = await client.get(url)
        return res.json()[:limit] if res.status_code == 200 else []

async def get_pilot_stats(character_id: int) -> dict:
    """Get overall stats for a pilot."""
    url = f"{ZKILL_BASE}/stats/characterID/{character_id}/"
    async with httpx.AsyncClient(headers={"User-Agent": "AURA-EVE-Agent/1.0"}) as client:
        res = await client.get(url)
        return res.json() if res.status_code == 200 else {}

async def get_corp_kills(corp_id: int, limit: int = 25) -> list:
    """Get recent kills for a corporation."""
    url = f"{ZKILL_BASE}/kills/corporationID/{corp_id}/"
    async with httpx.AsyncClient(headers={"User-Agent": "AURA-EVE-Agent/1.0"}) as client:
        res = await client.get(url)
        return res.json()[:limit] if res.status_code == 200 else []

async def get_corp_losses(corp_id: int, limit: int = 25) -> list:
    """Get recent losses for a corporation."""
    url = f"{ZKILL_BASE}/losses/corporationID/{corp_id}/"
    async with httpx.AsyncClient(headers={"User-Agent": "AURA-EVE-Agent/1.0"}) as client:
        res = await client.get(url)
        return res.json()[:limit] if res.status_code == 200 else []

async def get_corp_stats(corp_id: int) -> dict:
    """Get overall stats for a corporation."""
    url = f"{ZKILL_BASE}/stats/corporationID/{corp_id}/"
    async with httpx.AsyncClient(headers={"User-Agent": "AURA-EVE-Agent/1.0"}) as client:
        res = await client.get(url)
        return res.json() if res.status_code == 200 else {}

async def get_system_kills(system_id: int, limit: int = 25) -> list:
    """Get recent kills in a system."""
    url = f"{ZKILL_BASE}/kills/solarSystemID/{system_id}/"
    async with httpx.AsyncClient(headers={"User-Agent": "AURA-EVE-Agent/1.0"}) as client:
        res = await client.get(url)
        return res.json()[:limit] if res.status_code == 200 else []

async def analyze_pilot_killboard(kills: list, losses: list, stats: dict) -> dict:
    """Analyze raw killboard data into useful intel."""
    total_kills = stats.get("shipsDestroyed", 0)
    total_losses = stats.get("shipsLost", 0)
    isk_destroyed = stats.get("iskDestroyed", 0)
    isk_lost = stats.get("iskLost", 0)

    efficiency = 0
    if isk_destroyed + isk_lost > 0:
        efficiency = round((isk_destroyed / (isk_destroyed + isk_lost)) * 100, 1)

    # Analyze ship types flown from recent kills
    ships_flown = {}
    for kill in kills:
        victim = kill.get("victim", {})
        attackers = kill.get("attackers", [])
        for attacker in attackers:
            ship_id = attacker.get("ship_type_id", 0)
            if ship_id:
                ships_flown[ship_id] = ships_flown.get(ship_id, 0) + 1

    # Find most common ships
    top_ships = sorted(ships_flown.items(), key=lambda x: x[1], reverse=True)[:5]

    # Analyze gang size from recent kills
    gang_sizes = []
    for kill in kills:
        attackers = kill.get("attackers", [])
        gang_sizes.append(len(attackers))

    avg_gang_size = round(sum(gang_sizes) / len(gang_sizes), 1) if gang_sizes else 0

    solo_kills = sum(1 for k in kills if len(k.get("attackers", [])) == 1)
    solo_ratio = round((solo_kills / len(kills)) * 100, 1) if kills else 0

    return {
        "total_kills": total_kills,
        "total_losses": total_losses,
        "isk_efficiency": efficiency,
        "isk_destroyed_bil": round(isk_destroyed / 1_000_000_000, 2),
        "isk_lost_bil": round(isk_lost / 1_000_000_000, 2),
        "avg_gang_size": avg_gang_size,
        "solo_ratio_pct": solo_ratio,
        "top_ship_ids": [s[0] for s in top_ships],
        "recent_kill_count": len(kills),
        "recent_loss_count": len(losses)
    }