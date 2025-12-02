from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('test/<int:test_id>/', views.test_detail, name='test_detail'),
    # НОВАЯ СТРОКА:
    path('result/<int:result_id>/', views.result_detail, name='result_detail'),
]
