import asyncio
from tools.wormhole import get_wormhole_system_id, get_wormhole_kills

async def test():
    system_id = await get_wormhole_system_id('J102055')
    kills = await get_wormhole_kills(system_id, limit=5)
    for k in kills:
        print("keys:", list(k.keys()))
        print("time:", k.get('killmail_time'))
        print("attackers sample:", k.get('attackers', [{}])[0])
        print("---")

asyncio.run(test())