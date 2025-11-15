# conquistas_manager.py
from django.db.models import Count
from .models import Conquista, Perfil, AulaConcluida, Post, Comentario
from django.utils import timezone

class ConquistaManager:
    
    @staticmethod
    def verificar_conquistas_usuario(usuario, tipo_evento=None):
        """Verifica e desbloqueia conquistas para um usuário"""
        try:
            conquistas_para_verificar = Conquista.objects.filter(ativo=True)
            
            if tipo_evento:
                conquistas_para_verificar = conquistas_para_verificar.filter(tipo_evento=tipo_evento)
            
            conquistas_desbloqueadas = []
            
            for conquista in conquistas_para_verificar:
                # Verificar se o usuário já possui a conquista
                if conquista.usuarios.filter(id=usuario.id).exists():
                    continue
                
                # Calcular progresso atual
                progresso = conquista.calcular_progresso(usuario)
                
                # Se atingiu a meta, desbloquear conquista
                if progresso['atingiu_meta']:
                    conquista.usuarios.add(usuario)
                    
                    # Adicionar XP da recompensa
                    perfil = usuario.perfil
                    perfil.xp += conquista.xp_recompensa
                    perfil.save()
                    
                    conquistas_desbloqueadas.append(conquista)
                    
                    print(f"🏆 Conquista desbloqueada: {conquista.titulo} para {usuario.username}")
                    
                    # Registrar atividade
                    from .models import Atividade
                    Atividade.objects.create(
                        user=usuario,
                        titulo=f"Conquista desbloqueada: {conquista.titulo}",
                        xp_ganho=conquista.xp_recompensa
                    )
            
            return conquistas_desbloqueadas
            
        except Exception as e:
            print(f"❌ Erro em verificar_conquistas_usuario: {e}")
            return []
    
    @staticmethod
    def verificar_todas_conquistas(usuario):
        """Verifica todas as conquistas possíveis para um usuário"""
        tipos_evento = [
            'xp_total', 'nivel_atingido', 'aulas_concluidas', 
            'modulos_concluidos', 'sequencia_dias', 'questoes_corretas',
            'tempo_estudo', 'postagens_forum', 'comentarios', 
            'likes_recebidos', 'conquistas_desbloqueadas'
        ]
        
        todas_conquistas = []
        for tipo in tipos_evento:
            conquistas = ConquistaManager.verificar_conquistas_usuario(usuario, tipo)
            todas_conquistas.extend(conquistas)
        
        return todas_conquistas