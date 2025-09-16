from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from django.db.models.signals import post_save
from django.dispatch import receiver

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

    def __str__(self):
        return self.titulo



class Capitulo(models.Model):
    titulo = models.CharField(max_length=255)
    descricao = models.TextField()
    ordem = models.IntegerField()
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.titulo


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
    titulo = models.CharField(max_length=255)
    conteudo = models.TextField()
    ordem = models.IntegerField()
    ativo = models.BooleanField(default=True)

    def __str__(self):
        return self.titulo


class Forum(models.Model):
    titulo = models.CharField(max_length=255)
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name="foruns")
    conteudo = models.TextField()
    criado_em = models.DateTimeField(auto_now_add=True)
    ativo = models.BooleanField(default=True)

    def __str__(self):
        return self.titulo


class RespostaForum(models.Model):
    forum = models.ForeignKey(Forum, on_delete=models.CASCADE, related_name="respostas")
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    conteudo = models.TextField()
    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Resposta de {self.usuario.username}"


class Notificacao(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notificacoes")
    mensagem = models.TextField()
    lida = models.BooleanField(default=False)
    enviada_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Notificação para {self.usuario.username}"


#isso tem que esta no final#


@receiver(post_save, sender=User)
def criar_perfil(sender, instance, created, **kwargs):
    if created:
        Perfil.objects.create(user=instance)

@receiver(post_save, sender=User)
def salvar_perfil(sender, instance, **kwargs):
    instance.perfil.save()
