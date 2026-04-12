import asyncio
from app.service.visual_agent import run_visual_agent_stream
async def test():
    async for chunk in run_visual_agent_stream("设计一个logo", "", is_micro_task=True):
        print("CHUNK:", repr(chunk))
asyncio.run(test())
