from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    # <int:test_id> означает, что сюда подставится число (id теста)
    path('test/<int:test_id>/', views.test_detail, name='test_detail'),
]
