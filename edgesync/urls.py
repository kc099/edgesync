"""
URL configuration for edgesync project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.contrib.auth import views as auth_views
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

def home_view(request):
    """Redirect logged-in users to dashboard, show landing page for anonymous users"""
    if request.user.is_authenticated:
        return redirect('sensors:dashboard')
    return TemplateView.as_view(template_name='landing.html')(request)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', home_view, name='landing'),
    path('accounts/', include('allauth.urls')),
    path('api/', include('user.urls')),  # Add user authentication APIs
    path('api/', include('flows.urls')),  # Add flows APIs
    path('', include('sensors.urls')),  # Include sensors URLs at root level
    
    # API Documentation URLs (Swagger/OpenAPI)
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    
    # Documentation URLs
    path('docs/', TemplateView.as_view(template_name='docs.html'), name='docs'),
    path('docs/getting-started/', TemplateView.as_view(template_name='docs_getting_started.html'), name='docs_getting_started'),
    path('docs/api-reference/', TemplateView.as_view(template_name='docs_api_reference.html'), name='docs_api_reference'),
    path('docs/tutorials/', TemplateView.as_view(template_name='docs_tutorials.html'), name='docs_tutorials'),
    path('docs/best-practices/', TemplateView.as_view(template_name='docs_best_practices.html'), name='docs_best_practices'),
]
