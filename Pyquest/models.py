from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import Group, Permission
from django.db.models.signals import post_migrate
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
import re


class Perfil(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    xp = models.IntegerField(default=0)
    nivel = models.IntegerField(default=1)
    vidas = models.IntegerField(default=10)
    max_vidas = models.IntegerField(default=10)
    ultima_regeneracao = models.DateTimeField(default=timezone.now)
    conquistas = models.IntegerField(default=0)
    total_conquistas = models.IntegerField(default=50)
    sequencia = models.IntegerField(default=0)
    # CAMPOS ADICIONADOS DO ARQUIVO 2
    sequencia_maxima = models.IntegerField(default=0)
    ultima_atividade = models.DateTimeField(null=True, blank=True)
    avatar = models.ImageField(upload_to="avatars/", default="avatars/default.png")
    descricao = models.TextField(blank=True, null=True, default="Ainda não escreveu nada.")
    licoes = models.IntegerField(default=0)
    github = models.URLField(max_length=200, blank=True, null=True)
    linkedin = models.URLField(max_length=200, blank=True, null=True)
    tempo_total_estudo = models.IntegerField(default=0)  # em segundos
    xp_hoje = models.IntegerField(default=0)
    acertos_seguidos = models.IntegerField(default=0)
    recorde_acertos = models.IntegerField(default=0)
    precisao_geral = models.IntegerField(default=0)  # Em porcentagem
    ja_fez_atividade_hoje = models.BooleanField(default=False)
    ultima_verificacao_diaria = models.DateTimeField(auto_now_add=True)
    background_image = models.ImageField(
        upload_to="backgrounds/", 
        blank=True, 
        null=True,
        default="backgrounds/default-bg.jpg",
        verbose_name="Imagem de Fundo"
    )
    ultima_atualizacao_vidas = models.DateTimeField(auto_now=True)
    
    def atualizar_estatisticas_dashboard(self):
        """Atualiza estatísticas para o dashboard"""
        # Implemente a lógica para calcular precisão, acertos seguidos, etc.
        pass

    def calcular_xp_para_proximo_nivel(self):
        """Calcula o XP total necessário para o próximo nível"""
        return self.calcular_xp_para_nivel(self.nivel + 1)

    def adicionar_xp(self, xp_ganho):
        """Adiciona XP e verifica se subiu de nível"""
        self.xp += xp_ganho
        xp_necessario = self.calcular_xp_para_proximo_nivel()
        
        niveis_ganhos = 0
        while self.xp >= xp_necessario:
            self.nivel += 1
            niveis_ganhos += 1
            # Não subtraímos o XP - ele continua acumulando!
            xp_necessario = self.calcular_xp_para_proximo_nivel()
        
        self.save()
        return niveis_ganhos

    def get_progresso_nivel(self):
        """Retorna o progresso para o próximo nível em porcentagem (0-100)"""
        if self.nivel == 1:
            # Para o nível 1, o progresso é baseado no XP atual
            xp_necessario = self.calcular_xp_para_proximo_nivel()
            if xp_necessario > 0:
                return min(100, int((self.xp / xp_necessario) * 100))
            return 0
        else:
            # Para níveis > 1, calculamos o XP do nível atual
            xp_inicio_nivel = self.calcular_xp_para_nivel(self.nivel - 1)
            xp_fim_nivel = self.calcular_xp_para_proximo_nivel()
            xp_nivel_atual = self.xp - xp_inicio_nivel
            xp_necessario_nivel = xp_fim_nivel - xp_inicio_nivel
            
            if xp_necessario_nivel > 0:
                progresso = min(100, int((xp_nivel_atual / xp_necessario_nivel) * 100))
                return max(0, progresso)  # Garante que não seja negativo
            return 0

    def calcular_xp_para_nivel(self, nivel_alvo):
        """Calcula o XP total necessário para alcançar um nível específico"""
        xp_total = 0
        for nivel in range(1, nivel_alvo):
            xp_total += int(100 * (nivel ** 1.5))
        return xp_total
    
    def tempo_estudo_formatado(self):
        """Retorna o tempo formatado como HH:MM:SS ou MM:SS"""
        tempo_total_segundos = self.tempo_total_estudo
        minutos_totais = tempo_total_segundos // 60
        segundos_restantes = tempo_total_segundos % 60
        horas = minutos_totais // 60
        minutos = minutos_totais % 60
        
        if horas > 0:
            return f"{horas:02d}:{minutos:02d}:{segundos_restantes:02d}"
        else:
            return f"{minutos:02d}:{segundos_restantes:02d}"
    
    def contar_modulos_concluidos(self):
        """Conta quantos módulos o usuário concluiu completamente"""
        modulos_concluidos = 0
        modulos = Modulo.objects.filter(ativo=True).prefetch_related('aulas')
        
        for modulo in modulos:
            total_aulas = modulo.aulas.filter(ativo=True).count()
            if total_aulas > 0:
                # Contar aulas totalmente concluídas (teoria + prática)
                aulas_concluidas = AulaConcluida.objects.filter(
                    usuario=self.user,
                    aula__in=modulo.aulas.all(),
                    teoria_concluida=True,
                    pratica_concluida=True
                ).count()
                
                # Considerar módulo concluído se TODAS as aulas foram concluídas
                if aulas_concluidas == total_aulas:
                    modulos_concluidos += 1
        
        return modulos_concluidos

    # ===== MÉTODOS DO SISTEMA DE STREAK =====
    
    def verificar_e_atualizar_streak(self):
        """
        Lógica CORRIGIDA: Só aumenta streak quando há atividade
        Retorna: (novo_streak, streak_zerado, streak_aumentado)
        """
        agora = timezone.now()
        streak_zerado = False
        streak_aumentado = False
        
        print(f"🕒 Última atividade: {self.ultima_atividade}")
        print(f"🕒 Agora: {agora}")
        print(f"📊 Sequência atual: {self.sequencia}")
        print(f"🏆 Sequência máxima: {self.sequencia_maxima}")
        
        # Se nunca teve atividade OU streak é 0, iniciar streak em 1
        if not self.ultima_atividade or self.sequencia == 0:
            self.sequencia = 1
            self.ultima_atividade = agora
            # CORREÇÃO: Atualizar sequência máxima também
            if self.sequencia > self.sequencia_maxima:
                self.sequencia_maxima = self.sequencia
            self.save()
            print("🎯 Primeira atividade - Streak iniciado: 1")
            return 1, False, True
        
        # Verificar diferença em dias
        data_ultima = self.ultima_atividade.date()
        data_hoje = agora.date()
        dias_diferenca = (data_hoje - data_ultima).days
        
        print(f"📅 Última atividade: {data_ultima}")
        print(f"📅 Hoje: {data_hoje}")
        print(f"📅 Diferença em dias: {dias_diferenca}")
        
        streak_anterior = self.sequencia
        
        if dias_diferenca == 0:
            # Já teve atividade HOJE - apenas atualiza hora, NÃO aumenta streak
            print("✅ Já teve atividade hoje - streak mantido")
            self.ultima_atividade = agora
            self.save()
            streak_aumentado = False
            
        elif dias_diferenca == 1:
            # Última atividade foi ONTEM - AUMENTAR STREAK
            print("🎯 Última atividade foi ontem - AUMENTANDO STREAK")
            self.sequencia += 1
            self.ultima_atividade = agora
            
            # CORREÇÃO CRÍTICA: Atualizar sequência máxima se necessário
            if self.sequencia > self.sequencia_maxima:
                self.sequencia_maxima = self.sequencia
                print(f"🏆 NOVO RECORDE! Sequência máxima: {self.sequencia_maxima}")
            
            streak_aumentado = True
            print(f"📈 Streak aumentado: {streak_anterior} → {self.sequencia}")
            self.save()
            
        else:
            # Última atividade foi ANTES de ontem - ZERAR STREAK
            print(f"💀 Última atividade foi há {dias_diferenca} dias - ZERANDO STREAK")
            
            # Atualizar streak máximo antes de zerar
            if streak_anterior > self.sequencia_maxima:
                self.sequencia_maxima = streak_anterior
                print(f"🏆 Atualizando recorde antes de zerar: {self.sequencia_maxima}")
            
            # Zerar streak - COMEÇAR EM 0, não em 1
            self.sequencia = 0
            self.ultima_atividade = None  # Resetar para forçar nova atividade
            streak_zerado = True
            print(f"🔄 Streak zerado: {streak_anterior} → 0")
            self.save()
        
        # CORREÇÃO: Garantir que sempre salve se houve mudança
        print(f"✅ FINAL - Sequência: {self.sequencia}, Máxima: {self.sequencia_maxima}")
        
        return self.sequencia, streak_zerado, streak_aumentado
    
    def verificar_streak_automatico(self):
        """
        Verifica e corrige o streak automaticamente quando o perfil é acessado
        Zera se passou mais de 1 dia desde a última atividade
        """
        if not self.ultima_atividade:
            # Se nunca teve atividade, streak é 0
            if self.sequencia > 0:
                self.sequencia = 0
                self.save()
            return False
        
        agora = timezone.now()
        data_ultima = self.ultima_atividade.date()
        data_hoje = agora.date()
        dias_diferenca = (data_hoje - data_ultima).days
        
        print(f"🔍 Verificação automática do streak: {dias_diferenca} dias desde a última atividade")
        
        # Se passou mais de 1 dia, zerar o streak
        if dias_diferenca > 1:
            print(f"💀 Streak quebrado: {dias_diferenca} dias sem atividade")
            streak_anterior = self.sequencia
            
            # CORREÇÃO: Atualizar streak máximo antes de zerar
            if streak_anterior > self.sequencia_maxima:
                self.sequencia_maxima = streak_anterior
                print(f"🏆 Atualizando recorde na verificação automática: {self.sequencia_maxima}")
            
            # Zerar completamente - COMEÇAR EM 0, não em 1
            self.sequencia = 0
            self.ultima_atividade = None  # Resetar para forçar nova atividade
            self.save()
            
            print(f"🔄 Streak automático zerado: {streak_anterior} → 0")
            return True
        
        return False
    
    def verificar_streak_quebrado(self):
        """Verifica se o streak foi quebrado (mais de 24h sem atividade)"""
        if not self.ultima_atividade:
            return True  # Nunca teve atividade
        
        agora = timezone.now()
        diferenca = agora - self.ultima_atividade
        horas_passadas = diferenca.total_seconds() / 3600
        
        # Considera quebrado se passou MAIS de 24 horas
        return horas_passadas > 24
    
    def get_tempo_restante_streak(self):
        """Retorna tempo restante para manter o streak (em horas)"""
        if not self.ultima_atividade or self.sequencia == 0:
            return 24
        
        agora = timezone.now()
        diferenca = agora - self.ultima_atividade
        horas_passadas = diferenca.total_seconds() / 3600
        horas_restantes = 24 - horas_passadas
        
        return max(0, round(horas_restantes, 1))
    
    def get_bonus_streak(self):
        """Calcula bônus de XP baseado no streak atual"""
        # Bônus de 2% por dia de streak (máximo 50%)
        bonus_percent = min(self.sequencia * 2, 50)
        return bonus_percent / 100  # Retorna como decimal para multiplicação
    
    def reiniciar_streak(self):
        """Reinicia o streak atual (para testes)"""
        streak_anterior = self.sequencia
        self.sequencia = 0
        self.ultima_atividade = None
        self.save()
        return streak_anterior

    def regenerar_vidas(self):
        """Regenera vidas baseado no tempo passado - VERSÃO CORRIGIDA"""
        agora = timezone.now()
        
        # Se está com vidas máximas, não precisa regenerar
        if self.vidas >= self.max_vidas:
            self.ultima_atualizacao_vidas = agora
            self.save()
            return
        
        # Calcular tempo desde a última atualização
        diferenca = agora - self.ultima_atualizacao_vidas
        minutos_passados = diferenca.total_seconds() / 60
        
        # Regenera 1 vida a cada 10 minutos
        vidas_regeneradas = int(minutos_passados / 10)
        
        if vidas_regeneradas > 0:
            # Calcular novo tempo base para próxima regeneração
            minutos_restantes = minutos_passados % 10
            tempo_base = agora - timedelta(minutes=minutos_restantes)
            
            self.vidas = min(self.max_vidas, self.vidas + vidas_regeneradas)
            self.ultima_atualizacao_vidas = tempo_base
            self.save()
            print(f"✅ {vidas_regeneradas} vidas regeneradas! Total: {self.vidas}")

    def tempo_para_proxima_vida(self):
        """Retorna minutos até a próxima vida regenerar - VERSÃO CORRIGIDA"""
        if self.vidas >= self.max_vidas:
            return 0
        
        agora = timezone.now()
        diferenca = agora - self.ultima_atualizacao_vidas
        minutos_passados = diferenca.total_seconds() / 60
        minutos_restantes = 10 - (minutos_passados % 10)
        
        return int(minutos_restantes) if minutos_restantes > 0 else 0

    def usar_vida(self):
        """Usa uma vida e retorna se foi possível - VERSÃO CORRIGIDA"""
        if self.vidas > 0:
            self.vidas -= 1
            self.ultima_atualizacao_vidas = timezone.now()  # Resetar timer
            self.save()
            return True
        return False

    def verificar_reset_diario(self):
        """Verifica e reseta automaticamente se passou um dia - CORREÇÃO"""
        agora = timezone.now()
        
        # Se a última verificação foi há mais de 12 horas, resetar
        if agora - self.ultima_verificacao_diaria > timedelta(hours=12):
            # Verificar se mudou o dia
            if self.ultima_verificacao_diaria.date() < agora.date():
                self.ja_fez_atividade_hoje = False
            
            # CORREÇÃO: Atualizar sem chamar save() para evitar recursão
            self.ultima_verificacao_diaria = agora
    
    def save(self, *args, **kwargs):
        # CORREÇÃO: Chamar verificação antes do save para evitar recursão
        self.verificar_reset_diario()
        
        # CORREÇÃO: Evitar campos problemáticos no update_fields
        if 'update_fields' in kwargs:
            # Remover campos que podem causar problemas
            update_fields = kwargs['update_fields']
            if update_fields:
                # Filtrar campos problemáticos
                safe_fields = [field for field in update_fields 
                             if field not in ['ultima_verificacao_diaria', 'ja_fez_atividade_hoje']]
                kwargs['update_fields'] = safe_fields
        
        try:
            super().save(*args, **kwargs)
        except Exception as e:
            print(f"❌ Erro ao salvar perfil: {e}")
            # Tentar salvar sem update_fields em caso de erro
            if 'update_fields' in kwargs:
                kwargs.pop('update_fields')
                super().save(*args, **kwargs)
    
    def __str__(self):
            return f"Perfil de {self.user.username}"


class Progresso(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    data = models.DateField(default=timezone.now)
    percentual = models.IntegerField(default=0)
    tempo_estudo = models.DurationField(default=timedelta)
    missoes_concluidas = models.IntegerField(default=0)
    xp_ganho = models.IntegerField(default=0)  # XP ganho no dia

    def __str__(self):
        return f"Progresso {self.user.username} ({self.data})"


class Atividade(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    aula = models.ForeignKey("Aula", on_delete=models.CASCADE, null=True, blank=True)
    titulo = models.CharField(max_length=255)
    xp_ganho = models.IntegerField(default=0)
    data = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"{self.titulo} ({self.user.username})"


class Conquista(models.Model):
    RARIDADES = [
        ('comum', 'Comum'),
        ('rara', 'Rara'),
        ('epica', 'Épica'),
        ('lendaria', 'Lendária'),
    ]

    CATEGORIAS = [
        ('progresso', 'Progresso'),
        ('habilidade', 'Habilidade'),
        ('precisao', 'Precisão'),
        ('dominio', 'Domínio'),
        ('especial', 'Especial'),
    ]

    TIPOS_EVENTO = [
        ('xp_total', 'XP Total Alcançado'),
        ('nivel_atingido', 'Nível Alcançado'),
        ('aulas_concluidas', 'Aulas Concluídas'),
        ('modulos_concluidos', 'Módulos Concluídos'),
        ('sequencia_dias', 'Sequência de Dias'),
        ('questoes_corretas', 'Questões Corretas'),
        ('tempo_estudo', 'Tempo de Estudo'),
        ('postagens_forum', 'Postagens no Fórum'),
        ('comentarios', 'Comentários Feitos'),
        ('likes_recebidos', 'Likes Recebidos'),
        ('conquistas_desbloqueadas', 'Conquistas Desbloqueadas'),
    ]

    titulo = models.CharField(max_length=100)
    descricao = models.TextField()
    icone = models.ImageField(upload_to="conquistas/", blank=True, null=True)
    raridade = models.CharField(max_length=20, choices=RARIDADES, default="comum")
    categoria = models.CharField(max_length=20, choices=CATEGORIAS, default="progresso")
    usuarios = models.ManyToManyField(User, related_name="conquistas", blank=True)
    
    # Sistema dinâmico
    tipo_evento = models.CharField(max_length=50, choices=TIPOS_EVENTO)
    valor_requerido = models.IntegerField(default=1)
    xp_recompensa = models.IntegerField(default=10)
    
    # Para conquistas progressivas
    progressivo = models.BooleanField(default=False)
    multiplos = models.IntegerField(default=1)
    
    # Ordem de exibição
    ordem = models.IntegerField(default=0)
    
    # Metadados
    data_criacao = models.DateTimeField(auto_now_add=True)
    ativo = models.BooleanField(default=True)

    class Meta:
        ordering = ['categoria', 'ordem', 'raridade']

    def __str__(self):
        return self.titulo

    def verificar_desbloqueio(self, usuario):
        """Verifica se o usuário desbloqueou esta conquista"""
        if self.usuarios.filter(id=usuario.id).exists():
            return True
        
        progresso = self.calcular_progresso(usuario)
        return progresso['atingiu_meta']

    def calcular_progresso(self, usuario):
        """Calcula o progresso do usuário em relação a esta conquista - VERSÃO CORRIGIDA"""
        from django.db.models import Count, Q
        
        progresso_atual = 0
        meta = self.valor_requerido
        
        # CORREÇÃO: Converter tipo_evento se for numérico
        tipo_evento = self.tipo_evento
        if tipo_evento.isdigit():
            # Mapear número para código
            tipo_map = {
                '0': 'xp_total',
                '1': 'nivel_atingido', 
                '2': 'aulas_concluidas',
                '3': 'modulos_concluidos',
                '4': 'sequencia_dias',
                '5': 'questoes_corretas',
                '6': 'tempo_estudo',
                '7': 'postagens_forum',
                '8': 'comentarios',
                '9': 'likes_recebidos',
                '10': 'conquistas_desbloqueadas',
            }
            tipo_evento = tipo_map.get(tipo_evento, 'xp_total')
        
        print(f"🔍 Calculando progresso: {self.titulo}")
        print(f"   Tipo: {tipo_evento}, Meta: {meta}")
        
        try:
            if tipo_evento == 'xp_total':
                progresso_atual = usuario.perfil.xp
                print(f"   XP do usuário: {progresso_atual}")
                
            elif tipo_evento == 'nivel_atingido':
                progresso_atual = usuario.perfil.nivel
                print(f"   Nível do usuário: {progresso_atual}")
                
            elif tipo_evento == 'aulas_concluidas':
                progresso_atual = AulaConcluida.objects.filter(
                    usuario=usuario, 
                    teoria_concluida=True, 
                    pratica_concluida=True
                ).count()
                print(f"   Aulas totalmente concluídas: {progresso_atual}")
                
            elif tipo_evento == 'modulos_concluidos':
                modulos_concluidos = 0
                modulos = Modulo.objects.filter(ativo=True).prefetch_related('aulas')
                
                for modulo in modulos:
                    total_aulas = modulo.aulas.filter(ativo=True).count()
                    if total_aulas > 0:
                        aulas_concluidas = AulaConcluida.objects.filter(
                            usuario=usuario,
                            aula__in=modulo.aulas.all(),
                            teoria_concluida=True,
                            pratica_concluida=True
                        ).count()
                        
                        if aulas_concluidas == total_aulas:
                            modulos_concluidos += 1
                
                progresso_atual = modulos_concluidos
                print(f"   Módulos totalmente concluídos: {progresso_atual}")
                
            elif tipo_evento == 'sequencia_dias':
                progresso_atual = usuario.perfil.sequencia
                print(f"   Sequência atual: {progresso_atual}")
                
            elif tipo_evento == 'questoes_corretas':
                progresso_atual = 0  # Placeholder
                print(f"   Questões corretas: {progresso_atual} (não implementado)")
                
            elif tipo_evento == 'tempo_estudo':
                progresso_atual = usuario.perfil.tempo_total_estudo // 3600
                print(f"   Tempo de estudo (horas): {progresso_atual}")
                
            elif tipo_evento == 'postagens_forum':
                progresso_atual = Post.objects.filter(autor=usuario).count()
                print(f"   Postagens no fórum: {progresso_atual}")
                
            elif tipo_evento == 'comentarios':
                progresso_atual = Comentario.objects.filter(autor=usuario).count()
                print(f"   Comentários: {progresso_atual}")
                
            elif tipo_evento == 'likes_recebidos':
                posts_likes = Post.objects.filter(autor=usuario).aggregate(
                    total=Count('likes')
                )['total'] or 0
                
                comentarios_likes = Comentario.objects.filter(autor=usuario).aggregate(
                    total=Count('likes')
                )['total'] or 0
                
                progresso_atual = posts_likes + comentarios_likes
                print(f"   Likes recebidos: {progresso_atual}")
                
            elif tipo_evento == 'conquistas_desbloqueadas':
                # CORREÇÃO: Contar conquistas que o usuário realmente desbloqueou
                from django.db.models import Count
                progresso_atual = Conquista.objects.filter(usuarios=usuario, ativo=True).count()
                print(f"   Conquistas desbloqueadas: {progresso_atual}")

        except Exception as e:
            print(f"❌ ERRO ao calcular progresso para {self.titulo}: {str(e)}")
            progresso_atual = 0

        # CÁLCULO DO PERCENTUAL
        if meta > 0:
            percentual = min(100, int((progresso_atual / meta) * 100))
        else:
            percentual = 100 if progresso_atual > 0 else 0
        
        atingiu_meta = progresso_atual >= meta
        
        print(f"   📊 RESULTADO: {progresso_atual}/{meta} = {percentual}%")
        print(f"   🎯 Meta atingida: {atingiu_meta}")
        print("-" * 40)
        
        return {
            'progresso_atual': progresso_atual,
            'meta': meta,
            'percentual': percentual,
            'atingiu_meta': atingiu_meta,
            'falta': max(0, meta - progresso_atual)
        }


class Capitulo(models.Model):
    DIFICULDADE_CHOICES = [
        ('beginner', 'Iniciante'),
        ('intermediate', 'Intermediário'),
        ('advanced', 'Avançado'),
    ]
    
    titulo = models.CharField(max_length=200)
    descricao = models.TextField()
    ordem = models.IntegerField()
    ativo = models.BooleanField(default=True)
    dificuldade = models.CharField(max_length=20, choices=DIFICULDADE_CHOICES, default='beginner')
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.titulo
    
    def get_dificuldade_predominante(self):
        """Retorna a dificuldade predominante baseada nas aulas do capítulo"""
        from collections import Counter
        
        # Buscar todas as dificuldades das aulas ativas
        dificuldades = Aula.objects.filter(
            modulo__capitulo=self,
            ativo=True
        ).values_list('dificuldade', flat=True)
        
        if not dificuldades:
            return 'beginner'
        
        # Encontrar a dificuldade mais comum
        contador = Counter(dificuldades)
        return contador.most_common(1)[0][0]
    
    def get_nivel_dificuldade_display(self):
        """Retorna o display name da dificuldade"""
        dificuldade = self.get_dificuldade_predominante()
        dificuldade_map = {
            'beginner': 'Iniciante',
            'intermediate': 'Intermediário', 
            'advanced': 'Avançado'
        }
        return dificuldade_map.get(dificuldade, 'Iniciante')


class Modulo(models.Model):
    capitulo = models.ForeignKey(Capitulo, on_delete=models.CASCADE, related_name="modulos")
    titulo = models.CharField(max_length=255)
    descricao = models.TextField()
    ordem = models.IntegerField()
    ativo = models.BooleanField(default=True)
    tempo_estimado = models.IntegerField(null=True, blank=True)  # em minutos
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.titulo


class Aula(models.Model):
    modulo = models.ForeignKey(Modulo, on_delete=models.CASCADE, related_name="aulas")
    
    # Informações básicas
    titulo_aula = models.CharField(max_length=255, verbose_name="Título da Aula")
    titulo_tarefa = models.CharField(max_length=255, blank=True, null=True, verbose_name="Título da Tarefa")
    descricao_breve = models.TextField(blank=True, null=True, verbose_name="Descrição Breve")
    
    # Conteúdo teórico
    titulo_teoria = models.CharField(max_length=255, default="Conteúdo Teórico", verbose_name="Título do Conteúdo Teórico")
    
    # Conteúdo prático - COM VALOR PADRÃO
    titulo_pratica = models.CharField(max_length=255, default="Exercícios Práticos", verbose_name="Título do Conteúdo Prático")
    conteudo_pratico = models.TextField(
        default="Lista de exercícios para praticar os conceitos aprendidos.",
        verbose_name="Descrição da Lista de Exercícios"
    )
    
    # TEMPOS SEPARADOS
    tempo_teoria = models.IntegerField(default=30, verbose_name="Tempo Estimado para Teoria (minutos)")
    tempo_pratica = models.IntegerField(default=15, verbose_name="Tempo Estimado para Prática (minutos)")
    tempo_total = models.IntegerField(default=45, verbose_name="Tempo Total Estimado (minutos)")
    
    # XP SEPARADO - NOVOS CAMPOS
    xp_teoria = models.IntegerField(default=30, verbose_name="XP por Concluir Teoria")
    xp_pratica = models.IntegerField(default=0, verbose_name="XP Total das Questões Práticas")
    
    # Metadados
    ordem = models.IntegerField()
    ativo = models.BooleanField(default=True)
    data_atualizacao = models.DateTimeField(auto_now=True)
    
    data_criacao = models.DateTimeField(default=timezone.now)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE,
    )
    
    # Campos para controle de estrutura
    tem_teoria = models.BooleanField(default=True)
    tem_exercicios = models.BooleanField(default=True)
    
    def __str__(self):
        return self.titulo_aula
    
    def save(self, *args, **kwargs):
        # Garantir que os valores sejam inteiros
        try:
            self.tempo_teoria = int(self.tempo_teoria) if self.tempo_teoria is not None else 30
        except (ValueError, TypeError):
            self.tempo_teoria = 30
            
        try:
            self.tempo_pratica = int(self.tempo_pratica) if self.tempo_pratica is not None else 15
        except (ValueError, TypeError):
            self.tempo_pratica = 15
        
        # Calcular tempo total automaticamente - CORRIGIDO
        self.tempo_total = (self.tempo_teoria or 0) + (self.tempo_pratica or 0)
        
        # Calcular XP prático total baseado nas questões
        if self.pk:  # Só calcular se a aula já foi salva
            from django.db.models import Sum
            xp_pratico_calculado = self.questoes.aggregate(total_xp=Sum('xp'))['total_xp']
            self.xp_pratica = int(xp_pratico_calculado) if xp_pratico_calculado is not None else 0
        
        super().save(*args, **kwargs)
    
    def contar_questoes(self):
        return self.questoes.count()
    
    def contar_topicos(self):
        return self.topicos.count()
    
    def tem_conteudo_teorico(self):
        return self.topicos.exists()
    
    def get_xp_total(self):
        """Retorna o XP total da aula (teoria + prática)"""
        try:
            # Converte explicitamente para inteiro, tratando None e strings
            teorico = int(self.xp_teoria) if self.xp_teoria is not None else 0
            pratico = int(self.xp_pratica) if self.xp_pratica is not None else 0
            return teorico + pratico
        except (ValueError, TypeError):
            # Se houver qualquer erro na conversão, retorna 0
            return 0

    class Meta:
        ordering = ['ordem']


class AulaConcluida(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    aula = models.ForeignKey(Aula, on_delete=models.CASCADE)
    teoria_concluida = models.BooleanField(default=False)
    pratica_concluida = models.BooleanField(default=False)
    data_conclusao_teoria = models.DateTimeField(null=True, blank=True)
    data_conclusao_pratica = models.DateTimeField(null=True, blank=True)
    xp_teoria_ganho = models.IntegerField(default=0)
    xp_pratica_ganho = models.IntegerField(default=0)
    revisao_feita_teoria = models.BooleanField(default=False)
    revisao_feita_pratica = models.BooleanField(default=False)
    xp_revisao_ganho_teoria = models.IntegerField(default=0)
    xp_revisao_ganho_pratica = models.IntegerField(default=0)
    
    class Meta:
        unique_together = ['usuario', 'aula']
    
    def __str__(self):
        return f"{self.usuario.username} - {self.aula.titulo_aula}"


class TopicoTeorico(models.Model):
    aula = models.ForeignKey(Aula, on_delete=models.CASCADE, related_name="topicos")
    titulo = models.CharField(max_length=255, default="Tópico")
    ordem = models.IntegerField(default=1)
    conteudo = models.TextField(blank=True)
    
    class Meta:
        ordering = ['ordem']
    
    def __str__(self):
        return f"{self.titulo} - {self.aula.titulo_aula}"


class Questao(models.Model):
    TIPO_CHOICES = [
        ('multiple-choice', 'Múltipla Escolha'),
        ('code', 'Programação'), 
        ('fill-blank', 'Completar Lacunas'),
    ]
    
    aula = models.ForeignKey(Aula, on_delete=models.CASCADE, related_name="questoes")
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    enunciado = models.TextField()
    descricao = models.TextField(blank=True, null=True)
    ordem = models.IntegerField(default=1)
    xp = models.IntegerField(default=10)
    codigo_inicial = models.TextField(blank=True, null=True)
    saida_esperada = models.TextField(blank=True, null=True)
    respostas_corretas = models.JSONField(
        default=list,
        blank=True,
        help_text="Lista de respostas corretas para questões do tipo fill-blank"
    )
    
    class Meta:
        ordering = ['ordem']
        verbose_name = "Questão"
        verbose_name_plural = "Questões"
    
    def __str__(self):
        return f"{self.tipo} - {self.enunciado[:50]}"


class OpcaoQuestao(models.Model):
    questao = models.ForeignKey(Questao, on_delete=models.CASCADE, related_name="opcoes")
    texto = models.TextField()
    correta = models.BooleanField(default=False)
    ordem = models.IntegerField(default=1)
    
    class Meta:
        ordering = ['ordem']
    
    def __str__(self):
        return f"{self.texto[:30]} - {'✓' if self.correta else '✗'}"


class DicaQuestao(models.Model):
    questao = models.ForeignKey(Questao, on_delete=models.CASCADE, related_name="dicas")
    texto = models.TextField()
    ordem = models.IntegerField(default=1)
    
    class Meta:
        ordering = ['ordem']
    
    def __str__(self):
        return f"Dica {self.ordem}: {self.texto[:30]}"
    

class Hashtag(models.Model):
    nome = models.CharField(max_length=50, unique=True)
    contador = models.PositiveIntegerField(default=0)
    ultimo_uso = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"#{self.nome}"
    
    @classmethod
    def limpar_hashtags_automatico(cls):
        """Remove automaticamente hashtags que não são usadas por nenhum post"""
        hashtags_orfas = cls.objects.filter(contador=0)
        count = hashtags_orfas.count()
        
        if count > 0:
            print(f"🧹 Removendo {count} hashtags órfãs automaticamente...")
            hashtags_orfas.delete()
        
        return count


class Post(models.Model):
    autor = models.ForeignKey(User, on_delete=models.CASCADE)
    conteudo = models.TextField()
    imagem = models.ImageField(upload_to="posts/", blank=True, null=True)  # NOVO
    created_at = models.DateTimeField(auto_now_add=True)
    likes = models.ManyToManyField(User, blank=True, related_name="liked_posts")

    hashtags = models.ManyToManyField(Hashtag, blank=True)
    
    def save(self, *args, **kwargs):
        """Salva o post e processa hashtags após o primeiro save."""
        super().save(*args, **kwargs)
        self._processar_hashtags()
    
    def _processar_hashtags(self):
        """Cria e atualiza hashtags a partir do conteúdo do post."""
        hashtags_encontradas = re.findall(r'#(\w+)', self.conteudo or '')
        hashtags_encontradas = [h.lower().strip() for h in hashtags_encontradas if h.strip()]

        hashtags_atuais = set(self.hashtags.values_list('nome', flat=True))
        novas_hashtags = set(hashtags_encontradas)

        # Remover hashtags que não estão mais no texto
        for hashtag_nome in hashtags_atuais - novas_hashtags:
            try:
                h = Hashtag.objects.get(nome=hashtag_nome)
                if h.contador > 0:
                    h.contador -= 1
                    h.save(update_fields=["contador"])
                self.hashtags.remove(h)
            except Hashtag.DoesNotExist:
                pass

        # Adicionar ou atualizar hashtags novas
        for nome in novas_hashtags:
            hashtag, created = Hashtag.objects.get_or_create(nome=nome)
            if created:
                hashtag.contador = 1
            else:
                hashtag.contador += 1
            hashtag.ultimo_uso = timezone.now()
            hashtag.save(update_fields=["contador", "ultimo_uso"])
            self.hashtags.add(hashtag)
    
    def delete(self, *args, **kwargs):
        """Remove o post e atualiza automaticamente os contadores das hashtags"""
        print(f"🗑️ Excluindo post {self.id} - Atualizando hashtags...")
        
        # Salvar as hashtags antes de deletar para poder atualizar os contadores
        hashtags_do_post = list(self.hashtags.all())
        
        # Primeiro remover as relações ManyToMany
        self.hashtags.clear()
        
        # Deletar o post
        super().delete(*args, **kwargs)
        
        # Atualizar contadores de cada hashtag
        for hashtag in hashtags_do_post:
            # Recontar quantos posts usam essa hashtag AGORA
            posts_com_hashtag = Post.objects.filter(hashtags=hashtag).count()
            hashtag.contador = posts_com_hashtag
            
            if posts_com_hashtag == 0:
                # Se não há mais posts, zerar último uso
                hashtag.ultimo_uso = None
            else:
                # Buscar a data do último post que ainda usa essa hashtag
                ultimo_post = Post.objects.filter(hashtags=hashtag).order_by('-created_at').first()
                if ultimo_post:
                    hashtag.ultimo_uso = ultimo_post.created_at
            
            hashtag.save()
            print(f"  🔄 Hashtag #{hashtag.nome}: contador atualizado para {hashtag.contador}")
    

class Comentario(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="comentarios")
    autor = models.ForeignKey(User, on_delete=models.CASCADE, related_name="comentarios")
    texto = models.TextField()
    hashtags = models.CharField(max_length=255, blank=True)
    likes = models.ManyToManyField(User, blank=True, related_name="liked_comments")
    created_at = models.DateTimeField(auto_now_add=True)
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.CASCADE, related_name="replies")
    mencionado = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="mencionado_em")

    def __str__(self):
        return f"{self.autor.username} - {self.texto[:30]}"


class Notificacao(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notificacoes")
    mensagem = models.TextField()
    lida = models.BooleanField(default=False)
    enviada_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Notificação para {self.usuario.username}"


class ModuloConcluido(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    modulo = models.ForeignKey(Modulo, on_delete=models.CASCADE)
    data_conclusao = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['usuario', 'modulo']


class TentativaPratica(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    aula = models.ForeignKey(Aula, on_delete=models.CASCADE)
    vidas_usadas = models.IntegerField(default=0)
    vidas_restantes = models.IntegerField(default=3)
    data_tentativa = models.DateTimeField(auto_now_add=True)
    concluida = models.BooleanField(default=False)
    xp_ganho = models.IntegerField(default=0)
    
    class Meta:
        unique_together = ['usuario', 'aula']
        

class TempoEstudo(models.Model):
    TIPO_CHOICES = [
        ('teoria', 'Teoria'),
        ('pratica', 'Prática'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    aula = models.ForeignKey(Aula, on_delete=models.CASCADE)
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    tempo_segundos = models.IntegerField(default=0)
    data = models.DateField(default=timezone.now)
    criado_em = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['user', 'aula', 'tipo', 'data']
    
    def __str__(self):
        return f"{self.user.username} - {self.aula.titulo_aula} ({self.tipo}) - {self.data}"


class SessaoEstudo(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    aula = models.ForeignKey('Aula', on_delete=models.CASCADE, null=True, blank=True)
    tipo = models.CharField(max_length=10, choices=[('teoria', 'Teoria'), ('pratica', 'Prática')])
    inicio = models.DateTimeField(auto_now_add=True)
    fim = models.DateTimeField(null=True, blank=True)
    tempo_total = models.IntegerField(default=0)  # em segundos
    ativa = models.BooleanField(default=True)
    
    def finalizar_sessao(self):
        if self.ativa:
            self.fim = timezone.now()
            diferenca = self.fim - self.inicio
            self.tempo_total = int(diferenca.total_seconds())
            self.ativa = False
            self.save()
            
            # Atualizar perfil
            perfil = self.user.perfil
            perfil.tempo_total_estudo += self.tempo_total
            perfil.save()
            
            # Atualizar ou criar registro diário
            data_hoje = timezone.now().date()
            tempo_estudo, created = TempoEstudo.objects.get_or_create(
                user=self.user,
                aula=self.aula,
                tipo=self.tipo,
                data=data_hoje,
                defaults={'tempo_segundos': self.tempo_total}
            )
            
            if not created:
                tempo_estudo.tempo_segundos += self.tempo_total
                tempo_estudo.save()


class TempoEstudoDiario(models.Model):
    """Armazena o tempo de estudo por dia"""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    data = models.DateField(default=timezone.now)
    tempo_segundos = models.IntegerField(default=0)  # Tempo em segundos
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['user', 'data']
        verbose_name = "Tempo de Estudo Diário"
        verbose_name_plural = "Tempos de Estudo Diários"
    
    def __str__(self):
        return f"{self.user.username} - {self.data}: {self.tempo_formatado()}"
    
    def tempo_formatado(self):
        """Retorna o tempo formatado como HH:MM:SS ou MM:SS"""
        horas = self.tempo_segundos // 3600
        minutos = (self.tempo_segundos % 3600) // 60
        segundos = self.tempo_segundos % 60
        
        if horas > 0:
            return f"{horas:02d}:{minutos:02d}:{segundos:02d}"
        else:
            return f"{minutos:02d}:{segundos:02d}"


# ========== FUNÇÕES PARA MÓDULOS CONCLUÍDOS ==========

def verificar_e_marcar_modulo_concluido(usuario, aula):
    """Verifica se todas as aulas do módulo foram concluídas e marca o módulo como concluído"""
    try:
        modulo = aula.modulo
        
        # Verificar se TODAS as aulas do módulo foram concluídas (teoria + prática)
        total_aulas = modulo.aulas.filter(ativo=True).count()
        
        if total_aulas > 0:
            aulas_totalmente_concluidas = AulaConcluida.objects.filter(
                usuario=usuario,
                aula__in=modulo.aulas.all(),
                teoria_concluida=True,
                pratica_concluida=True
            ).count()
            
            # Se todas as aulas foram concluídas, marcar módulo como concluído
            if aulas_totalmente_concluidas == total_aulas:
                ModuloConcluido.objects.get_or_create(
                    usuario=usuario,
                    modulo=modulo
                )
                print(f"✅ Módulo '{modulo.titulo}' marcado como concluído para {usuario.username}")
                return True
            else:
                # Se não estão todas concluídas, remover da lista de concluídos (caso exista)
                ModuloConcluido.objects.filter(
                    usuario=usuario,
                    modulo=modulo
                ).delete()
        
        return False
        
    except Exception as e:
        print(f"❌ Erro ao verificar módulo concluído: {e}")
        return False


# ========== SIGNALS CORRIGIDOS ==========

@receiver(post_save, sender=User)
def criar_perfil(sender, instance, created, **kwargs):
    """
    Signal para criar perfil automaticamente quando um usuário é criado.
    CORREÇÃO: Usar create em vez de get_or_create para evitar loops
    """
    if created:
        # CORREÇÃO: Verificar se já existe um perfil antes de criar
        if not hasattr(instance, 'perfil'):
            try:
                # CORREÇÃO: Usar create com valores padrão explícitos
                Perfil.objects.create(
                    user=instance,
                    ultima_verificacao_diaria=timezone.now(),
                    ultima_atualizacao_vidas=timezone.now()
                )
                print(f"✅ Perfil criado para usuário: {instance.username}")
            except Exception as e:
                print(f"❌ Erro ao criar perfil: {e}")


@receiver(post_save, sender=User)
def salvar_perfil(sender, instance, **kwargs):
    """
    Signal para salvar perfil quando usuário é salvo.
    CORREÇÃO: Verificar se o perfil existe antes de tentar salvar
    """
    try:
        if hasattr(instance, 'perfil'):
            instance.perfil.save()
    except Perfil.DoesNotExist:
        # Se o perfil não existe, criar um
        Perfil.objects.get_or_create(user=instance)
        print(f"🔄 Perfil criado para usuário: {instance.username}")


@receiver(post_save, sender=AulaConcluida)
def verificar_modulo_ao_concluir_aula(sender, instance, **kwargs):
    """Verifica se o módulo deve ser marcado como concluído quando uma aula é concluída"""
    print(f"🔍 Signal AulaConcluida: {instance.aula.titulo_aula} - Teoria: {instance.teoria_concluida}, Prática: {instance.pratica_concluida}")
    
    if instance.teoria_concluida and instance.pratica_concluida:
        verificar_e_marcar_modulo_concluido(instance.usuario, instance.aula)


@receiver(post_migrate)
def create_professor_group(sender, **kwargs):
    """Cria grupo de professores após migração"""
    if sender.name == 'PyQuest': 
        group, created = Group.objects.get_or_create(name='professores')
        if created:
            print("✅ Grupo 'professores' criado com sucesso!")