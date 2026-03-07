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
- Ranked pilot list with kill counts
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
        by analyzing recent kill activity. Returns pilot names, kill counts, and
        most used ships. Use when asked who the dangerous pilots are in a corp,
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
    }
]


async def get_pilot_intel(pilot_name: str) -> str:
    """Fetch full pilot intel from ESI and zKillboard."""
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

        analysis = await analyze_pilot_killboard(
            kills, losses, stats, character_id
        )

        return json.dumps({
            "profile": profile,
            "analysis": analysis
        }, indent=2)

    except Exception as e:
        return f"Error fetching pilot intel: {str(e)}"


async def get_corp_intel(corp_name: str) -> str:
    """Fetch full corp intel from ESI and zKillboard."""
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
        efficiency = 0
        if isk_destroyed + isk_lost > 0:
            efficiency = round(
                (isk_destroyed / (isk_destroyed + isk_lost)) * 100, 1
            )

        timezones = {}
        for kill in kills[:25]:
            for label in kill.get("zkb", {}).get("labels", []):
                if label.startswith("tz:"):
                    tz = label.replace("tz:", "").upper()
                    timezones[tz] = timezones.get(tz, 0) + 1

        dominant_tz = max(
            timezones, key=timezones.get
        ) if timezones else "Unknown"

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
    """Fetch top active pilots in a corp from kill data."""
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
    """Fetch full k-space system intel."""
    try:
        intel = await get_full_system_intel(system_name)
        if not intel:
            return f"No system found with name '{system_name}'"
        return json.dumps(intel, indent=2)
    except Exception as e:
        return f"Error fetching system intel: {str(e)}"


async def get_wormhole_intel_tool(system_name: str) -> str:
    """Fetch full wormhole system intel."""
    try:
        intel = await get_full_wormhole_intel(system_name)
        if not intel:
            return f"No wormhole system found with name '{system_name}'"
        return json.dumps(intel, indent=2)
    except Exception as e:
        return f"Error fetching wormhole intel: {str(e)}"


async def process_tool_call(tool_name: str, tool_input: dict) -> str:
    """Route tool calls to the correct handler."""
    handlers = {
        "get_pilot_intel": lambda: get_pilot_intel(tool_input["pilot_name"]),
        "get_corp_intel": lambda: get_corp_intel(tool_input["corp_name"]),
        "get_corp_top_pilots": lambda: get_corp_top_pilots_tool(tool_input["corp_name"]),
        "get_system_intel": lambda: get_system_intel_tool(tool_input["system_name"]),
        "get_wormhole_intel": lambda: get_wormhole_intel_tool(tool_input["system_name"]),
    }
    handler = handlers.get(tool_name)
    if handler:
        return await handler()
    return f"Unknown tool: {tool_name}"


conversation_history = []


async def chat_async(user_message: str) -> str:
    """Main async chat function with tool use support."""
    conversation_history.append({
        "role": "user",
        "content": user_message
    })

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

            conversation_history.append({
                "role": "assistant",
                "content": response.content
            })
            conversation_history.append({
                "role": "user",
                "content": tool_results
            })

        else:
            final_text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    final_text += block.text

            conversation_history.append({
                "role": "assistant",
                "content": final_text
            })

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