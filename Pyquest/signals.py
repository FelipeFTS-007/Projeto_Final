# signals.py
from django.db.models.signals import post_save, m2m_changed
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Perfil, AulaConcluida, Post, Comentario, Conquista
from .conquistas_manager import ConquistaManager

@receiver(post_save, sender=Perfil)
def verificar_conquistas_perfil(sender, instance, **kwargs):
    """Verifica conquistas relacionadas a XP e nível quando o perfil é atualizado"""
    ConquistaManager.verificar_conquistas_usuario(instance.user, 'xp_total')
    ConquistaManager.verificar_conquistas_usuario(instance.user, 'nivel_atingido')

@receiver(post_save, sender=AulaConcluida)
def verificar_conquistas_aulas(sender, instance, **kwargs):
    """Verifica conquistas relacionadas a aulas concluídas"""
    if instance.teoria_concluida and instance.pratica_concluida:
        ConquistaManager.verificar_conquistas_usuario(instance.usuario, 'aulas_concluidas')

@receiver(post_save, sender=Post)
def verificar_conquistas_posts(sender, instance, created, **kwargs):
    """Verifica conquistas relacionadas a posts"""
    if created:
        ConquistaManager.verificar_conquistas_usuario(instance.autor, 'postagens_forum')

@receiver(post_save, sender=Comentario)
def verificar_conquistas_comentarios(sender, instance, created, **kwargs):
    """Verifica conquistas relacionadas a comentários"""
    if created:
        ConquistaManager.verificar_conquistas_usuario(instance.autor, 'comentarios')

# Signal para quando o streak é atualizado
@receiver(post_save, sender=Perfil)
def verificar_conquistas_streak(sender, instance, **kwargs):
    """Verifica conquistas relacionadas a sequência de dias"""
    if instance.sequencia > 0:
        ConquistaManager.verificar_conquistas_usuario(instance.user, 'sequencia_dias')