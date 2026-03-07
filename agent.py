import os
import json
import asyncio
from anthropic import Anthropic
from dotenv import load_dotenv
from tools.esi import get_full_pilot_profile, search_corporation
from tools.zkill import (get_pilot_kills, get_pilot_losses, 
                          get_pilot_stats, get_corp_kills, 
                          get_corp_losses, get_corp_stats, 
                          analyze_pilot_killboard)
from tools.dotlan import get_full_system_intel

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

When presenting pilot intel, always include:
- Threat level (🔴 HIGH / 🟡 MEDIUM / 🟢 LOW)
- Corp and alliance
- Kill efficiency and ISK stats
- Behavior analysis (solo/fleet, gang size, activity)
- Tactical recommendation

When presenting system intel, always include:
- Security class and status
- Recent kill activity with activity rating
- Tactical recommendation for the situation

Always be concise. Format responses cleanly. Use emoji for threat levels 
and status indicators."""

# Tool definitions for Claude
TOOLS = [
    {
        "name": "get_pilot_intel",
        "description": "Get complete intel on an EVE pilot including their ESI profile, kill history, losses, and behavioral analysis from zKillboard. Use this whenever a user asks about a specific pilot or character.",
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
        "description": "Get complete intel on an EVE corporation including member count, alliance, kill history and stats from zKillboard. Use this whenever a user asks about a corporation or alliance.",
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
        "name": "get_system_intel",
        "description": "Get complete intel on an EVE system including security status, recent kills, pod kills, NPC kills and jump activity. Use this whenever a user asks about a system, whether k-space or wormhole space.",
        "input_schema": {
            "type": "object",
            "properties": {
                "system_name": {
                    "type": "string",
                    "description": "The name of the EVE system to look up"
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

        analysis = await analyze_pilot_killboard(kills, losses, stats)

        return json.dumps({
            "profile": profile,
            "analysis": analysis,
            "recent_kills_sample": kills[:5],
            "recent_losses_sample": losses[:5]
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

        total_kills = stats.get("shipsDestroyed", 0)
        total_losses = stats.get("shipsLost", 0)
        isk_destroyed = stats.get("iskDestroyed", 0)
        isk_lost = stats.get("iskLost", 0)
        efficiency = 0
        if isk_destroyed + isk_lost > 0:
            efficiency = round(
                (isk_destroyed / (isk_destroyed + isk_lost)) * 100, 1
            )

        return json.dumps({
            "corp_profile": corp,
            "stats": {
                "total_kills": total_kills,
                "total_losses": total_losses,
                "isk_efficiency": efficiency,
                "isk_destroyed_bil": round(isk_destroyed / 1_000_000_000, 2),
                "isk_lost_bil": round(isk_lost / 1_000_000_000, 2)
            },
            "recent_kills_sample": kills[:5],
            "recent_losses_sample": losses[:5]
        }, indent=2)

    except Exception as e:
        return f"Error fetching corp intel: {str(e)}"

async def get_system_intel_tool(system_name: str) -> str:
    """Fetch full system intel."""
    try:
        intel = await get_full_system_intel(system_name)
        if not intel:
            return f"No system found with name '{system_name}'"
        return json.dumps(intel, indent=2)
    except Exception as e:
        return f"Error fetching system intel: {str(e)}"

async def process_tool_call(tool_name: str, tool_input: dict) -> str:
    """Route tool calls to the right function."""
    if tool_name == "get_pilot_intel":
        return await get_pilot_intel(tool_input["pilot_name"])
    elif tool_name == "get_corp_intel":
        return await get_corp_intel(tool_input["corp_name"])
    elif tool_name == "get_system_intel":
        return await get_system_intel_tool(tool_input["system_name"])
    else:
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

        # If Claude wants to use a tool
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

            # Add assistant response and tool results to history
            conversation_history.append({
                "role": "assistant",
                "content": response.content
            })
            conversation_history.append({
                "role": "user",
                "content": tool_results
            })

        # Claude has a final text response
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

def chat(user_message: str) -> str:
    """Sync wrapper for chat_async — called by FastAPI."""
    return asyncio.run(chat_async(user_message))

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