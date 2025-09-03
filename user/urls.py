from django.urls import path
from . import views
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    # Authentication endpoints
    path('public-key/', views.public_key_view, name='public_key'),
    path('login/', views.login_view, name='login'),
    path('signup/', views.signup_view, name='signup'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile_view, name='profile'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('google-oauth/', views.google_oauth_view, name='google_oauth'),
    
    # Organization endpoints
    path('organizations/', views.organizations_view, name='organizations'),
    path('organizations/<int:org_id>/', views.organization_detail_view, name='organization_detail'),
    path('organizations/<int:org_id>/members/', views.organization_members_view, name='organization_members'),
    path('organizations/<int:org_id>/members/<int:member_id>/', views.organization_member_detail_view, name='organization_member_detail'),
    
    # Project endpoints
    path('projects/', views.projects_view, name='projects'),
    path('projects/<uuid:project_uuid>/', views.project_detail_view, name='project_detail'),
    
    # Dashboard template endpoints
    path('dashboard-templates/', views.dashboard_templates_view, name='dashboard_templates'),
    path('dashboard-templates/<uuid:template_uuid>/', views.dashboard_template_detail_view, name='dashboard_template_detail'),
    path('dashboard-templates/<uuid:template_uuid>/widgets/<str:widget_id>/data/', views.dashboard_widget_data_view, name='dashboard_widget_data'),
    path('dashboard-templates/<uuid:template_uuid>/widgets/<str:widget_id>/samples/', views.widget_samples_view, name='widget_widget_samples'),
] 