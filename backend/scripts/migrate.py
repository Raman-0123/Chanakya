import asyncio
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import get_datastores, get_repositories


async def main() -> None:
    stores = get_datastores()
    await stores.connect()
    repositories = get_repositories()
    repositories.bind(stores)
    await repositories.initialize()
    print("Database schema and Neo4j ontology are ready")
    await stores.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
