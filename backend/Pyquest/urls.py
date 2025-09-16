from django.urls import path
from . import views

urlpatterns = [
    path("cadastro/", views.cadastro_view, name="cadastro"),
    path("", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path('home/', views.home, name='home'),
    path('conteudo/', views.conteudo, name='conteudo'),
    path('modulos/', views.modulos, name='modulos'),
    path('tarefas/', views.tarefas, name='tarefas'),
    path('teoria/', views.teoria, name='teoria'),
    path('pratica/', views.pratica, name='pratica'),
    path('perfil/', views.perfil, name='perfil'),
    path('ranking/', views.ranking, name='ranking'),
    path('forum/', views.forum, name='forum'),
    path('dashboard/', views.dashboard, name='dashboard'),
]