# Time-Series Data Architecture & Migration Plan

Author: Platform Engineering
Status: Draft (v1)
Last Updated: 2025-08-12

## 1. Objectives

1. Replace generic relational storage (SQLite/Postgres `SensorData` table) for high‑volume telemetry with a purpose-built time-series stack.
2. Achieve scalable write throughput, tiered retention, efficient aggregations, and clear multi-tenant isolation (Org → Project → Device → Sensor).
3. Enable downstream processing (flows, dashboards, ML) without overloading OLTP database.
4. Preserve developer ergonomics (simple API surface) and provide migration safety.

## 2. Options Comparison (Concise)

| Criterion | AWS Timestream | InfluxDB (OSS/Cloud) | TimescaleDB | ClickHouse | Choice Rationale |
|----------|----------------|----------------------|-------------|------------|------------------|
| Write Scaling | Serverless auto-scaling | Good; needs sizing | Good (extension) | Excellent | Timestream for managed ops |
| Managed Service | Yes | Cloud option | RDS PG base | Cloud offerings | Prefer managed (reduce ops) |
| Native Retention Tiers | Yes (magnetic + memory) | Yes (RP) | Manual partition | TTL / partitions | Built-in tiering |
| Cost Predictability | Pay usage | Variable | Instance-based | Instance-based | Usage-aligned early stage |
| Query Latency (ad-hoc) | Good | Good | Good | Very good | Adequate |
| Multi-tenant Tagging | Dimensions | Tags | Columns | Columns | Dimensions natural |
| Integrations (AWS) | Tight (Athena, IAM) | Less | Standard PG | Less AWS-native | AWS synergy |

Decision: Adopt AWS Timestream for telemetry storage (Phase 1). Retain Postgres for metadata (devices, orgs, flows) and processed aggregates (optional materialized views).

## 3. Data Hierarchy Mapping

Business Entities:
- Organization (org_id / slug)
- Project (project_uuid)
- Device (device_uuid)
- Sensor Type (sensor_type)
- Measurement Timestamp (ts)
- Value (float or heterogeneous) + optional text/raw payload

### 3.1 Timestream Schema

Database: `edgesync_ts`
Tables:
1. `raw_readings` (memory store → magnetic after retention window)
2. `agg_1m` (down-sampled 1 minute)
3. `agg_1h` (down-sampled 1 hour)

Each table uses dimensions (low cardinality) + measures.

Dimensions (string dimensions unless noted):
- `org` (organization slug or UUID)
- `project` (project UUID)
- `device` (device UUID)
- `sensor` (normalized sensor_type)
- `fw_ver` (optional device firmware version)
- `unit` (e.g., C, %, kPa) – optional
- `source` (e.g., esp32, simulator)

Measures:
- `value` (DOUBLE) – primary numeric value
- `str_value` (VARCHAR) – OPTIONAL for string/unstructured; only write when needed to control cost
- `status_code` (BIGINT) – optional health / custom code

Time: ingestion timestamp.

Retention (example):
- `raw_readings`: 7 days in memory store, 30 days magnetic
- `agg_1m`: 30 days memory, 180 days magnetic
- `agg_1h`: 180 days memory, 730 days magnetic

### 3.2 Ingest Rules

1. If sensor value is numeric → write measure `value` only.
2. If sensor value is string → write `value=0` + `str_value='raw'` (mirrors current WidgetSample strategy) OR create separate measurement category; evaluate cost.
3. Bulk ingestion uses Timestream BatchWriteRecords (max 100 records/batch) with grouping by table.

### 3.3 Aggregation Flow

Lambda / ECS scheduled every minute:
- Query last minute of `raw_readings` grouped by (org, project, device, sensor)
- Compute: avg, min, max, count, last
- Write to `agg_1m` with measures: `avg_value`, `min_value`, `max_value`, `count`, `last_value` (multi-measure record)

Hourly job: down-sample `agg_1m` into `agg_1h` similarly.

### 3.4 Flow & Dashboard Query Strategy

Use case | Table | Query Pattern
---------|-------|--------------
Live widget (≤ latest 50) | Keep existing Postgres `WidgetSample` ring buffer (fast, low overhead) | Already implemented
Recent timeline (last 5–30 min) | `raw_readings` | Filter dims + ORDER BY time DESC LIMIT N
Trend (last 24h – 7d) | `agg_1m` | Aggregate again client-side if needed
Long range (weeks+) | `agg_1h` | Direct
Anomaly detection / ML | mix | Export to S3 via Timestream + Athena for offline training

## 4. Migration Strategy

Phase | Action | Risk Mitigation
----- | ------ | ---------------
0 | Switch SQLite → Postgres for relational operational tables | Standard Django migration
1 | Dual-write raw sensor data: Postgres `SensorData` + Timestream `raw_readings` | Feature flag `TS_DUAL_WRITE=on`
2 | Verify parity (sample queries vs Postgres aggregates) | Automated nightly diff report
3 | Stop writing numeric data to Postgres (keep only legacy/backup) | Read path still Postgres for existing screens
4 | Refactor APIs to source from Timestream for historical endpoints | Side-by-side staging endpoints `/api/v2/...`
5 | Drop/partition large Postgres `SensorData` (or leave minimal retention) | Backup snapshot before prune

## 5. Code Integration Points

File | Change
---- | ------
`sensors/consumers.py` | After `save_sensor_data`, enqueue async batch writer (Celery) or direct Timestream write (non-blocking)
`services/timeseries.py` (new) | Wrapper: `write_raw(records: List[SensorRecord])`, `query_series(...)`
`settings.py` | AWS creds (IAM role), feature flags, retention env vars
`tests/test_timeseries_parity.py` | Parity assertions dual-write phase

### 5.1 Pseudocode – Write Adapter
```python
# services/timeseries.py
import boto3, time
from datetime import datetime, timezone
from typing import Sequence

ts_client = boto3.client('timestream-write')

RAW_TABLE = 'raw_readings'
DB = 'edgesync_ts'

def build_record(org, project, device, sensor, unit, value, str_value=None, source='esp32'):    
    dimensions = [
        {'Name': 'org', 'Value': org},
        {'Name': 'project', 'Value': project},
        {'Name': 'device', 'Value': device},
        {'Name': 'sensor', 'Value': sensor},
        {'Name': 'source', 'Value': source},
    ]
    if unit:
        dimensions.append({'Name': 'unit', 'Value': unit})

    measures = []
    if isinstance(value, (int, float)):
        measures.append({
            'Name': 'value', 'Value': str(value), 'Type': 'DOUBLE'
        })
    if str_value is not None:
        measures.append({
            'Name': 'str_value', 'Value': str(str_value), 'Type': 'VARCHAR'
        })
    ts = str(int(time.time() * 1000))  # ms precision
    return {
        'Dimensions': dimensions,
        'Time': ts,
        'TimeUnit': 'MILLISECONDS',
        'MeasureName': 'telemetry',
        'MeasureValueType': 'MULTI',
        'MeasureValues': measures
    }

def write_batch(records: Sequence[dict]):
    if not records: return
    # Split into chunks ≤ 100
    for i in range(0, len(records), 100):
        chunk = records[i:i+100]
        ts_client.write_records(DatabaseName=DB, TableName=RAW_TABLE, Records=chunk)
```

### 5.2 Consumer Hook (Async Friendly)
Add lightweight queue (Redis list) or Celery task to avoid blocking WebSocket path.

```python
# sensors/consumers.py (inside receive loop after validation)
if settings.TS_DUAL_WRITE:
    timeseries_enqueue(device_id=device_uuid, org=org_slug, project=project_uuid, sensor=sensor_type, value=value, unit=unit, str_value=str_val)
```

### 5.3 Query Adapter (Simplified)
```python
# services/timeseries_query.py
import boto3
query = boto3.client('timestream-query')

def query_recent(org, project, device, sensor, since_minutes=15):
    sql = f"""
        SELECT time, measure_value::double as value
        FROM "edgesync_ts"."raw_readings"
        WHERE org='{org}' AND project='{project}' AND device='{device}' AND sensor='{sensor}'
          AND time > ago({since_minutes}m)
        ORDER BY time DESC
        LIMIT 500
    """
    return query.query(QueryString=sql)
```

## 6. Multi-Tenant Isolation
- Enforce upstream: Only query dims the authenticated user has access to (auth service returns allowed org/project IDs).
- Implement a dimension whitelist & validate requested dims to prevent cost-spike from high-cardinality abuse.
- Add per-org write quotas (counter in Redis) to throttle abusive devices before hitting AWS cost explosions.

## 7. Cost Controls
Strategy | Detail
---------|-------
Dual-write termination | Disable Postgres path early once confidence reached
Adaptive sampling | Allow per-device down-sampling when > threshold msgs/sec
Aggregation pruning | Only keep min/avg/max/count aggregates; drop raw after retention
Backpressure | Reject writes > configured RPS per org with 429 + advisory

## 8. Failure Modes & Handling
Scenario | Mitigation
-------- | ----------
Timestream write throttling | Retry w/ exponential backoff in queue worker
Partial batch failure | Log failed records; requeue individually
Dimension explosion | Validation + enforced allowed sets
AWS outage | Buffer writes to S3 (jsonl) and replay later
High latency queries | Use aggregated tables; pre-warm parameterized queries

## 9. Rollout Timeline (Indicative)
Week 0–1: Infra provisioning + feature flags + skeleton adapter
Week 2: Dual-write numeric data; parity tests
Week 3: Aggregation Lambda + 1m table
Week 4: Historical API v2 endpoints
Week 5: Switch dashboard historical queries to Timestream
Week 6: Disable Postgres writes (raw), retention purge

## 10. Open Questions
- Max acceptable telemetry ingestion latency (ms)?
- Estimated peak writes/sec initial customers? (Need for buffering tier?)
- Need encryption at field level or rely on transport + IAM?
- Future text/unstructured payload strategy (images, logs) → S3 not Timestream.

## 11. Success Criteria
- P95 ingest → query availability < 5s for last 5 minutes data.
- No WebSocket latency increase > 10ms after dual-write enabled.
- Cost per 1M points within forecast variance ±15% after 30 days.
- Data parity diff script error rate < 0.1% before cutover.

---
This design isolates time-series growth, reduces relational bloat, and sets the foundation for scalable analytics.
