import asyncio
from dotenv import load_dotenv
load_dotenv()
from app.config import settings
import logging

logging.basicConfig(level=logging.INFO)

async def test():
    from app.service.image_generator import generate_brand_images
    print("Testing generate_brand_images...")
    try:
        res = await generate_brand_images("logo", "test logo", "1:1")
        print("Result:", res)
    except Exception as e:
        print("Crash:", e)

asyncio.run(test())
