import httpx

ESI_BASE = "https://esi.evetech.net/latest"
FUZZWORK_BASE = "https://market.fuzzwork.co.uk/aggregates"
JANICE_BASE = "https://janice.e-351.com/api/rest/v2"

JITA_STATION_ID = 60003760

BLUE_LOOT_PRICES = {
    30370: ("Sleeper Data Library", 1_000_000),
    30371: ("Sleeper Drone AI Nexus", 2_000_000),
    30372: ("Sleeper Drone Navigation Unit", 3_000_000),
    30373: ("Sleeper Drone Tactical Limiter", 3_000_000),
    30374: ("Sleeper Interface Nexus", 4_000_000),
    30375: ("Sleeper Mainframe", 5_000_000),
    30376: ("Sleeper Nano-Ribbon", 100_000),
    30377: ("Sleeper Ruined Drone Schematics", 50_000),
    30378: ("Sleeper Ruined Explosive Device", 50_000),
    30379: ("Sleeper Ruined Hull Section", 50_000),
    30380: ("Sleeper Ruined Power Core", 50_000),
    30381: ("Sleeper Ruined Weapon Subroutines", 50_000),
    30383: ("Sleeper Sacred Manufactory", 7_000_000),
    30384: ("Sleeper Ancient Coords Database", 8_000_000),
    30385: ("Sleeper Preserved Relic", 10_000_000),
    30386: ("Sleeper Antique Drone AI", 12_000_000),
    30387: ("Unstable Wormhole Data", 500_000),
    30395: ("Talocan Data Acquisition Unit", 2_000_000),
    30396: ("Talocan Power Conduit", 3_000_000),
    30397: ("Talocan Plasmitic Neurolink", 4_000_000),
    30398: ("Talocan Polycarbonate Casing", 5_000_000),
    30399: ("Talocan Scattered Vessel Logs", 1_000_000),
    30400: ("Talocan Tectonic Plate", 6_000_000),
}

PUSHX_RATE_PER_M3 = 600
PUSHX_MINIMUM = 1_000_000
BROKER_FEE = 0.03
SALES_TAX = 0.036


async def appraise_loot(loot_text: str) -> dict:
    """Appraise a loot list using Janice API."""
    try:
        async with httpx.AsyncClient() as client:
            res = await client.post(
                f"{JANICE_BASE}/appraisal",
                params={"designation": "appraisal", "pricing": "split"},
                headers={
                    "X-ApiKey": "janice",
                    "Content-Type": "text/plain",
                    "Accept": "application/json"
                },
                content=loot_text.encode(),
                timeout=15.0
            )
            if res.status_code != 200:
                return {"error": f"Janice API returned {res.status_code}"}

            data = res.json()
            items = data.get("items", [])
            parsed_items = []
            for item in items[:20]:
                parsed_items.append({
                    "name": item.get("itemType", {}).get("name", "Unknown"),
                    "quantity": item.get("amount", 0),
                    "buy": item.get("buyPrice", 0),
                    "sell": item.get("sellPrice", 0),
                })

            return {
                "total_buy_isk": data.get("totalBuyPrice", 0),
                "total_sell_isk": data.get("totalSellPrice", 0),
                "total_split_isk": data.get("totalSplitPrice", 0),
                "item_count": len(items),
                "items": parsed_items,
                "janice_link": data.get("appraisalLink", "")
            }
    except Exception as e:
        return {"error": str(e)}


async def get_market_price(item_name: str) -> dict:
    """Get current Jita buy/sell price for an item."""
    try:
        async with httpx.AsyncClient() as client:
            # Resolve name to type_id
            res = await client.post(
                f"{ESI_BASE}/universe/ids/",
                json=[item_name],
                timeout=10.0
            )
            if res.status_code != 200:
                return {"error": "Could not resolve item name"}

            data = res.json()
            inventory_types = data.get("inventory_types", [])
            if not inventory_types:
                return {"error": f"No item found with name '{item_name}'"}

            type_id = inventory_types[0]["id"]
            resolved_name = inventory_types[0]["name"]

            # Fetch Jita prices from Fuzzwork
            market_res = await client.get(
                f"{FUZZWORK_BASE}/",
                params={"station": JITA_STATION_ID, "types": type_id},
                timeout=10.0
            )
            if market_res.status_code != 200:
                return {"error": "Could not fetch market data"}

            market_data = market_res.json().get(str(type_id), {})
            buy = market_data.get("buy", {})
            sell = market_data.get("sell", {})

            jita_buy = float(buy.get("max", 0) or 0)
            jita_sell = float(sell.get("min", 0) or 0)

            return {
                "item": resolved_name,
                "type_id": type_id,
                "jita_buy": jita_buy,
                "jita_sell": jita_sell,
                "buy_volume": int(float(buy.get("volume", 0) or 0)),
                "sell_volume": int(float(sell.get("volume", 0) or 0)),
                "spread_pct": round(
                    ((jita_sell - jita_buy) / jita_sell) * 100, 2
                ) if jita_sell > 0 else 0
            }
    except Exception as e:
        return {"error": str(e)}


async def calculate_haul(loot_value_isk: float, volume_m3: float = 0) -> dict:
    """Calculate net profit after hauling fees and taxes."""
    if volume_m3 > 0:
        hauling_fee = max(volume_m3 * PUSHX_RATE_PER_M3, PUSHX_MINIMUM)
    else:
        est_volume = loot_value_isk / 300_000
        hauling_fee = max(est_volume * PUSHX_RATE_PER_M3, PUSHX_MINIMUM)

    tax_total = loot_value_isk * (BROKER_FEE + SALES_TAX)
    net_profit = loot_value_isk - hauling_fee - tax_total
    margin_pct = round((net_profit / loot_value_isk) * 100, 1) if loot_value_isk > 0 else 0

    return {
        "gross_value_isk": loot_value_isk,
        "hauling_fee_isk": round(hauling_fee),
        "tax_and_fees_isk": round(tax_total),
        "net_profit_isk": round(net_profit),
        "margin_pct": margin_pct,
        "worth_hauling": net_profit > 0
    }


async def value_blue_loot(loot_text: str) -> dict:
    """Value blue loot using fixed NPC buy prices."""
    lines = loot_text.strip().split("\n")
    results = []
    total = 0

    name_lookup = {
        name.lower(): (tid, price)
        for tid, (name, price) in BLUE_LOOT_PRICES.items()
    }

    unrecognized = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        qty = 1
        name = line

        if " x " in line.lower():
            parts = line.rsplit(" x ", 1)
            name = parts[0].strip()
            try:
                qty = int(parts[1].strip().replace(",", ""))
            except ValueError:
                qty = 1

        match = name_lookup.get(name.lower())
        if match:
            type_id, unit_price = match
            item_total = unit_price * qty
            total += item_total
            results.append({
                "name": name,
                "quantity": qty,
                "unit_price_isk": unit_price,
                "total_isk": item_total
            })
        else:
            unrecognized.append(name)

    return {
        "items": results,
        "total_isk": total,
        "unrecognized_items": unrecognized,
        "note": "Blue loot prices are fixed NPC buy prices at Outer Ring stations"
    }


async def get_fit_cost(fit_text: str) -> dict:
    """Estimate Jita cost of an EFT-format fit."""
    lines = fit_text.strip().split("\n")
    items = {}

    for line in lines:
        line = line.strip()
        if not line or line.startswith("//") or line.startswith("#"):
            continue
        if line.startswith("[") and "," in line:
            ship = line[1:line.index(",")].strip()
            items[ship] = items.get(ship, 0) + 1
        elif line.startswith("["):
            continue
        else:
            if " x" in line:
                parts = line.rsplit(" x", 1)
                name = parts[0].strip()
                try:
                    qty = int(parts[1].strip())
                except ValueError:
                    qty = 1
            else:
                name = line
                qty = 1
            if name:
                items[name] = items.get(name, 0) + qty

    if not items:
        return {"error": "Could not parse any items from fit"}

    all_names = list(items.keys())
    type_ids = {}

    try:
        async with httpx.AsyncClient() as client:
            res = await client.post(
                f"{ESI_BASE}/universe/ids/",
                json=all_names,
                timeout=10.0
            )
            if res.status_code == 200:
                data = res.json()
                for entry in data.get("inventory_types", []):
                    type_ids[entry["name"].lower()] = entry["id"]

            id_list = list(type_ids.values())
            if not id_list:
                return {"error": "Could not resolve any item names to type IDs"}

            market_res = await client.get(
                f"{FUZZWORK_BASE}/",
                params={"station": JITA_STATION_ID, "types": ",".join(map(str, id_list))},
                timeout=10.0
            )
            market_data = market_res.json() if market_res.status_code == 200 else {}

            breakdown = []
            total = 0
            unpriced = []

            for name, qty in items.items():
                tid = type_ids.get(name.lower())
                if not tid:
                    unpriced.append(name)
                    continue
                mdata = market_data.get(str(tid), {})
                sell_min = float(mdata.get("sell", {}).get("min", 0) or 0)
                item_total = sell_min * qty
                total += item_total
                breakdown.append({
                    "name": name,
                    "quantity": qty,
                    "unit_price_isk": sell_min,
                    "total_isk": item_total
                })

            breakdown.sort(key=lambda x: x["total_isk"], reverse=True)

            return {
                "total_fit_cost_isk": round(total),
                "breakdown": breakdown,
                "unpriced_items": unpriced
            }

    except Exception as e:
        return {"error": str(e)}