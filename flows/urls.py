from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import FlowDiagramViewSet

router = DefaultRouter()
router.register(r'flows', FlowDiagramViewSet, basename='flows')

urlpatterns = [
    path('', include(router.urls)),
] 