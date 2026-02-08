#!/usr/bin/env python3
"""
Load account-device-IP network into Neo4j for the dashboard (get_account_network).

Schema: (:Account {account_id}), (:Device {device_id}), (:IP {ip_id}),
        (Account)-[:USES_DEVICE]->(Device), (Account)-[:LOGGED_FROM]->(IP).

Loads: unlabeled_fraud_dataset.csv (account_id, device_id, ip_address) and
       synthetic_fraud_dataset.csv (account_id, device_id, ip_hash as ip_id).

Env: NEO4J_URI (default bolt://localhost:7687), NEO4J_USER (neo4j), NEO4J_PASSWORD.

Usage:
  python backend/scripts/neo4j_load_network.py
  (from project root: python -m backend.scripts.neo4j_load_network)
"""
from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
UNLABELED_CSV = DATA_DIR / "unlabeled_fraud_dataset.csv"
SYNTHETIC_CSV = DATA_DIR / "synthetic_fraud_dataset.csv"


def get_driver():
    try:
        from neo4j import GraphDatabase
    except ImportError:
        raise ImportError("Install neo4j: pip install neo4j")
    uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    user = os.environ.get("NEO4J_USER", "neo4j")
    password = os.environ.get("NEO4J_PASSWORD", "password")
    return GraphDatabase.driver(uri, auth=(user, password))


def create_constraints(driver) -> None:
    with driver.session() as session:
        for q in [
            "CREATE CONSTRAINT account_account_id IF NOT EXISTS FOR (a:Account) REQUIRE a.account_id IS UNIQUE",
            "CREATE CONSTRAINT device_device_id IF NOT EXISTS FOR (d:Device) REQUIRE d.device_id IS UNIQUE",
            "CREATE CONSTRAINT ip_ip_id IF NOT EXISTS FOR (i:IP) REQUIRE i.ip_id IS UNIQUE",
        ]:
            try:
                session.run(q)
            except Exception as e:
                if "EquivalentSchemaRuleAlreadyExists" not in str(e):
                    print(f"Constraint note: {e}")


def _safe(s) -> str | None:
    if s is None:
        return None
    try:
        if pd.isna(s):
            return None
    except Exception:
        pass
    s = str(s).strip()
    return s if s else None


def load_csv_into_graph(driver, csv_path: Path, account_col: str, device_col: str, ip_col: str) -> int:
    """Load one CSV into Neo4j; return number of rows processed."""
    if not csv_path.exists():
        print(f"Skip (not found): {csv_path}")
        return 0
    df = pd.read_csv(csv_path)
    if account_col not in df.columns or device_col not in df.columns or ip_col not in df.columns:
        print(f"Skip (missing columns): {csv_path}")
        return 0
    count = 0
    with driver.session() as session:
        for _, row in df.iterrows():
            acc = _safe(row.get(account_col))
            dev = _safe(row.get(device_col))
            ip = _safe(row.get(ip_col))
            if not acc or (not dev and not ip):
                continue
            session.run(
                "MERGE (a:Account {account_id: $aid})",
                aid=acc,
            )
            if dev:
                session.run("MERGE (d:Device {device_id: $did})", did=dev)
                session.run(
                    "MATCH (a:Account {account_id: $aid}) MATCH (d:Device {device_id: $did}) MERGE (a)-[:USES_DEVICE]->(d)",
                    aid=acc,
                    did=dev,
                )
            if ip:
                session.run("MERGE (i:IP {ip_id: $iid})", iid=ip)
                session.run(
                    "MATCH (a:Account {account_id: $aid}) MATCH (i:IP {ip_id: $iid}) MERGE (a)-[:LOGGED_FROM]->(i)",
                    aid=acc,
                    iid=ip,
                )
            count += 1
    print(f"Loaded {count} rows from {csv_path.name}")
    return count


def main() -> None:
    driver = get_driver()
    try:
        create_constraints(driver)
        load_csv_into_graph(driver, UNLABELED_CSV, "account_id", "device_id", "ip_address")
        load_csv_into_graph(driver, SYNTHETIC_CSV, "account_id", "device_id", "ip_hash")  # ip_hash -> ip_id
    finally:
        driver.close()
    print("Done. Dashboard network.py will use Neo4j when NEO4J_URI is set.")


if __name__ == "__main__":
    main()
