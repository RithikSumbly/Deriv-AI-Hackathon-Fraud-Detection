# Fraud network model (Neo4j)

Simple graph for device/IP-based fraud detection: **shared devices**, **fraud clusters**, and **accounts indirectly connected to known fraud**.

---

## 1. Graph schema

### Node labels and properties

| Label   | Primary key | Properties (optional) | Description                    |
|--------|-------------|----------------------|--------------------------------|
| `Account` | `id` (string) | `is_fraud` (boolean), `account_id` (= id) | One node per account.          |
| `Device`  | `id` (string) | —                    | One node per distinct device.  |
| `IP`       | `id` (string) | —                    | One node per distinct IP hash. |

### Relationship types

| Type           | From    | To     | Direction  | Meaning                          |
|----------------|---------|--------|------------|----------------------------------|
| `USED_DEVICE`  | Account | Device | outgoing   | Account used this device.        |
| `LOGGED_FROM_IP` | Account | IP     | outgoing   | Account logged in from this IP.   |

### Schema diagram (text)

```
(Account)-[:USED_DEVICE]->(Device)
(Account)-[:LOGGED_FROM_IP]->(IP)
```

### Constraints and indexes (run once)

```cypher
CREATE CONSTRAINT account_id IF NOT EXISTS FOR (a:Account) REQUIRE a.id IS UNIQUE;
CREATE CONSTRAINT device_id IF NOT EXISTS FOR (d:Device) REQUIRE d.id IS UNIQUE;
CREATE CONSTRAINT ip_id IF NOT EXISTS FOR (i:IP) REQUIRE i.id IS UNIQUE;
CREATE INDEX account_fraud IF NOT EXISTS FOR (a:Account) ON (a.is_fraud);
```

---

## 2. Sample Cypher queries

### 2.1 Shared devices across accounts

**Devices used by more than one account (with account count):**

```cypher
MATCH (d:Device)<-[:USED_DEVICE]-(a:Account)
WITH d, count(DISTINCT a) AS account_count
WHERE account_count > 1
RETURN d.id AS device_id, account_count
ORDER BY account_count DESC;
```

**For a given account, list other accounts sharing the same device:**

```cypher
MATCH (a:Account {id: $account_id})-[:USED_DEVICE]->(d:Device)<-[:USED_DEVICE]-(other:Account)
WHERE other.id <> a.id
RETURN other.id AS shared_with_account;
```

**Per-account: number of other accounts sharing this account’s device:**

```cypher
MATCH (a:Account)-[:USED_DEVICE]->(d:Device)<-[:USED_DEVICE]-(b:Account)
WHERE b.id <> a.id
WITH a, count(DISTINCT b) AS shared_device_peers
RETURN a.id AS account_id, shared_device_peers
ORDER BY shared_device_peers DESC;
```

### 2.2 Shared IPs across accounts

**IPs used by more than one account:**

```cypher
MATCH (i:IP)<-[:LOGGED_FROM_IP]-(a:Account)
WITH i, count(DISTINCT a) AS account_count
WHERE account_count > 1
RETURN i.id AS ip_id, account_count
ORDER BY account_count DESC;
```

**Per-account: number of other accounts sharing this account’s IP:**

```cypher
MATCH (a:Account)-[:LOGGED_FROM_IP]->(i:IP)<-[:LOGGED_FROM_IP]-(b:Account)
WHERE b.id <> a.id
WITH a, count(DISTINCT b) AS shared_ip_peers
RETURN a.id AS account_id, shared_ip_peers
ORDER BY shared_ip_peers DESC;
```

### 2.3 Fraud clusters (device/IP connected to known fraud)

**Accounts in the same “cluster” as at least one known fraud (shared device or IP):**

```cypher
MATCH (fraud:Account {is_fraud: true})
MATCH (fraud)-[:USED_DEVICE|LOGGED_FROM_IP]->(n)<-[:USED_DEVICE|LOGGED_FROM_IP]-(member:Account)
WITH DISTINCT member
RETURN member.id AS account_id
ORDER BY account_id;
```

**Cluster size per account (number of accounts connected via shared device or IP to this account):**

```cypher
MATCH (a:Account)
OPTIONAL MATCH (a)-[:USED_DEVICE]->(d:Device)<-[:USED_DEVICE]-(dPeer:Account)
OPTIONAL MATCH (a)-[:LOGGED_FROM_IP]->(i:IP)<-[:LOGGED_FROM_IP]-(iPeer:Account)
WITH a,
  count(DISTINCT dPeer) + count(DISTINCT iPeer) - count(DISTINCT (CASE WHEN dPeer.id = iPeer.id THEN dPeer END)) AS cluster_approx
RETURN a.id AS account_id, cluster_approx AS cluster_size
ORDER BY cluster_size DESC;
```

Simpler **“same device or same IP as any fraud”** flag:

```cypher
MATCH (fraud:Account {is_fraud: true})-[:USED_DEVICE|LOGGED_FROM_IP]->(n)<-[:USED_DEVICE|LOGGED_FROM_IP]-(a:Account)
RETURN DISTINCT a.id AS account_id;
```

### 2.4 Accounts indirectly connected to known fraud

**Shortest path length from an account to any known-fraud account (via device or IP):**

```cypher
MATCH (a:Account {id: $account_id})
MATCH (fraud:Account {is_fraud: true})
MATCH path = shortestPath((a)-[:USED_DEVICE|LOGGED_FROM_IP*]-(fraud))
RETURN length(path) AS path_length
ORDER BY path_length
LIMIT 1;
```

**All accounts within 2 hops of any fraud (path length = 2 means one intermediate node):**

```cypher
MATCH (fraud:Account {is_fraud: true})
MATCH (a:Account)-[:USED_DEVICE|LOGGED_FROM_IP*1..2]-(fraud)
WHERE a.is_fraud = false
RETURN DISTINCT a.id AS account_id;
```

**Per-account: minimum path length to any fraud (null if no path):**

```cypher
MATCH (a:Account)
OPTIONAL MATCH (fraud:Account {is_fraud: true})
OPTIONAL MATCH path = shortestPath((a)-[:USED_DEVICE|LOGGED_FROM_IP*]-(fraud))
WITH a, path
WHERE path IS NOT NULL
WITH a, min(length(path)) AS min_path_to_fraud
RETURN a.id AS account_id, min_path_to_fraud
ORDER BY min_path_to_fraud;
```

---

## 3. Converting graph signals into ML features

Use these as **extra inputs** to your existing classifier (alongside declared income, VPN, etc.).

| Feature name              | Description | Cypher / derivation |
|--------------------------|-------------|----------------------|
| `device_shared_count`    | Number of *other* accounts that use the same device as this account. | Count of `(a)-[:USED_DEVICE]->(d)<-[:USED_DEVICE]-(b)` with `b <> a`. Can also use degree of `d` minus 1. |
| `ip_shared_count`        | Number of *other* accounts that used the same IP. | Same pattern for `LOGGED_FROM_IP`. |
| `same_device_as_fraud`   | 1 if this account shares a device with any known-fraud account, else 0. | Exists path `(a)-[:USED_DEVICE]->(d)<-[:USED_DEVICE]-(fraud)` with `fraud.is_fraud = true`. |
| `same_ip_as_fraud`       | 1 if this account shares an IP with any known-fraud account, else 0. | Same for `LOGGED_FROM_IP`. |
| `min_path_to_fraud`      | Shortest path length (in steps) from this account to any fraud account; null/missing if disconnected. | `shortestPath` to any `Account` with `is_fraud = true`; use a large constant (e.g. 99) for null so the model sees “far from fraud”. |
| `fraud_cluster_size`     | Number of accounts in the same device/IP “cluster” as this account (or degree-based proxy). | Count distinct accounts reachable via one shared device or IP; or use the cluster_size query above. |

### Pipeline

1. **Build the graph** from your source data: one `Account` per account, one `Device` per `device_id`, one `IP` per `ip_hash`; create `USED_DEVICE` and `LOGGED_FROM_IP` from account–device and account–IP mappings.
2. **Run Cypher** (or the provided Python script) to compute, per account:  
   `device_shared_count`, `ip_shared_count`, `same_device_as_fraud`, `same_ip_as_fraud`, `min_path_to_fraud`, (optionally) `fraud_cluster_size`.
3. **Join** these columns to your existing tabular dataset by `account_id`.
4. **Retrain** the fraud classifier (and anomaly model if desired) with the new graph features.

### Usage note

- For **training**, you can use `is_fraud` on nodes to compute `same_device_as_fraud`, `same_ip_as_fraud`, and `min_path_to_fraud` (known fraud is part of the graph).
- For **inference** on new accounts, you can either: (a) update the graph with new accounts and recompute the same queries (no `is_fraud` for new accounts), or (b) use only features that do not depend on fraud labels (e.g. `device_shared_count`, `ip_shared_count`, and optionally a “distance to high-risk cluster” if you define risk by something other than current labels).

The script `backend/scripts/neo4j_graph_features.py` loads the synthetic CSV into Neo4j and exports `backend/data/graph_features.csv` with: `account_id`, `device_shared_count`, `ip_shared_count`, `same_device_as_fraud`, `same_ip_as_fraud`, `min_path_to_fraud`. Merge that CSV with your tabular data by `account_id` and retrain.
