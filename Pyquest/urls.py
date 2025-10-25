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
    path("forum/", views.forum, name="forum"),
    path('create/', views.create_post, name='create_post'),  # Nome correto
    path('forum/<int:post_id>/edit/', views.edit_post, name='edit_post'),
    path("forum/<int:post_id>/delete/", views.delete_post, name="delete_post"),
    path('forum/<int:post_id>/comment/', views.add_comment, name='add_comment'),
    path('forum/<int:post_id>/like/', views.like_post, name='like_post'),
    path('forum/comment/<int:comment_id>/like/', views.like_comment, name='like_comment'),
    path('forum/<int:post_id>/reply/<int:parent_id>/', views.reply_comment, name='reply_comment'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('criar-conteudo/', views.criar_conteudo, name='criar_conteudo'),
    path('api/modulos/<int:capitulo_id>/', views.get_modulos_ajax, name='get_modulos_ajax'),
    path('api/criar-capitulo/', views.criar_capitulo_ajax, name='criar_capitulo_ajax'),
    path('api/criar-modulo/', views.criar_modulo_ajax, name='criar_modulo_ajax'),
    path('gerenciar-conteudo/', views.gerenciar_conteudo, name='gerenciar_conteudo'),
    path('editar-conteudo/<int:aula_id>/', views.editar_conteudo, name='editar_conteudo'),
    path('excluir-conteudo/<int:aula_id>/', views.excluir_conteudo, name='excluir_conteudo'),
    path('alternar-status-aula/<int:aula_id>/', views.alternar_status_aula, name='alternar_status_aula'),
    path("forum/top_hashtags/", views.top_hashtags_json, name="top_hashtags_json"),
]