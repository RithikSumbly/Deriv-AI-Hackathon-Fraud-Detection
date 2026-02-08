"""
Account network graph: devices and IPs shared between accounts.

Uses Neo4j when NEO4J_URI is set (run backend/scripts/neo4j_load_network.py to populate);
otherwise falls back to CSV-based in-memory mappings. Same {nodes, edges} format for the UI.
"""
from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
UNLABELED_CSV = DATA_DIR / "unlabeled_fraud_dataset.csv"
SYNTHETIC_CSV = DATA_DIR / "synthetic_fraud_dataset.csv"

_neo4j_driver = None


def _get_neo4j_driver():
    """Lazy-init Neo4j driver from NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD. Returns None if not configured or import/connect fails."""
    global _neo4j_driver
    if _neo4j_driver is not None:
        return _neo4j_driver
    if not os.environ.get("NEO4J_URI"):
        return None
    try:
        from neo4j import GraphDatabase
        uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
        user = os.environ.get("NEO4J_USER", "neo4j")
        password = os.environ.get("NEO4J_PASSWORD", "password")
        _neo4j_driver = GraphDatabase.driver(uri, auth=(user, password))
        _neo4j_driver.verify_connectivity()
        return _neo4j_driver
    except Exception:
        _neo4j_driver = None
        return None


def _node_prop(node, key: str):
    if node is None:
        return None
    if hasattr(node, "get"):
        return node.get(key)
    try:
        return node[key]
    except (KeyError, TypeError):
        return getattr(node, key, None)


def _neo4j_record_to_graph(record, account_id: str) -> dict:
    """Convert Neo4j query record to frontend format {nodes, edges}. Record has a, devices, ips, linked_accounts."""
    nodes: list[dict] = []
    edges: list[dict] = []

    primary = record.get("a")
    if not primary:
        return {"nodes": [{"id": account_id, "label": account_id, "type": "primary_account"}], "edges": []}

    aid = _node_prop(primary, "account_id") or account_id
    aid = str(aid)
    nodes.append({"id": aid, "label": aid, "type": "primary_account"})

    devices = record.get("devices") or []
    ips = record.get("ips") or []
    linked = record.get("linked_accounts") or []

    device_ids: set[str] = set()
    for d in devices:
        did = _node_prop(d, "device_id")
        if did:
            device_ids.add(str(did))
    for did in sorted(device_ids):
        nodes.append({"id": did, "label": did, "type": "device"})

    ip_ids: set[str] = set()
    for i in ips:
        iid = _node_prop(i, "ip_id")
        if iid:
            ip_ids.add(str(iid))
    for iid in sorted(ip_ids):
        nodes.append({"id": iid, "label": iid, "type": "ip"})

    other_ids: set[str] = set()
    for o in linked:
        oid = _node_prop(o, "account_id")
        if oid and oid != aid:
            other_ids.add(str(oid))
    for oid in sorted(other_ids):
        nodes.append({"id": oid, "label": oid, "type": "other_account"})

    # Edges: need (account, device) and (account, ip) for primary + linked in subgraph
    account_ids = {aid} | other_ids
    seen_edges: set[tuple[str, str]] = set()

    driver = _get_neo4j_driver()
    if driver and (device_ids or ip_ids):
        with driver.session() as session:
            if device_ids:
                r = session.run(
                    """
                    MATCH (a:Account)-[:USES_DEVICE]->(d:Device)
                    WHERE a.account_id IN $account_ids AND d.device_id IN $device_ids
                    RETURN a.account_id AS aid, d.device_id AS did
                    """,
                    account_ids=list(account_ids),
                    device_ids=list(device_ids),
                )
                for rec in r:
                    a_id = rec.get("aid")
                    d_id = rec.get("did")
                    if a_id and d_id and (a_id, d_id) not in seen_edges:
                        seen_edges.add((a_id, d_id))
                        edges.append({"source": a_id, "target": d_id, "relationship": "uses device"})
            if ip_ids:
                r = session.run(
                    """
                    MATCH (a:Account)-[:LOGGED_FROM]->(i:IP)
                    WHERE a.account_id IN $account_ids AND i.ip_id IN $ip_ids
                    RETURN a.account_id AS aid, i.ip_id AS iid
                    """,
                    account_ids=list(account_ids),
                    ip_ids=list(ip_ids),
                )
                for rec in r:
                    a_id = rec.get("aid")
                    i_id = rec.get("iid")
                    if a_id and i_id and (a_id, i_id) not in seen_edges:
                        seen_edges.add((a_id, i_id))
                        edges.append({"source": a_id, "target": i_id, "relationship": "logged from"})

    return {"nodes": nodes, "edges": edges}


def _get_account_network_neo4j(account_id: str) -> dict | None:
    """Return graph from Neo4j or None on any failure."""
    driver = _get_neo4j_driver()
    if not driver:
        return None
    try:
        with driver.session() as session:
            r = session.run(
                """
                MATCH (a:Account {account_id: $account_id})
                OPTIONAL MATCH (a)-[:USES_DEVICE]->(d:Device)<-[:USES_DEVICE]-(other:Account)
                OPTIONAL MATCH (a)-[:LOGGED_FROM]->(ip:IP)<-[:LOGGED_FROM]-(other2:Account)
                WITH a,
                     collect(DISTINCT d) AS devices,
                     collect(DISTINCT ip) AS ips,
                     collect(DISTINCT other) + collect(DISTINCT other2) AS linked_accounts
                RETURN a, devices, ips, linked_accounts
                """,
                account_id=account_id,
            )
            record = r.single()
            if not record:
                return {"nodes": [{"id": account_id, "label": account_id, "type": "primary_account"}], "edges": []}
            return _neo4j_record_to_graph(dict(record), account_id)
    except Exception:
        return None


def _load_mappings() -> tuple[dict[str, list[tuple[str, str]]], dict[str, list[str]], dict[str, list[str]]]:
    """
    Load account -> (device_id, ip_id), device_id -> [account_ids], ip_id -> [account_ids].
    Uses unlabeled_fraud_dataset (device_id, ip_address) and synthetic_fraud_dataset (device_id, ip_hash).
    """
    account_devices_ips: dict[str, list[tuple[str, str]]] = {}
    device_to_accounts: dict[str, list[str]] = {}
    ip_to_accounts: dict[str, list[str]] = {}

    def add_row(acc, dev, ip_id) -> None:
        if acc is None or (pd.isna(acc) if hasattr(acc, "__float__") else False):
            return
        acc = str(acc).strip()
        dev = "" if dev is None or (pd.isna(dev) if hasattr(dev, "__float__") else False) else str(dev).strip()
        ip_id = "" if ip_id is None or (pd.isna(ip_id) if hasattr(ip_id, "__float__") else False) else str(ip_id).strip()
        if not dev and not ip_id:
            return
        account_devices_ips.setdefault(acc, []).append((dev, ip_id))
        if dev:
            device_to_accounts.setdefault(dev, []).append(acc)
        if ip_id:
            ip_to_accounts.setdefault(ip_id, []).append(acc)

    if UNLABELED_CSV.exists():
        try:
            df = pd.read_csv(UNLABELED_CSV)
            for _, row in df.iterrows():
                add_row(row.get("account_id"), row.get("device_id"), row.get("ip_address"))
        except Exception:
            pass

    if SYNTHETIC_CSV.exists():
        try:
            df = pd.read_csv(SYNTHETIC_CSV)
            for _, row in df.iterrows():
                add_row(row.get("account_id"), row.get("device_id"), row.get("ip_hash"))
        except Exception:
            pass

    return account_devices_ips, device_to_accounts, ip_to_accounts


def _get_account_network_csv(account_id: str) -> dict:
    """CSV-based implementation (fallback when Neo4j is not available)."""
    account_id = str(account_id).strip()
    nodes: list[dict] = []
    edges: list[dict] = []

    account_devices_ips, device_to_accounts, ip_to_accounts = _load_mappings()

    if account_id not in account_devices_ips:
        nodes.append({"id": account_id, "label": account_id, "type": "primary_account"})
        return {"nodes": nodes, "edges": edges}

    nodes.append({"id": account_id, "label": account_id, "type": "primary_account"})

    primary_pairs = account_devices_ips[account_id]
    devices_used: set[str] = set()
    ips_used: set[str] = set()
    for d, i in primary_pairs:
        if d:
            devices_used.add(d)
        if i:
            ips_used.add(i)

    other_accounts: set[str] = set()
    for dev in devices_used:
        for acc in device_to_accounts.get(dev, []):
            if acc != account_id:
                other_accounts.add(acc)
    for ip in ips_used:
        for acc in ip_to_accounts.get(ip, []):
            if acc != account_id:
                other_accounts.add(acc)

    all_devices: set[str] = set(devices_used)
    all_ips: set[str] = set(ips_used)
    for acc in other_accounts:
        for d, i in account_devices_ips.get(acc, []):
            if d:
                all_devices.add(d)
            if i:
                all_ips.add(i)

    for acc in sorted(other_accounts):
        nodes.append({"id": acc, "label": acc, "type": "other_account"})
    for dev in sorted(all_devices):
        nodes.append({"id": dev, "label": dev, "type": "device"})
    for ip in sorted(all_ips):
        nodes.append({"id": ip, "label": ip, "type": "ip"})

    accounts_in_graph = {account_id} | other_accounts
    seen: set[tuple[str, str]] = set()
    for acc in accounts_in_graph:
        for d, i in account_devices_ips.get(acc, []):
            if d and d in all_devices and (acc, d) not in seen:
                seen.add((acc, d))
                edges.append({"source": acc, "target": d, "relationship": "uses device"})
            if i and i in all_ips and (acc, i) not in seen:
                seen.add((acc, i))
                edges.append({"source": acc, "target": i, "relationship": "logged from"})

    return {"nodes": nodes, "edges": edges}


def get_account_network(account_id: str) -> dict:
    """
    Build graph for the given account: nodes (primary_account, other_account, device, ip)
    and edges (account -> device, account -> ip). Uses Neo4j when configured and available;
    otherwise falls back to CSV-based data.

    Returns:
        {"nodes": [{"id", "label", "type"}], "edges": [{"source", "target", "relationship"}]}
    """
    result = _get_account_network_neo4j(str(account_id).strip())
    if result is not None:
        return result
    return _get_account_network_csv(account_id)
