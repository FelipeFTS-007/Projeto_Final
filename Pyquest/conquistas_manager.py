# PyQuest/conquistas_manager.py
from django.db.models import Count
from .models import Conquista, Perfil, AulaConcluida, Post, Comentario
from django.utils import timezone

class ConquistaManager:
    
    @staticmethod
    def verificar_conquistas_usuario(usuario, tipo_evento=None, valor=0):
        """Verifica e desbloqueia conquistas para um usuário"""
        conquistas_para_verificar = Conquista.objects.filter(ativo=True)
        
        if tipo_evento:
            conquistas_para_verificar = conquistas_para_verificar.filter(tipo_evento=tipo_evento)
        
        conquistas_desbloqueadas = []
        
        for conquista in conquistas_para_verificar:
            if not conquista.usuarios.filter(id=usuario.id).exists():
                progresso = conquista.calcular_progresso(usuario)
                
                if progresso['atingiu_meta']:
                    conquista.usuarios.add(usuario)
                    
                    # Adicionar XP da recompensa
                    perfil = usuario.perfil
                    perfil.xp += conquista.xp_recompensa
                    perfil.save()
                    
                    conquistas_desbloqueadas.append(conquista)
                    
                    # Registrar atividade
                    from .models import Atividade
                    Atividade.objects.create(
                        user=usuario,
                        titulo=f"Conquista desbloqueada: {conquista.titulo}",
                        xp_ganho=conquista.xp_recompensa
                    )
        
        return conquistas_desbloqueadas
    
    @staticmethod
    def verificar_todas_conquistas(usuario):
        """Verifica todas as conquistas possíveis para um usuário"""
        return ConquistaManager.verificar_conquistas_usuario(usuario)