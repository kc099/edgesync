from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # Accepts 'ws/sensors/' or '/ws/sensors/' (Channels passes path without leading slash)
    re_path(r'^/?ws/sensors/?$', consumers.SensorDataConsumer.as_asgi()),
    # Widget live-data stream
    re_path(r'^/?ws/widgets/(?P<widget_id>[^/]+)/?$', consumers.WidgetDataConsumer.as_asgi()),
] 