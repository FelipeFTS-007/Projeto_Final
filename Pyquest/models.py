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
    
    ultima_atualizacao_vidas = models.DateTimeField(auto_now=True)



    # ===== MÉTODOS DO SISTEMA DE STREAK =====
    
    def verificar_e_atualizar_streak(self):
        """
        Lógica SIMPLES: Aumenta streak apenas se a última atividade foi ONTEM
        Retorna: (novo_streak, streak_zerado, streak_aumentado)
        """
        agora = timezone.now()
        streak_zerado = False
        streak_aumentado = False
        
        print(f"🕒 Última atividade: {self.ultima_atividade}")
        print(f"🕒 Agora: {agora}")
        
        # Se nunca teve atividade, iniciar streak
        if not self.ultima_atividade:
            self.sequencia = 1
            self.ultima_atividade = agora
            self.save()
            print("🎯 Primeira atividade - Streak iniciado: 1")
            return 1, False, True
        
        # Verificar se a última atividade foi ONTEM (para aumentar streak)
        # ou se foi HOJE (apenas manter) ou se foi ANTES de ONTEM (zerar)
        data_ultima = self.ultima_atividade.date()
        data_hoje = agora.date()
        dias_diferenca = (data_hoje - data_ultima).days
        
        print(f"📅 Última atividade: {data_ultima}")
        print(f"📅 Hoje: {data_hoje}")
        print(f"📅 Diferença em dias: {dias_diferenca}")
        
        if dias_diferenca == 0:
            # Já teve atividade HOJE - apenas atualiza hora, NÃO aumenta streak
            print("✅ Já teve atividade hoje - streak mantido")
            self.ultima_atividade = agora
            self.save()
            streak_aumentado = False
            
        elif dias_diferenca == 1:
            # Última atividade foi ONTEM - AUMENTAR STREAK
            print("🎯 Última atividade foi ontem - AUMENTANDO STREAK")
            streak_anterior = self.sequencia
            self.sequencia += 1
            self.ultima_atividade = agora
            streak_aumentado = True
            print(f"📈 Streak aumentado: {streak_anterior} → {self.sequencia}")
            self.save()
            
        else:
            # Última atividade foi ANTES de ontem - ZERAR STREAK
            print("💀 Última atividade foi antes de ontem - ZERANDO STREAK")
            streak_anterior = self.sequencia
            
            # Atualizar streak máximo antes de zerar
            if streak_anterior > self.sequencia_maxima:
                self.sequencia_maxima = streak_anterior
            
            self.sequencia = 1
            self.ultima_atividade = agora
            streak_zerado = True
            print(f"🔄 Streak zerado: {streak_anterior} → 1")
            self.save()
        
        # Atualizar streak máximo se necessário
        if self.sequencia > self.sequencia_maxima:
            self.sequencia_maxima = self.sequencia
            self.save()
        
        return self.sequencia, streak_zerado, streak_aumentado
    
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

    # ... SEUS OUTROS MÉTODOS EXISTENTES ...
    def regenerar_vidas(self):
        """Regenera vidas baseado no tempo passado"""
        agora = timezone.now()
        diferenca = agora - self.ultima_atualizacao_vidas
        
        # Regenera 1 vida a cada 30 minutos
        minutos_passados = diferenca.total_seconds() / 60
        vidas_regeneradas = int(minutos_passados / 30)
        
        if vidas_regeneradas > 0:
            self.vidas = min(self.max_vidas, self.vidas + vidas_regeneradas)
            self.ultima_atualizacao_vidas = agora
            self.save()
    
    def tempo_para_proxima_vida(self):
        """Retorna minutos até a próxima vida regenerar"""
        if self.vidas >= self.max_vidas:
            return 0
        
        agora = timezone.now()
        diferenca = agora - self.ultima_atualizacao_vidas
        minutos_passados = diferenca.total_seconds() / 60
        minutos_restantes = 30 - (minutos_passados % 30)
        
        return int(minutos_restantes)
    
    
    def usar_vida(self):
        """Usa uma vida e retorna se foi possível"""
        if self.vidas > 0:
            self.vidas -= 1
            self.ultima_atualizacao_vidas = timezone.now()
            self.save()
            return True
        return False

    # ... SEUS OUTROS MÉTODOS EXISTENTES ...


    

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
    multiplos = models.IntegerField(default=1)  # Para conquistas como "Alcance 100, 500, 1000 XP"
    
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
        """Calcula o progresso do usuário em relação a esta conquista"""
        from django.db.models import Sum, Count
        from datetime import date, timedelta
        
        progresso_atual = 0
        meta = self.valor_requerido
        
        if self.tipo_evento == 'xp_total':
            progresso_atual = usuario.perfil.xp
            
        elif self.tipo_evento == 'nivel_atingido':
            progresso_atual = usuario.perfil.nivel
            
        elif self.tipo_evento == 'aulas_concluidas':
            progresso_atual = AulaConcluida.objects.filter(
                usuario=usuario, 
                teoria_concluida=True, 
                pratica_concluida=True
            ).count()
            
        elif self.tipo_evento == 'modulos_concluidos':
            # Implementar lógica para módulos concluídos
            modulos_concluidos = ModuloConcluido.objects.filter(usuario=usuario).count()
            progresso_atual = modulos_concluidos
            
        elif self.tipo_evento == 'sequencia_dias':
            progresso_atual = usuario.perfil.sequencia
            
        elif self.tipo_evento == 'questoes_corretas':
            # Implementar quando tiver sistema de respostas
            progresso_atual = 0  # Placeholder
            
        elif self.tipo_evento == 'tempo_estudo':
            # Soma do tempo de estudo do Progresso
            tempo_total = Progresso.objects.filter(user=usuario).aggregate(
                total=Sum('tempo_estudo')
            )['total'] or timedelta()
            progresso_atual = int(tempo_total.total_seconds() / 3600)  # Horas
            
        elif self.tipo_evento == 'postagens_forum':
            progresso_atual = Post.objects.filter(autor=usuario).count()
            
        elif self.tipo_evento == 'comentarios':
            progresso_atual = Comentario.objects.filter(autor=usuario).count()
            
        elif self.tipo_evento == 'likes_recebidos':
            posts_likes = Post.objects.filter(autor=usuario).aggregate(
                total=Count('likes')
            )['total'] or 0
            comentarios_likes = Comentario.objects.filter(autor=usuario).aggregate(
                total=Count('likes')
            )['total'] or 0
            progresso_atual = posts_likes + comentarios_likes
            
        elif self.tipo_evento == 'conquistas_desbloqueadas':
            progresso_atual = usuario.conquistas.count()

        percentual = min(100, int((progresso_atual / meta) * 100)) if meta > 0 else 100
        atingiu_meta = progresso_atual >= meta
        
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





# models.py - ATUALIZAR o modelo Aula
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
    
    # No models.py, na classe Aula
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

# models.py - ADICIONE este modelo
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
        # ADICIONADO DO ARQUIVO 2
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

# models.py - ATUALIZAR o modelo Post
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





# Adicione ao models.py
class ModuloConcluido(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    modulo = models.ForeignKey(Modulo, on_delete=models.CASCADE)
    data_conclusao = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['usuario', 'modulo']






#isso tem que esta no final#


@receiver(post_save, sender=User)
def criar_perfil(sender, instance, created, **kwargs):
    if created:
        Perfil.objects.create(user=instance)

@receiver(post_save, sender=User)
def salvar_perfil(sender, instance, **kwargs):
    instance.perfil.save()



@receiver(post_migrate)
def create_professor_group(sender, **kwargs):
    if sender.name == 'PyQuest': 
        group, created = Group.objects.get_or_create(name='professores')
        if created:
            # Adicione permissões específicas se necessário
            print("Grupo 'professores' criado com sucesso!")



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
    
    # Adicione esta classe se não existir
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