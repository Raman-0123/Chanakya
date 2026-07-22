import asyncio
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import get_datastores, get_repositories
from app.rag import evidence_store


async def main() -> None:
    stores = get_datastores()
    await stores.connect()
    get_repositories().bind(stores)
    count = await evidence_store.ensure_corpus()
    print(f"Seeded {count} evidence documents")
    await stores.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
