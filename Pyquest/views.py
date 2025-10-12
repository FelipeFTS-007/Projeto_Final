from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils import timezone
from .models import Perfil, Progresso, Atividade, Conquista,  Post, Comentario, Hashtag
from django.db.models import Count, Q
from datetime import datetime, timedelta
from django.dispatch import receiver
from django.db.models.signals import post_save
from django.http import JsonResponse
import json
from .forms import *


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




@login_required
def forum(request):
    try:
        # Estatísticas
        total_users = User.objects.count()
        
        hoje = timezone.now().date()
        active_today = User.objects.filter(
            Q(post__created_at__date=hoje) | 
            Q(comentarios__created_at__date=hoje)
        ).distinct().count()
        
        posts_today = Post.objects.filter(created_at__date=hoje).count()
        
        # Tópicos em alta (hashtags mais usadas na última semana)
        uma_semana_atras = timezone.now() - timedelta(days=7)
        trending_tags = Hashtag.objects.filter(
            posts__created_at__gte=uma_semana_atras
        ).annotate(count=Count('posts')).order_by('-count')[:10]
        
        # Contribuidores destaque (usuários com mais XP)
        top_users = User.objects.filter(perfil__isnull=False).order_by('-perfil__xp')[:10]
        
        # Filtros
        current_filter = request.GET.get('filter', 'all')
        search_query = request.GET.get('q', '')
        
        posts = Post.objects.all().order_by("-created_at").prefetch_related("comentarios", "hashtags","autor__perfil" )
        
        # Aplicar filtro de busca
        if search_query:
            posts = posts.filter(
                Q(conteudo__icontains=search_query) |
                Q(hashtags__nome__icontains=search_query) |
                Q(autor__username__icontains=search_query)
            ).distinct()
        
        # Aplicar filtros
        if current_filter == 'popular':
            posts = posts.annotate(like_count=Count('likes')).order_by('-like_count', '-created_at')
        elif current_filter == 'recent':
            posts = posts.order_by('-created_at')
        elif current_filter == 'following':
            # Implementar lógica de seguir usuários depois
            posts = posts.order_by('-created_at')
        
        context = {
            "posts": posts,
            "total_users": total_users,
            "active_today": active_today,
            "posts_today": posts_today,
            "trending_tags": trending_tags,
            "top_users": top_users,
            "current_filter": current_filter,
            "search_query": search_query,
        }

        return render(request, "Pyquest/forum.html", context)
    
    except Exception as e:
        # Fallback em caso de erro
        print(f"Erro no forum: {e}")
        posts = Post.objects.all().order_by("-created_at")
        context = {
            "posts": posts,
            "total_users": User.objects.count(),
            "active_today": 0,
            "posts_today": 0,
            "trending_tags": [],
            "top_users": [],
            "current_filter": "all",
            "search_query": "",
        }
        return render(request, "Pyquest/forum.html", context)

# views.py - ATUALIZAR create_post e edit_post
@login_required
def create_post(request):
    if request.method == "POST":
        conteudo = request.POST.get("conteudo")
        hashtags_text = request.POST.get("hashtags", "")
        imagem = request.FILES.get("imagem")  # NOVO

        if conteudo:
            post = Post.objects.create(
                autor=request.user,
                conteudo=conteudo,
                imagem=imagem,  # NOVO
                created_at=timezone.now()
            )
            
            # salvar hashtags
            hashtags = [tag.strip().lower() for tag in hashtags_text.split(",") if tag.strip()]
            for nome in hashtags:
                tag, created = Hashtag.objects.get_or_create(nome=nome)
                post.hashtags.add(tag)

        return redirect("forum")
    return redirect("forum")



@login_required
def edit_post(request, post_id):
    post = get_object_or_404(Post, id=post_id, autor=request.user)
    if request.method == "POST":
        conteudo = request.POST.get("conteudo")
        hashtags_text = request.POST.get("hashtags", "")
        imagem = request.FILES.get("imagem")  # NOVO

        if conteudo:
            post.conteudo = conteudo
            
            # NOVO: Atualizar imagem se for fornecida
            if imagem:
                post.imagem = imagem
            
            post.hashtags.clear()

            hashtags = [tag.strip().lower() for tag in hashtags_text.split(",") if tag.strip()]
            for nome in hashtags:
                tag, created = Hashtag.objects.get_or_create(nome=nome)
                post.hashtags.add(tag)

            post.save()
        return redirect("forum")
    return redirect("forum")



@login_required
def delete_post(request, post_id):
    post = get_object_or_404(Post, id=post_id, autor=request.user)
    if request.method == "POST":
        post.delete()
        return redirect("forum")
    # 👇 redireciona direto sem pedir confirmação
    post.delete()
    return redirect("forum")




@login_required
def add_comment(request, post_id):
    if request.method == "POST":
        post = get_object_or_404(Post, id=post_id)
        texto = request.POST.get("texto")
        
        if texto.strip():
            comentario = Comentario.objects.create(
                post=post, 
                autor=request.user, 
                texto=texto
            )
            
            # Se for uma requisição AJAX, retorna JSON
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'comment_id': comentario.id,
                    'author': comentario.autor.username,
                    'text': comentario.texto,
                })
    
    # Redirecionamento normal para requisições não-AJAX
    return redirect("forum")

@login_required
def like_post(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    if request.user in post.likes.all():
        post.likes.remove(request.user)
    else:
        post.likes.add(request.user)
    return redirect("forum")

@login_required
def like_comment(request, comment_id):
    comentario = get_object_or_404(Comentario, id=comment_id)
    if request.user in comentario.likes.all():
        comentario.likes.remove(request.user)
    else:
        comentario.likes.add(request.user)
    return redirect("forum")


@login_required
def reply_comment(request, post_id, parent_id):
    post = get_object_or_404(Post, id=post_id)
    parent_comment = get_object_or_404(Comentario, id=parent_id)

    if request.method == "POST":
        texto = request.POST.get("texto")
        if texto.strip():
            # Adiciona menção ao usuário respondido
            texto_com_menção = f"@{parent_comment.autor.username} {texto}"
            
            reply = Comentario.objects.create(
                post=post,
                autor=request.user,
                texto=texto_com_menção,
                parent=parent_comment,
                mencionado=parent_comment.autor
            )
            
            # Se for uma requisição AJAX, retorna JSON
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'reply_id': reply.id,
                    'author': reply.autor.username,
                    'text': reply.texto,
                    'mentioned': parent_comment.autor.username,
                })
    
    return redirect("forum")


def is_professor(user):
    return user.groups.filter(name='professores').exists() or user.is_staff

@user_passes_test(is_professor)
def criar_conteudo(request):
    # Inicializar forms
    chapter_form = ChapterForm(request.POST or None, prefix='chapter')
    module_form = ModuleForm(request.POST or None, prefix='module')
    task_form = TaskForm(request.POST or None, prefix='task')
    theory_form = TheoryContentForm(request.POST or None, prefix='theory')
    publish_form = PublishSettingsForm(request.POST or None, prefix='publish')
    
    # Forms para questões (serão dinâmicos)
    question_forms = []
    
    if request.method == 'POST':
        # Verificar qual passo está sendo enviado
        current_step = request.POST.get('current_step', '1')
        
        if current_step == '1' and chapter_form.is_valid() and module_form.is_valid() and task_form.is_valid():
            # Processar estrutura
            return render(request, 'Pyquest/criar_conteudo.html', {
                'chapter_form': chapter_form,
                'module_form': module_form,
                'task_form': task_form,
                'theory_form': theory_form,
                'publish_form': publish_form,
                'current_step': '2',
                'structure_data': {
                    'chapter': chapter_form.cleaned_data,
                    'module': module_form.cleaned_data,
                    'task': task_form.cleaned_data,
                }
            })
            
        elif current_step == '2' and theory_form.is_valid():
            # Processar conteúdo teórico
            return render(request, 'Pyquest/criar_conteudo.html', {
                'chapter_form': chapter_form,
                'module_form': module_form,
                'task_form': task_form,
                'theory_form': theory_form,
                'publish_form': publish_form,
                'current_step': '3',
                'structure_data': request.session.get('structure_data', {}),
                'theory_data': theory_form.cleaned_data
            })
            
        elif current_step == '3':
            # Processar questões (lógica mais complexa)
            # Aqui você processaria as questões dinâmicas
            return render(request, 'Pyquest/criar_conteudo.html', {
                'chapter_form': chapter_form,
                'module_form': module_form,
                'task_form': task_form,
                'theory_form': theory_form,
                'publish_form': publish_form,
                'current_step': '4',
                'structure_data': request.session.get('structure_data', {}),
                'theory_data': request.session.get('theory_data', {}),
                'questions_data': request.session.get('questions_data', [])
            })
            
        elif current_step == '4' and publish_form.is_valid():
            # Salvar tudo no banco de dados
            # Aqui você implementaria a lógica de salvamento
            return redirect('conteudo')  # Redirecionar para página de conteúdo
    
    return render(request, 'Pyquest/criar_conteudo.html', {
        'chapter_form': chapter_form,
        'module_form': module_form,
        'task_form': task_form,
        'theory_form': theory_form,
        'publish_form': publish_form,
        'current_step': '1',
    })

@login_required
@user_passes_test(is_professor)
def gerenciar_conteudo(request):
    # Sua lógica para gerenciar conteúdo
    return render(request, 'Pyquest/gerenciar_conteudo.html')

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



def dashboard(request):
    return render(request, "Pyquest/dashboard.html")




