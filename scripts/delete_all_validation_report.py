import asyncio
import shutil
from pathlib import Path
from pegasus.core.config import get_settings
from pegasus.core.database import AsyncSessionLocal, dispose_engine
from pegasus.repositories.validation_repository import ValidationRunRepository
from pegasus.api.v1.validation_helpers import validation_jobs_root

async def main():
    settings = get_settings()
    print("Loading settings...")
    
    # 1. Clear database validation runs
    print("Connecting to the database...")
    async with AsyncSessionLocal() as session:
        print("Deleting all validation runs from the database...")
        count = await ValidationRunRepository.delete_all_runs(session)
        await session.commit()
        print(f"Successfully deleted {count} validation runs from the database.")

    # 2. Clear job directories on disk
    jobs_root = validation_jobs_root(settings)
    print(f"Jobs root directory is: {jobs_root}")
    if jobs_root.exists():
        deleted_count = 0
        for item in jobs_root.iterdir():
            try:
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()
                deleted_count += 1
            except Exception as e:
                print(f"Failed to delete {item}: {e}")
        print(f"Deleted {deleted_count} files/directories from {jobs_root}.")
    else:
        print("Jobs root directory does not exist.")

    await dispose_engine()

if __name__ == "__main__":
    asyncio.run(main())
