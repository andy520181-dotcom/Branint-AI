import asyncio
from dotenv import load_dotenv
load_dotenv()
from app.config import settings
from app.service.visual_agent import run_visual_agent_stream

async def test():
    print("Testing visual agent stream...")
    async for chunk in run_visual_agent_stream("logo设计", "", is_micro_task=True):
        print(repr(chunk))

asyncio.run(test())
