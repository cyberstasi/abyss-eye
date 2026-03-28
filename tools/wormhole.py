import asyncio
from collections import defaultdict
from tools.http_client import get, post, zkill_get, batch_gather

ESI_BASE = "https://esi.evetech.net/latest"
ZKILL_BASE = "https://zkillboard.com/api"

WH_CLASS_INFO = {
    "C1": {"difficulty": "Low", "mass": "~500M kg", "sites": "Gas, Relic, Data, Combat", "capitals": False},
    "C2": {"difficulty": "Low-Med", "mass": "~1B kg", "sites": "Gas, Relic, Data, Combat", "capitals": False},
    "C3": {"difficulty": "Medium", "mass": "~1.8B kg", "sites": "Gas, Relic, Data, Combat", "capitals": False},
    "C4": {"difficulty": "High", "mass": "~2B kg", "sites": "Combat, Gas — dual statics", "capitals": False},
    "C5": {"difficulty": "Very High", "mass": "~3B kg", "sites": "Combat, Gas — capital eligible", "capitals": True},
    "C6": {"difficulty": "Extreme", "mass": "~3B kg", "sites": "Combat — capital required", "capitals": True},
    "C13": {"difficulty": "Special", "mass": "~5M kg", "sites": "Shattered frigate hole", "capitals": False},
    "Thera": {"difficulty": "Special", "mass": "Varies", "sites": "Multiple statics, NPC station", "capitals": False},
    "Pochven": {"difficulty": "Triglavian", "mass": "Varies", "sites": "Triglavian combat sites", "capitals": False},
    "Unknown": {"difficulty": "Unknown", "mass": "Unknown", "sites": "Unknown", "capitals": False},
}

EXCLUDED_CORPS = {
    1000001, 1000002, 1000003, 1000004, 1000005, 1000006,
    1000007, 1000008, 1000009, 1000010, 1000011, 1000012,
    1000013, 1000014, 1000015, 1000016, 1000017, 1000018,
    1000019, 1000020, 1000021, 1000022, 1000023, 1000024,
    1000025, 1000026, 1000027, 1000028, 1000029, 1000030,
    1000165, 1000166, 1000167, 1000168, 1000169, 1000170,
    1000171, 1000172, 1000173, 1000174, 1000182
}

CAPITAL_TYPE_IDS = {
    673, 3514, 3628, 11567, 12003, 12011, 12013, 12017,
    12019, 12021, 17918, 17920, 19720, 19722, 19724,
    22852, 23757, 23911, 24483, 24484, 24690, 28661
}


async def get_wormhole_system_id(system_name: str) -> int | None:
    res = await post(f"{ESI_BASE}/universe/ids/", json=[system_name])
    if res.status_code != 200:
        return None
    systems = res.json().get("systems", [])
    return systems[0]["id"] if systems else None

async def get_wormhole_system_info(system_id: int) -> dict:
    res = await get(f"{ESI_BASE}/universe/systems/{system_id}/")
    return res.json() if res.status_code == 200 else {}

async def get_wh_class_from_region(system_id: int, system_info: dict) -> str:
    try:
        constellation_id = system_info.get("constellation_id")
        if not constellation_id:
            return "Unknown"
        r = await get(f"{ESI_BASE}/universe/constellations/{constellation_id}/")
        if r.status_code != 200:
            return "Unknown"
        region_id = r.json().get("region_id")
        if not region_id:
            return "Unknown"
        r2 = await get(f"{ESI_BASE}/universe/regions/{region_id}/")
        if r2.status_code != 200:
            return "Unknown"
        region_name = r2.json().get("name", "")
        class_map = {
            "A": "C1", "B": "C2", "C": "C3", "D": "C4",
            "E": "C5", "F": "C6", "G": "C13", "H": "Thera",
            "P": "Pochven"
        }
        first_letter = region_name[0].upper() if region_name else ""
        return class_map.get(first_letter, "Unknown")
    except Exception:
        return "Unknown"


async def _fetch_wh_killmail(kill: dict) -> dict | None:
    """Fetch a single wormhole killmail from ESI."""
    kill_id = kill.get("killmail_id")
    kill_hash = kill.get("zkb", {}).get("hash")
    if not kill_id or not kill_hash:
        return None
    try:
        r = await get(f"{ESI_BASE}/killmails/{kill_id}/{kill_hash}/", timeout=5.0)
        if r.status_code == 200:
            full_kill = r.json()
            full_kill["zkb"] = kill.get("zkb", {})
            return full_kill
    except Exception:
        pass
    return None


async def get_wormhole_kills(system_id: int, limit: int = 50) -> list:
    try:
        res = await zkill_get(f"{ZKILL_BASE}/kills/solarSystemID/{system_id}/", timeout=10.0)
        if res.status_code != 200:
            return []
        zkill_data = res.json()[:limit]
    except Exception:
        return []

    coros = [_fetch_wh_killmail(kill) for kill in zkill_data]
    results = await batch_gather(coros, batch_size=15)
    return [r for r in results if r and not isinstance(r, Exception)]


async def get_zkill_system_stats(system_id: int) -> dict:
    try:
        res = await zkill_get(f"{ZKILL_BASE}/stats/solarSystemID/{system_id}/", timeout=10.0)
        return res.json() if res.status_code == 200 else {}
    except Exception:
        return {}


async def _fetch_corp_with_alliance(corp_id: int) -> dict | None:
    """Fetch corp info and resolve alliance name."""
    try:
        r = await get(f"{ESI_BASE}/corporations/{corp_id}/", timeout=5.0)
        if r.status_code != 200:
            return None
        data = r.json()
        alliance_name = "No Alliance"
        alliance_id = data.get("alliance_id")
        if alliance_id:
            r2 = await get(f"{ESI_BASE}/alliances/{alliance_id}/", timeout=5.0)
            if r2.status_code == 200:
                alliance_name = r2.json().get("name", "No Alliance")
        return {
            "corp_id": corp_id,
            "name": data.get("name", "Unknown"),
            "ticker": data.get("ticker", ""),
            "members": data.get("member_count", 0),
            "alliance": alliance_name
        }
    except Exception:
        return None


async def resolve_corp_names(corp_ids: list) -> list:
    if not corp_ids:
        return []
    coros = [_fetch_corp_with_alliance(corp_id) for corp_id in corp_ids]
    results = await batch_gather(coros, batch_size=15)
    return [r for r in results if r and not isinstance(r, Exception)]


def analyze_wh_kills(kills: list) -> dict:
    if not kills:
        return {
            "total_recent_kills": 0,
            "likely_occupied": False,
            "active_corp_ids": [],
            "activity_pattern": "⚪ NO ACTIVITY — Appears empty",
            "capital_activity": False,
            "farming_signs": False,
            "farming_kill_count": 0,
            "dominant_timezone": "Unknown"
        }

    corp_days = defaultdict(set)
    corp_kill_count = defaultdict(int)
    capital_seen = False
    farming_kills = 0
    timezones = defaultdict(int)

    for kill in kills:
        kill_time = kill.get("killmail_time", "")
        kill_date = kill_time[:10]

        for attacker in kill.get("attackers", []):
            corp_id = attacker.get("corporation_id")
            if corp_id and corp_id not in EXCLUDED_CORPS:
                corp_days[corp_id].add(kill_date)
                corp_kill_count[corp_id] += 1
            ship_id = attacker.get("ship_type_id", 0)
            if ship_id in CAPITAL_TYPE_IDS:
                capital_seen = True

        if any(a.get("faction_id") for a in kill.get("attackers", [])):
            farming_kills += 1

        for label in kill.get("zkb", {}).get("labels", []):
            if label.startswith("tz:"):
                tz = label.replace("tz:", "").upper()
                timezones[tz] += 1

    resident_corps = {
        corp_id: corp_kill_count[corp_id]
        for corp_id, days in corp_days.items()
        if len(days) >= 2
    }

    top_residents = sorted(
        resident_corps.items(), key=lambda x: x[1], reverse=True
    )[:3]

    total = len(kills)
    if total == 0:
        pattern = "⚪ NO ACTIVITY — Appears empty"
    elif total <= 5:
        pattern = "🟡 LOW — Occasional visitors"
    elif total <= 15:
        pattern = "🟠 MODERATE — Regular traffic"
    elif total <= 30:
        pattern = "🔴 HIGH — Active system"
    else:
        pattern = "🔴 VERY HIGH — Heavily active system"

    dominant_tz = max(timezones, key=timezones.get) if timezones else "Unknown"
    farming_signs = farming_kills > (total * 0.3) if total > 0 else False

    return {
        "total_recent_kills": total,
        "likely_occupied": len(top_residents) > 0 or total > 5,
        "active_corp_ids": [c[0] for c in top_residents],
        "activity_pattern": pattern,
        "capital_activity": capital_seen,
        "farming_signs": farming_signs,
        "farming_kill_count": farming_kills,
        "dominant_timezone": dominant_tz
    }


async def get_full_wormhole_intel(system_name: str) -> dict | None:
    system_id = await get_wormhole_system_id(system_name)
    if not system_id:
        return None

    if system_id < 31000000:
        return {
            "error": f"{system_name} is not a wormhole system",
            "system_id": system_id
        }

    system_info, kills, stats = await asyncio.gather(
        get_wormhole_system_info(system_id),
        get_wormhole_kills(system_id),
        get_zkill_system_stats(system_id)
    )

    wh_class = await get_wh_class_from_region(system_id, system_info)
    class_info = WH_CLASS_INFO.get(wh_class, WH_CLASS_INFO["Unknown"])
    kill_analysis = analyze_wh_kills(kills)

    active_corp_ids = kill_analysis.get("active_corp_ids", [])
    resolved_corps = await resolve_corp_names(active_corp_ids)

    return {
        "system_id": system_id,
        "name": system_name,
        "wh_class": wh_class,
        "class_info": class_info,
        "kill_analysis": kill_analysis,
        "likely_residents": resolved_corps,
        "all_time_kills": stats.get("shipsDestroyed", 0),
        "all_time_losses": stats.get("shipsLost", 0),
    }
