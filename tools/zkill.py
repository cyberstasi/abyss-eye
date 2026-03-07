import httpx
import asyncio
from collections import defaultdict
from tools.esi import resolve_type_names

ESI_BASE = "https://esi.evetech.net/latest"
ZKILL_BASE = "https://zkillboard.com/api"

# Known wormhole ship hulls for WH pilot detection
WH_SHIP_IDS = {
    # T3 Cruisers
    29984, 29986, 29988, 29990,
    # T3 Destroyers  
    42124, 42132, 42133, 42134, 42135,
    # Recons
    11969, 11957, 11971, 11961, 11963, 11965,
    # Logi
    11987, 11985, 11989,
    # Common WH ships
    17918, 17920,  # Nestors
    33151,         # Stratios
    37483,         # Astero
}

CAPITAL_SHIP_IDS = {
    673, 3514, 3628, 11567, 12003, 12011, 12013, 12017,
    12019, 12021, 17918, 17920, 19720, 19722, 19724,
    22852, 23757, 23911, 24483, 24484, 24690, 28661
}

async def fetch_full_killmail(kill_id: int, kill_hash: str) -> dict:
    """Fetch full killmail details from ESI."""
    url = f"{ESI_BASE}/killmails/{kill_id}/{kill_hash}/"
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(url, timeout=5.0)
            return r.json() if r.status_code == 200 else {}
        except Exception:
            return {}

async def get_pilot_kills(character_id: int, limit: int = 25) -> list:
    url = f"{ZKILL_BASE}/kills/characterID/{character_id}/"
    async with httpx.AsyncClient(headers={"User-Agent": "AURA-EVE-Agent/1.0"}) as client:
        res = await client.get(url)
        return res.json()[:limit] if res.status_code == 200 else []

async def get_pilot_losses(character_id: int, limit: int = 25) -> list:
    url = f"{ZKILL_BASE}/losses/characterID/{character_id}/"
    async with httpx.AsyncClient(headers={"User-Agent": "AURA-EVE-Agent/1.0"}) as client:
        res = await client.get(url)
        return res.json()[:limit] if res.status_code == 200 else []

async def get_pilot_stats(character_id: int) -> dict:
    url = f"{ZKILL_BASE}/stats/characterID/{character_id}/"
    async with httpx.AsyncClient(headers={"User-Agent": "AURA-EVE-Agent/1.0"}) as client:
        res = await client.get(url)
        return res.json() if res.status_code == 200 else {}

async def get_corp_kills(corp_id: int, limit: int = 25) -> list:
    url = f"{ZKILL_BASE}/kills/corporationID/{corp_id}/"
    async with httpx.AsyncClient(headers={"User-Agent": "AURA-EVE-Agent/1.0"}) as client:
        res = await client.get(url)
        return res.json()[:limit] if res.status_code == 200 else []

async def get_corp_losses(corp_id: int, limit: int = 25) -> list:
    url = f"{ZKILL_BASE}/losses/corporationID/{corp_id}/"
    async with httpx.AsyncClient(headers={"User-Agent": "AURA-EVE-Agent/1.0"}) as client:
        res = await client.get(url)
        return res.json()[:limit] if res.status_code == 200 else []

async def get_corp_stats(corp_id: int) -> dict:
    url = f"{ZKILL_BASE}/stats/corporationID/{corp_id}/"
    async with httpx.AsyncClient(headers={"User-Agent": "AURA-EVE-Agent/1.0"}) as client:
        res = await client.get(url)
        return res.json() if res.status_code == 200 else {}

async def get_system_kills(system_id: int, limit: int = 25) -> list:
    url = f"{ZKILL_BASE}/kills/solarSystemID/{system_id}/"
    async with httpx.AsyncClient(headers={"User-Agent": "AURA-EVE-Agent/1.0"}) as client:
        res = await client.get(url)
        return res.json()[:limit] if res.status_code == 200 else []

async def analyze_pilot_killboard(
    kills: list, losses: list, stats: dict, character_id: int
) -> dict:
    """Deep analysis of pilot killboard data."""

    total_kills = stats.get("shipsDestroyed", 0)
    total_losses = stats.get("shipsLost", 0)
    isk_destroyed = stats.get("iskDestroyed", 0)
    isk_lost = stats.get("iskLost", 0)

    efficiency = 0
    if isk_destroyed + isk_lost > 0:
        efficiency = round(
            (isk_destroyed / (isk_destroyed + isk_lost)) * 100, 1
        )

    # Fetch full kill details for deep analysis
    full_kills = []
    async with httpx.AsyncClient() as client:
        for kill in kills[:15]:
            kill_id = kill.get("killmail_id")
            kill_hash = kill.get("zkb", {}).get("hash")
            if kill_id and kill_hash:
                try:
                    r = await client.get(
                        f"{ESI_BASE}/killmails/{kill_id}/{kill_hash}/",
                        timeout=5.0
                    )
                    if r.status_code == 200:
                        full_kill = r.json()
                        full_kill["zkb"] = kill.get("zkb", {})
                        full_kills.append(full_kill)
                except Exception:
                    continue

    # Analyze ships flown by this pilot
    ships_flown = defaultdict(int)
    gang_sizes = []
    solo_kills = 0
    wh_kills = 0
    capital_kills = 0
    kill_dates = []
    timezones = defaultdict(int)
    awox_flags = []

    for kill in full_kills:
        kill_time = kill.get("killmail_time", "")
        if kill_time:
            kill_dates.append(kill_time[:10])

        attackers = kill.get("attackers", [])
        gang_sizes.append(len(attackers))

        if len(attackers) == 1:
            solo_kills += 1

        # Find this pilot in attackers
        for attacker in attackers:
            if attacker.get("character_id") == character_id:
                ship_id = attacker.get("ship_type_id", 0)
                if ship_id:
                    ships_flown[ship_id] += 1
                if ship_id in WH_SHIP_IDS:
                    wh_kills += 1
                if ship_id in CAPITAL_SHIP_IDS:
                    capital_kills += 1

        # Check for awox — same corp attacking
        victim_corp = kill.get("victim", {}).get("corporation_id")
        for attacker in attackers:
            if (attacker.get("character_id") == character_id and
                    attacker.get("corporation_id") == victim_corp):
                awox_flags.append(kill.get("killmail_id"))

        # Timezone
        for label in kill.get("zkb", {}).get("labels", []):
            if label.startswith("tz:"):
                tz = label.replace("tz:", "").upper()
                timezones[tz] += 1

    # Resolve ship names
    top_ship_ids = sorted(
        ships_flown.items(), key=lambda x: x[1], reverse=True
    )[:5]
    ship_id_list = [s[0] for s in top_ship_ids]
    ship_names = await resolve_type_names(ship_id_list)
    top_ships_named = [
        ship_names.get(sid, f"Unknown[{sid}]")
        for sid in ship_id_list
    ]

    avg_gang_size = round(
        sum(gang_sizes) / len(gang_sizes), 1
    ) if gang_sizes else 0

    solo_ratio = round(
        (solo_kills / len(full_kills)) * 100, 1
    ) if full_kills else 0

    dominant_tz = max(
        timezones, key=timezones.get
    ) if timezones else "Unknown"

    # Activity recency
    if kill_dates:
        most_recent = kill_dates[0]
        from datetime import datetime, timezone
        try:
            recent_dt = datetime.strptime(most_recent, "%Y-%m-%d")
            now = datetime.now()
            days_since = (now - recent_dt).days
            if days_since <= 7:
                recency = f"🔴 VERY RECENT — active {days_since}d ago"
            elif days_since <= 30:
                recency = f"🟠 RECENT — active {days_since}d ago"
            elif days_since <= 90:
                recency = f"🟡 MODERATE — active {days_since}d ago"
            else:
                recency = f"⚪ INACTIVE — last active {days_since}d ago"
        except Exception:
            recency = "Unknown"
    else:
        recency = "No recent activity"

    # WH pilot flag
    wh_pilot = wh_kills >= 3 or (
        len(full_kills) > 0 and wh_kills / len(full_kills) > 0.3
    )

    return {
        "total_kills": total_kills,
        "total_losses": total_losses,
        "isk_efficiency": efficiency,
        "isk_destroyed_bil": round(isk_destroyed / 1_000_000_000, 2),
        "isk_lost_bil": round(isk_lost / 1_000_000_000, 2),
        "avg_gang_size": avg_gang_size,
        "solo_ratio_pct": solo_ratio,
        "top_ships": top_ships_named,
        "recent_kill_count": len(full_kills),
        "recent_loss_count": len(losses),
        "dominant_timezone": dominant_tz,
        "activity_recency": recency,
        "wh_pilot": wh_pilot,
        "capital_capable": capital_kills > 0,
        "awox_flags": awox_flags,
        "solo_kills": solo_kills
    }

async def get_corp_top_pilots(corp_id: int, limit: int = 50) -> list:
    """Get top active pilots in a corp from recent kill activity."""
    url = f"{ZKILL_BASE}/kills/corporationID/{corp_id}/"
    async with httpx.AsyncClient(headers={"User-Agent": "AURA-EVE-Agent/1.0"}) as client:
        try:
            res = await client.get(url, timeout=10.0)
            if res.status_code != 200:
                return []
            zkill_data = res.json()[:limit]
        except Exception:
            return []

    # Fetch full kill mails to get attacker details
    pilot_kills = defaultdict(int)
    pilot_ships = defaultdict(set)

    async with httpx.AsyncClient() as client:
        for kill in zkill_data:
            kill_id = kill.get("killmail_id")
            kill_hash = kill.get("zkb", {}).get("hash")
            if not kill_id or not kill_hash:
                continue
            try:
                r = await client.get(
                    f"{ESI_BASE}/killmails/{kill_id}/{kill_hash}/",
                    timeout=5.0
                )
                if r.status_code != 200:
                    continue
                full_kill = r.json()
                for attacker in full_kill.get("attackers", []):
                    if attacker.get("corporation_id") == corp_id:
                        char_id = attacker.get("character_id")
                        ship_id = attacker.get("ship_type_id")
                        if char_id:
                            pilot_kills[char_id] += 1
                            if ship_id:
                                pilot_ships[char_id].add(ship_id)
            except Exception:
                continue

    # Sort by kill count
    top_pilots = sorted(
        pilot_kills.items(), key=lambda x: x[1], reverse=True
    )[:10]

    # Resolve character names and ship names
    results = []
    async with httpx.AsyncClient() as client:
        for char_id, kill_count in top_pilots:
            try:
                r = await client.get(
                    f"{ESI_BASE}/characters/{char_id}/",
                    timeout=5.0
                )
                char_name = "Unknown"
                if r.status_code == 200:
                    char_name = r.json().get("name", "Unknown")

                # Resolve top ship for this pilot
                top_ship_id = max(
                    pilot_ships[char_id],
                    key=lambda s: list(pilot_ships[char_id]).count(s)
                ) if pilot_ships[char_id] else None

                ship_name = "Unknown"
                if top_ship_id:
                    r2 = await client.get(
                        f"{ESI_BASE}/universe/types/{top_ship_id}/",
                        timeout=5.0
                    )
                    if r2.status_code == 200:
                        ship_name = r2.json().get("name", "Unknown")

                results.append({
                    "character_id": char_id,
                    "name": char_name,
                    "kills_in_sample": kill_count,
                    "most_used_ship": ship_name
                })
            except Exception:
                continue

    return results
