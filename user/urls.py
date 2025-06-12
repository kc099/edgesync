from django.urls import path
from . import views

urlpatterns = [
    path('public-key/', views.get_public_key, name='get_public_key'),
    path('login/', views.login_view, name='login'),
    path('signup/', views.signup_view, name='signup'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile_view, name='profile'),
] 