"""Integration test: Cosmos DB MCP read/write (Issue #153).

Requires:
  - COSMOS_ENDPOINT env var (or uses default dev endpoint)
  - Azure CLI login (DefaultAzureCredential)
  - Cosmos DB publicNetworkAccess must be ENABLED
"""

import os
import sys
import uuid

from azure.cosmos import CosmosClient
from azure.identity import DefaultAzureCredential

ENDPOINT = os.getenv(
    "COSMOS_ENDPOINT",
    "https://cosmos-albaranes-dev.documents.azure.com:443/",
)
DATABASE = "albaranes-db"
CONTAINERS = ["tiendas", "dlq", "albaranes", "upload-sessions"]


def get_client() -> CosmosClient:
    credential = DefaultAzureCredential()
    return CosmosClient(url=ENDPOINT, credential=credential)


def test_connection():
    """Test basic connection and list databases."""
    print(f"\n{'='*60}")
    print("Testing Cosmos DB connection")
    print(f"Endpoint: {ENDPOINT}")
    print(f"{'='*60}")

    try:
        client = get_client()
        dbs = list(client.list_databases())
        db_names = [db["id"] for db in dbs]
        print(f"✅ Connected. Databases: {db_names}")
        assert DATABASE in db_names, f"Database '{DATABASE}' not found"
        return {"test": "connection", "status": "OK", "databases": db_names}
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return {"test": "connection", "status": "ERROR", "error": str(e)}


def test_containers():
    """Verify all expected containers exist."""
    print(f"\n{'='*60}")
    print(f"Testing containers in {DATABASE}")
    print(f"{'='*60}")

    try:
        client = get_client()
        db = client.get_database_client(DATABASE)
        existing = [c["id"] for c in db.list_containers()]
        print(f"   Containers: {existing}")

        missing = [c for c in CONTAINERS if c not in existing]
        if missing:
            print(f"⚠️  Missing containers: {missing}")
            return {"test": "containers", "status": "WARN", "missing": missing}

        print(f"✅ All {len(CONTAINERS)} containers exist")
        return {"test": "containers", "status": "OK", "containers": existing}
    except Exception as e:
        print(f"❌ Error: {e}")
        return {"test": "containers", "status": "ERROR", "error": str(e)}


def test_crud():
    """Test CRUD operations on the tiendas container."""
    print(f"\n{'='*60}")
    print("Testing CRUD on 'tiendas' container")
    print(f"{'='*60}")

    test_id = f"integration-test-{uuid.uuid4().hex[:8]}"

    try:
        client = get_client()
        db = client.get_database_client(DATABASE)
        container = db.get_container_client("tiendas")

        # CREATE — partition key is /tienda_id
        pk_value = f"TEST-{test_id}"
        doc = {
            "id": test_id,
            "tienda_id": pk_value,
            "codigo": "TEST-001",
            "nombre": "Tienda Test Integration",
            "ciudad": "Madrid",
            "_integration_test": True,
        }
        created = container.create_item(body=doc)
        print(f"✅ CREATE: {created['id']}")

        # READ
        read = container.read_item(item=test_id, partition_key=pk_value)
        assert read["nombre"] == "Tienda Test Integration"
        print(f"✅ READ: {read['nombre']}")

        # UPDATE (upsert)
        doc["nombre"] = "Tienda Test Updated"
        updated = container.upsert_item(body=doc)
        print(f"✅ UPDATE: {updated['nombre']}")

        # QUERY
        query = "SELECT * FROM c WHERE c._integration_test = true"
        items = list(container.query_items(query=query, enable_cross_partition_query=True))
        print(f"✅ QUERY: {len(items)} item(s) found")

        # DELETE
        container.delete_item(item=test_id, partition_key=pk_value)
        print(f"✅ DELETE: {test_id}")

        return {"test": "crud", "status": "OK"}

    except Exception as e:
        print(f"❌ CRUD Error: {e}")
        # Cleanup attempt
        try:
            client = get_client()
            db = client.get_database_client(DATABASE)
            container = db.get_container_client("tiendas")
            container.delete_item(item=test_id, partition_key=pk_value)
        except Exception:
            pass
        return {"test": "crud", "status": "ERROR", "error": str(e)}


def main():
    print("🚀 Cosmos DB Integration Test")
    print(f"Endpoint: {ENDPOINT}")
    results = []

    results.append(test_connection())
    if results[-1]["status"] == "OK":
        results.append(test_containers())
        results.append(test_crud())
    else:
        print("\n⚠️  Skipping further tests — connection failed")

    print(f"\n{'='*60}")
    print("📊 Summary")
    print(f"{'='*60}")
    errors = [r for r in results if r["status"] == "ERROR"]
    for r in results:
        icon = {"OK": "✅", "WARN": "⚠️"}.get(r["status"], "❌")
        print(f"  {icon} {r['test']}: {r['status']}")

    if errors:
        print(f"\n❌ {len(errors)} test(s) failed")
        sys.exit(1)
    else:
        print("\n✅ All tests passed")


if __name__ == "__main__":
    main()
