Here is how the two data-paths work and how they fit into the code you already have.
1. Device-node widgets (“raw sensor → widget”)
Backend
When a widget is created for a device variable we insert/ensure one lightweight row in TrackedVariable and stream every new reading into WidgetSample (max 50 rows, trimmed in the same DB write).
Frontend
When the widget mounts it does one HTTP GET to
…/dashboard-templates/<uuid>/widgets/<widget_id>/samples – that returns the 50 rows from WidgetSample.
Immediately after that it opens its WebSocket (ws/widgets/<widget_id>/).
Every new reading pushed by the consumer is appended to the in-memory array (and UI re-renders).
We don’t use localStorage; the 50-sample ring buffer already lives in the DB, so a browser refresh simply pulls them again via the GET. (Keeps the client trivial and guarantees consistency across tabs.)
Why not cache in the browser?
Persistence across page reloads is already solved by WidgetSample.
Using localStorage would require extra reconciliation logic and would only duplicate what the DB is storing anyway.
2. Output-node widgets (“flow processing → widget”)
Execution path you already have
MQTT/device data
 ⭢ (optional) DeviceProcessor “read” node
 ⭢ Function / custom / moving-average processors (NodeScheduler executes them according to dependency graph)
 ⭢ Display / Output node
 ⭢ FlowExecutor._on_node_complete() stores the result in FlowNodeOutput and pushes a WebSocket message (flow_node_output_<flow_uuid>_<node_id> group).
That part of the stack is already in your repo; you successfully wrote to FlowNodeOutput when a flow executed earlier.
Widget consumption
Widget that targets an output node continues to call the existing REST endpoints
/flows/<flow_uuid>/nodes/<node_id>/output and /output/history/ for the first render.
It then opens ws/flows/<flow_uuid>/nodes/<node_id>/output/ (FlowNodeOutputConsumer) for live updates.
The only thing you still need is a way to run the flow automatically (cron or an MQTT trigger) if you want continuous processing; pressing “Execute” manually is enough for PoC.
3. Why two different tables?
You could try to shoe-horn both device readings and processed node outputs into a single table, but:
Device widgets
 • Don’t need full execution context, error fields, etc.
 • Need to expire aggressively (limit 50).
Flow-node widgets
 • Already have FlowExecution → FlowNodeOutput chain; the schema encodes exec-id and timestamp.
 • Deleting old rows blindly would break historical charts.
So keeping a tiny ring-buffer table (WidgetSample) for raw sensor widgets avoids touching the heavier execution tables and lets you expire rows cheaply with one DELETE query.
The extra schema overhead is minimal: two small tables, no joins outside their own endpoint.
4. Does the existing executor really stream through the processors?
Yes. Quick recap:
FlowExecutor.execute()
 - builds NodeScheduler, passing it the nodes list and reverse dependency graph.
NodeScheduler.execute_flow()
 - walks the resolved levels; for each node it calls _execute_single_node().
_execute_single_node()
 - instantiates the Processor via ProcessorFactory.
 - Supplies each processor the merged outputs of its predecessors (get_node_input_data).
 - Collects the result and saves it in the ExecutionContext.
After a node is marked “completed” _on_node_complete() fires, persists to FlowNodeOutput and emits the WebSocket update.
So every processor in the chain sees the predecessors’ data exactly once per execution, produces its own output, and the final display / output node ends up in FlowNodeOutput, which your widget can subscribe to. The only prerequisite is that a DeviceProcessor at the head of the chain can read a sensor value; that’s why we needed the devices table.
5. Summary of responsibilities
DB tables
WidgetSample → short-term ring buffer for sensor widgets (≤ 50 rows).
FlowNodeOutput → full history for processed/output widgets.
Backend actors
sensors/consumers.py → capture live MQTT readings, persist to WidgetSample, broadcast to widget group.
FlowExecutor → run flow, persist results to FlowNodeOutput, broadcast to node group.
Frontend hooks
useDeviceWidgetData() → GET samples, then WebSocket.
useFlowNodeWidgetData() → GET /output/history, then WebSocket.
With this split you cover both instant device visualisation and flow-derived analytics without overloading any single model, and without storing unnecessary data.