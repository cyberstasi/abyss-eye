import httpx

ESI_BASE = "https://esi.evetech.net/latest"

# Dogma attribute IDs we care about
ATTR_HI_SLOTS = 14
ATTR_MED_SLOTS = 13
ATTR_LOW_SLOTS = 12
ATTR_RIG_SLOTS = 1137
ATTR_CPU = 48
ATTR_POWER = 11
ATTR_MASS = 4
ATTR_SIGNATURE = 552
ATTR_MAX_VELOCITY = 37
ATTR_CAPACITOR = 482

# Propulsion module mass requirements (approximate kg thresholds)
# Based on module naming conventions
PROP_SIZE_MASS = {
    "1mn":   5_000_000,      # up to 5,000t
    "5mn":   15_000_000,     # up to 15,000t
    "10mn":  100_000_000,    # up to 100,000t (cruisers/BCs)
    "50mn":  100_000_000,    # battlecruiser range
    "100mn": 900_000_000,    # battleships only
    "500mn": 9_000_000_000,  # capitals only
}

# CPU/PG rough estimates for common modules (fallback if ESI lookup fails)
# Format: module_keyword -> (cpu, pg)
MODULE_RESOURCE_ESTIMATES = {
    "large shield extender": (50, 200),
    "medium shield extender": (30, 100),
    "small shield extender": (15, 50),
    "microwarpdrive": (50, 100),
    "afterburner": (20, 50),
    "warp scrambler": (10, 1),
    "warp disruptor": (20, 1),
    "stasis web": (20, 1),
    "energy neutralizer": (60, 50),
    "armor plate": (0, 100),
    "armor repairer": (30, 50),
}


async def get_ship_attributes(ship_name: str) -> dict:
    """
    Look up a ship's fitting attributes from ESI.
    Returns slots, CPU, PG, mass, and other relevant stats.
    """
    async with httpx.AsyncClient() as client:
        try:
            # Resolve ship name to type_id
            res = await client.post(
                f"{ESI_BASE}/universe/ids/",
                json=[ship_name],
                timeout=10.0
            )
            if res.status_code != 200:
                return {"error": f"Could not resolve ship name: {ship_name}"}

            data = res.json()
            types = data.get("inventory_types", [])
            if not types:
                return {"error": f"Ship not found: {ship_name}"}

            type_id = types[0]["id"]

            # Fetch dogma attributes
            dogma_res = await client.get(
                f"{ESI_BASE}/universe/types/{type_id}/",
                timeout=10.0
            )
            if dogma_res.status_code != 200:
                return {"error": "Could not fetch ship data"}

            type_data = dogma_res.json()
            dogma_attrs = {
                attr["attribute_id"]: attr["value"]
                for attr in type_data.get("dogma_attributes", [])
            }

            # Get group for ship class
            group_id = type_data.get("group_id")
            ship_class = "Unknown"
            if group_id:
                gr = await client.get(
                    f"{ESI_BASE}/universe/groups/{group_id}/",
                    timeout=5.0
                )
                if gr.status_code == 200:
                    ship_class = gr.json().get("name", "Unknown")

            return {
                "ship_name": ship_name,
                "type_id": type_id,
                "ship_class": ship_class,
                "hi_slots": int(dogma_attrs.get(ATTR_HI_SLOTS, 0)),
                "med_slots": int(dogma_attrs.get(ATTR_MED_SLOTS, 0)),
                "low_slots": int(dogma_attrs.get(ATTR_LOW_SLOTS, 0)),
                "rig_slots": int(dogma_attrs.get(ATTR_RIG_SLOTS, 3)),
                "cpu_output": dogma_attrs.get(ATTR_CPU, 0),
                "pg_output": dogma_attrs.get(ATTR_POWER, 0),
                "mass_kg": dogma_attrs.get(ATTR_MASS, 0),
                "signature_radius": dogma_attrs.get(ATTR_SIGNATURE, 0),
                "max_velocity": dogma_attrs.get(ATTR_MAX_VELOCITY, 0),
                "capacitor_capacity": dogma_attrs.get(ATTR_CAPACITOR, 0),
            }

        except Exception as e:
            return {"error": str(e)}


def get_prop_size_from_name(module_name: str) -> str:
    """Extract propulsion module size from name."""
    name_lower = module_name.lower()
    for size in ["500mn", "100mn", "50mn", "10mn", "5mn", "1mn"]:
        if size in name_lower:
            return size
    return None


def validate_fit(ship_attrs: dict, high_slots: list, mid_slots: list,
                 low_slots: list, rigs: list, subsystems: list) -> list:
    """
    Validate a fit against ship attributes.
    Returns a list of validation warnings.
    """
    warnings = []

    if "error" in ship_attrs:
        return [f"Could not validate fit: {ship_attrs['error']}"]

    ship_mass = ship_attrs.get("mass_kg", 0)
    ship_class = ship_attrs.get("ship_class", "Unknown")

    # Slot count validation
    hi_count = len([m for m in high_slots if m.get("name") != "Empty"])
    med_count = len([m for m in mid_slots if m.get("name") != "Empty"])
    low_count = len([m for m in low_slots if m.get("name") != "Empty"])
    rig_count = len([m for m in rigs if m.get("name") != "Empty"])

    if hi_count > ship_attrs.get("hi_slots", 99):
        warnings.append(
            f"⚠️ Too many high slot modules ({hi_count} fitted, {ship_attrs['hi_slots']} available)"
        )
    if med_count > ship_attrs.get("med_slots", 99):
        warnings.append(
            f"⚠️ Too many mid slot modules ({med_count} fitted, {ship_attrs['med_slots']} available)"
        )
    if low_count > ship_attrs.get("low_slots", 99):
        warnings.append(
            f"⚠️ Too many low slot modules ({low_count} fitted, {ship_attrs['low_slots']} available)"
        )
    if rig_count > ship_attrs.get("rig_slots", 3):
        warnings.append(
            f"⚠️ Too many rigs ({rig_count} fitted, {ship_attrs['rig_slots']} available)"
        )

    # Propulsion size validation
    all_modules = high_slots + mid_slots + low_slots
    for module in all_modules:
        name = module.get("name", "")
        name_lower = name.lower()

        if any(prop in name_lower for prop in ["afterburner", "microwarpdrive"]):
            prop_size = get_prop_size_from_name(name)
            if prop_size and ship_mass > 0:
                max_mass = PROP_SIZE_MASS.get(prop_size, 0)
                if ship_mass > max_mass:
                    warnings.append(
                        f"⚠️ {name} requires a lighter ship — "
                        f"{ship_class} ({ship_mass/1_000_000:.0f}kt) exceeds "
                        f"{prop_size.upper()} mass limit ({max_mass/1_000_000:.0f}kt)"
                    )
                elif ship_mass < max_mass / 20:
                    # Module is way too big for the ship
                    warnings.append(
                        f"⚠️ {name} is oversized for {ship_class} — "
                        f"consider a smaller propulsion module"
                    )

    # T3 subsystem validation
    if ship_class == "Strategic Cruiser":
        sub_count = len(subsystems)
        if sub_count > 0 and sub_count < 5:
            warnings.append(
                f"⚠️ Strategic Cruiser has {sub_count}/5 subsystems fitted"
            )

    # Cloak + MWD incompatibility (can't warp cloaked with MWD)
    module_names_lower = [m.get("name", "").lower() for m in all_modules]
    has_covert_cloak = any("covert ops cloaking" in n for n in module_names_lower)
    has_mwd = any("microwarpdrive" in n for n in module_names_lower)
    has_regular_cloak = any(
        "cloaking device" in n and "covert" not in n
        for n in module_names_lower
    )

    if has_regular_cloak and has_mwd:
        warnings.append(
            "⚠️ Standard cloak + MWD: cannot activate MWD while cloaked "
            "(use Covert Ops cloak for cloak+MWD trick)"
        )

    return warnings
