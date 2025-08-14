# Observability Implementation Plan

Author: Platform Engineering
Status: Draft (v1)
Last Updated: 2025-08-12

## 1. Goals
Provide actionable visibility across ingest → processing (flows) → delivery (WebSockets, API) to:
1. Measure product funnel (device onboarding → first data → dashboard visualization → retained usage).
2. Detect performance regressions & errors rapidly.
3. Enable capacity planning (flow concurrency, message throughput).
4. Supply metrics for pricing & entitlements (messages, flow-runtime).

## 2. Pillars
| Pillar | Stack | Scope |
|--------|-------|-------|
| Metrics | Prometheus (exporters) / OTLP → Prometheus | Rates, counts, durations |
| Traces | OpenTelemetry SDK → OTLP collector (Tempo/Jaeger) | Request/flow/data path spans |
| Logs | Structured JSON (Loki or CloudWatch) | Audit + errors + correlation IDs |
| Events (Product) | Analytics pipeline (Snowplow/Segment or custom) | Funnel & activation |

Initial implementation can co-locate Collector + Prometheus + Loki in docker-compose for dev; production deploy via ECS or EC2.

## 3. Instrumentation Targets
### 3.1 Backend (Django / Channels)
Component | Metrics | Traces | Logs (Key Fields)
--------- | ------- | ------ | -----------------
WebSocket ingest (SensorDataConsumer.receive) | ingest_messages_total, ingest_batch_size, ingest_processing_latency_ms | span: ws.receive -> save_db -> dual_write -> widget_broadcast | org, project, device, sensor, message_id
Widget broadcast | broadcast_queue_size, broadcast_latency_ms | span: ws.broadcast | widget_id, flow_node, latency_ms
Flow executor (future) | flow_exec_duration_ms, flow_exec_active, node_exec_duration_ms, flow_failures_total | span: flow.exec(root) -> node.exec(child...) | flow_id, exec_id, node_id, status
DB interactions | sensor_insert_latency_ms | auto via otel instrumentation | n/a
Timestream adapter | ts_write_batch_latency_ms, ts_write_failures_total | span: ts.write_batch | batch_size, retry_count
Auth / permissions | auth_failures_total | span: auth.check | user_id, reason
HTTP APIs (DRF) | request_duration_ms{path,method,status} | auto instrumentation | path, status_code, org
Celery tasks | task_duration_ms, task_retries_total | span per task | task_name, status

### 3.2 Frontend
- WebSocket connect latency
- Time to first widget render (from ws open to first data point)
- Flow of: login → create org → add device → first data in widget (timestamps sent to analytics endpoint)

### 3.3 Product Funnel Events (Server authoritative when possible)
Event | Trigger | Properties
----- | ------- | ----------
OrgCreated | Organization.save (post_create) | org_id, user_id
ProjectCreated | Project.save | project_id, org_id
DeviceRegistered | Device.save | device_uuid, org_id
FirstDeviceData | first SensorData per device | device_uuid, org_id, time_since_registration_s
FirstDashboardWidget | DashboardTemplate created w/widget count >0 | dashboard_uuid, org_id
FirstLiveWidgetData | first WidgetSample for that widget | widget_id, time_since_widget_created_s
FlowCreated | FlowDiagram.save | flow_uuid, project_id
FlowExecuted | FlowExecution status=completed | duration_ms, node_count
UserRetentionCheck | daily job | day_x_active: bool

## 4. Correlation & Context Strategy
- Generate a `request_id` (UUID4) for each HTTP request (middleware) and a `trace_id` from OTel; propagate via response header `X-Request-ID`.
- For WebSockets: on connect, assign `connection_id` and embed in logs + attach as attribute to spans.
- Device messages: assign `message_id` (uuid4) at ingestion; included in broadcast so client can ACK or reference issues.
- Include tenant context: `org_id`, `project_id`, `device_uuid` in every log line and span attributes (when applicable).

## 5. Data Model for Structured Logs
JSON fields:
```
{
  "ts": "2025-08-12T10:23:11.234Z",
  "level": "INFO|WARN|ERROR",
  "msg": "...",
  "logger": "edgesync.sensors.consumer",
  "request_id": "uuid",
  "trace_id": "otel-trace-id",
  "span_id": "otel-span-id",
  "org_id": "...",
  "project_id": "...",
  "device_uuid": "...",
  "widget_id": "...",
  "flow_id": "...",
  "exec_id": "...",
  "metric_overrides": {"latency_ms": 12.3}
}
```

## 6. Implementation Steps
Phase | Steps | Output
----- | ----- | ------
1 | Add OpenTelemetry dependencies & base config | OTEL SDK initialized
2 | Logging formatter for JSON + context filter | Structured logs
3 | Metrics registry (Prometheus client) + /metrics endpoint | Scrapeable metrics
4 | Instrument key code paths (manual spans + counters) | Granular telemetry
5 | Product funnel event emitter + async writer (Kafka/SQS or DB table) | Growth analytics
6 | Dashboard: internal Observability view (charts of key metrics) | Ops visibility

### 6.1 Dependencies (Python)
Add to `requirements.txt`:
```
opentelemetry-api
opentelemetry-sdk
opentelemetry-exporter-otlp
opentelemetry-instrumentation-django
opentelemetry-instrumentation-logging
opentelemetry-instrumentation-requests
prometheus-client
```
(Version pinning after initial POC.)

### 6.2 Settings Snippet
```python
# settings.py (pseudo)
OTEL_ENABLED = env.bool("OTEL_ENABLED", False)
if OTEL_ENABLED:
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    provider = TracerProvider(resource=Resource.create({"service.name": "edgesync-backend"}))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"))))
    from opentelemetry import trace
    trace.set_tracer_provider(provider)
```

### 6.3 Prometheus Metrics Setup
```python
# monitoring/metrics.py
from prometheus_client import Counter, Histogram, Gauge

INGEST_MESSAGES = Counter('ingest_messages_total', 'Total sensor messages', ['org','project','device','sensor'])
INGEST_BATCH_SIZE = Histogram('ingest_batch_size', 'Batch size distribution')
INGEST_LATENCY = Histogram('ingest_processing_latency_ms', 'Ingest processing latency ms')
BROADCAST_LATENCY = Histogram('broadcast_latency_ms', 'Latency from ingest to broadcast ms')
FLOW_EXEC_DURATION = Histogram('flow_exec_duration_ms', 'Flow execution duration ms', ['flow_id'])
FLOW_ACTIVE = Gauge('flow_exec_active', 'Active flow executions')
```
Expose `/metrics` via simple Django view guarded (optionally) by basic auth.

### 6.4 Code Instrumentation Example
`sensors/consumers.py` receive method (pseudo):
```python
start = time.time()
message_id = uuid4()
# after parsing each reading:
INGEST_MESSAGES.labels(org=org, project=project, device=device_uuid, sensor=sensor_type).inc()
# ... after DB + widget broadcast
INGEST_LATENCY.observe((time.time()-start)*1000)
```
Broadcast latency: capture timestamp when message first seen; include in WidgetSample broadcast payload optionally for frontend measurement.

### 6.5 Tracing Spans
Name Convention:
- HTTP: `http <METHOD> <path>` (auto)
- WS ingest: `ws.ingest.receive`
- Write sensor row: `db.sensor.insert`
- Dual write: `ts.write`
- Widget broadcast: `ws.broadcast.widget`
- Flow execution root: `flow.execute` with attributes: flow_id, node_count
- Node execution: `flow.node.execute` (node_id, type)

### 6.6 Product Funnel Event Emitter
Minimal table `product_events`:
Columns: id (pk), event_type, user_id, org_id, project_id, entity_id, properties(json), created_at.
Helper: `emit_event(event_type, **kwargs)` (writes row + optionally publishes to queue later).
Nightly job builds funnel metrics aggregated into `product_event_aggregates` or exports to analytics warehouse.

### 6.7 Dashboards (Initial)
Metric | Chart Type | Notes
------ | ---------- | -----
Ingest RPS (overall & per org) | Line | Detect spikes
Ingest latency P50/P95 | Heatmap or line | Performance SLA
Broadcast latency P95 | Line | UI reactivity
Active WebSocket connections | Gauge | Capacity planning
Flow executions success vs failure | Stacked bar | Reliability
Top orgs by messages last 24h | Table | Billing insight
Time to first device data | Distribution | Activation metric

### 6.8 Alerting Threshold Examples
Alert | Condition | Initial Threshold
------|----------|------------------
High ingest latency | P95 ingest > 500ms for 5m | Page if > 1s
Broadcast lag | P95 broadcast > 300ms | Warning at 500ms
Flow failure spike | failure_rate > 5% over 10m | Investigate
Message drop (dual-write) | ts_write_failures_total > 0 in 5m | Critical
Abusive org | ingest_messages_total{org=X} growth > 5x baseline in hour | Rate limit

## 7. Rollout Plan
Week | Deliverables
---- | ------------
1 | Add dependencies, JSON logging formatter, metrics endpoint, baseline ingest metrics
2 | WebSocket & broadcast spans + metrics, product event table & first 5 events
3 | Flow execution instrumentation, alert rules, internal Grafana dashboard
4 | Dual-write metrics (Timestream) + funnel report prototype + doc handoff

## 8. Success Criteria
- P95 ingest + broadcast latency visible & < target thresholds.
- Funnel report (activation conversion %) generated weekly.
- Ability to attribute >90% flow failures to categorized causes (error codes).
- Billing-friendly counts (messages per org, flow runtime) queryable quickly.

## 9. Future Enhancements
- Real user monitoring (RUM) for frontend (Core Web Vitals + WebSocket UI latency)
- Anomaly detection on ingest patterns
- Trace sampling adjustments (head vs tail) for high-volume flows
- SLO budgeting & error budget burn dashboards

---
This plan delivers a pragmatic, phased observability foundation aligned with upcoming time-series migration and scaling needs.
