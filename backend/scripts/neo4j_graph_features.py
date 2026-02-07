#!/usr/bin/env python3
"""
Neo4j fraud network: load synthetic data into the graph and export graph-based ML features.

Graph: Account -[:USED_DEVICE]-> Device, Account -[:LOGGED_FROM_IP]-> IP.
Output: CSV with device_shared_count, ip_shared_count, same_device_as_fraud,
        same_ip_as_fraud, min_path_to_fraud (and optional fraud_cluster_size).

Requires: Neo4j running (e.g. Docker: docker run -p 7474:7474 -p 7687:7687 neo4j),
          and pip install neo4j.

Usage:
  export NEO4J_URI="bolt://localhost:7687" NEO4J_USER=neo4j NEO4J_PASSWORD=yourpassword
  python scripts/neo4j_graph_features.py [--load-only] [--export-only]
  Default: load CSV into Neo4j (if --load-only skip export), then export features.
  --export-only: skip load (graph already populated).
"""
from pathlib import Path
import argparse
import os
import pandas as pd

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "synthetic_fraud_dataset.csv"
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "graph_features.csv"


def get_driver():
    try:
        from neo4j import GraphDatabase
    except ImportError:
        raise ImportError("Install neo4j: pip install neo4j")
    uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    user = os.environ.get("NEO4J_USER", "neo4j")
    password = os.environ.get("NEO4J_PASSWORD", "password")
    return GraphDatabase.driver(uri, auth=(user, password))


def create_constraints(driver):
    with driver.session() as session:
        for q in [
            "CREATE CONSTRAINT account_id IF NOT EXISTS FOR (a:Account) REQUIRE a.id IS UNIQUE",
            "CREATE CONSTRAINT device_id IF NOT EXISTS FOR (d:Device) REQUIRE d.id IS UNIQUE",
            "CREATE CONSTRAINT ip_id IF NOT EXISTS FOR (i:IP) REQUIRE i.id IS UNIQUE",
        ]:
            try:
                session.run(q)
            except Exception as e:
                if "EquivalentSchemaRuleAlreadyExists" not in str(e):
                    print(f"Constraint note: {e}")


def load_graph_from_csv(driver, data_path: Path):
    """Create Account, Device, IP nodes and USED_DEVICE, LOGGED_FROM_IP edges from CSV."""
    df = pd.read_csv(data_path)
    create_constraints(driver)

    with driver.session() as session:
        # Clear (optional; remove for incremental load)
        session.run("MATCH (n) DETACH DELETE n")

        # Create nodes in batches
        accounts = df[["account_id", "is_fraud"]].drop_duplicates("account_id")
        for _, row in accounts.iterrows():
            session.run(
                "MERGE (a:Account {id: $id}) SET a.is_fraud = $is_fraud",
                id=row["account_id"],
                is_fraud=bool(row["is_fraud"]),
            )

        devices = df["device_id"].unique().tolist()
        for d in devices:
            session.run("MERGE (d:Device {id: $id})", id=d)

        ips = df["ip_hash"].unique().tolist()
        for i in ips:
            session.run("MERGE (i:IP {id: $id})", id=i)

        # Create relationships
        for _, row in df.iterrows():
            session.run(
                "MATCH (a:Account {id: $aid}) MATCH (d:Device {id: $did}) MERGE (a)-[:USED_DEVICE]->(d)",
                aid=row["account_id"],
                did=row["device_id"],
            )
            session.run(
                "MATCH (a:Account {id: $aid}) MATCH (i:IP {id: $iid}) MERGE (a)-[:LOGGED_FROM_IP]->(i)",
                aid=row["account_id"],
                iid=row["ip_hash"],
            )
    print("Graph loaded.")


def export_graph_features(driver) -> pd.DataFrame:
    """Run Cypher to compute per-account graph features; return DataFrame."""
    with driver.session() as session:
        # Device shared count (others using same device)
        r = session.run("""
            MATCH (a:Account)-[:USED_DEVICE]->(d:Device)<-[:USED_DEVICE]-(b:Account)
            WHERE b.id <> a.id
            WITH a, count(DISTINCT b) AS c
            RETURN a.id AS account_id, c AS device_shared_count
        """)
        device_count = {rec["account_id"]: rec["device_shared_count"] for rec in r}

        # IP shared count
        r = session.run("""
            MATCH (a:Account)-[:LOGGED_FROM_IP]->(i:IP)<-[:LOGGED_FROM_IP]-(b:Account)
            WHERE b.id <> a.id
            WITH a, count(DISTINCT b) AS c
            RETURN a.id AS account_id, c AS ip_shared_count
        """)
        ip_count = {rec["account_id"]: rec["ip_shared_count"] for rec in r}

        # Same device as any fraud (0/1)
        r = session.run("""
            MATCH (fraud:Account {is_fraud: true})-[:USED_DEVICE]->(d:Device)<-[:USED_DEVICE]-(a:Account)
            RETURN DISTINCT a.id AS account_id
        """)
        same_dev_fraud = {rec["account_id"] for rec in r}

        # Same IP as any fraud (0/1)
        r = session.run("""
            MATCH (fraud:Account {is_fraud: true})-[:LOGGED_FROM_IP]->(i:IP)<-[:LOGGED_FROM_IP]-(a:Account)
            RETURN DISTINCT a.id AS account_id
        """)
        same_ip_fraud = {rec["account_id"] for rec in r}

        # Min path length to any fraud (no path => 999 in output)
        r = session.run("""
            MATCH (a:Account)
            OPTIONAL MATCH (f:Account {is_fraud: true})
            WHERE a.id <> f.id
            OPTIONAL MATCH path = shortestPath((a)-[:USED_DEVICE|LOGGED_FROM_IP*]-(f))
            WITH a, path
            WITH a, CASE WHEN path IS NOT NULL THEN length(path) END AS plen
            WITH a, min(plen) AS min_path_to_fraud
            RETURN a.id AS account_id, min_path_to_fraud
        """)
        min_path = {}
        for rec in r:
            plen = rec["min_path_to_fraud"]
            min_path[rec["account_id"]] = int(plen) if plen is not None else 999

        # All account IDs (from graph)
        r = session.run("MATCH (a:Account) RETURN a.id AS account_id")
        all_ids = [rec["account_id"] for rec in r]

    rows = []
    for aid in all_ids:
        rows.append({
            "account_id": aid,
            "device_shared_count": device_count.get(aid, 0),
            "ip_shared_count": ip_count.get(aid, 0),
            "same_device_as_fraud": 1 if aid in same_dev_fraud else 0,
            "same_ip_as_fraud": 1 if aid in same_ip_fraud else 0,
            "min_path_to_fraud": min_path.get(aid, 999),
        })
    return pd.DataFrame(rows)


def main():
    parser = argparse.ArgumentParser(description="Load fraud graph into Neo4j and export graph features")
    parser.add_argument("--load-only", action="store_true", help="Only load CSV into Neo4j; do not export")
    parser.add_argument("--export-only", action="store_true", help="Only export features (graph already loaded)")
    args = parser.parse_args()

    driver = get_driver()
    try:
        if not args.export_only:
            if not DATA_PATH.exists():
                raise FileNotFoundError(f"Data not found: {DATA_PATH}")
            load_graph_from_csv(driver, DATA_PATH)
        if not args.load_only:
            df = export_graph_features(driver)
            OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(OUTPUT_PATH, index=False)
            print(f"Exported {len(df)} rows to {OUTPUT_PATH}")
    finally:
        driver.close()


if __name__ == "__main__":
    main()
