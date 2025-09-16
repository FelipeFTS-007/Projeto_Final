from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from .models import Perfil, Progresso, Atividade, Conquista
from datetime import timedelta
from django.dispatch import receiver
from django.db.models.signals import post_save



# ---------- AUTENTICAÇÃO ----------

def cadastro_view(request):
    if request.method == "POST":
        nome = request.POST.get("first_name")
        email = request.POST.get("email")
        username = request.POST.get("username")
        senha1 = request.POST.get("password1")
        senha2 = request.POST.get("password2")

        # --- VALIDAÇÕES ---
        if not username or not senha1 or not senha2:
            messages.error(request, "Preencha todos os campos obrigatórios.")
            return redirect("cadastro")

        if senha1 != senha2:
            messages.error(request, "As senhas não coincidem.")
            return redirect("cadastro")

        if len(senha1) < 8:
            messages.error(request, "A senha deve ter pelo menos 8 caracteres.")
            return redirect("cadastro")

        if User.objects.filter(username=username).exists():
            messages.error(request, "Nome de usuário já está em uso.")
            return redirect("cadastro")

        if User.objects.filter(email=email).exists():
            messages.error(request, "Email já está cadastrado.")
            return redirect("cadastro")

        # --- CRIA USUÁRIO ---
        user = User.objects.create_user(
            username=username,
            password=senha1,
            email=email,
            first_name=nome
        )
        login(request, user)
        messages.success(request, "Conta criada com sucesso!")
        return redirect("login")

    return render(request, "Pyquest/cadastro.html")




def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        senha = request.POST.get("password")

        if not username or not senha:
            messages.error(request, "Preencha todos os campos.")
            return redirect("login")

        # Verifica usuário e senha
        user = authenticate(request, username=username, password=senha)

        if user is not None:
            login(request, user)
            messages.success(request, "Login realizado com sucesso!")
            return redirect("home")
        else:
            messages.error(request, "Usuário ou senha inválidos.")
            return redirect("login")

    return render(request, "Pyquest/login.html")

@login_required
def home(request):
    perfil, _ = Perfil.objects.get_or_create(user=request.user)
    perfil.regenerar_vidas()

    hoje = timezone.now().date()
    progresso_hoje, _ = Progresso.objects.get_or_create(user=request.user, data=hoje)

    ontem = hoje - timedelta(days=1)
    progresso_ontem = Progresso.objects.filter(user=request.user, data=ontem).first()

    atividades = Atividade.objects.filter(user=request.user).order_by("-data")[:5]



    context = {
        "vidas": perfil.vidas,
        "max_vidas": perfil.max_vidas,
        "proxima_vida": perfil.tempo_para_proxima_vida(),  # minutos para regenerar
        "nome": request.user.first_name or request.user.username,
        "xp": perfil.xp,
        "nivel": perfil.nivel,
        "vidas": perfil.vidas,
        "max_vidas": perfil.max_vidas,
        "conquistas": perfil.conquistas,
        "total_conquistas": perfil.total_conquistas,
        "sequencia": perfil.sequencia,
        "progresso": progresso_hoje.percentual,
        "meta": 60,  # pode ser dinâmica depois
        "tempo": progresso_hoje.tempo_estudo,
        "dif_tempo": (progresso_hoje.tempo_estudo - progresso_ontem.tempo_estudo) if progresso_ontem else timedelta(),
        "xp_diario": progresso_hoje.xp_ganho,
        "atividades": atividades,
    }
    return render(request, "Pyquest/home.html", context)



def logout_view(request):
    logout(request)
    return redirect("login")



@login_required
def perfil(request):
    perfil, created = Perfil.objects.get_or_create(user=request.user)

    XP_POR_NIVEL = 100

    # --- subir de nível automático ---
    while perfil.xp >= XP_POR_NIVEL:
        perfil.nivel += 1
        perfil.xp -= XP_POR_NIVEL
        perfil.save()

    conquistas_desbloqueadas = request.user.conquistas.all()
    conquistas_bloqueadas = Conquista.objects.exclude(id__in=conquistas_desbloqueadas)

    # --- progresso até o próximo nível ---
    progresso_xp = (perfil.xp % XP_POR_NIVEL) / XP_POR_NIVEL * 100

    if request.method == "POST":
        if "avatar" in request.FILES:
            perfil.avatar = request.FILES["avatar"]

        perfil.descricao = request.POST.get("descricao", "").strip()
        perfil.github = request.POST.get("github", "").strip()
        perfil.linkedin = request.POST.get("linkedin", "").strip()

        perfil.save()
        messages.success(request, "Perfil atualizado com sucesso!")
        return redirect("perfil")


    desbloq_qs = request.user.conquistas.all()
    bloq_qs = Conquista.objects.exclude(id__in=desbloq_qs)

    desbloq_count = desbloq_qs.count()
    bloq_count = bloq_qs.count()
    total = desbloq_count + bloq_count

   
    context = {
        "perfil": perfil,
        "conquistas_desbloqueadas": conquistas_desbloqueadas,
        "conquistas_bloqueadas": conquistas_bloqueadas,
        "progresso_xp": progresso_xp,
        "conquistas_desbloqueadas": desbloq_qs,
        "conquistas_bloqueadas": bloq_qs,
        "desbloq_count": desbloq_count,
        "total_conquistas": total,
    }
    return render(request, "Pyquest/perfil.html", context)


# views.py (substitua a função ranking existente)


@login_required
def ranking(request):
    # ordena por XP decrescente
    perfis = Perfil.objects.select_related('user').order_by('-xp')

    # calcula posição do usuário atual (1-based). se não encontrado, fica None
    posicao_usuario = None
    try:
        # lista de user_id na mesma ordem do queryset
        ids = list(perfis.values_list('user_id', flat=True))
        if request.user.id in ids:
            posicao_usuario = ids.index(request.user.id) + 1
    except Exception:
        posicao_usuario = None

    contexto = {
        "perfis": perfis,
        "usuario_logado": request.user.id,
        "posicao_usuario": posicao_usuario,
    }
    return render(request, "Pyquest/ranking.html", contexto)




@receiver(post_save, sender=User)
def criar_perfil(sender, instance, created, **kwargs):
    if created:
        Perfil.objects.get_or_create(user=instance)




# ---------- PÁGINAS EXISTENTES ----------


def conteudo(request):
    return render(request, "Pyquest/conteudo.html")

def modulos(request):
    return render(request, "Pyquest/modulos.html")

def tarefas(request):
    return render(request, "Pyquest/tarefas.html")

def teoria(request):
    return render(request, "Pyquest/teoria.html")

def pratica(request):
    return render(request, "Pyquest/pratica.html")



def forum(request):
    return render(request, "Pyquest/forum.html")

def dashboard(request):
    return render(request, "Pyquest/dashboard.html")




