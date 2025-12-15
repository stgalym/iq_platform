from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('test/<int:test_id>/', views.test_detail, name='test_detail'),
    # НОВАЯ СТРОКА:
    path('result/<int:result_id>/', views.result_detail, name='result_detail'),
    path('hr/dashboard/', views.hr_dashboard, name='hr_dashboard'),
    path('invite/<uuid:uuid>/', views.accept_invitation, name='accept_invitation'),
    path('upgrade/<str:plan_type>/', views.upgrade_profile, name='upgrade_profile'),
]
