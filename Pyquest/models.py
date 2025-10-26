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
    avatar = models.ImageField(upload_to="avatars/", default="avatars/default.png")
    descricao = models.TextField(blank=True, null=True, default="Ainda não escreveu nada.")
    licoes = models.IntegerField(default=0)
    github = models.URLField(max_length=200, blank=True, null=True)
    linkedin = models.URLField(max_length=200, blank=True, null=True)



    def regenerar_vidas(self):
        agora = timezone.now()
        minutos_por_vida = 30  # quanto tempo demora para regenerar 1 vida

        # diferença em minutos desde a última regeneração
        diff = int((agora - self.ultima_regeneracao).total_seconds() // 60)

        if diff >= minutos_por_vida and self.vidas < self.max_vidas:
            # quantas vidas regenerar
            vidas_regeneradas = diff // minutos_por_vida
            self.vidas = min(self.max_vidas, self.vidas + vidas_regeneradas)
            self.ultima_regeneracao = agora
            self.save()

    def tempo_para_proxima_vida(self):
        minutos_por_vida = 30
        agora = timezone.now()
        diff = int((agora - self.ultima_regeneracao).total_seconds() // 60)
        restante = minutos_por_vida - (diff % minutos_por_vida)
        return restante if self.vidas < self.max_vidas else 0

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

    titulo = models.CharField(max_length=100)
    descricao = models.TextField()
    icone = models.ImageField(upload_to="conquistas/", blank=True, null=True)
    raridade = models.CharField(max_length=20, choices=RARIDADES, default="comum")
    categoria = models.CharField(max_length=20, choices=CATEGORIAS, default="progresso")
    usuarios = models.ManyToManyField(User, related_name="conquistas", blank=True)
    objetivo = models.CharField(max_length=255, blank=True, null=True)


    def __str__(self):
        return self.titulo



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
    
    class Meta:
        ordering = ['ordem']
    
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



