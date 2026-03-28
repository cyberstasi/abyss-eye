from tools.http_client import get, zkill_get, batch_gather

ESI_BASE = "https://esi.evetech.net/latest"
ZKILL_BASE = "https://zkillboard.com/api"

# Base EHP estimates by ship class (rough averages in HP)
# Used when we can't pull dogma attributes
SHIP_CLASS_EHP = {
    "Frigate": 4_000,
    "Destroyer": 6_000,
    "Cruiser": 18_000,
    "Battlecruiser": 50_000,
    "Battleship": 90_000,
    "Strategic Cruiser": 45_000,
    "Heavy Assault Cruiser": 35_000,
    "Recon Ship": 20_000,
    "Logistics": 25_000,
    "Interdictor": 8_000,
    "Heavy Interdictor": 30_000,
    "Command Ship": 60_000,
    "Carrier": 800_000,
    "Dreadnought": 1_200_000,
    "Supercarrier": 3_000_000,
    "Titan": 10_000_000,
    "Capsule": 500,
    "Shuttle": 1_000,
    "Industrial": 15_000,
    "Freighter": 200_000,
}

# Logi ship type IDs (common ones)
LOGI_TYPE_IDS = {
    11987, 11985, 11989,  # Guardian, Basilisk, Oneiros, Scimitar
    37458, 37459, 37460, 37461,  # T3 logi destroyers
    35779, 35780,  # Apostle, Minokawa (FAX)
}

# Logi group IDs
LOGI_GROUP_IDS = {832}  # Logistics group


async def _fetch_type_bulk(type_id: int) -> tuple[int, dict]:
    """Fetch a single type's name and group info from ESI."""
    try:
        r = await get(f"{ESI_BASE}/universe/types/{type_id}/", timeout=5.0)
        if r.status_code == 200:
            data = r.json()
            return type_id, {
                "name": data.get("name", f"Unknown[{type_id}]"),
                "group_id": data.get("group_id"),
                "description": data.get("description", "")
            }
    except Exception:
        pass
    return type_id, {"name": f"Unknown[{type_id}]", "group_id": None}


async def resolve_type_names_bulk(type_ids: list) -> dict:
    """Resolve multiple type IDs to names and group info — concurrent batched requests."""
    if not type_ids:
        return {}
    coros = [_fetch_type_bulk(tid) for tid in type_ids]
    results = await batch_gather(coros, batch_size=15)
    return {
        tid: info
        for item in results
        if not isinstance(item, Exception)
        for tid, info in [item]
    }


async def _fetch_group_name(group_id: int) -> tuple[int, str]:
    """Fetch group name — returns (group_id, name) for use with batch_gather."""
    name = await get_group_name(group_id)
    return group_id, name


async def get_group_name(group_id: int) -> str:
    """Get group name from group ID."""
    if not group_id:
        return "Unknown"
    try:
        r = await get(f"{ESI_BASE}/universe/groups/{group_id}/", timeout=5.0)
        if r.status_code == 200:
            return r.json().get("name", "Unknown")
    except Exception:
        pass
    return "Unknown"


async def get_ship_class(ship_type_id: int) -> str:
    """Get ship class/group name for a ship type ID."""
    if not ship_type_id:
        return "Unknown"
    try:
        r = await get(f"{ESI_BASE}/universe/types/{ship_type_id}/", timeout=5.0)
        if r.status_code != 200:
            return "Unknown"
        group_id = r.json().get("group_id")
        if group_id:
            gr = await get(f"{ESI_BASE}/universe/groups/{group_id}/", timeout=5.0)
            if gr.status_code == 200:
                return gr.json().get("name", "Unknown")
    except Exception:
        pass
    return "Unknown"


def estimate_fight_duration(
    total_damage: int,
    ship_class: str,
    attacker_count: int,
    logi_present: bool,
    damage_distribution: dict
) -> dict:
    """
    Estimate fight duration based on damage, ship class, and attacker count.
    Returns duration bracket and fight type classification.
    """

    # Get base EHP for ship class
    base_ehp = SHIP_CLASS_EHP.get(ship_class, 20_000)

    # Overkill ratio — how much extra damage was dealt
    overkill_pct = round(((total_damage - base_ehp) / base_ehp) * 100, 1) if base_ehp > 0 else 0

    # Estimate DPS applied based on attacker count and ship class assumptions
    # Rough DPS per attacker by context
    if attacker_count == 1:
        assumed_dps = 400
    elif attacker_count <= 3:
        assumed_dps = 350 * attacker_count
    elif attacker_count <= 10:
        assumed_dps = 300 * attacker_count
    else:
        assumed_dps = 250 * attacker_count

    # Estimated duration in seconds
    estimated_seconds = base_ehp / assumed_dps if assumed_dps > 0 else 60

    # Logi extends fights significantly
    if logi_present:
        estimated_seconds *= 3.5

    # Classify fight type
    if attacker_count >= 20 and not logi_present:
        fight_type = "Blap / Gank"
        duration_label = "< 5 seconds"
    elif estimated_seconds < 10:
        fight_type = "Blap / Gank"
        duration_label = "< 10 seconds"
    elif estimated_seconds < 30:
        fight_type = "Fast Kill"
        duration_label = "10–30 seconds"
    elif estimated_seconds < 90:
        fight_type = "Sustained Brawl"
        duration_label = "30–90 seconds"
    elif estimated_seconds < 300:
        fight_type = "Extended Engagement"
        duration_label = "1–5 minutes"
    else:
        fight_type = "Grinding / Siege"
        duration_label = "5+ minutes"

    if logi_present:
        fight_type += " (Logi Present)"

    # Top attacker damage share
    top_attacker_pct = 0
    if damage_distribution:
        top_damage = max(damage_distribution.values())
        top_attacker_pct = round((top_damage / total_damage) * 100, 1) if total_damage > 0 else 0

    return {
        "estimated_duration": duration_label,
        "estimated_seconds": round(estimated_seconds),
        "fight_type": fight_type,
        "total_damage_dealt": total_damage,
        "ship_base_ehp_estimate": base_ehp,
        "overkill_pct": overkill_pct,
        "attacker_count": attacker_count,
        "logi_present": logi_present,
        "top_attacker_damage_pct": top_attacker_pct
    }


async def extract_fit_from_killmail(kill_id: int, kill_hash: str) -> dict:
    """Extract full fit and fight analysis from a killmail."""
    try:
        r = await get(f"{ESI_BASE}/killmails/{kill_id}/{kill_hash}/", timeout=10.0)
        if r.status_code != 200:
            return {"error": f"Could not fetch killmail {kill_id}"}

        km = r.json()
        victim = km.get("victim", {})
        attackers = km.get("attackers", [])
        ship_type_id = victim.get("ship_type_id")
        items = victim.get("items", [])
        total_damage = victim.get("damage_taken", 0)

        # Resolve ship name and class
        ship_name = "Unknown"
        ship_class = "Unknown"
        if ship_type_id:
            sr = await get(f"{ESI_BASE}/universe/types/{ship_type_id}/", timeout=5.0)
            if sr.status_code == 200:
                ship_data = sr.json()
                ship_name = ship_data.get("name", "Unknown")
                group_id = ship_data.get("group_id")
                if group_id:
                    gr = await get(f"{ESI_BASE}/universe/groups/{group_id}/", timeout=5.0)
                    if gr.status_code == 200:
                        ship_class = gr.json().get("name", "Unknown")

        # Collect all module type IDs — resolve concurrently
        module_ids = [item.get("item_type_id") for item in items if item.get("item_type_id")]
        unique_ids = list(set(module_ids))
        type_data = await resolve_type_names_bulk(unique_ids)

        # Resolve group names concurrently
        group_ids = list(set(
            v["group_id"] for v in type_data.values() if v.get("group_id")
        ))
        group_results = await batch_gather(
            [_fetch_group_name(gid) for gid in group_ids],
            batch_size=15
        )
        group_names = {
            gid: name
            for item in group_results
            if not isinstance(item, Exception)
            for gid, name in [item]
        }

        # Classify modules by slot flag
        high_slots, mid_slots, low_slots, rigs, subsystems, drones = [], [], [], [], [], []

        for item in items:
            type_id = item.get("item_type_id")
            flag = item.get("flag", 0)
            qty = item.get("quantity_destroyed", 0) + item.get("quantity_dropped", 0)
            if qty == 0:
                qty = 1

            info = type_data.get(type_id, {})
            name = info.get("name", f"Unknown[{type_id}]")
            group_id = info.get("group_id")
            group = group_names.get(group_id, "Unknown")
            entry = {"name": name, "qty": qty, "group": group, "type_id": type_id}

            if 27 <= flag <= 34:
                high_slots.append(entry)
            elif 19 <= flag <= 26:
                mid_slots.append(entry)
            elif 11 <= flag <= 18:
                low_slots.append(entry)
            elif 92 <= flag <= 99:
                rigs.append(entry)
            elif 125 <= flag <= 132:
                subsystems.append(entry)
            elif flag in (87, 88, 89):
                drones.append(entry)

        fit_analysis = analyze_fit_modules(
            high_slots, mid_slots, low_slots, rigs, subsystems, ship_name
        )

        attacker_count = len(attackers)
        damage_distribution = {
            str(a.get("character_id", i)): a.get("damage_done", 0)
            for i, a in enumerate(attackers)
        }

        # Check for logi in attackers
        logi_present = any(
            a.get("ship_type_id") in LOGI_TYPE_IDS
            for a in attackers
        )

        if not logi_present:
            attacker_ship_ids = [a.get("ship_type_id") for a in attackers if a.get("ship_type_id")]
            attacker_type_data = await resolve_type_names_bulk(attacker_ship_ids[:20])
            logi_present = any(
                v.get("group_id") in LOGI_GROUP_IDS
                for v in attacker_type_data.values()
            )

        fight_duration = estimate_fight_duration(
            total_damage=total_damage,
            ship_class=ship_class,
            attacker_count=attacker_count,
            logi_present=logi_present,
            damage_distribution=damage_distribution
        )

        top_attackers = sorted(
            attackers, key=lambda a: a.get("damage_done", 0), reverse=True
        )[:5]

        return {
            "kill_id": kill_id,
            "killmail_time": km.get("killmail_time", ""),
            "ship": ship_name,
            "ship_class": ship_class,
            "ship_type_id": ship_type_id,
            "pilot_id": victim.get("character_id"),
            "corp_id": victim.get("corporation_id"),
            "high_slots": high_slots,
            "mid_slots": mid_slots,
            "low_slots": low_slots,
            "rigs": rigs,
            "subsystems": subsystems,
            "drones": drones,
            "fit_analysis": fit_analysis,
            "fight_duration": fight_duration,
            "top_attackers": top_attackers
        }

    except Exception as e:
        return {"error": str(e)}


def analyze_fit_modules(high, mid, low, rigs, subsystems, ship_name) -> dict:
    """Classify and analyze a set of fit modules."""
    all_modules = high + mid + low + rigs + subsystems
    module_names = [m["name"].lower() for m in all_modules]

    shield_tank = any(
        any(k in n for k in ["shield extender", "shield booster", "shield hardener",
                              "shield resistance", "invulnerability"])
        for n in module_names
    )
    armor_tank = any(
        any(k in n for k in ["armor plate", "armor repairer", "armor hardener",
                              "energized", "coating"])
        for n in module_names
    )

    if shield_tank and not armor_tank:
        tank_type = "Shield"
    elif armor_tank and not shield_tank:
        tank_type = "Armor"
    elif shield_tank and armor_tank:
        tank_type = "Mixed"
    else:
        tank_type = "Unknown"

    has_mwd = any("microwarpdrive" in n for n in module_names)
    has_ab = any("afterburner" in n and "microwarpdrive" not in n for n in module_names)
    has_scram = any("warp scrambler" in n for n in module_names)
    has_disruptor = any("warp disruptor" in n for n in module_names)
    has_web = any("stasis web" in n for n in module_names)
    has_neut = any("energy neutralizer" in n or "nosferatu" in n for n in module_names)
    has_ecm = any("ecm" in n or "burst jammer" in n for n in module_names)
    has_damp = any("sensor dampener" in n for n in module_names)
    has_cloak = any("cloak" in n for n in module_names)
    covert_cloak = any("covert ops cloaking" in n for n in module_names)

    weapon_type = "Unknown"
    for n in module_names:
        if any(w in n for w in ["autocannon", "artillery", "railgun", "blaster",
                                  "beam laser", "pulse laser"]):
            weapon_type = "Turret"
            break
        if any(w in n for w in ["missile launcher", "torpedo", "rocket launcher",
                                  "cruise missile", "heavy assault missile"]):
            weapon_type = "Missile"
            break
        if "bomb launcher" in n:
            weapon_type = "Bomb"
            break

    long_range = any(
        any(k in n for k in ["artillery", "railgun", "beam laser", "cruise missile",
                               "torpedo"])
        for n in module_names
    )
    short_range = any(
        any(k in n for k in ["autocannon", "blaster", "pulse laser", "rocket",
                               "heavy assault missile"])
        for n in module_names
    )

    if long_range and not short_range:
        range_profile = "Long Range"
    elif short_range and not long_range:
        range_profile = "Short Range / Brawl"
    else:
        range_profile = "Flexible"

    return {
        "tank_type": tank_type,
        "propulsion": "MWD" if has_mwd else ("AB" if has_ab else "None"),
        "weapon_type": weapon_type,
        "range_profile": range_profile,
        "has_scram": has_scram,
        "has_disruptor": has_disruptor,
        "has_web": has_web,
        "has_neut": has_neut,
        "has_ecm": has_ecm,
        "has_damp": has_damp,
        "has_cloak": has_cloak,
        "covert_cloak": covert_cloak,
    }


async def get_killmail_from_zkill(kill_id: int) -> dict:
    """Fetch killmail hash from zKillboard then full data from ESI."""
    try:
        r = await zkill_get(f"{ZKILL_BASE}/killID/{kill_id}/", timeout=10.0)
        if r.status_code != 200:
            return {"error": f"zKillboard returned {r.status_code}"}

        data = r.json()
        if not data:
            return {"error": f"No killmail found with ID {kill_id}"}

        kill_hash = data[0].get("zkb", {}).get("hash")
        if not kill_hash:
            return {"error": "Could not get killmail hash"}

        return await extract_fit_from_killmail(kill_id, kill_hash)

    except Exception as e:
        return {"error": str(e)}


async def parse_eft_fit(fit_text: str) -> dict:
    """Parse an EFT format fit into structured data."""
    lines = [l.strip() for l in fit_text.strip().split("\n")]

    ship_name = "Unknown"
    fit_name = "Unknown"
    high_slots, mid_slots, low_slots, rigs, subsystems, drones = [], [], [], [], [], []

    if lines and lines[0].startswith("["):
        header = lines[0][1:lines[0].index("]")] if "]" in lines[0] else lines[0][1:]
        if "," in header:
            ship_name, fit_name = header.split(",", 1)
            ship_name = ship_name.strip()
            fit_name = fit_name.strip()
        lines = lines[1:]

    current_section = "high"
    section_break_count = 0

    for line in lines:
        if not line:
            section_break_count += 1
            if section_break_count == 1:
                current_section = "mid"
            elif section_break_count == 2:
                current_section = "low"
            elif section_break_count == 3:
                current_section = "rig"
            elif section_break_count == 4:
                current_section = "subsystem"
            elif section_break_count == 5:
                current_section = "drone"
            continue

        section_break_count = 0
        qty = 1
        name = line

        if " x" in line:
            parts = line.rsplit(" x", 1)
            try:
                qty = int(parts[1].strip())
                name = parts[0].strip()
            except ValueError:
                pass

        if name.startswith("[") or name == "Empty":
            continue

        entry = {"name": name, "qty": qty, "group": "Unknown", "type_id": None}

        if current_section == "high":
            high_slots.append(entry)
        elif current_section == "mid":
            mid_slots.append(entry)
        elif current_section == "low":
            low_slots.append(entry)
        elif current_section == "rig":
            rigs.append(entry)
        elif current_section == "subsystem":
            subsystems.append(entry)
        elif current_section == "drone":
            drones.append(entry)

    analysis = analyze_fit_modules(
        high_slots, mid_slots, low_slots, rigs, subsystems, ship_name
    )

    return {
        "ship": ship_name,
        "fit_name": fit_name,
        "high_slots": high_slots,
        "mid_slots": mid_slots,
        "low_slots": low_slots,
        "rigs": rigs,
        "subsystems": subsystems,
        "drones": drones,
        "analysis": analysis,
        "fight_duration": None
    }


async def compare_fits(enemy_fit: dict, your_fit: dict) -> dict:
    """Compare two parsed fits and return tactical assessment."""
    ea = enemy_fit.get("fit_analysis") or enemy_fit.get("analysis", {})
    ya = your_fit.get("analysis", {})

    enemy_ship = enemy_fit.get("ship", "Unknown")
    your_ship = your_fit.get("ship", "Unknown")
    fight_info = enemy_fit.get("fight_duration", {})

    assessment = []
    win_conditions = []
    loss_conditions = []
    recommendation = "ENGAGE"

    assessment.append(f"Enemy tank: {ea.get('tank_type','?')} | Your tank: {ya.get('tank_type','?')}")
    assessment.append(f"Enemy range: {ea.get('range_profile','?')} | Your range: {ya.get('range_profile','?')}")
    assessment.append(f"Enemy prop: {ea.get('propulsion','?')} | Your prop: {ya.get('propulsion','?')}")

    enemy_has_tackle = ea.get("has_scram") or ea.get("has_disruptor")
    you_have_tackle = ya.get("has_scram") or ya.get("has_disruptor")

    if enemy_has_tackle and not you_have_tackle:
        loss_conditions.append("Enemy can hold you — you cannot hold them back")
        recommendation = "DISENGAGE"
    elif you_have_tackle and not enemy_has_tackle:
        win_conditions.append("You control the fight — enemy cannot escape")

    if ea.get("has_web") and not ya.get("has_web"):
        loss_conditions.append("Enemy web will cripple your speed")
        if ya.get("propulsion") == "MWD":
            loss_conditions.append("Your MWD is nullified by web + scram combo")
    elif ya.get("has_web") and not ea.get("has_web"):
        win_conditions.append("Your web neutralizes their mobility")

    if ea.get("has_neut"):
        loss_conditions.append("Enemy neuts — active tank at risk of cap death")
    if ya.get("has_neut"):
        win_conditions.append("Your neuts can shut down their active tank")

    if ea.get("covert_cloak"):
        loss_conditions.append("Enemy can disengage under covert cloak at will")
    if ya.get("covert_cloak"):
        win_conditions.append("You can bail under cloak if fight goes wrong")

    enemy_range = ea.get("range_profile", "")
    your_range = ya.get("range_profile", "")

    if enemy_range == "Long Range" and your_range == "Short Range / Brawl":
        loss_conditions.append("Enemy wants range — close fast or disengage")
        win_conditions.append("If you can brawl, you win the DPS race at close range")
    elif enemy_range == "Short Range / Brawl" and your_range == "Long Range":
        win_conditions.append("Kite at range — deny them their optimal")
        loss_conditions.append("If they close, your DPS drops significantly")

    if ea.get("has_ecm"):
        loss_conditions.append("ECM can break your lock — fight becomes a lottery")

    # Factor in fight duration from killmail
    if fight_info:
        fight_type = fight_info.get("fight_type", "")
        duration = fight_info.get("estimated_duration", "")
        if fight_info.get("logi_present"):
            loss_conditions.append(f"Previous kill had logi support — expect sustained fight ({duration})")
        assessment.append(f"Previous engagement type: {fight_type} — estimated {duration}")

    if len(loss_conditions) > len(win_conditions) + 1:
        recommendation = "DISENGAGE — unfavorable matchup"
    elif len(win_conditions) >= len(loss_conditions):
        recommendation = "ENGAGE — favorable matchup"
    else:
        recommendation = "SITUATIONAL — depends on execution"

    return {
        "enemy_ship": enemy_ship,
        "your_ship": your_ship,
        "matchup_assessment": assessment,
        "win_conditions": win_conditions,
        "loss_conditions": loss_conditions,
        "recommendation": recommendation,
        "fight_duration_context": fight_info
    }
