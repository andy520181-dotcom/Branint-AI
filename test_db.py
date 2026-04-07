import asyncio
from sqlalchemy import select
from app.db.database import engine
from app.model.session import Session

async def check():
    async with engine.begin() as conn:
        result = await conn.execute(select(Session.id, Session.title, Session.is_pinned).limit(5))
        for row in result:
            print(row)

asyncio.run(check())
