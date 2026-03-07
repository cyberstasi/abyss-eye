import os
import json
import asyncio
from anthropic import Anthropic
from dotenv import load_dotenv
from tools.esi import get_full_pilot_profile, search_corporation
from tools.zkill import (get_pilot_kills, get_pilot_losses,
                          get_pilot_stats, get_corp_kills,
                          get_corp_losses, get_corp_stats,
                          analyze_pilot_killboard,
                          get_corp_top_pilots)
from tools.dotlan import get_full_system_intel
from tools.wormhole import get_full_wormhole_intel
from tools.trader import (appraise_loot, get_market_price, calculate_haul,
                           value_blue_loot, get_fit_cost)

load_dotenv()

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

EVE_SYSTEM_PROMPT = """You are AURA, an elite EVE Online AI assistant built for a wormhole corporation.

You have deep knowledge of:
- EVE Online game mechanics, ships, modules, and fittings
- Wormhole space (j-space) operations, signatures, and mass mechanics
- PvP combat, fleet doctrines, and threat assessment
- Market trading, industry, and ISK making
- Corporation and alliance politics

You are direct, tactical, and speak like an experienced FC and industrialist.
You use EVE terminology naturally. You don't over-explain basic game concepts
unless asked.

You have access to live tools. When a user asks about a pilot, corporation,
or system, ALWAYS use your tools to get real data before responding.
Never guess or use training data when live data is available.

PILOT THREAT CARDS must always include:
- Threat level: 🔴 HIGH / 🟡 MEDIUM / 🟢 LOW
- Corp and alliance affiliation
- ISK efficiency and kill/loss stats
- Top ships flown by name
- Solo vs fleet behavior and avg gang size
- Active timezone
- Activity recency flag
- WH pilot flag if applicable
- Capital capability if applicable
- Awox flag if applicable
- Tactical recommendation

CORP INTEL must always include:
- Alliance affiliation and member count
- ISK efficiency and kill stats
- Known behavior patterns from kill data
- Tactical recommendation

CORP TOP PILOTS must always include:
- Ranked pilot list with kill counts and K/D ratio
- Most used ship per pilot
- Brief threat note on top 3

SYSTEM INTEL must always include:
- Security class
- Recent kill activity with rating
- Jump traffic
- Tactical recommendation

WORMHOLE INTEL must always include:
- WH class and difficulty
- Likely residents with corp and alliance names
- Activity pattern and dominant timezone
- Capital activity flag
- Tactical recommendation

TRADER responses must always include:
- Clear ISK totals in readable format (B/M suffix)
- Buy vs sell price where relevant
- Net profit after fees where applicable
- Clear recommendation

Always be concise. Format responses cleanly. Use emoji for threat levels
and status indicators."""

TOOLS = [
    {
        "name": "get_pilot_intel",
        "description": """Get complete intel on an EVE pilot. Fetches ESI profile,
        zKillboard kill history, ship analysis, timezone detection, WH pilot flag,
        capital capability, awox history, and activity recency. Use whenever a user
        asks about a specific pilot or character.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "pilot_name": {
                    "type": "string",
                    "description": "The exact name of the EVE pilot to look up"
                }
            },
            "required": ["pilot_name"]
        }
    },
    {
        "name": "get_corp_intel",
        "description": """Get complete intel on an EVE corporation. Fetches ESI profile,
        member count, alliance, zKillboard kill/loss history and ISK stats.
        Use whenever a user asks about a corporation or alliance.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "corp_name": {
                    "type": "string",
                    "description": "The name of the EVE corporation to look up"
                }
            },
            "required": ["corp_name"]
        }
    },
    {
        "name": "get_corp_top_pilots",
        "description": """Get the most active and dangerous pilots in a corporation
        by analyzing recent kill activity. Returns pilot names, kill counts, K/D ratio,
        and most used ships. Use when asked who the dangerous pilots are in a corp,
        who to watch out for, or who the FCs are.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "corp_name": {
                    "type": "string",
                    "description": "The name of the EVE corporation"
                }
            },
            "required": ["corp_name"]
        }
    },
    {
        "name": "get_system_intel",
        "description": """Get live intel on a k-space EVE system. Returns security status,
        ship kills, pod kills, NPC kills, and jump count from the last hour.
        Use for highsec, lowsec, and nullsec systems.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "system_name": {
                    "type": "string",
                    "description": "The name of the k-space system e.g. Jita, Amarr, GE-8JV"
                }
            },
            "required": ["system_name"]
        }
    },
    {
        "name": "get_wormhole_intel",
        "description": """Get detailed intel on a wormhole system. Returns WH class,
        difficulty, activity level, likely resident corps and alliances identified
        from kill history, dominant timezone, capital activity, and tactical assessment.
        Use when a user asks about a J-system or wormhole system.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "system_name": {
                    "type": "string",
                    "description": "The name of the wormhole system e.g. J105934"
                }
            },
            "required": ["system_name"]
        }
    },
    {
        "name": "appraise_loot",
        "description": """Appraise a list of items using Janice to get Jita buy/sell value.
        Use when a user pastes loot, a cargo scan, or asks what their items are worth.
        Input should be item names with optional quantities like 'Tritanium x 1000'.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "loot_text": {
                    "type": "string",
                    "description": "Raw loot list, one item per line. Format: 'Item Name x Quantity' or just 'Item Name'"
                }
            },
            "required": ["loot_text"]
        }
    },
    {
        "name": "get_market_price",
        "description": """Get current Jita buy and sell price for a specific EVE item.
        Use when a user asks what something is worth or what the current price is.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "item_name": {
                    "type": "string",
                    "description": "The exact name of the EVE item"
                }
            },
            "required": ["item_name"]
        }
    },
    {
        "name": "calculate_haul",
        "description": """Calculate net profit after hauling fees and taxes for a loot haul.
        Use when a user wants to know if a haul is worth it or what they'll net after fees.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "loot_value_isk": {
                    "type": "number",
                    "description": "Total ISK value of the loot"
                },
                "volume_m3": {
                    "type": "number",
                    "description": "Volume of the loot in m3. Use 0 if unknown."
                }
            },
            "required": ["loot_value_isk"]
        }
    },
    {
        "name": "value_blue_loot",
        "description": """Value wormhole blue loot using fixed NPC buy prices.
        Use when a user asks about blue loot value from WH sites like Sleeper loot.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "loot_text": {
                    "type": "string",
                    "description": "Blue loot list, one item per line. Format: 'Item Name x Quantity'"
                }
            },
            "required": ["loot_text"]
        }
    },
    {
        "name": "get_fit_cost",
        "description": """Calculate the Jita market cost of an EVE ship fitting.
        Accepts EFT format fits. Use when a user pastes a fit and wants to know what it costs.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "fit_text": {
                    "type": "string",
                    "description": "Ship fitting in EFT format"
                }
            },
            "required": ["fit_text"]
        }
    }
]


async def get_pilot_intel(pilot_name: str) -> str:
    try:
        profile = await get_full_pilot_profile(pilot_name)
        if not profile:
            return f"No pilot found with name '{pilot_name}'"
        character_id = profile["character_id"]
        kills, losses, stats = await asyncio.gather(
            get_pilot_kills(character_id),
            get_pilot_losses(character_id),
            get_pilot_stats(character_id)
        )
        analysis = await analyze_pilot_killboard(kills, losses, stats, character_id)
        return json.dumps({"profile": profile, "analysis": analysis}, indent=2)
    except Exception as e:
        return f"Error fetching pilot intel: {str(e)}"


async def get_corp_intel(corp_name: str) -> str:
    try:
        corp = await search_corporation(corp_name)
        if not corp:
            return f"No corporation found with name '{corp_name}'"
        corp_id = corp["corporation_id"]
        kills, losses, stats = await asyncio.gather(
            get_corp_kills(corp_id),
            get_corp_losses(corp_id),
            get_corp_stats(corp_id)
        )
        isk_destroyed = stats.get("iskDestroyed", 0)
        isk_lost = stats.get("iskLost", 0)
        efficiency = round(
            (isk_destroyed / (isk_destroyed + isk_lost)) * 100, 1
        ) if isk_destroyed + isk_lost > 0 else 0
        timezones = {}
        for kill in kills[:25]:
            for label in kill.get("zkb", {}).get("labels", []):
                if label.startswith("tz:"):
                    tz = label.replace("tz:", "").upper()
                    timezones[tz] = timezones.get(tz, 0) + 1
        dominant_tz = max(timezones, key=timezones.get) if timezones else "Unknown"
        capital_capable = any(
            loss.get("zkb", {}).get("totalValue", 0) > 1_000_000_000
            for loss in losses[:10]
        )
        return json.dumps({
            "corp_profile": corp,
            "stats": {
                "total_kills": stats.get("shipsDestroyed", 0),
                "total_losses": stats.get("shipsLost", 0),
                "isk_efficiency": efficiency,
                "isk_destroyed_bil": round(isk_destroyed / 1_000_000_000, 2),
                "isk_lost_bil": round(isk_lost / 1_000_000_000, 2),
                "dominant_timezone": dominant_tz,
                "capital_capable": capital_capable
            }
        }, indent=2)
    except Exception as e:
        return f"Error fetching corp intel: {str(e)}"


async def get_corp_top_pilots_tool(corp_name: str) -> str:
    try:
        corp = await search_corporation(corp_name)
        if not corp:
            return f"No corporation found with name '{corp_name}'"
        corp_id = corp["corporation_id"]
        top_pilots = await get_corp_top_pilots(corp_id)
        return json.dumps({
            "corp_name": corp["name"],
            "corp_ticker": corp["ticker"],
            "top_pilots": top_pilots
        }, indent=2)
    except Exception as e:
        return f"Error fetching corp pilots: {str(e)}"


async def get_system_intel_tool(system_name: str) -> str:
    try:
        intel = await get_full_system_intel(system_name)
        if not intel:
            return f"No system found with name '{system_name}'"
        return json.dumps(intel, indent=2)
    except Exception as e:
        return f"Error fetching system intel: {str(e)}"


async def get_wormhole_intel_tool(system_name: str) -> str:
    try:
        intel = await get_full_wormhole_intel(system_name)
        if not intel:
            return f"No wormhole system found with name '{system_name}'"
        return json.dumps(intel, indent=2)
    except Exception as e:
        return f"Error fetching wormhole intel: {str(e)}"


async def appraise_loot_tool(loot_text: str) -> str:
    try:
        result = await appraise_loot(loot_text)
        return json.dumps(result, indent=2)
    except Exception as e:
        return f"Error appraising loot: {str(e)}"


async def get_market_price_tool(item_name: str) -> str:
    try:
        result = await get_market_price(item_name)
        return json.dumps(result, indent=2)
    except Exception as e:
        return f"Error fetching price: {str(e)}"


async def calculate_haul_tool(loot_value_isk: float, volume_m3: float = 0) -> str:
    try:
        result = await calculate_haul(loot_value_isk, volume_m3)
        return json.dumps(result, indent=2)
    except Exception as e:
        return f"Error calculating haul: {str(e)}"


async def value_blue_loot_tool(loot_text: str) -> str:
    try:
        result = await value_blue_loot(loot_text)
        return json.dumps(result, indent=2)
    except Exception as e:
        return f"Error valuing blue loot: {str(e)}"


async def get_fit_cost_tool(fit_text: str) -> str:
    try:
        result = await get_fit_cost(fit_text)
        return json.dumps(result, indent=2)
    except Exception as e:
        return f"Error calculating fit cost: {str(e)}"


async def process_tool_call(tool_name: str, tool_input: dict) -> str:
    handlers = {
        "get_pilot_intel": lambda: get_pilot_intel(tool_input["pilot_name"]),
        "get_corp_intel": lambda: get_corp_intel(tool_input["corp_name"]),
        "get_corp_top_pilots": lambda: get_corp_top_pilots_tool(tool_input["corp_name"]),
        "get_system_intel": lambda: get_system_intel_tool(tool_input["system_name"]),
        "get_wormhole_intel": lambda: get_wormhole_intel_tool(tool_input["system_name"]),
        "appraise_loot": lambda: appraise_loot_tool(tool_input["loot_text"]),
        "get_market_price": lambda: get_market_price_tool(tool_input["item_name"]),
        "calculate_haul": lambda: calculate_haul_tool(
            tool_input["loot_value_isk"], tool_input.get("volume_m3", 0)
        ),
        "value_blue_loot": lambda: value_blue_loot_tool(tool_input["loot_text"]),
        "get_fit_cost": lambda: get_fit_cost_tool(tool_input["fit_text"]),
    }
    handler = handlers.get(tool_name)
    if handler:
        return await handler()
    return f"Unknown tool: {tool_name}"


conversation_history = []


async def chat_async(user_message: str) -> str:
    conversation_history.append({"role": "user", "content": user_message})

    while True:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=8096,
            system=EVE_SYSTEM_PROMPT,
            tools=TOOLS,
            messages=conversation_history
        )

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    print(f"[AURA] Calling tool: {block.name}({block.input})")
                    result = await process_tool_call(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result
                    })
            conversation_history.append({"role": "assistant", "content": response.content})
            conversation_history.append({"role": "user", "content": tool_results})

        else:
            final_text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    final_text += block.text
            conversation_history.append({"role": "assistant", "content": final_text})
            return final_text


if __name__ == "__main__":
    async def main():
        print("AURA Online. Type 'exit' to quit.\n")
        while True:
            user_input = input("You: ").strip()
            if user_input.lower() == "exit":
                break
            if user_input:
                response = await chat_async(user_input)
                print(f"\nAURA: {response}\n")

    asyncio.run(main())
