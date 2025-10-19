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
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Count
from datetime import timedelta
from django.utils import timezone


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
    storage = messages.get_messages(request)
    for message in storage:
        pass  # Isso limpa as mensagens    

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
@login_required
def perfil(request):
    perfil, created = Perfil.objects.get_or_create(user=request.user)

    XP_POR_NIVEL = 100

    while perfil.xp >= XP_POR_NIVEL:
        perfil.nivel += 1
        perfil.xp -= XP_POR_NIVEL
        perfil.save()

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

    # ========== FILTROS CORRIGIDOS ========== #
    raridade = request.GET.get('raridade', 'todas')
    categoria = request.GET.get('categoria', 'todas')
    
    # Buscar TODAS as conquistas
    conquistas_query = Conquista.objects.all()
    
    # Aplicar filtros apenas se não for "todas"
    if raridade != 'todas':
        conquistas_query = conquistas_query.filter(raridade=raridade)
    
    if categoria != 'todas':
        conquistas_query = conquistas_query.filter(categoria=categoria)
    
    # Paginação
    itens_por_pagina = 2
    paginator = Paginator(conquistas_query, itens_por_pagina)
    
    page_number = request.GET.get('page')
    
    try:
        page_obj = paginator.get_page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.get_page(1)
    except EmptyPage:
        page_obj = paginator.get_page(paginator.num_pages)
    
    # Separar conquistas da página atual
    conquistas_pagina = page_obj.object_list
    conquistas_desbloqueadas_pagina = [c for c in conquistas_pagina if c in request.user.conquistas.all()]
    conquistas_bloqueadas_pagina = [c for c in conquistas_pagina if c not in request.user.conquistas.all()]

    context = {
        "perfil": perfil,
        "conquistas_desbloqueadas": conquistas_desbloqueadas_pagina,
        "conquistas_bloqueadas": conquistas_bloqueadas_pagina,
        "progresso_xp": progresso_xp,
        "desbloq_count": request.user.conquistas.count(),
        "total_conquistas": Conquista.objects.count(),
        "page_obj": page_obj,
        "raridade_filtro": raridade,
        "categoria_filtro": categoria,
    }
    return render(request, "Pyquest/perfil.html", context)


# views.py (substitua a função ranking existente)


@login_required
def ranking(request):
    # ordena por XP decrescente
    perfis_completo = Perfil.objects.select_related('user').order_by('-xp')
    
    # Paginação - usa uma cópia para não afetar o Top 3
    paginator = Paginator(perfis_completo, 10)  # 10 usuários por página
    page_number = request.GET.get('page')
    
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)
    
    # calcula posição do usuário atual (1-based)
    posicao_usuario = None
    try:
        ids = list(perfis_completo.values_list('user_id', flat=True))
        if request.user.id in ids:
            posicao_usuario = ids.index(request.user.id) + 1
    except Exception:
        posicao_usuario = None

    contexto = {
        "perfis": perfis_completo,  # Lista COMPLETA para o Top 3
        "page_obj": page_obj,       # Lista PAGINADA para o ranking completo
        "usuario_logado": request.user.id,
        "posicao_usuario": posicao_usuario,
        "is_paginated": paginator.num_pages > 1,
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
        
     

       
        
        # DEBUG: Verificar hashtags
        print("=== DEBUG HASHTAGS ===")
        uma_semana_atras = timezone.now() - timedelta(days=7)
        todas_hashtags = Hashtag.objects.all()
        print(f"Total de hashtags: {todas_hashtags.count()}")
        
        for tag in todas_hashtags:
            print(f"#{tag.nome} - {tag.contador} usos - {tag.ultimo_uso}")
        
        # Tópicos em alta - versão temporária para teste
        trending_tags = Hashtag.objects.filter(
        contador__gte=1  # Pelo menos 1 uso
        ).order_by('-contador', '-ultimo_uso')[:10]

        print(f"DEBUG: {trending_tags.count()} trending tags com contador >= 1")
        for tag in trending_tags:
            print(f"DEBUG: #{tag.nome} - contador: {tag.contador}")
        
        
        
        # Contribuidores destaque (usuários com mais XP)
        top_users = User.objects.filter(perfil__isnull=False).order_by('-perfil__xp')[:10]
        
        # Filtros
        current_filter = request.GET.get('filter', 'all')
        search_query = request.GET.get('q', '')
        
        posts = Post.objects.all().order_by("-created_at").prefetch_related("comentarios", "hashtags", "autor__perfil")
        
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

        # Paginação
        paginator = Paginator(posts, 10)
        page_number = request.GET.get('page')
        try:
            posts = paginator.page(page_number)
        except PageNotAnInteger:
            posts = paginator.page(1)
        except EmptyPage:
            posts = paginator.page(paginator.num_pages)

        context = {
            "posts": posts,
            "total_users": total_users,
            "active_today": active_today,
            "posts_today": posts_today,
            "trending_tags": trending_tags,
            "top_users": top_users,
            "current_filter": current_filter,
            "search_query": search_query,
            "is_paginated": paginator.num_pages > 1,
            "page_obj": posts,
        }

        return render(request, "Pyquest/forum.html", context)
    
    except Exception as e:
        # Fallback em caso de erro
        print(f"Erro no forum: {e}")
        posts = Post.objects.all().order_by("-created_at")
        paginator = Paginator(posts, 10)
        page_number = request.GET.get('page')
        try:
            posts = paginator.page(page_number)
        except PageNotAnInteger:
            posts = paginator.page(1)
        except EmptyPage:
            posts = paginator.page(paginator.num_pages)
            
        context = {
            "posts": posts,
            "total_users": User.objects.count(),
            "active_today": 0,
            "posts_today": 0,
            "trending_tags": Hashtag.objects.order_by('-contador')[:10],
            "top_users": User.objects.filter(perfil__isnull=False).order_by('-perfil__xp')[:10],
            "current_filter": "all",
            "search_query": "",
            "is_paginated": paginator.num_pages > 1,
            "page_obj": posts,
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

@login_required
@user_passes_test(is_professor)
def criar_conteudo(request):
    # Sua lógica para criar conteúdo
    return render(request, 'Pyquest/criar_conteudo.html')

@login_required
@user_passes_test(is_professor)
def gerenciar_conteudo(request):
    # Sua lógica para gerenciar conteúdo
    return render(request, 'Pyquest/gerenciar_conteudo.html')

# ---------- PÁGINAS EXISTENTES ----------


def conteudo(request):
    # Simulando dados dos capítulos com imagens específicas
    chapters = [
        {
            'id': 1, 
            'nome': 'Fundamentos do Python', 
            'progresso': 85, 
            'bloqueado': False,
            'imagem': 'imagem/package_100dp_2682EA_FILL0_wght400_GRAD0_opsz48.png',  # CAMINHO COMPLETO
            'descricao': 'Aprenda os conceitos básicos e essenciais do Python'
        },
        {
            'id': 2, 
            'nome': 'Controle de Fluxo', 
            'progresso': 50, 
            'bloqueado': False,
            'imagem': 'imagem/cached_100dp_2682EA_FILL0_wght400_GRAD0_opsz48.png',
            'descricao': 'Domine condicionais e loops para controlar o fluxo do programa'
        },
        {
            'id': 3, 
            'nome': 'Estruturas de Dados', 
            'progresso': 0, 
            'bloqueado': False,
            'imagem': 'imagem/flowsheet_100dp_2682EA_FILL0_wght400_GRAD0_opsz48.png',
            'descricao': 'Aprenda a usar listas, tuplas, dicionários e conjuntos'
        },
        {
            'id': 4, 
            'nome': 'Funções', 
            'progresso': 0, 
            'bloqueado': True,
            'imagem': 'imagem/functions_100dp_2682EAFF_FILL0_wght400_GRAD0_opsz48.png',
            'descricao': 'Organize seu código com funções e parâmetros'
        },
        {
            'id': 5, 
            'nome': 'Programação Orientada a Objetos', 
            'progresso': 0, 
            'bloqueado': True,
            'imagem': 'imagem/code_blocks_100dp_2682EA_FILL0_wght400_GRAD0_opsz48 (1).png',
            'descricao': 'Domine classes, objetos e herança'
        },
        {
            'id': 6, 
            'nome': 'Módulos e Pacotes', 
            'progresso': 0, 
            'bloqueado': True,
            'imagem': 'imagem/package_100dp_2682EA_FILL0_wght400_GRAD0_opsz48.png',
            'descricao': 'Aprenda a usar e criar módulos e pacotes'
        },
    ]
    
    # ⬇️ SUBSTITUA APENAS ESTA PARTE ⬇️
    paginator = Paginator(chapters, 3)  # 3 capítulos por página
    page_number = request.GET.get('page')
    
    try:
        page_obj = paginator.get_page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.get_page(1)
    except EmptyPage:
        page_obj = paginator.get_page(paginator.num_pages)
    
    return render(request, "Pyquest/conteudo.html", {'page_obj': page_obj})

def modulos(request):
    # Simulando dados dos módulos
    modulos_list = [
        {'id': 1, 'nome': 'Introdução ao Python', 'concluido': True, 'progresso': 100, 'xp': 100},
        {'id': 2, 'nome': 'Variáveis e Tipos', 'concluido': True, 'progresso': 100, 'xp': 150},
        {'id': 3, 'nome': 'Operadores', 'concluido': False, 'progresso': 80, 'xp': 120},
        {'id': 4, 'nome': 'Estruturas de Controle', 'concluido': False, 'progresso': 0, 'xp': 200},
        {'id': 5, 'nome': 'Funções Básicas', 'concluido': False, 'progresso': 0, 'xp': 180},
        {'id': 6, 'nome': 'Listas e Tuplas', 'concluido': False, 'progresso': 0, 'xp': 160},
    ]
    
   # ⬇️ SUBSTITUA APENAS ESTA PARTE ⬇️
    paginator = Paginator(modulos_list, 3)  # 3 módulos por página
    page_number = request.GET.get('page')
    
    try:
        page_obj = paginator.get_page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.get_page(1)
    except EmptyPage:
        page_obj = paginator.get_page(paginator.num_pages)
    
    return render(request, "Pyquest/modulos.html", {'page_obj': page_obj})

def tarefas(request):
    # Simulando tarefas de teoria e prática
    tarefas_teoria = [
        {'id': 1, 'titulo': 'Conceitos Fundamentais', 'concluido': True, 'tipo': 'teoria', 'xp': 25, 'tempo': '10 min'},
        {'id': 2, 'titulo': 'Sintaxe e Estrutura', 'concluido': True, 'tipo': 'teoria', 'xp': 25, 'tempo': '15 min'},
        {'id': 3, 'titulo': 'Boas Práticas', 'concluido': False, 'tipo': 'teoria', 'xp': 25, 'tempo': '10 min'},
        {'id': 4, 'titulo': 'Debugging', 'concluido': False, 'tipo': 'teoria', 'xp': 30, 'tempo': '12 min'},
    ]
    
    tarefas_pratica = [
        {'id': 5, 'titulo': 'Exercícios Básicos', 'concluido': True, 'tipo': 'pratica', 'xp': 40, 'tempo': '15 min'},
        {'id': 6, 'titulo': 'Desafios Intermediários', 'concluido': True, 'tipo': 'pratica', 'xp': 60, 'tempo': '20 min'},
        {'id': 7, 'titulo': 'Projeto Prático', 'concluido': False, 'tipo': 'pratica', 'xp': 80, 'tempo': '30 min'},
        {'id': 8, 'titulo': 'Desafio Avançado', 'concluido': False, 'tipo': 'pratica', 'xp': 100, 'tempo': '25 min'},
    ]
    
    # Combinar todas as tarefas para paginação
    todas_tarefas = tarefas_teoria + tarefas_pratica
    
    paginator = Paginator(todas_tarefas, 4)  # 4 tarefas por página
    page_number = request.GET.get('page')
    
    try:
        page_obj = paginator.get_page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.get_page(1)
    except EmptyPage:
        page_obj = paginator.get_page(paginator.num_pages)
    
    # Separar tarefas da página atual por tipo
    tarefas_pagina = page_obj.object_list
    tarefas_teoria_pagina = [t for t in tarefas_pagina if t['tipo'] == 'teoria']
    tarefas_pratica_pagina = [t for t in tarefas_pagina if t['tipo'] == 'pratica']
    
    context = {
        'page_obj': page_obj,
        'tarefas_teoria': tarefas_teoria_pagina,
        'tarefas_pratica': tarefas_pratica_pagina,
        'total_teoria': len(tarefas_teoria),
        'total_pratica': len(tarefas_pratica),
    }
    
    return render(request, "Pyquest/tarefas.html", context)

def teoria(request):
    # Simulando lições de teoria com conteúdo
    lessons = [
        {
            'id': 1, 
            'titulo': 'Conceitos Fundamentais', 
            'concluido': True, 
            'conteudo': 'Python é uma linguagem de programação de alto nível, interpretada e de propósito geral...',
            'exemplo_codigo': '# Meu primeiro programa\nprint("Olá, Mundo!")',
            'caracteristicas': ['Sintaxe simples', 'Interpretada', 'Multiplataforma']
        },
        {
            'id': 2, 
            'titulo': 'Sintaxe e Estrutura', 
            'concluido': True, 
            'conteudo': 'Aprenda a escrever código corretamente, incluindo indentação e comandos básicos...',
            'exemplo_codigo': '# Estrutura condicional\nif idade >= 18:\n    print("Maior de idade")',
            'caracteristicas': ['Indentação obrigatória', 'Estruturas de controle', 'Funções built-in']
        },
        {
            'id': 3, 
            'titulo': 'Boas Práticas', 
            'concluido': False, 
            'conteudo': 'Descubra convenções de código e padrões de nomenclatura...',
            'exemplo_codigo': '# Boas práticas de nomenclatura\nminha_variavel = 10',
            'caracteristicas': ['PEP 8', 'Nomes descritivos', 'Comentários']
        },
        {
            'id': 4, 
            'titulo': 'Debugging Básico', 
            'concluido': False, 
            'conteudo': 'Aprenda a identificar e corrigir erros no seu código...',
            'exemplo_codigo': '# Debugging\nimport pdb; pdb.set_trace()',
            'caracteristicas': ['Tratamento de erros', 'Depuração', 'Logs']
        },
    ]
    # ⬇️ SUBSTITUA APENAS ESTA PARTE ⬇️
    paginator = Paginator(lessons, 1)  # 1 lição por página
    page_number = request.GET.get('page')
    
    try:
        page_obj = paginator.get_page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.get_page(1)
    except EmptyPage:
        page_obj = paginator.get_page(paginator.num_pages)
    
    # Determinar lição atual e próxima
    current_lesson = page_obj[0] if page_obj else None
    next_lesson_id = current_lesson['id'] + 1 if current_lesson and current_lesson['id'] < len(lessons) else None
    
    context = {
        'page_obj': page_obj,
        'current_lesson': current_lesson,
        'next_lesson_id': next_lesson_id,
        'total_lessons': len(lessons),
    }
    
    return render(request, "Pyquest/teoria.html", context)

@login_required
def completar_licao(request, licao_id):
    """Marca uma lição como concluída e redireciona para a próxima"""
    # Aqui você implementaria a lógica para marcar a lição como concluída
    # Por enquanto, apenas redireciona para a próxima lição
    
    next_licao_id = licao_id + 1
    
    # Verifica se existe próxima lição
    if next_licao_id <= 4:  # Supondo 4 lições no total
        return redirect(f'{request.build_absolute_uri("/teoria/")}?page={next_licao_id}')
    else:
        # Se for a última lição, volta para as tarefas
        messages.success(request, "🎉 Parabéns! Você completou todas as lições deste módulo!")
        return redirect('tarefas')

def pratica(request):
    return render(request, "Pyquest/pratica.html")



def dashboard(request):
    return render(request, "Pyquest/dashboard.html")