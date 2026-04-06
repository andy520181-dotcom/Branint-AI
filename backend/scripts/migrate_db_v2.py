import asyncio
from sqlalchemy import text
from app.db.database import Base, AsyncSessionFactory

# 依赖载入，激活 metadata
import app.model.session
import app.model.user

async def run_migration():
    async with AsyncSessionFactory() as session:
        # Create all tables (will create 'users' if it doesn't exist)
        conn = await session.connection()
        await conn.run_sync(Base.metadata.create_all)
        
        # Add column 'agent_media' to 'sessions'
        try:
            await session.execute(text("ALTER TABLE sessions ADD COLUMN agent_media JSONB NOT NULL DEFAULT '{}'::jsonb"))
            await session.commit()
            print("Successfully added agent_media to sessions.")
        except Exception as e:
            await session.rollback()
            if "already exists" in str(e):
                print("agent_media column already exists, skipping.")
            else:
                print(f"Error adding column: {e}")

if __name__ == "__main__":
    asyncio.run(run_migration())
