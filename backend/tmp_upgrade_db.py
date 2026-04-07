import asyncio
import sys

from sqlalchemy import text
from app.db.database import engine

async def upgrade_db():
    async with engine.begin() as conn:
        try:
            await conn.execute(text("ALTER TABLE sessions ADD COLUMN title TEXT;"))
            print("Added title column")
        except Exception as e:
            print(f"Failed to add title column: {e}")
            
        try:
            await conn.execute(text("ALTER TABLE sessions ADD COLUMN is_pinned BOOLEAN DEFAULT FALSE;"))
            print("Added is_pinned column")
        except Exception as e:
            print(f"Failed to add is_pinned column: {e}")
            
        try:
            await conn.execute(text("UPDATE sessions SET title = SUBSTRING(user_prompt, 1, 40) WHERE title IS NULL;"))
            print("Backfilled titles with user_prompt")
        except Exception as e:
            print(f"Failed to backfill titles: {e}")

if __name__ == "__main__":
    asyncio.run(upgrade_db())
