import asyncio

from petty.endpoints import Proxy

from gamestate.state import GameState


async def resend_armor_stands(node: Proxy, gamestate: GameState) -> None:
    await asyncio.sleep(1.0)
    while node.open and node.downstream.open:
        packets = gamestate.build_armor_stand_resend_packets()
        if packets:
            node.downstream.send_packets(packets)
        await asyncio.sleep(5.0)
