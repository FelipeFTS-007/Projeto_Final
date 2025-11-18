from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils import timezone
from .models import *
from django.db.models import Count, Sum, Q, Avg
from datetime import datetime, timedelta
from django.dispatch import receiver
from django.db.models.signals import post_save
from django.http import JsonResponse
import json
import random
from .forms import *
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST, require_GET
from django.db import models
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.conf import settings
from .conquistas_manager import ConquistaManager




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
    
    # VERIFICAÇÃO AUTOMÁTICA DO RESET DIÁRIO
    perfil.verificar_reset_diario()
    perfil.save()  # Isso garante que o reset seja salvo se necessário
    
    perfil.regenerar_vidas()
    perfil.verificar_streak_automatico()
    perfil.regenerar_vidas()

    hoje = timezone.now().date()
    progresso_hoje, _ = Progresso.objects.get_or_create(user=request.user, data=hoje)

    # CALCULAR TEMPO DE ESTUDO CORRETAMENTE
    tempo_total_segundos = perfil.tempo_total_estudo
    minutos_totais = tempo_total_segundos // 60
    segundos_restantes = tempo_total_segundos % 60
    horas = minutos_totais // 60
    minutos = minutos_totais % 60
    
    if horas > 0:
        tempo_formatado = f"{horas:02d}:{minutos:02d}:{segundos_restantes:02d}"
    else:
        tempo_formatado = f"{minutos:02d}:{segundos_restantes:02d}"

    # Calcular progresso das vidas
    progresso_vidas = int((perfil.vidas / perfil.max_vidas) * 100) if perfil.max_vidas > 0 else 0

    atividades = Atividade.objects.filter(user=request.user).order_by("-data")[:5]

    # Calcular progresso do nível
    progresso_nivel = perfil.get_progresso_nivel()
    xp_necessario = perfil.calcular_xp_para_proximo_nivel()

    context = {
        "vidas": perfil.vidas,
        "max_vidas": perfil.max_vidas,
        "progresso_vidas": progresso_vidas,
        "proxima_vida": perfil.tempo_para_proxima_vida(),
        "nome": request.user.first_name or request.user.username,
        "xp": perfil.xp,
        "nivel": perfil.nivel,
        "progresso_nivel": progresso_nivel,
        "xp_necessario": xp_necessario,
        "conquistas": perfil.conquistas,
        "total_conquistas": perfil.total_conquistas,
        "sequencia": perfil.sequencia,
        "ja_fez_atividade_hoje": perfil.ja_fez_atividade_hoje,  # NOVO
        "progresso": progresso_hoje.percentual,
        "meta": 60,
        "tempo": tempo_formatado,
        "tempo_segundos": tempo_total_segundos,
        "xp_diario": progresso_hoje.xp_ganho,
        "atividades": atividades,
        "perfil": perfil,
    }
    return render(request, "Pyquest/home.html", context)


def logout_view(request):
    logout(request)
    return redirect("login")



# views.py - ATUALIZE a função perfil (parte das conquistas)

@login_required
def perfil(request):
    perfil, created = Perfil.objects.get_or_create(user=request.user)

    # NOVO SISTEMA: Usar progresso do nível sem zerar XP
    progresso_xp = perfil.get_progresso_nivel()
    xp_necessario = perfil.calcular_xp_para_proximo_nivel()

    if request.method == "POST":
        if "avatar" in request.FILES:
            perfil.avatar = request.FILES["avatar"]

        perfil.descricao = request.POST.get("descricao", "").strip()
        perfil.github = request.POST.get("github", "").strip()
        perfil.linkedin = request.POST.get("linkedin", "").strip()

        perfil.save()
        messages.success(request, "Perfil atualizado com sucesso!")
        return redirect("perfil")

    # ========== FILTROS E PAGINAÇÃO CORRIGIDOS ========== #
    raridade = request.GET.get('raridade', 'todas')
    categoria = request.GET.get('categoria', 'todas')
    
    # Buscar TODAS as conquistas
    conquistas_query = Conquista.objects.filter(ativo=True)
    
    # Aplicar filtros
    if raridade != 'todas':
        conquistas_query = conquistas_query.filter(raridade=raridade)
    
    if categoria != 'todas':
        conquistas_query = conquistas_query.filter(categoria=categoria)
    
    # Ordenar por raridade (da menos rara para a mais rara)
    ordem_raridade = {
        'comum': 1,
        'rara': 2, 
        'epica': 3,
        'lendaria': 4
    }
    
    # Calcular progresso para TODAS as conquistas filtradas
    todas_conquistas_com_progresso = []
    for conquista in conquistas_query:
        try:
            progresso = conquista.calcular_progresso(request.user)
            desbloqueada = conquista.verificar_desbloqueio(request.user)
            todas_conquistas_com_progresso.append({
                'conquista': conquista,
                'progresso': progresso,
                'desbloqueada': desbloqueada,
                'ordem_raridade': ordem_raridade.get(conquista.raridade, 5)
            })
        except Exception as e:
            print(f"❌ Erro ao calcular progresso da conquista {conquista.titulo}: {e}")
            todas_conquistas_com_progresso.append({
                'conquista': conquista,
                'progresso': {
                    'progresso_atual': 0,
                    'meta': conquista.valor_requerido,
                    'percentual': 0,
                    'atingiu_meta': False,
                    'falta': conquista.valor_requerido
                },
                'desbloqueada': False,
                'ordem_raridade': ordem_raridade.get(conquista.raridade, 5)
            })
    
    # Ordenar por raridade (da menos rara para a mais rara)
    todas_conquistas_com_progresso.sort(key=lambda x: x['ordem_raridade'])
    
    # Separar conquistas desbloqueadas e bloqueadas
    conquistas_desbloqueadas = [c for c in todas_conquistas_com_progresso if c['desbloqueada']]
    conquistas_bloqueadas = [c for c in todas_conquistas_com_progresso if not c['desbloqueada']]
    
    # PAGINAÇÃO SEPARADA - MOSTRAR APENAS AS QUE EXISTEM
    itens_por_pagina = 8  # Máximo por página
    
    # Para a primeira página: mostrar até 4 desbloqueadas + até 4 bloqueadas
    page_number = request.GET.get('page', 1)
    
    try:
        page_number = int(page_number)
    except:
        page_number = 1
    
    # Calcular índices para desbloqueadas
    start_desbloqueadas = (page_number - 1) * 4
    end_desbloqueadas = start_desbloqueadas + 4
    desbloqueadas_pagina = conquistas_desbloqueadas[start_desbloqueadas:end_desbloqueadas]
    
    # Calcular índices para bloqueadas
    start_bloqueadas = (page_number - 1) * 4
    end_bloqueadas = start_bloqueadas + 4
    bloqueadas_pagina = conquistas_bloqueadas[start_bloqueadas:end_bloqueadas]
    
    # Calcular total de páginas (baseado no que tem mais itens)
    total_paginas_desbloqueadas = (len(conquistas_desbloqueadas) + 3) // 4  # Arredonda para cima
    total_paginas_bloqueadas = (len(conquistas_bloqueadas) + 3) // 4  # Arredonda para cima
    total_paginas = max(total_paginas_desbloqueadas, total_paginas_bloqueadas)
    
    # Criar objeto de paginação simulado para o template
    class PaginacaoSimulada:
        def __init__(self, numero, total_paginas):
            self.number = numero
            self.paginator = self.PaginatorSimulado(total_paginas)
        
        class PaginatorSimulado:
            def __init__(self, num_pages):
                self.num_pages = num_pages
            
            @property
            def count(self):
                return len(conquistas_desbloqueadas) + len(conquistas_bloqueadas)
        
        def has_previous(self):
            return self.number > 1
        
        def has_next(self):
            return self.number < self.paginator.num_pages
        
        def previous_page_number(self):
            return self.number - 1
        
        def next_page_number(self):
            return self.number + 1
        
        @property
        def start_index(self):
            return ((self.number - 1) * 8) + 1
        
        @property
        def end_index(self):
            end = self.number * 8
            total = len(conquistas_desbloqueadas) + len(conquistas_bloqueadas)
            return min(end, total)
    
    page_obj = PaginacaoSimulada(page_number, total_paginas)

    context = {
        "perfil": perfil,
        "conquistas_desbloqueadas": desbloqueadas_pagina,
        "conquistas_bloqueadas": bloqueadas_pagina,
        "progresso_xp": progresso_xp,
        "xp_necessario": xp_necessario,
        "desbloq_count": len(conquistas_desbloqueadas),  # Total geral
        "total_conquistas": conquistas_query.count(),
        "page_obj": page_obj,
        "raridade_filtro": raridade,
        "categoria_filtro": categoria,
        "pagina_atual": page_number,
        "total_paginas": total_paginas,
    }
    return render(request, "Pyquest/perfil.html", context)


# views.py (substitua a função ranking existente)


@login_required
def ranking(request):
    # ordena por XP decrescente
    perfis_completo = Perfil.objects.select_related('user').order_by('-xp')
    
    # Paginação - usa uma cópia para não afetar o Top 3
    paginator = Paginator(perfis_completo, 3)  # 10 usuários por página
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
        total_users = User.objects.count()
        hoje = timezone.now().date()

        active_today = User.objects.filter(
            Q(post__created_at__date=hoje) |
            Q(comentarios__created_at__date=hoje)
        ).distinct().count()

        posts_today = Post.objects.filter(created_at__date=hoje).count()

        # 🔹 Hashtags ordenadas e filtradas
        trending_tags = (
            Hashtag.objects
            .filter(contador__gte=1)
            .order_by('-contador', '-ultimo_uso')[:10]
        )

        # 🔹 Usuários com mais XP
        top_users = (
            User.objects
            .filter(perfil__isnull=False)
            .order_by('-perfil__xp')[:10]
        )

        # 🔹 Posts e filtros
        current_filter = request.GET.get('filter', 'all')
        search_query = request.GET.get('q', '')

        posts = (
            Post.objects
            .all()
            .order_by("-created_at")
            .prefetch_related("comentarios", "hashtags", "autor__perfil")
        )

        if search_query:
            posts = posts.filter(
                Q(conteudo__icontains=search_query) |
                Q(hashtags__nome__icontains=search_query) |
                Q(autor__username__icontains=search_query)
            ).distinct()

        if current_filter == 'popular':
            posts = posts.annotate(like_count=Count('likes')).order_by('-like_count', '-created_at')
        elif current_filter == 'recent':
            posts = posts.order_by('-created_at')

        paginator = Paginator(posts, 3)
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
        print(f"[ERRO] forum: {e}")
        posts = Post.objects.all().order_by("-created_at")
        paginator = Paginator(posts, 10)
        try:
            posts = paginator.page(1)
        except:
            posts = []

        context = {
            "posts": posts,
            "total_users": User.objects.count(),
            "active_today": 0,
            "posts_today": 0,
            "trending_tags": Hashtag.objects.order_by('-contador', '-ultimo_uso')[:10],
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
        conteudo = request.POST.get("conteudo", "").strip()
        hashtags_text = request.POST.get("hashtags", "")

        if not conteudo:
            return redirect("forum")

        post = Post.objects.create(
            autor=request.user,
            conteudo=conteudo
        )

        # 🔹 Processar hashtags
        hashtags = [tag.strip().lower().lstrip('#') for tag in hashtags_text.split(",") if tag.strip()]
        for nome in hashtags:
            tag, created = Hashtag.objects.get_or_create(nome=nome)
            tag.contador = (tag.contador or 0) + 1
            tag.ultimo_uso = timezone.now()
            tag.save()
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
        texto = request.POST.get("texto", "").strip()

        if not texto:
            return JsonResponse({"success": False, "error": "Comentário vazio."})

        comentario = Comentario.objects.create(
            post=post,
            autor=request.user,
            texto=texto
        )

        # 🔹 Detectar e registrar hashtags usadas em comentários
        hashtags = [tag.strip('#').lower() for tag in texto.split() if tag.startswith('#')]
        for nome in hashtags:
            tag, created = Hashtag.objects.get_or_create(nome=nome)
            tag.contador = (tag.contador or 0) + 1
            tag.ultimo_uso = timezone.now()
            tag.save()

        # 🔹 Retorno AJAX com avatar e conquistas
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            perfil = comentario.autor.perfil
            conquistas_data = []
            if hasattr(perfil, "conquistas") and hasattr(perfil.conquistas, "all"):
                conquistas_data = [
                    {"titulo": c.titulo, "icone": c.icone.url if c.icone else None}
                    for c in perfil.conquistas.all()
                ]
            return JsonResponse({
                "success": True,
                "comment_id": comentario.id,
                "author": comentario.autor.username,
                "text": comentario.texto,
                "avatar_url": perfil.avatar.url if perfil.avatar else "/static/img/default-avatar.png",
                "bio": perfil.descricao or "",
                "xp": perfil.xp,
                "level": perfil.nivel,
                "github": perfil.github or "#",
                "linkedin": perfil.linkedin or "#",
                "conquistas": conquistas_data,
            })

    return redirect("forum")

@login_required
def like_post(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    liked = False

    if request.user in post.likes.all():
        post.likes.remove(request.user)
    else:
        post.likes.add(request.user)
        liked = True

    # Se for uma requisição AJAX, retorna JSON
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({
            "liked": liked,
            "likes_count": post.likes.count(),
        })

    # Fallback (caso JS falhe)
    return redirect("forum")


@login_required
def like_comment(request, comment_id):
    comentario = get_object_or_404(Comentario, id=comment_id)
    liked = False

    if request.user in comentario.likes.all():
        comentario.likes.remove(request.user)
    else:
        comentario.likes.add(request.user)
        liked = True

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({
            "liked": liked,
            "likes_count": comentario.likes.count(),
        })

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




def top_hashtags_json(request):
    hashtags = Hashtag.objects.order_by('-contador', '-ultimo_uso')[:5]
    data = [
        {"nome": h.nome, "contador": h.contador}
        for h in hashtags
    ]
    return JsonResponse({"hashtags": data})


def is_professor(user):
    return user.groups.filter(name='professores').exists() or user.is_staff

# views.py - ATUALIZAR criar_conteudo
import json
from django.http import JsonResponse


# views.py - ATUALIZAR a view criar_conteudo
@login_required
@csrf_exempt
def criar_conteudo(request):
    if request.method == 'POST':
        try:
            print("=== INICIANDO CRIAÇÃO DE CONTEÚDO ===")
            
            # Dados básicos
            capitulo_id = request.POST.get('capitulo_id')
            modulo_id = request.POST.get('modulo_id')
            titulo_aula = request.POST.get('titulo_aula')
            
            print(f"Dados recebidos - Capítulo: {capitulo_id}, Módulo: {modulo_id}, Título: {titulo_aula}")
            
            # Dados do conteúdo teórico
            titulo_teoria = request.POST.get('titulo_teoria', 'Conteúdo Teórico')
            descricao_breve = request.POST.get('descricao_breve', '')
            
            # Dados do conteúdo prático - AGORA OBRIGATÓRIO
            titulo_pratica = request.POST.get('titulo_pratica', 'Exercícios Práticos')
            conteudo_pratico = request.POST.get('conteudo_pratico', '')  # AGORA OBRIGATÓRIO
            
            print(f"Dados práticos - Título: {titulo_pratica}, Descrição: {conteudo_pratico[:100]}...")
            
            # NOVOS CAMPOS DE TEMPO E XP
            tempo_teoria = request.POST.get('tempo_estimado_teoria', 30)
            tempo_pratica = request.POST.get('tempo_estimado_pratica', 15)
            xp_teoria = request.POST.get('theory_xp', 30)
            
            # Processar tópicos
            topicos_json = request.POST.get('topicos_json', '[]')
            print(f"Tópicos JSON recebido: {topicos_json[:200]}...")
            
            try:
                topicos_data = json.loads(topicos_json)
                print(f"Processando {len(topicos_data)} tópicos...")
            except json.JSONDecodeError as e:
                print(f"Erro ao decodificar tópicos JSON: {e}")
                topicos_data = []
            
            # Processar questões
            questoes_json = request.POST.get('questoes_json', '[]')
            print(f"Questões JSON recebido: {questoes_json[:200]}...")
            
            try:
                questoes_data = json.loads(questoes_json)
                print(f"Processando {len(questoes_data)} questões...")
            except json.JSONDecodeError as e:
                print(f"Erro ao decodificar questões JSON: {e}")
                questoes_data = []
            
            # CRIAR A AULA COM OS NOVOS CAMPOS
            aula = Aula.objects.create(
                modulo_id=modulo_id,
                titulo_aula=titulo_aula,
                titulo_teoria=titulo_teoria,
                descricao_breve=descricao_breve,
                # CAMPOS PRÁTICOS - AGORA OBRIGATÓRIOS
                titulo_pratica=titulo_pratica,
                conteudo_pratico=conteudo_pratico,
                # TEMPOS E XP
                tempo_teoria=tempo_teoria,
                tempo_pratica=tempo_pratica,
                xp_teoria=xp_teoria,
                ordem=Aula.objects.filter(modulo_id=modulo_id).count() + 1,
                criado_por=request.user,
                tem_teoria=len(topicos_data) > 0,
                tem_exercicios=len(questoes_data) > 0
            )
            
            print(f"Aula criada: {aula.titulo_aula} (ID: {aula.id})")
            print(f"Tempos - Teoria: {tempo_teoria}min, Prática: {tempo_pratica}min, Total: {aula.tempo_total}min")
            print(f"XP - Teoria: {xp_teoria}, Prática: {aula.xp_pratica}, Total: {aula.get_xp_total()}")
            print(f"Conteúdo prático salvo: {conteudo_pratico[:100]}...")
            
            # --- PROCESSAR TÓPICOS ---
            for i, topico_data in enumerate(topicos_data):
                titulo = topico_data.get('titulo', f'Tópico {i+1}').strip()
                conteudo = topico_data.get('conteudo', '').strip()
                
                if titulo or conteudo:
                    TopicoTeorico.objects.create(
                        aula=aula,
                        titulo=titulo or f'Tópico {i+1}',
                        conteudo=conteudo,
                        ordem=topico_data.get('ordem', i + 1)
                    )
                    print(f"Tópico criado: {titulo}")
            
            # --- PROCESSAR QUESTÕES ---
            xp_total_pratica = 0
            
            for i, questao_data in enumerate(questoes_data):
                tipo = questao_data.get('type')
                xp_questao = questao_data.get('xp', 10)
                xp_total_pratica += xp_questao
                
                print(f"Criando questão {i+1}: {tipo} - {xp_questao} XP")
                
                # Determinar enunciado
                if tipo == 'multiple-choice':
                    enunciado = questao_data.get('pergunta', '')
                elif tipo == 'code':
                    enunciado = questao_data.get('instrucao', '')
                elif tipo == 'fill-blank':
                    enunciado = questao_data.get('texto', '')
                else:
                    enunciado = questao_data.get('enunciado', '')
                
                # Criar questão
                questao = Questao.objects.create(
                    aula=aula,
                    tipo=tipo,
                    enunciado=enunciado,
                    descricao=questao_data.get('descricao', ''),
                    ordem=questao_data.get('ordem', i + 1),
                    xp=xp_questao
                )
                
                # Campos específicos
                if tipo == 'code':
                    questao.codigo_inicial = questao_data.get('codigo_inicial', '')
                    questao.saida_esperada = questao_data.get('saida_esperada', '')
                    questao.save()
                
                # Dicas
                dicas = questao_data.get('dicas', [])
                for j, dica_texto in enumerate(dicas):
                    if dica_texto and dica_texto.strip():
                        DicaQuestao.objects.create(
                            questao=questao,
                            texto=dica_texto.strip(),
                            ordem=j + 1
                        )
                
                # Opções (múltipla escolha)
                if tipo == 'multiple-choice':
                    opcoes = questao_data.get('opcoes', [])
                    for k, opcao_data in enumerate(opcoes):
                        texto_opcao = opcao_data.get('texto', '').strip()
                        if texto_opcao:
                            OpcaoQuestao.objects.create(
                                questao=questao,
                                texto=texto_opcao,
                                correta=opcao_data.get('correta', False),
                                ordem=k + 1
                            )
                
                # Respostas (completar lacunas)
                elif tipo == 'fill-blank':
                    respostas = questao_data.get('respostas', [])
                    for k, resposta in enumerate(respostas):
                        if resposta and resposta.strip():
                            OpcaoQuestao.objects.create(
                                questao=questao,
                                texto=resposta.strip(),
                                correta=True,
                                ordem=k + 1
                            )
            
            # Atualizar XP prático total
            aula.xp_pratica = xp_total_pratica
            aula.save()
            
            print(f"XP prático total calculado: {xp_total_pratica}")
            print("Conteúdo criado com sucesso!")
            return redirect('gerenciar_conteudo')
            
        except Exception as e:
            print(f"Erro ao criar conteúdo: {str(e)}")
            import traceback
            traceback.print_exc()
            return JsonResponse({'success': False, 'error': str(e)})
    
    # GET request - mostrar formulário
    capitulos = Capitulo.objects.all()
    return render(request, 'Pyquest/criar_conteudo.html', {'capitulos': capitulos})

@login_required
def get_modulos_ajax(request, capitulo_id):
    """Retorna módulos de um capítulo para AJAX"""
    modulos = Modulo.objects.filter(capitulo_id=capitulo_id, ativo=True).values('id', 'titulo')
    return JsonResponse(list(modulos), safe=False)

@login_required
@user_passes_test(is_professor)
def criar_capitulo_ajax(request):
    """Cria capítulo via AJAX"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            capitulo = Capitulo.objects.create(
                titulo=data['titulo'],
                descricao=data.get('descricao', ''),
                ordem=Capitulo.objects.count() + 1,
                ativo=True,
                dificuldade=data.get('dificuldade', 'beginner')
            )
            return JsonResponse({
                'success': True,
                'capitulo': {
                    'id': capitulo.id,
                    'titulo': capitulo.titulo
                }
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

@login_required
@user_passes_test(is_professor)
def criar_modulo_ajax(request):
    """Cria módulo via AJAX"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            modulo = Modulo.objects.create(
                capitulo_id=data['capitulo_id'],
                titulo=data['titulo'],
                descricao=data.get('descricao', ''),
                ordem=Modulo.objects.filter(capitulo_id=data['capitulo_id']).count() + 1,
                ativo=True
            )
            return JsonResponse({
                'success': True,
                'modulo': {
                    'id': modulo.id,
                    'titulo': modulo.titulo
                }
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
        



# views.py - FUNÇÃO gerenciar_conteudo ATUALIZADA COM XP TOTAL
@login_required
def gerenciar_conteudo(request):
    # Buscar aulas criadas pelo usuário atual
    aulas = Aula.objects.filter(criado_por=request.user).select_related(
        'modulo', 
        'modulo__capitulo'
    ).prefetch_related('questoes').order_by('-data_criacao')
    
    # Obter todos os capítulos para o filtro
    capitulos = Capitulo.objects.all()
    
    # Inicializar filtros
    search_query = request.GET.get('search', '')
    capitulo_selecionado = request.GET.get('capitulo', '')
    status_selecionado = request.GET.get('status', '')
    
    # Aplicar filtros
    if search_query:
        aulas = aulas.filter(
            Q(titulo_aula__icontains=search_query) |
            Q(descricao_breve__icontains=search_query) |
            Q(modulo__titulo__icontains=search_query) |
            Q(modulo__capitulo__titulo__icontains=search_query)
        )
    
    if capitulo_selecionado:
        aulas = aulas.filter(modulo__capitulo_id=capitulo_selecionado)
    
    if status_selecionado:
        if status_selecionado == 'ativo':
            aulas = aulas.filter(ativo=True)
        elif status_selecionado == 'inativo':
            aulas = aulas.filter(ativo=False)
    
    # Calcular estatísticas
    total_aulas = aulas.count()
    aulas_publicadas = aulas.filter(ativo=True).count()
    aulas_inativas = aulas.filter(ativo=False).count()
    
    # Calcular total de questões
    total_questoes = Questao.objects.filter(aula__in=aulas).count()
    
    # CALCULAR XP TOTAL DISPONÍVEL (NOVO)
    total_xp_disponivel = 0
    for aula in aulas:
        total_xp_disponivel += aula.get_xp_total()
    
    print(f"Encontradas {total_aulas} aulas para gerenciamento")
    print(f"Aulas ativas: {aulas_publicadas}, Inativas: {aulas_inativas}")
    print(f"Total de questões: {total_questoes}")
    print(f"XP total disponível: {total_xp_disponivel}")
    
    context = {
        'aulas': aulas,
        'capitulos': capitulos,
        'total_aulas': total_aulas,
        'aulas_publicadas': aulas_publicadas,
        'aulas_inativas': aulas_inativas,
        'total_questoes': total_questoes,
        'total_xp_disponivel': total_xp_disponivel,  # NOVO
        'search_query': search_query,
        'capitulo_selecionado': capitulo_selecionado,
        'status_selecionado': status_selecionado,
    }
    
    return render(request, 'Pyquest/gerenciar_conteudo.html', context)

# views.py - VIEW editar_conteudo COMPLETA E ATUALIZADA
@login_required
def editar_conteudo(request, aula_id):
    aula = get_object_or_404(Aula, id=aula_id, criado_por=request.user)
    
    if request.method == 'POST':
        try:
            print("=== INICIANDO EDIÇÃO DE CONTEÚDO ===")
            
            # Dados básicos da estrutura
            capitulo_id = request.POST.get('capitulo_id')
            modulo_id = request.POST.get('modulo_id')
            titulo_aula = request.POST.get('titulo_aula')
            
            print(f"Dados recebidos - Capítulo: {capitulo_id}, Módulo: {modulo_id}, Título: {titulo_aula}")
            
            # Dados do conteúdo teórico
            titulo_teoria = request.POST.get('titulo_teoria', 'Conteúdo Teórico')
            descricao_breve = request.POST.get('descricao_breve', '')
            
            # Dados do conteúdo prático - CORREÇÃO: CAPTURAR CAMPOS PRÁTICOS
            titulo_pratica = request.POST.get('titulo_pratica', 'Exercícios Práticos')
            conteudo_pratico = request.POST.get('conteudo_pratico', '')
            
            # NOVOS CAMPOS DE TEMPO E XP
            tempo_teoria = request.POST.get('tempo_estimado_teoria', 30)
            tempo_pratica = request.POST.get('tempo_estimado_pratica', 15)
            xp_teoria = request.POST.get('theory_xp', 30)
            
            # Processar tópicos teóricos
            topicos_json = request.POST.get('topicos_json', '[]')
            print(f"Tópicos JSON recebido: {topicos_json[:200]}...")
            
            try:
                topicos_data = json.loads(topicos_json)
                print(f"Processando {len(topicos_data)} tópicos...")
            except json.JSONDecodeError as e:
                print(f"Erro ao decodificar tópicos JSON: {e}")
                topicos_data = []
            
            # Processar questões
            questoes_json = request.POST.get('questoes_json', '[]')
            print(f"Questões JSON recebido: {questoes_json[:200]}...")
            
            try:
                questoes_data = json.loads(questoes_json)
                print(f"Processando {len(questoes_data)} questões...")
            except json.JSONDecodeError as e:
                print(f"Erro ao decodificar questões JSON: {e}")
                questoes_data = []
            
            # ATUALIZAR A AULA COM TODOS OS CAMPOS - CORREÇÃO COMPLETA
            aula.titulo_aula = titulo_aula
            aula.titulo_teoria = titulo_teoria
            aula.descricao_breve = descricao_breve
            
            # CAMPOS PRÁTICOS - CORREÇÃO ADICIONADA
            aula.titulo_pratica = titulo_pratica
            aula.conteudo_pratico = conteudo_pratico
            
            # TEMPOS E XP
            aula.tempo_teoria = tempo_teoria
            aula.tempo_pratica = tempo_pratica
            aula.xp_teoria = xp_teoria
            aula.modulo_id = modulo_id
            aula.tem_teoria = len(topicos_data) > 0
            aula.tem_exercicios = len(questoes_data) > 0
            
            # O tempo_total será calculado automaticamente no save()
            
            aula.save()
            
            print(f"Aula atualizada: {aula.titulo_aula} (ID: {aula.id})")
            print(f"Tempos - Teoria: {tempo_teoria}min, Prática: {tempo_pratica}min, Total: {aula.tempo_total}min")
            print(f"XP - Teoria: {xp_teoria}, Prática: {aula.xp_pratica}, Total: {aula.get_xp_total()}")
            print(f"Conteúdo prático salvo: {conteudo_pratico[:100]}...")
            
            # --- PROCESSAR TÓPICOS TEÓRICOS ---
            # Remover tópicos existentes
            aula.topicos.all().delete()
            
            # Criar novos tópicos
            for i, topico_data in enumerate(topicos_data):
                titulo = topico_data.get('titulo', f'Tópico {i+1}').strip()
                conteudo = topico_data.get('conteudo', '').strip()
                
                if titulo or conteudo:
                    TopicoTeorico.objects.create(
                        aula=aula,
                        titulo=titulo or f'Tópico {i+1}',
                        conteudo=conteudo,
                        ordem=topico_data.get('ordem', i + 1)
                    )
                    print(f"Tópico criado: {titulo}")
            
            # --- PROCESSAR QUESTÕES ---
            # Remover questões existentes
            aula.questoes.all().delete()
            
            xp_total_pratica = 0
            
            # Processar cada questão
            for i, questao_data in enumerate(questoes_data):
                tipo = questao_data.get('type')
                xp_questao = questao_data.get('xp', 10)
                xp_total_pratica += xp_questao
                
                print(f"Criando questão {i+1}: {tipo} - {xp_questao} XP")
                
                # Determinar o enunciado baseado no tipo
                if tipo == 'multiple-choice':
                    enunciado = questao_data.get('pergunta', '')
                elif tipo == 'code':
                    enunciado = questao_data.get('instrucao', '')
                elif tipo == 'fill-blank':
                    enunciado = questao_data.get('texto', '')
                else:
                    enunciado = questao_data.get('enunciado', '')
                
                # Criar questão base
                questao = Questao.objects.create(
                    aula=aula,
                    tipo=tipo,
                    enunciado=enunciado,
                    descricao=questao_data.get('descricao', ''),
                    ordem=questao_data.get('ordem', i + 1),
                    xp=xp_questao
                )
                
                # Adicionar campos específicos por tipo
                if tipo == 'code':
                    questao.codigo_inicial = questao_data.get('codigo_inicial', '')
                    questao.saida_esperada = questao_data.get('saida_esperada', '')
                    questao.save()
                
                # --- PROCESSAR DICAS ---
                dicas = questao_data.get('dicas', [])
                print(f"Adicionando {len(dicas)} dicas para questão {i+1}")
                
                for j, dica_texto in enumerate(dicas):
                    if dica_texto and dica_texto.strip():
                        DicaQuestao.objects.create(
                            questao=questao,
                            texto=dica_texto.strip(),
                            ordem=j + 1
                        )
                
                # --- PROCESSAR OPÇÕES PARA MÚLTIPLA ESCOLHA ---
                if tipo == 'multiple-choice':
                    opcoes = questao_data.get('opcoes', [])
                    print(f"Adicionando {len(opcoes)} opções para questão {i+1}")
                    
                    for k, opcao_data in enumerate(opcoes):
                        texto_opcao = opcao_data.get('texto', '').strip()
                        if texto_opcao:
                            OpcaoQuestao.objects.create(
                                questao=questao,
                                texto=texto_opcao,
                                correta=opcao_data.get('correta', False),
                                ordem=k + 1
                            )
                
                # --- PROCESSAR RESPOSTAS PARA COMPLETAR LACUNAS ---
                elif tipo == 'fill-blank':
                    respostas = questao_data.get('respostas', [])
                    print(f"Adicionando {len(respostas)} respostas para questão {i+1}")
                    
                    for k, resposta in enumerate(respostas):
                        if resposta and resposta.strip():
                            OpcaoQuestao.objects.create(
                                questao=questao,
                                texto=resposta.strip(),
                                correta=True,
                                ordem=k + 1
                            )
            
            # Atualizar XP prático total
            aula.xp_pratica = xp_total_pratica
            aula.save()
            
            print(f"XP prático total calculado: {xp_total_pratica}")
            print("=== CONTEÚDO ATUALIZADO COM SUCESSO ===")
            messages.success(request, 'Conteúdo atualizado com sucesso!')
            return redirect('gerenciar_conteudo')
            
        except Exception as e:
            print(f"ERRO AO ATUALIZAR CONTEÚDO: {str(e)}")
            import traceback
            traceback.print_exc()
            messages.error(request, f'Erro ao atualizar conteúdo: {str(e)}')
            return redirect('gerenciar_conteudo')
    
    # ========== GET REQUEST - CARREGAR DADOS EXISTENTES ==========
    
    capitulos = Capitulo.objects.all()
    modulos = Modulo.objects.filter(capitulo=aula.modulo.capitulo)
    
    # --- PREPARAR TÓPICOS EXISTENTES ---
    topicos_existentes = []
    for topico in aula.topicos.all().order_by('ordem'):
        topicos_existentes.append({
            'titulo': topico.titulo,
            'conteudo': topico.conteudo,
            'ordem': topico.ordem
        })
    
    # Se não houver tópicos mas houver conteúdo no campo antigo, migrar
    if not topicos_existentes and hasattr(aula, 'conteudo_teorico') and aula.conteudo_teorico:
        topicos_existentes.append({
            'titulo': 'Conteúdo Principal',
            'conteudo': aula.conteudo_teorico,
            'ordem': 1
        })
    
    # --- PREPARAR QUESTÕES EXISTENTES ---
    questoes_existentes = []
    for questao in aula.questoes.all().order_by('ordem'):
        questao_data = {
            'type': questao.tipo,
            'ordem': questao.ordem,
            'xp': questao.xp,
            'descricao': questao.descricao or '',
            'dicas': [dica.texto for dica in questao.dicas.all().order_by('ordem')]
        }
        
        # Dados específicos por tipo
        if questao.tipo == 'multiple-choice':
            questao_data['pergunta'] = questao.enunciado
            questao_data['opcoes'] = []
            for opcao in questao.opcoes.all().order_by('ordem'):
                questao_data['opcoes'].append({
                    'texto': opcao.texto,
                    'correta': opcao.correta
                })
        
        elif questao.tipo == 'code':
            questao_data['instrucao'] = questao.enunciado
            questao_data['codigo_inicial'] = questao.codigo_inicial or ''
            questao_data['saida_esperada'] = questao.saida_esperada or ''
        
        elif questao.tipo == 'fill-blank':
            questao_data['texto'] = questao.enunciado
            questao_data['respostas'] = [opcao.texto for opcao in questao.opcoes.filter(correta=True).order_by('ordem')]
        
        questoes_existentes.append(questao_data)
    
    # --- DEBUG: VERIFICAR DADOS CARREGADOS ---
    print("=== DADOS CARREGADOS PARA EDIÇÃO ===")
    print(f"Aula: {aula.titulo_aula}")
    print(f"Tópicos: {len(topicos_existentes)}")
    print(f"Questões: {len(questoes_existentes)}")
    print(f"Tempo teoria: {aula.tempo_teoria}")
    print(f"Tempo prática: {aula.tempo_pratica}")
    print(f"Tempo total: {aula.tempo_total}")
    print(f"XP teoria: {aula.xp_teoria}")
    print(f"XP prática: {aula.xp_pratica}")
    print(f"XP total: {aula.get_xp_total()}")
    print(f"Título prática: {aula.titulo_pratica}")
    print(f"Conteúdo prático: {aula.conteudo_pratico[:100] if aula.conteudo_pratico else 'Vazio'}")
    
    for i, topico in enumerate(topicos_existentes):
        print(f"Tópico {i+1}: {topico['titulo']} - Conteúdo: {len(topico['conteudo'])} chars")
    
    for i, questao in enumerate(questoes_existentes):
        print(f"Questão {i+1}: {questao['type']} - Dicas: {len(questao['dicas'])} - XP: {questao['xp']}")
    
    # --- CONTEXT PARA TEMPLATE ---
    context = {
        'aula': aula,
        'capitulos': capitulos,
        'modulos': modulos,
        'topicos_json': json.dumps(topicos_existentes, ensure_ascii=False),
        'topicos': topicos_existentes,
        'questoes_json': json.dumps(questoes_existentes, ensure_ascii=False),
        'questoes': questoes_existentes,
    }
    
    return render(request, 'Pyquest/editar_conteudo.html', context)
    
# views.py - FUNÇÃO gerenciar_conteudo CORRIGIDA (com ativo/inativo)
@login_required
def gerenciar_conteudo(request):
    # Buscar aulas criadas pelo usuário atual
    aulas = Aula.objects.filter(criado_por=request.user).select_related(
        'modulo', 
        'modulo__capitulo'
    ).prefetch_related('questoes').order_by('-data_criacao')
    
    # Obter todos os capítulos para o filtro
    capitulos = Capitulo.objects.all()
    
    # Inicializar filtros
    search_query = request.GET.get('search', '')
    capitulo_selecionado = request.GET.get('capitulo', '')
    status_selecionado = request.GET.get('status', '')
    
    # Aplicar filtros
    if search_query:
        aulas = aulas.filter(
            Q(titulo_aula__icontains=search_query) |
            Q(descricao_breve__icontains=search_query) |
            Q(modulo__titulo__icontains=search_query) |
            Q(modulo__capitulo__titulo__icontains=search_query)
        )
    
    if capitulo_selecionado:
        aulas = aulas.filter(modulo__capitulo_id=capitulo_selecionado)
    
    if status_selecionado:
        if status_selecionado == 'ativo':
            aulas = aulas.filter(ativo=True)
        elif status_selecionado == 'inativo':
            aulas = aulas.filter(ativo=False)
    
    # Calcular estatísticas
    total_aulas = aulas.count()
    aulas_publicadas = aulas.filter(ativo=True).count()
    aulas_inativas = aulas.filter(ativo=False).count()
    
    # Calcular total de questões
    total_questoes = Questao.objects.filter(aula__in=aulas).count()
    
    print(f"Encontradas {total_aulas} aulas para gerenciamento")
    print(f"Aulas ativas: {aulas_publicadas}, Inativas: {aulas_inativas}")
    print(f"Total de questões: {total_questoes}")
    
    context = {
        'aulas': aulas,
        'capitulos': capitulos,
        'total_aulas': total_aulas,
        'aulas_publicadas': aulas_publicadas,
        'aulas_inativas': aulas_inativas,
        'total_questoes': total_questoes,
        'search_query': search_query,
        'capitulo_selecionado': capitulo_selecionado,
        'status_selecionado': status_selecionado,
    }
    
    return render(request, 'Pyquest/gerenciar_conteudo.html', context)


# views.py - ADICIONAR função para alternar status da aula
@login_required
def alternar_status_aula(request, aula_id):
    aula = get_object_or_404(Aula, id=aula_id, criado_por=request.user)
    
    if request.method == 'POST':
        aula.ativo = not aula.ativo
        aula.save()
        
        status = "ativada" if aula.ativo else "desativada"
        messages.success(request, f'Aula "{aula.titulo_aula}" {status} com sucesso!')
    
    return redirect('gerenciar_conteudo')

# views.py - ADICIONAR função excluir_conteudo
@login_required
@user_passes_test(is_professor)
def excluir_conteudo(request, aula_id):
    aula = get_object_or_404(Aula, id=aula_id, criado_por=request.user)
    
    if request.method == 'POST':
        titulo = aula.titulo_aula
        aula.delete()
        messages.success(request, f'Aula "{titulo}" excluída com sucesso!')
    
    return redirect('gerenciar_conteudo')




@login_required
def conteudo(request):
    capitulos = Capitulo.objects.filter(ativo=True).prefetch_related(
        'modulos__aulas'
    ).order_by('ordem')
    
    # Aplicar paginação
    paginator = Paginator(capitulos, 3)
    page_number = request.GET.get('page')
    
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)
    
    capitulos_com_stats = []
    
    for capitulo in page_obj:
        total_modulos = capitulo.modulos.filter(ativo=True).count()
        total_aulas = Aula.objects.filter(modulo__capitulo=capitulo, ativo=True).count()
        
        # **CALCULAR TEMPO TOTAL DO CAPÍTULO (CORRIGIDO)**
        tempo_total_capitulo_minutos = 0
        for modulo in capitulo.modulos.filter(ativo=True):
            for aula in modulo.aulas.filter(ativo=True):
                # Usar o método get_tempo_total() se existir, ou calcular manualmente
                if hasattr(aula, 'get_tempo_total') and callable(getattr(aula, 'get_tempo_total')):
                    tempo_aula = aula.get_tempo_total() or 0
                else:
                    # Calcular manualmente se o método não existir
                    tempo_teoria = aula.tempo_teoria or 0
                    tempo_pratica = aula.tempo_pratica or 0
                    tempo_aula = tempo_teoria + tempo_pratica
                
                if isinstance(tempo_aula, (int, float)) and tempo_aula > 0:
                    tempo_total_capitulo_minutos += tempo_aula
        
        # Se ainda for zero, usar um valor padrão baseado no número de aulas
        if tempo_total_capitulo_minutos == 0 and total_aulas > 0:
            tempo_total_capitulo_minutos = total_aulas * 30  # 30 minutos por aula como fallback
        
        # Converter minutos para horas (formato: Xh Ymin)
        horas_capitulo = tempo_total_capitulo_minutos // 60
        minutos_capitulo = tempo_total_capitulo_minutos % 60
        
        # Formatar tempo para exibição
        if horas_capitulo > 0:
            tempo_formatado = f"{horas_capitulo}h {minutos_capitulo}min"
        else:
            tempo_formatado = f"{minutos_capitulo}min"
        
        # Resto do código permanece igual...
        modulos_concluidos = 0
        for modulo in capitulo.modulos.filter(ativo=True):
            # Contar TOTAL DE PARTES (teoria + prática) disponíveis
            total_partes = 0
            partes_concluidas = 0
            
            for aula in modulo.aulas.filter(ativo=True):
                # Contar partes disponíveis
                if aula.tem_teoria:
                    total_partes += 1
                if aula.tem_exercicios:
                    total_partes += 1
                
                # Verificar partes concluídas
                conclusao = AulaConcluida.objects.filter(
                    usuario=request.user,
                    aula=aula
                ).first()
                
                if conclusao:
                    if aula.tem_teoria and conclusao.teoria_concluida:
                        partes_concluidas += 1
                    if aula.tem_exercicios and conclusao.pratica_concluida:
                        partes_concluidas += 1
            
            # Considerar módulo concluído apenas se TODAS as partes foram concluídas
            if total_partes > 0 and partes_concluidas == total_partes:
                modulos_concluidos += 1
        
        # Calcular percentual
        if total_modulos > 0:
            progresso_percentual = int((modulos_concluidos / total_modulos) * 100)
        else:
            progresso_percentual = 0
        
        # **LÓGICA DE BLOQUEIO**
        bloqueado = False
        if capitulo.ordem > 1:
            capitulo_anterior = Capitulo.objects.filter(
                ordem=capitulo.ordem - 1, 
                ativo=True
            ).first()
            
            if capitulo_anterior:
                modulos_anterior_concluidos = 0
                for modulo in capitulo_anterior.modulos.filter(ativo=True):
                    total_partes_anterior = 0
                    partes_concluidas_anterior = 0
                    
                    for aula in modulo.aulas.filter(ativo=True):
                        if aula.tem_teoria:
                            total_partes_anterior += 1
                        if aula.tem_exercicios:
                            total_partes_anterior += 1
                        
                        conclusao = AulaConcluida.objects.filter(
                            usuario=request.user,
                            aula=aula
                        ).first()
                        
                        if conclusao:
                            if aula.tem_teoria and conclusao.teoria_concluida:
                                partes_concluidas_anterior += 1
                            if aula.tem_exercicios and conclusao.pratica_concluida:
                                partes_concluidas_anterior += 1
                    
                    if total_partes_anterior > 0 and partes_concluidas_anterior == total_partes_anterior:
                        modulos_anterior_concluidos += 1
                
                total_modulos_anterior = capitulo_anterior.modulos.filter(ativo=True).count()
                
                porcentagem_minima_para_liberar = 50
                
                if total_modulos_anterior > 0:
                    progresso_anterior = (modulos_anterior_concluidos / total_modulos_anterior) * 100
                    if progresso_anterior < porcentagem_minima_para_liberar:
                        bloqueado = True
        
        print(f"📊 Capítulo {capitulo.ordem}: {modulos_concluidos}/{total_modulos} módulos - {progresso_percentual}% - Tempo: {tempo_formatado} - Bloqueado: {bloqueado}")
        
        capitulos_com_stats.append({
            'capitulo': capitulo,
            'total_modulos': total_modulos,
            'total_aulas': total_aulas,
            'modulos_concluidos': modulos_concluidos,
            'progresso_percentual': progresso_percentual,
            'bloqueado': bloqueado,
            'dificuldade': capitulo.dificuldade,
            'tempo_total_minutos': tempo_total_capitulo_minutos,
            'tempo_formatado': tempo_formatado,
        })
    
    # **ESTATÍSTICAS CORRETAS**
    total_capitulos_concluidos = len([c for c in capitulos_com_stats if c['progresso_percentual'] == 100])
    total_capitulos_em_progresso = len([c for c in capitulos_com_stats if 0 < c['progresso_percentual'] < 100])
    total_capitulos_bloqueados = len([c for c in capitulos_com_stats if c['bloqueado']])
    
    print(f"🎯 Estatísticas - Concluídos: {total_capitulos_concluidos}, Em progresso: {total_capitulos_em_progresso}, Bloqueados: {total_capitulos_bloqueados}")
    
    context = {
        'capitulos_com_stats': capitulos_com_stats,
        'total_concluidos': total_capitulos_concluidos,
        'total_em_progresso': total_capitulos_em_progresso,
        'total_bloqueados': total_capitulos_bloqueados,
        'page_obj': page_obj,
        'is_paginated': paginator.num_pages > 1,
    }

    return render(request, "Pyquest/conteudo.html", context)

@login_required
def debug_capitulos(request):
    """View para debug do progresso dos capítulos"""
    capitulos = Capitulo.objects.filter(ativo=True).order_by('ordem')
    
    debug_info = []
    for capitulo in capitulos:
        total_modulos = capitulo.modulos.filter(ativo=True).count()
        modulos_concluidos = 0
        
        for modulo in capitulo.modulos.filter(ativo=True):
            modulo_concluido = True
            for aula in modulo.aulas.filter(ativo=True):
                try:
                    conclusao = AulaConcluida.objects.get(usuario=request.user, aula=aula)
                    if (aula.tem_teoria and not conclusao.teoria_concluida) or (aula.tem_exercicios and not conclusao.pratica_concluida):
                        modulo_concluido = False
                        break
                except AulaConcluida.DoesNotExist:
                    modulo_concluido = False
                    break
            
            if modulo_concluido:
                modulos_concluidos += 1
        
        debug_info.append({
            'capitulo': capitulo.titulo,
            'ordem': capitulo.ordem,
            'modulos_concluidos': modulos_concluidos,
            'total_modulos': total_modulos,
            'percentual': int((modulos_concluidos / total_modulos * 100)) if total_modulos > 0 else 0
        })
    
    return JsonResponse({'debug': debug_info})

# NOVA FUNÇÃO: Determinar dificuldade do capítulo baseado nas aulas
def determinar_dificuldade_capitulo(capitulo):
    # Buscar todas as aulas do capítulo
    aulas = Aula.objects.filter(
        modulo__capitulo=capitulo, 
        ativo=True
    )
    
    if not aulas.exists():
        return 'beginner'  # Padrão se não houver aulas
    
    # Contar dificuldades
    dificuldades = aulas.values_list('dificuldade', flat=True)
    
    # Determinar a dificuldade predominante
    from collections import Counter
    contador = Counter(dificuldades)
    dificuldade_mais_comum = contador.most_common(1)[0][0]
    
    return dificuldade_mais_comum




# views.py - ATUALIZE a função modulos
@login_required
def modulos(request):
    capitulo_id = request.GET.get('capitulo')
    
    if capitulo_id:
        try:
            capitulo = Capitulo.objects.get(id=capitulo_id, ativo=True)
            modulos = Modulo.objects.filter(capitulo=capitulo, ativo=True).order_by('ordem')
            
            # Preparar dados dinâmicos para cada módulo
            modulos_com_stats = []
            for modulo in modulos:
                # Buscar aulas do módulo
                aulas_do_modulo = Aula.objects.filter(modulo=modulo, ativo=True)
                
                # Contar TOTAL DE PARTES (teoria + prática) disponíveis
                total_partes = 0
                for aula in aulas_do_modulo:
                    if aula.tem_teoria:
                        total_partes += 1
                    if aula.tem_exercicios:
                        total_partes += 1
                
                # Contar partes concluídas pelo usuário
                partes_concluidas = 0
                for aula in aulas_do_modulo:
                    conclusao = AulaConcluida.objects.filter(
                        usuario=request.user, 
                        aula=aula
                    ).first()
                    
                    if conclusao:
                        if aula.tem_teoria and conclusao.teoria_concluida:
                            partes_concluidas += 1
                        if aula.tem_exercicios and conclusao.pratica_concluida:
                            partes_concluidas += 1
                
                # Calcular progresso - SE NÃO HÁ PARTES, PROGRESSO É 0
                if total_partes > 0:
                    progresso_percentual = int((partes_concluidas / total_partes) * 100)
                else:
                    progresso_percentual = 0
                
                # XP total do módulo (soma do XP teórico + prático de todas as aulas)
                xp_total = 0
                for aula in aulas_do_modulo:
                    xp_total += aula.get_xp_total()
                
                # CALCULAR TEMPO TOTAL DO MÓDULO
                tempo_total_modulo = 0
                for aula in aulas_do_modulo:
                    tempo_aula = aula.tempo_total or 0
                    if isinstance(tempo_aula, int) and tempo_aula > 0:
                        tempo_total_modulo += tempo_aula
                
                modulos_com_stats.append({
                    'modulo': modulo,
                    'total_aulas': aulas_do_modulo.count(),  # Mantém contagem de aulas para referência
                    'total_partes': total_partes,  # Nova: total de partes (teoria + prática)
                    'partes_concluidas': partes_concluidas,  # Nova: partes concluídas
                    'progresso_percentual': progresso_percentual,
                    'xp_total': xp_total,
                    'tempo_total_modulo': tempo_total_modulo,
                })
            
            # Progresso geral do capítulo - CORREÇÃO
            total_modulos_capitulo = modulos.count()
            
            # Contar módulos onde TODAS as partes foram concluídas
            modulos_concluidos_capitulo = 0
            for mod_stat in modulos_com_stats:
                if mod_stat['total_partes'] > 0 and mod_stat['partes_concluidas'] == mod_stat['total_partes']:
                    modulos_concluidos_capitulo += 1
            
            if total_modulos_capitulo > 0:
                progresso_capitulo = int((modulos_concluidos_capitulo / total_modulos_capitulo) * 100)
            else:
                progresso_capitulo = 0
            
            # XP total do capítulo
            xp_total_capitulo = sum(m['xp_total'] for m in modulos_com_stats)
            
            context = {
                'capitulo': capitulo,
                'modulos_com_stats': modulos_com_stats,
                'progresso_capitulo': progresso_capitulo,
                'modulos_concluidos_capitulo': modulos_concluidos_capitulo,
                'total_modulos_capitulo': total_modulos_capitulo,
                'xp_total_capitulo': xp_total_capitulo,
            }
            return render(request, "Pyquest/modulos.html", context)
            
        except Capitulo.DoesNotExist:
            messages.error(request, "Capítulo não encontrado.")
            return redirect('conteudo')
    
    # Fallback se não houver capítulo específico (código similar corrigido)
    capitulo = Capitulo.objects.filter(ativo=True).first()
    if capitulo:
        modulos = Modulo.objects.filter(capitulo=capitulo, ativo=True).order_by('ordem')
        
        modulos_com_stats = []
        for modulo in modulos:
            aulas_do_modulo = Aula.objects.filter(modulo=modulo, ativo=True)
            
            # Contar TOTAL DE PARTES (teoria + prática) disponíveis
            total_partes = 0
            for aula in aulas_do_modulo:
                if aula.tem_teoria:
                    total_partes += 1
                if aula.tem_exercicios:
                    total_partes += 1
            
            # Contar partes concluídas pelo usuário
            partes_concluidas = 0
            for aula in aulas_do_modulo:
                conclusao = AulaConcluida.objects.filter(
                    usuario=request.user, 
                    aula=aula
                ).first()
                
                if conclusao:
                    if aula.tem_teoria and conclusao.teoria_concluida:
                        partes_concluidas += 1
                    if aula.tem_exercicios and conclusao.pratica_concluida:
                        partes_concluidas += 1
            
            if total_partes > 0:
                progresso_percentual = int((partes_concluidas / total_partes) * 100)
            else:
                progresso_percentual = 0
            
            xp_total = 0
            for aula in aulas_do_modulo:
                xp_total += aula.get_xp_total()
            
            tempo_total_modulo = 0
            for aula in aulas_do_modulo:
                tempo_aula = aula.tempo_total or 0
                if isinstance(tempo_aula, int) and tempo_aula > 0:
                    tempo_total_modulo += tempo_aula
            
            modulos_com_stats.append({
                'modulo': modulo,
                'total_aulas': aulas_do_modulo.count(),
                'total_partes': total_partes,
                'partes_concluidas': partes_concluidas,
                'progresso_percentual': progresso_percentual,
                'xp_total': xp_total,
                'tempo_total_modulo': tempo_total_modulo,
            })
        
        total_modulos_capitulo = modulos.count()
        
        modulos_concluidos_capitulo = 0
        for mod_stat in modulos_com_stats:
            if mod_stat['total_partes'] > 0 and mod_stat['partes_concluidas'] == mod_stat['total_partes']:
                modulos_concluidos_capitulo += 1
        
        progresso_capitulo = int((modulos_concluidos_capitulo / total_modulos_capitulo) * 100) if total_modulos_capitulo > 0 else 0
        xp_total_capitulo = sum(m['xp_total'] for m in modulos_com_stats)
        
        context = {
            'capitulo': capitulo,
            'modulos_com_stats': modulos_com_stats,
            'progresso_capitulo': progresso_capitulo,
            'modulos_concluidos_capitulo': modulos_concluidos_capitulo,
            'total_modulos_capitulo': total_modulos_capitulo,
            'xp_total_capitulo': xp_total_capitulo,
        }
    else:
        context = {
            'capitulo': None,
            'modulos_com_stats': [],
            'progresso_capitulo': 0,
            'modulos_concluidos_capitulo': 0,
            'total_modulos_capitulo': 0,
            'xp_total_capitulo': 0,
        }
    
    return render(request, "Pyquest/modulos.html", context)

# views.py - ATUALIZAR função tarefas
@login_required
def tarefas(request):
    modulo_id = request.GET.get('modulo_id')
    
    if not modulo_id:
        messages.error(request, "Módulo não especificado.")
        return redirect('conteudo')
    
    try:
        modulo = Modulo.objects.select_related('capitulo').get(id=modulo_id, ativo=True)
        
        # Buscar todas as aulas do módulo
        aulas = Aula.objects.filter(
            modulo=modulo, 
            ativo=True
        ).prefetch_related(
            'topicos',
            'questoes',
            'aulaconcluida_set'
        ).order_by('ordem')
        
        # Separar dados para template
        aulas_com_dados = []
        total_xp_teoria = 0
        total_xp_pratica = 0
        total_aulas_concluidas_teoria = 0
        total_aulas_concluidas_pratica = 0
        
        for aula in aulas:
            # Verificar conclusão separada
            aula_concluida_teoria = False
            aula_concluida_pratica = False
            revisao_feita_teoria = False
            revisao_feita_pratica = False
            
            conclusao = AulaConcluida.objects.filter(
                usuario=request.user, 
                aula=aula
            ).first()
            
            if conclusao:
                aula_concluida_teoria = conclusao.teoria_concluida
                aula_concluida_pratica = conclusao.pratica_concluida
                revisao_feita_teoria = conclusao.revisao_feita_teoria
                revisao_feita_pratica = conclusao.revisao_feita_pratica
            
            # Contar tópicos e questões
            total_topicos = aula.topicos.count()
            total_questoes = aula.questoes.count()
            
            # Calcular XP
            xp_teoria = aula.xp_teoria or 0
            xp_pratica = aula.xp_pratica or 0
            
            total_xp_teoria += xp_teoria
            total_xp_pratica += xp_pratica
            
            # Verificar conclusão para estatísticas
            if aula_concluida_teoria and total_topicos > 0:
                total_aulas_concluidas_teoria += 1
            if aula_concluida_pratica and total_questoes > 0:
                total_aulas_concluidas_pratica += 1
            
            aulas_com_dados.append({
                'aula': aula,
                'concluida_teoria': aula_concluida_teoria,
                'concluida_pratica': aula_concluida_pratica,
                'revisao_feita_teoria': revisao_feita_teoria,
                'revisao_feita_pratica': revisao_feita_pratica,
                'total_topicos': total_topicos,
                'total_questoes': total_questoes,
                'xp_teoria': xp_teoria,
                'xp_pratica': xp_pratica,
                'tempo_teoria': aula.tempo_teoria or 0,
                'tempo_pratica': aula.tempo_pratica or 0,
            })
        
        # Calcular totais
        total_aulas_teoria = len([a for a in aulas_com_dados if a['total_topicos'] > 0])
        total_aulas_pratica = len([a for a in aulas_com_dados if a['total_questoes'] > 0])
        
        # Calcular progresso percentual
        progresso_teoria = int((total_aulas_concluidas_teoria / total_aulas_teoria * 100)) if total_aulas_teoria > 0 else 0
        progresso_pratica = int((total_aulas_concluidas_pratica / total_aulas_pratica * 100)) if total_aulas_pratica > 0 else 0
        
        # Progresso geral do módulo
        total_aulas_geral = len(aulas_com_dados)
        total_aulas_concluidas_geral = len([a for a in aulas_com_dados if a['concluida_teoria'] and a['concluida_pratica']])
        progresso_geral = int((total_aulas_concluidas_geral / total_aulas_geral * 100)) if total_aulas_geral > 0 else 0
        
        context = {
            'modulo': modulo,
            'aulas_com_dados': aulas_com_dados,
            'total_aulas_teoria': total_aulas_teoria,
            'total_aulas_pratica': total_aulas_pratica,
            'total_aulas_concluidas_teoria': total_aulas_concluidas_teoria,
            'total_aulas_concluidas_pratica': total_aulas_concluidas_pratica,
            'progresso_teoria': progresso_teoria,
            'progresso_pratica': progresso_pratica,
            'progresso_geral': progresso_geral,
            'total_xp_teoria': total_xp_teoria,
            'total_xp_pratica': total_xp_pratica,
            'total_xp_geral': total_xp_teoria + total_xp_pratica,
        }
        
        return render(request, "Pyquest/tarefas.html", context)
        
    except Modulo.DoesNotExist:
        messages.error(request, "Módulo não encontrado.")
        return redirect('conteudo')


@login_required
def teoria(request):
    aula_id = request.GET.get('aula_id')
    
    if not aula_id:
        messages.error(request, "Aula não especificada.")
        return redirect('tarefas')
    
    try:
        # Buscar a aula com todos os tópicos teóricos
        aula = Aula.objects.select_related('modulo', 'modulo__capitulo').get(
            id=aula_id, 
            ativo=True
        )
        
        # Buscar todos os tópicos teóricos da aula, ordenados
        topicos = TopicoTeorico.objects.filter(aula=aula).order_by('ordem')
        
        # Verificar se o usuário já concluiu a parte teórica (apenas para mostrar botão diferente)
        aula_concluida = AulaConcluida.objects.filter(
            usuario=request.user,
            aula=aula,
            teoria_concluida=True
        ).exists()
        
        context = {
            'aula': aula,
            'topicos': topicos,
            'aula_concluida': aula_concluida,  # Apenas para mostrar botão diferente
            'total_topicos': topicos.count(),
        }
        
        return render(request, "Pyquest/teoria.html", context)
        
    except Aula.DoesNotExist:
        messages.error(request, "Aula não encontrada.")
        return redirect('tarefas')


# No views.py, atualize a função marcar_aula_concluida
@login_required
@require_POST
def marcar_aula_concluida(request):
    try:
        data = json.loads(request.body)
        aula_id = data.get('aula_id')
        tipo = data.get('tipo')  # 'teoria' ou 'pratica'
        is_revisao = data.get('is_revisao', False)
        tempo_estudado = data.get('tempo_estudado', 0)
        
        print(f"🎯 Marcando aula como concluída - Aula: {aula_id}, Tipo: {tipo}, Revisão: {is_revisao}")
        
        aula = Aula.objects.get(id=aula_id, ativo=True)
        
        # Buscar ou criar registro de conclusão
        aula_concluida, created = AulaConcluida.objects.get_or_create(
            usuario=request.user,
            aula=aula
        )
        
        xp_ganho = 0
        redirect_url = f"/tarefas/?modulo_id={aula.modulo.id}"
        mensagem = ""
        niveis_ganhos = 0
        
        if is_revisao:
            # LÓGICA DE REVISÃO - XP REDUZIDO (SEMPRE DISPONÍVEL)
            if tipo == 'teoria':
                xp_ganho = 5
                mensagem = "Revisão teórica concluída! +5 XP"
                
            elif tipo == 'pratica':
                xp_ganho = 5
                mensagem = "Revisão prática concluída! +5 XP"
                
        else:
            # LÓGICA ORIGINAL (primeira conclusão)
            if tipo == 'teoria' and not aula_concluida.teoria_concluida:
                aula_concluida.teoria_concluida = True
                aula_concluida.data_conclusao_teoria = timezone.now()
                aula_concluida.xp_teoria_ganho = aula.xp_teoria
                xp_ganho = aula.xp_teoria
                mensagem = f"Aula teórica concluída! +{aula.xp_teoria} XP"
                
            elif tipo == 'pratica' and not aula_concluida.pratica_concluida:
                aula_concluida.pratica_concluida = True
                aula_concluida.data_conclusao_pratica = timezone.now()
                aula_concluida.xp_pratica_ganho = aula.xp_pratica
                xp_ganho = aula.xp_pratica
                mensagem = f"Aula prática concluída! +{aula.xp_pratica} XP"
            else:
                # Se já estava concluído mas não é revisão, tratar como revisão
                xp_ganho = 5
                mensagem = "Revisão concluída! +5 XP"
                is_revisao = True
        
        # Se ganhou XP, processar
        if xp_ganho > 0:
            # Para revisões, não precisamos salvar nada no modelo AulaConcluida
            # pois queremos permitir revisões ilimitadas
            if not is_revisao:
                aula_concluida.save()
            
            # Adicionar XP ao perfil
            perfil = request.user.perfil
            niveis_ganhos = perfil.adicionar_xp(xp_ganho)
            
            # Adicionar mensagem de nível se ganhou algum
            if niveis_ganhos > 0:
                mensagem += f" 🎉 Subiu para o nível {perfil.nivel}!"
            
            # Registrar atividade
            tipo_atividade = "teoria" if tipo == 'teoria' else "prática"
            if is_revisao:
                atividade_titulo = f"Revisão de {tipo_atividade}: {aula.titulo_aula}"
            else:
                atividade_titulo = f"Aula de {tipo_atividade} concluída: {aula.titulo_aula}"
                
            Atividade.objects.create(
                user=request.user,
                aula=aula,
                titulo=atividade_titulo,
                xp_ganho=xp_ganho
            )
            
            # Registrar atividade para o streak
            perfil.verificar_e_atualizar_streak()
        
        print(f"✅ Aula marcada como concluída - XP: {xp_ganho}, Mensagem: {mensagem}")
        
        return JsonResponse({
            'success': True, 
            'xp_ganho': xp_ganho,
            'niveis_ganhos': niveis_ganhos,
            'nivel_atual': request.user.perfil.nivel,
            'redirect_url': redirect_url,
            'mensagem': mensagem,
            'is_revisao': is_revisao
        })
        
    except Aula.DoesNotExist:
        print(f"❌ Aula não encontrada: {aula_id}")
        return JsonResponse({'success': False, 'error': 'Aula não encontrada'})
    except Exception as e:
        print(f"❌ Erro ao marcar aula como concluída: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)})

# ---------- PÁGINAS EXISTENTES ---------- #





@receiver(post_save, sender=Perfil)
def verificar_conquistas_perfil(sender, instance, **kwargs):
    """Verifica conquistas relacionadas a XP e nível"""
    ConquistaManager.verificar_conquistas_usuario(instance.user, 'xp_total')
    ConquistaManager.verificar_conquistas_usuario(instance.user, 'nivel_atingido')

@receiver(post_save, sender=AulaConcluida)
def verificar_conquistas_aulas(sender, instance, created, **kwargs):
    """Verifica conquistas relacionadas a aulas concluídas"""
    if created and instance.teoria_concluida and instance.pratica_concluida:
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

@receiver(post_save, sender=Progresso)
def verificar_conquistas_sequencia(sender, instance, **kwargs):
    """Verifica conquistas relacionadas a sequência de dias"""
    ConquistaManager.verificar_conquistas_usuario(instance.user, 'sequencia_dias')

# views.py
@csrf_exempt
def atualizar_vida(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            aula_id = data.get('aula_id')
            vida_perdida = data.get('vida_perdida')
            vidas_restantes = data.get('vidas_restantes')
            question_id = data.get('question_id')
            
            # Aqui você salva no banco de dados
            # Exemplo: atualizar perfil do usuário
            perfil = request.perfil
            perfil.vidas = vidas_restantes
            perfil.save()
            
            return JsonResponse({'success': True, 'vidas_restantes': vidas_restantes})
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Método não permitido'})


# ===== VIEWS DO SISTEMA DE STREAK =====

@login_required
@require_POST
def registrar_atividade_streak(request):
    """Registra uma atividade do usuário e atualiza o streak"""
    try:
        data = json.loads(request.body)
        tipo_atividade = data.get('tipo', 'questao')
        xp_base = data.get('xp_base', 0)
        
        print(f"🎯 Registrar atividade - Tipo: {tipo_atividade}, XP: {xp_base}")
        
        perfil = request.user.perfil
        agora = timezone.now()
        
        # VERIFICAR RESET DIÁRIO ANTES DE TUDO
        perfil.verificar_reset_diario()
        
        # MARCAR QUE JÁ FEZ ATIVIDADE HOJE
        perfil.ja_fez_atividade_hoje = True
        
        # Se nunca teve atividade OU streak é 0, iniciar streak em 1
        if not perfil.ultima_atividade or perfil.sequencia == 0:
            perfil.sequencia = 1
            perfil.ultima_atividade = agora
            perfil.save()
            print("🎯 Primeira atividade - Streak iniciado: 1")
            return JsonResponse({
                'success': True,
                'streak_anterior': 0,
                'streak_atual': 1,
                'streak_maximo': perfil.sequencia_maxima,
                'streak_zerado': False,
                'streak_aumentado': True,
                'ja_fez_atividade_hoje': True,
            })
        
        # Verificar diferença em dias
        data_ultima = perfil.ultima_atividade.date()
        data_hoje = agora.date()
        dias_diferenca = (data_hoje - data_ultima).days
        
        print(f"📅 Última atividade: {data_ultima}")
        print(f"📅 Hoje: {data_hoje}")
        print(f"📅 Diferença em dias: {dias_diferenca}")
        
        streak_zerado = False
        streak_aumentado = False
        streak_anterior = perfil.sequencia
        
        if dias_diferenca == 0:
            # Já teve atividade HOJE - apenas atualiza hora, NÃO aumenta streak
            print("✅ Já teve atividade hoje - streak mantido")
            perfil.ultima_atividade = agora
            perfil.save()
            
        elif dias_diferenca == 1:
            # Última atividade foi ONTEM - AUMENTAR STREAK
            print("🎯 Última atividade foi ontem - AUMENTANDO STREAK")
            perfil.sequencia += 1
            perfil.ultima_atividade = agora
            streak_aumentado = True
            print(f"📈 Streak aumentado: {streak_anterior} → {perfil.sequencia}")
            perfil.save()
            
        else:
            # Última atividade foi ANTES de ontem - ZERAR STREAK
            print(f"💀 Última atividade foi há {dias_diferenca} dias - ZERANDO STREAK")
            
            # Atualizar streak máximo antes de zerar
            if streak_anterior > perfil.sequencia_maxima:
                perfil.sequencia_maxima = streak_anterior
            
            # Zerar streak e começar de novo
            perfil.sequencia = 1
            perfil.ultima_atividade = agora
            streak_zerado = True
            print(f"🔄 Streak zerado: {streak_anterior} → 1")
            perfil.save()
        
        # Atualizar streak máximo se necessário
        if perfil.sequencia > perfil.sequencia_maxima:
            perfil.sequencia_maxima = perfil.sequencia
            perfil.save()
        
        return JsonResponse({
            'success': True,
            'streak_anterior': streak_anterior,
            'streak_atual': perfil.sequencia,
            'streak_maximo': perfil.sequencia_maxima,
            'streak_zerado': streak_zerado,
            'streak_aumentado': streak_aumentado,
            'bonus_streak': f"+{int(perfil.get_bonus_streak() * 100)}%",
            'xp_base': xp_base,
            'xp_bonus': int(xp_base * perfil.get_bonus_streak()),
            'xp_total': xp_base + int(xp_base * perfil.get_bonus_streak()),
            'level_up': False,
            'nivel_atual': perfil.nivel,
            'xp_atual': perfil.xp,
            'conquistas_desbloqueadas': [],
            'tempo_restante': perfil.get_tempo_restante_streak(),
            'ja_fez_atividade_hoje': perfil.ja_fez_atividade_hoje,  # IMPORTANTE
        })
        
    except Exception as e:
        print(f"❌ Erro em registrar_atividade_streak: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)})
    
@login_required
def api_streak_usuario(request):
    """API para obter dados de streak do usuário"""
    try:
        perfil = request.user.perfil
        return JsonResponse({
            'success': True,
            'streak_atual': perfil.sequencia,
            'streak_maximo': perfil.sequencia_maxima,
            'bonus_streak': perfil.get_bonus_streak() * 100,
            'ultima_atividade': perfil.ultima_atividade.isoformat() if perfil.ultima_atividade else None,
            'tempo_restante': perfil.get_tempo_restante_streak(),
            'streak_quebrado': perfil.verificar_streak_quebrado()
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

def verificar_conquistas_streak(usuario, streak_atual):
    """Verifica e concede conquistas baseadas em streak"""
    conquistas_streak = {
        3: "🔥 Iniciante Consistente",
        7: "🔥💪 Streak Semanal", 
        14: "🔥🌟 Mestre da Constância",
        30: "🔥💎 Lenda do Mês",
        60: "🔥🚀 Mestre Supremo",
        100: "🔥👑 Deus da Persistência"
    }
    
    conquistas_desbloqueadas = []
    
    for dias, titulo in conquistas_streak.items():
        if streak_atual >= dias:
            try:
                conquista, created = Conquista.objects.get_or_create(
                    titulo=titulo,
                    defaults={
                        'descricao': f'Mantenha um streak de {dias} dias consecutivos',
                        'raridade': 'raro' if dias <= 14 else 'épico' if dias <= 60 else 'lendário',
                        'categoria': 'streak',
                        'icone': f'conquistas/streak_{dias}.png'
                    }
                )
                
                if conquista not in usuario.conquistas.all():
                    usuario.conquistas.add(conquista)
                    conquistas_desbloqueadas.append(titulo)
                    print(f"🏆 Conquista desbloqueada: {titulo}")
                    
            except Exception as e:
                print(f"⚠️ Erro ao criar/conceder conquista {titulo}: {e}")
    
    return conquistas_desbloqueadas


@csrf_exempt
@require_POST
def registrar_xp_revisao(request):
    try:
        data = json.loads(request.body)
        aula_id = data.get('aula_id')
        xp_revisao = data.get('xp_revisao', 5)
        
        # Buscar o perfil do usuário
        perfil = request.user.perfil
        
        # Adicionar XP da revisão
        perfil.xp += xp_revisao
        perfil.save()
        
        # Registrar na tabela de atividades (opcional)
        # Atividade.objects.create(
        #     usuario=request.user,
        #     tipo='revisao',
        #     xp_ganho=xp_revisao,
        #     aula_id=aula_id
        # )
        
        return JsonResponse({
            'success': True,
            'xp_total': perfil.xp,
            'xp_revisao': xp_revisao,
            'message': f'XP de revisão registrado com sucesso!'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })



@csrf_exempt
def salvar_tempo_pratica(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            aula_id = data.get('aula_id')
            tempo_segundos = int(data.get('tempo_segundos', 0))
            
            print(f"📊 Salvando tempo prática DIÁRIO: {tempo_segundos} segundos para aula {aula_id}")
            
            user = request.user
            aula = Aula.objects.get(id=aula_id)
            
            # Salvar no TempoEstudoDiario (tempo diário)
            hoje = timezone.now().date()
            tempo_diario, created = TempoEstudoDiario.objects.get_or_create(
                user=user,
                data=hoje,
                defaults={'tempo_segundos': tempo_segundos}
            )
            
            if not created:
                tempo_diario.tempo_segundos += tempo_segundos
                tempo_diario.save()
            
            # Também salvar no TempoEstudo (para compatibilidade)
            tempo_estudo, created = TempoEstudo.objects.get_or_create(
                user=user,
                aula=aula,
                tipo='pratica',
                data=hoje,
                defaults={'tempo_segundos': tempo_segundos}
            )
            
            if not created:
                tempo_estudo.tempo_segundos += tempo_segundos
                tempo_estudo.save()
            
            # Atualizar perfil (para compatibilidade)
            perfil = user.perfil
            tempo_anterior = perfil.tempo_total_estudo
            perfil.tempo_total_estudo += tempo_segundos
            perfil.save()
            
            # Formatar tempo diário para resposta
            tempo_total_hoje = tempo_diario.tempo_segundos
            horas_hoje = tempo_total_hoje // 3600
            minutos_hoje = (tempo_total_hoje % 3600) // 60
            segundos_hoje = tempo_total_hoje % 60
            
            if horas_hoje > 0:
                tempo_formatado = f"{horas_hoje:02d}:{minutos_hoje:02d}:{segundos_hoje:02d}"
            else:
                tempo_formatado = f"{minutos_hoje:02d}:{segundos_hoje:02d}"
            
            print(f"✅ Tempo prática salvo! Total hoje: {tempo_diario.tempo_segundos} segundos")
            print(f"   Anterior: {tempo_anterior}, Atual: {perfil.tempo_total_estudo}")
            
            return JsonResponse({
                'success': True, 
                'tempo_salvo': tempo_segundos,
                'tempo_total_hoje': tempo_diario.tempo_segundos,
                'tempo_total_formatado': tempo_formatado,
                'tempo_total_geral': perfil.tempo_total_estudo  # CORREÇÃO AQUI: 'estudo' em vez de 'estudy'
            })
            
        except Exception as e:
            print(f"❌ Erro ao salvar tempo prática: {e}")
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Método não permitido'})

@csrf_exempt
def salvar_tempo_teoria(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            aula_id = data.get('aula_id')
            tempo_segundos = int(data.get('tempo_segundos', 0))
            
            print(f"📊 Salvando tempo teoria DIÁRIO: {tempo_segundos} segundos para aula {aula_id}")
            
            user = request.user
            aula = Aula.objects.get(id=aula_id)
            
            # Salvar no TempoEstudoDiario (tempo diário)
            hoje = timezone.now().date()
            tempo_diario, created = TempoEstudoDiario.objects.get_or_create(
                user=user,
                data=hoje,
                defaults={'tempo_segundos': tempo_segundos}
            )
            
            if not created:
                tempo_diario.tempo_segundos += tempo_segundos
                tempo_diario.save()
            
            # Também salvar no TempoEstudo (para compatibilidade)
            tempo_estudo, created = TempoEstudo.objects.get_or_create(
                user=user,
                aula=aula,
                tipo='teoria',
                data=hoje,
                defaults={'tempo_segundos': tempo_segundos}
            )
            
            if not created:
                tempo_estudo.tempo_segundos += tempo_segundos
                tempo_estudo.save()
            
            # Atualizar perfil (para compatibilidade)
            perfil = user.perfil
            tempo_anterior = perfil.tempo_total_estudo
            perfil.tempo_total_estudo += tempo_segundos
            perfil.save()
            
            # Formatar tempo diário para resposta
            tempo_total_hoje = tempo_diario.tempo_segundos
            horas_hoje = tempo_total_hoje // 3600
            minutos_hoje = (tempo_total_hoje % 3600) // 60
            segundos_hoje = tempo_total_hoje % 60
            
            if horas_hoje > 0:
                tempo_formatado = f"{horas_hoje:02d}:{minutos_hoje:02d}:{segundos_hoje:02d}"
            else:
                tempo_formatado = f"{minutos_hoje:02d}:{segundos_hoje:02d}"
            
            print(f"✅ Tempo teoria salvo! Total hoje: {tempo_diario.tempo_segundos} segundos")
            print(f"   Anterior: {tempo_anterior}, Atual: {perfil.tempo_total_estudo}")
            
            return JsonResponse({
                'success': True, 
                'tempo_salvo': tempo_segundos,
                'tempo_total_hoje': tempo_diario.tempo_segundos,
                'tempo_total_formatado': tempo_formatado,
                'tempo_total_geral': perfil.tempo_total_estudo  # CORREÇÃO AQUI: 'estudo' em vez de 'estudy'
            })
            
        except Exception as e:
            print(f"❌ Erro ao salvar tempo teoria: {e}")
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Método não permitido'})

def api_tempo_estudo(request):
    """API para obter dados de tempo de estudo para a home"""
    if request.user.is_authenticated:
        try:
            perfil = Perfil.objects.get(user=request.user)
            
            # Tempo total formatado
            tempo_total_segundos = perfil.tempo_total_estudo
            horas = tempo_total_segundos // 3600
            minutos = (tempo_total_segundos % 3600) // 60
            tempo_formatado = f"{horas:02d}:{minutos:02d}"
            
            # Tempo de hoje
            hoje = timezone.now().date()
            tempo_hoje = TempoEstudo.objects.filter(
                user=request.user, 
                data=hoje
            ).aggregate(total=Sum('tempo_segundos'))['total'] or 0
            
            # Tempo de ontem
            ontem = hoje - timedelta(days=1)
            tempo_ontem = TempoEstudo.objects.filter(
                user=request.user, 
                data=ontem
            ).aggregate(total=Sum('tempo_segundos'))['total'] or 0
            
            # Diferença em relação a ontem
            dif_tempo = tempo_hoje - tempo_ontem
            dif_formatada = f"+{dif_tempo//60}min" if dif_tempo > 0 else f"{dif_tempo//60}min"
            
            return JsonResponse({
                'success': True,
                'tempo_total': tempo_formatado,
                'tempo_hoje_minutos': tempo_hoje // 60,
                'diferenca_ontem': dif_formatada,
                'tempo_total_segundos': tempo_total_segundos
            })
            
        except Perfil.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Perfil não encontrado'})
    
    return JsonResponse({'success': False, 'error': 'Usuário não autenticado'})
@csrf_exempt
def testar_tempo(request):
    """View temporária para testar o salvamento de tempo"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            segundos = data.get('segundos', 60)
            
            perfil = Perfil.objects.get(user=request.user)
            perfil.tempo_total_estudo += segundos
            perfil.save()
            
            return JsonResponse({
                'success': True, 
                'tempo_anterior': perfil.tempo_total_estudo - segundos,
                'tempo_atual': perfil.tempo_total_estudo
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Método POST requerido'})
def debug_tempo(request):
    """View para debug do sistema de tempo"""
    if request.user.is_authenticated:
        try:
            perfil = Perfil.objects.get(user=request.user)
            tempo_estudos = TempoEstudo.objects.filter(user=request.user)
            
            # CORREÇÃO: Formatação correta do tempo
            tempo_total_segundos = perfil.tempo_total_estudo
            minutos_totais = tempo_total_segundos // 60
            segundos_restantes = tempo_total_segundos % 60
            horas = minutos_totais // 60
            minutos = minutos_totais % 60
            
            debug_info = {
                'perfil_id': perfil.id,
                'user': perfil.user.username,
                'tempo_total_estudo': tempo_total_segundos,
                'tempo_formatado_correto': f"{horas:02d}:{minutos:02d}:{segundos_restantes:02d}",
                'tempo_formatado_minutos': f"{minutos_totais:02d}:{segundos_restantes:02d}",
                'total_registros_tempo': tempo_estudos.count(),
                'registros': list(tempo_estudos.values('aula__titulo_aula', 'tipo', 'tempo_segundos', 'data'))
            }
            
            return JsonResponse({'success': True, 'debug': debug_info})
            
        except Perfil.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Perfil não encontrado'})
    
    return JsonResponse({'success': False, 'error': 'Usuário não autenticado'})

@login_required
def pratica(request):
    aula_id = request.GET.get('aula_id')
    
    if not aula_id:
        messages.error(request, "Aula não especificada.")
        return redirect('tarefas')
    
    try:
        # Buscar a aula com todas as questões e relacionamentos
        aula = Aula.objects.select_related('modulo', 'modulo__capitulo').prefetch_related(
            'questoes__opcoes',
            'questoes__dicas'
        ).get(
            id=aula_id, 
            ativo=True
        )
        
        # Verificar se o usuário já concluiu a parte prática
        aula_concluida = AulaConcluida.objects.filter(
            usuario=request.user,
            aula=aula,
            pratica_concluida=True
        ).exists()
        
        # Atualizar vidas do perfil
        perfil = request.user.perfil
        perfil.regenerar_vidas()
        
        # Buscar ou criar tentativa atual
        tentativa, created = TentativaPratica.objects.get_or_create(
            usuario=request.user,
            aula=aula,
            defaults={
                'vidas_restantes': perfil.vidas,
                'vidas_usadas': 0
            }
        )
        
        # Sincronizar vidas com perfil
        if tentativa.vidas_restantes != perfil.vidas:
            tentativa.vidas_restantes = perfil.vidas
            tentativa.save()
        
        # ✅ CORREÇÃO: Preparar dados para o template INCLUINDO saida_esperada
        questions_data = []
        for questao in aula.questoes.all().order_by('ordem'):
            questao_data = {
                'id': questao.id,
                'tipo': questao.tipo,
                'enunciado': questao.enunciado,
                'descricao': questao.descricao,
                'xp': questao.xp,
                'codigo_inicial': questao.codigo_inicial,
                'saida_esperada': questao.saida_esperada,  # ✅ AGORA INCLUÍDO
                'opcoes': [],
                'dicas': []
            }
            
            # Adicionar opções para múltipla escolha
            if questao.tipo == 'multiple-choice':
                for opcao in questao.opcoes.all().order_by('ordem'):
                    questao_data['opcoes'].append({
                        'id': opcao.id,
                        'texto': opcao.texto,
                        'correta': opcao.correta
                    })
            
            # Adicionar dicas
            for dica in questao.dicas.all().order_by('ordem'):
                questao_data['dicas'].append(dica.texto)
            
            questions_data.append(questao_data)
        
        context = {
            'aula': aula,
            'aula_concluida': aula_concluida,
            'questions_data': questions_data,
            'questoes_json': json.dumps(questions_data, ensure_ascii=False),
            'vidas_restantes': tentativa.vidas_restantes,
            'max_vidas': perfil.max_vidas,
            'pratica_concluida': aula_concluida,  # Para controle de revisão
        }
        
        return render(request, "Pyquest/pratica.html", context)
        
    except Aula.DoesNotExist:
        messages.error(request, "Aula não encontrada.")
        return redirect('tarefas')

@login_required
@require_POST
def usar_vida_pratica(request):
    """Usa uma vida durante a prática - VERSÃO CORRIGIDA"""
    try:
        data = json.loads(request.body)
        aula_id = data.get('aula_id')
        
        # Usar a API centralizada de vidas
        response = api_usar_vida(request)
        response_data = json.loads(response.content)
        
        if response_data['success'] and aula_id:
            # Atualizar tentativa específica da aula
            try:
                aula = Aula.objects.get(id=aula_id)
                tentativa, created = TentativaPratica.objects.get_or_create(
                    usuario=request.user,
                    aula=aula
                )
                tentativa.vidas_usadas += 1
                tentativa.vidas_restantes = response_data['vidas_restantes']
                tentativa.save()
            except Aula.DoesNotExist:
                pass
        
        return JsonResponse(response_data)
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_POST
def finalizar_pratica(request):
    """Finaliza a prática e calcula recompensas"""
    try:
        data = json.loads(request.body)
        aula_id = data.get('aula_id')
        xp_total = data.get('xp_total', 0)
        vidas_restantes = data.get('vidas_restantes', 0)
        
        aula = get_object_or_404(Aula, id=aula_id)
        perfil = request.user.perfil
        
        # Buscar tentativa
        tentativa = TentativaPratica.objects.get(
            usuario=request.user,
            aula=aula
        )
        
        # Atualizar tentativa
        tentativa.concluida = True
        tentativa.xp_ganho = xp_total
        tentativa.vidas_restantes = vidas_restantes
        tentativa.save()
        
        # Bônus por vidas restantes
        bonus_vidas = 0
        if vidas_restantes > 0:
            bonus_vidas = vidas_restantes * 5  # 5 XP por vida restante
        
        xp_final = xp_total + bonus_vidas
        
        # Marcar aula como concluída se não estava
        aula_concluida, created = AulaConcluida.objects.get_or_create(
            usuario=request.user,
            aula=aula
        )
        
        if not aula_concluida.pratica_concluida:
            aula_concluida.pratica_concluida = True
            aula_concluida.data_conclusao_pratica = timezone.now()
            aula_concluida.xp_pratica_ganho = xp_final
            aula_concluida.save()
            
            # Atualizar perfil
            perfil.xp += xp_final
            perfil.save()
            
            # Registrar atividade
            Atividade.objects.create(
                user=request.user,
                aula=aula,
                titulo=f"Prática concluída: {aula.titulo_aula}",
                xp_ganho=xp_final
            )
        
        return JsonResponse({
            'success': True,
            'xp_total': xp_final,
            'bonus_vidas': bonus_vidas,
            'vidas_restantes': vidas_restantes,
            'redirect_url': f"/tarefas/?modulo_id={aula.modulo.id}"
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_POST
def salvar_progresso_questao(request):
    """Salva o progresso individual de cada questão"""
    try:
        data = json.loads(request.body)
        questao_id = data.get('questao_id')
        concluida = data.get('concluida', False)
        xp_ganho = data.get('xp_ganho', 0)
        tempo_gasto = data.get('tempo_gasto', 0)
        
        questao = get_object_or_404(Questao, id=questao_id)
        
        # Buscar ou criar registro de progresso da questão
        # (Você pode criar um modelo ProgressoQuestao se quiser rastrear individualmente)
        
        # Atualizar perfil do usuário se ganhou XP
        if concluida and xp_ganho > 0:
            perfil = request.user.perfil
            perfil.xp += xp_ganho
            
            # Verificar se subiu de nível
            XP_POR_NIVEL = 100
            while perfil.xp >= XP_POR_NIVEL:
                perfil.nivel += 1
                perfil.xp -= XP_POR_NIVEL
            
            perfil.save()
            
            # Registrar atividade
            Atividade.objects.create(
                user=request.user,
                aula=questao.aula,
                titulo=f"Questão concluída: {questao.enunciado[:50]}...",
                xp_ganho=xp_ganho
            )
        
        return JsonResponse({
            'success': True,
            'xp_total': request.user.perfil.xp,
            'nivel': request.user.perfil.nivel,
            'xp_ganho': xp_ganho
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@csrf_exempt
def iniciar_sessao_estudo(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        aula_id = data.get('aula_id')
        tipo = data.get('tipo', 'teoria')
        
        # Finalizar qualquer sessão ativa anterior
        sessoes_ativas = SessaoEstudo.objects.filter(user=request.user, ativa=True)
        for sessao in sessoes_ativas:
            sessao.finalizar_sessao()
        
        # Iniciar nova sessão
        from .models import Aula
        aula = Aula.objects.get(id=aula_id) if aula_id else None
        
        sessao = SessaoEstudo.objects.create(
            user=request.user,
            aula=aula,
            tipo=tipo
        )
        
        return JsonResponse({'sessao_id': sessao.id, 'status': 'sessao_iniciada'})

@csrf_exempt
def finalizar_sessao_estudo(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        sessao_id = data.get('sessao_id')
        
        try:
            sessao = SessaoEstudo.objects.get(id=sessao_id, user=request.user, ativa=True)
            sessao.finalizar_sessao()
            
            perfil = request.user.perfil
            return JsonResponse({
                'status': 'sessao_finalizada',
                'tempo_total': sessao.tempo_total,
                'tempo_total_formatado': perfil.tempo_estudo_formatado()
            })
        except SessaoEstudo.DoesNotExist:
            return JsonResponse({'status': 'sessao_nao_encontrada'})
        
def verificar_sessao_ativa(request):
    sessao_ativa = SessaoEstudo.objects.filter(user=request.user, ativa=True).first()
    
    if sessao_ativa:
        return JsonResponse({
            'ativa': True,
            'sessao_id': sessao_ativa.id,
            'inicio': sessao_ativa.inicio.isoformat()
        })
    else:
        return JsonResponse({'ativa': False})





@csrf_exempt
@login_required
def salvar_tempo_estudo(request):
    """Salva o tempo de estudo do timer da home - VERSÃO DIÁRIA"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            tempo_segundos = int(data.get('tempo_segundos', 0))
            tipo = data.get('tipo', 'estudo_geral')
            
            print(f"⏱️ Salvando tempo de estudo DIÁRIO: {tempo_segundos} segundos")
            
            if tempo_segundos <= 0:
                return JsonResponse({'success': False, 'error': 'Tempo inválido'})
            
            # Salvar no TempoEstudoDiario
            hoje = timezone.now().date()
            tempo_diario, created = TempoEstudoDiario.objects.get_or_create(
                user=request.user,
                data=hoje,
                defaults={'tempo_segundos': tempo_segundos}
            )
            
            if not created:
                tempo_diario.tempo_segundos += tempo_segundos
                tempo_diario.save()
            
            # Também atualizar o perfil (para compatibilidade)
            perfil = request.user.perfil
            perfil.tempo_total_estudo += tempo_segundos
            perfil.save()
            
            # Registrar atividade
            Atividade.objects.create(
                user=request.user,
                titulo=f"Estudo geral: {tempo_segundos // 60} minutos",
                xp_ganho=0
            )
            
            # Formatar tempo para resposta
            tempo_total_hoje = tempo_diario.tempo_segundos
            horas = tempo_total_hoje // 3600
            minutos = (tempo_total_hoje % 3600) // 60
            segundos = tempo_total_hoje % 60
            
            if horas > 0:
                tempo_formatado = f"{horas:02d}:{minutos:02d}:{segundos:02d}"
            else:
                tempo_formatado = f"{minutos:02d}:{segundos:02d}"
            
            print(f"✅ Tempo diário salvo! Total hoje: {tempo_diario.tempo_segundos} segundos")
            
            return JsonResponse({
                'success': True, 
                'tempo_salvo': tempo_segundos,
                'tempo_total_hoje': tempo_diario.tempo_segundos,
                'tempo_total_formatado': tempo_formatado,
                'tempo_total_geral': perfil.tempo_total_estudo  # CORREÇÃO AQUI
            })
            
        except Exception as e:
            print(f"❌ Erro ao salvar tempo estudo diário: {e}")
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Método não permitido'})

@csrf_exempt
@login_required  
def testar_tempo(request):
    """View para testar o salvamento de tempo (apenas desenvolvimento)"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            segundos = data.get('segundos', 60)
            
            perfil = Perfil.objects.get(user=request.user)
            perfil.tempo_total_estudo += segundos
            perfil.save()
            
            return JsonResponse({
                'success': True, 
                'tempo_anterior': perfil.tempo_total_estudo - segundos,
                'tempo_atual': perfil.tempo_total_estudo
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Método POST requerido'})

# views.py
@login_required
def forcar_verificacao_conquistas(request):
    """View para forçar a verificação de todas as conquistas (para testes)"""
    conquistas_desbloqueadas = ConquistaManager.verificar_todas_conquistas(request.user)
    
    if conquistas_desbloqueadas:
        messages.success(request, f"{len(conquistas_desbloqueadas)} conquistas verificadas!")
    else:
        messages.info(request, "Nenhuma nova conquista desbloqueada.")
    
    return redirect('perfil')

@login_required
def corrigir_conquistas(request):
    """Corrige o tipo_evento das conquistas existentes"""
    from .models import Conquista
    
    # Mapeamento de números para códigos
    correcoes = {
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
    
    conquistas_corrigidas = 0
    for conquista in Conquista.objects.all():
        if conquista.tipo_evento.isdigit():
            codigo_correto = correcoes.get(conquista.tipo_evento)
            if codigo_correto:
                print(f"🔧 Corrigindo {conquista.titulo}: {conquista.tipo_evento} -> {codigo_correto}")
                conquista.tipo_evento = codigo_correto
                conquista.save()
                conquistas_corrigidas += 1
    
    messages.success(request, f"{conquistas_corrigidas} conquistas corrigidas!")
    return redirect('perfil')


@login_required
def dashboard(request):
    perfil = request.user.perfil
    perfil.verificar_streak_automatico()
    
    context = {
        'perfil': perfil,
        'current_time': timezone.now().strftime('%d/%m/%Y %H:%M'),
    }
    
    return render(request, "Pyquest/dashboard.html", context)

@login_required
def api_dashboard_basico(request):
    """API para dados básicos do dashboard - COM TEMPO DIÁRIO"""
    perfil = request.user.perfil
    
    # TEMPO DE ESTUDO DIÁRIO (zera todo dia)
    hoje = timezone.now().date()
    tempo_estudo_hoje = TempoEstudoDiario.objects.filter(
        user=request.user,
        data=hoje
    ).aggregate(total_tempo=Sum('tempo_segundos'))['total_tempo'] or 0
    
    # Formatar tempo de hoje
    horas_hoje = tempo_estudo_hoje // 3600
    minutos_hoje = (tempo_estudo_hoje % 3600) // 60
    segundos_hoje = tempo_estudo_hoje % 60
    
    if horas_hoje > 0:
        tempo_formatado = f"{horas_hoje:02d}:{minutos_hoje:02d}:{segundos_hoje:02d}"
    else:
        tempo_formatado = f"{minutos_hoje:02d}:{segundos_hoje:02d}"
    
    # XP ganho hoje
    xp_hoje = Atividade.objects.filter(
        user=request.user,
        data__date=hoje
    ).aggregate(total_xp=Sum('xp_ganho'))['total_xp'] or 0
    
    # Módulos concluídos
    modulos_concluidos = ModuloConcluido.objects.filter(usuario=request.user).count()
    total_modulos = Modulo.objects.filter(ativo=True).count()
    
    # Sequência ATUALIZADA - usa verificação correta
    sequencia_atual = perfil.sequencia
    
    # Precisão (placeholder - implemente conforme seu sistema)
    precisao = 89
    
    # Acertos seguidos (placeholder)
    acertos_seguidos = perfil.acertos_seguidos
    recorde_acertos = perfil.sequencia_maxima  # Usando o streak máximo como recorde
    
    return JsonResponse({
        'tempo_estudo': tempo_formatado,
        'tempo_segundos': tempo_estudo_hoje,  # Para cálculos
        'xp_total': perfil.xp,
        'xp_hoje': xp_hoje,
        'modulos_concluidos': modulos_concluidos,
        'total_modulos': total_modulos,
        'sequencia_atual': sequencia_atual,
        'precisao': precisao,
        'acertos_seguidos': acertos_seguidos,
        'recorde_acertos': recorde_acertos,
    })

@login_required
def api_dashboard_xp(request):
    """API para dados do gráfico de XP - VERSÃO CORRIGIDA"""
    period = request.GET.get('period', 'week')
    
    try:
        hoje = timezone.now().date()
        
        if period == 'day':
            # Últimas 24 horas (em períodos de 4h)
            labels = ['00h', '04h', '08h', '12h', '16h', '20h']
            xp_data = []
            
            for i in range(6):
                hora_inicio = i * 4
                hora_fim = (i + 1) * 4
                
                # Buscar XP ganho nesse período
                xp_periodo = Atividade.objects.filter(
                    user=request.user,
                    data__date=hoje,
                    data__hour__gte=hora_inicio,
                    data__hour__lt=hora_fim
                ).aggregate(total_xp=Sum('xp_ganho'))['total_xp'] or 0
                
                xp_data.append(xp_periodo)
        
        elif period == 'week':
            # Últimos 7 dias
            labels = []
            xp_data = []
            
            for i in range(6, -1, -1):
                date = hoje - timedelta(days=i)
                labels.append(date.strftime('%a'))
                
                xp_dia = Atividade.objects.filter(
                    user=request.user,
                    data__date=date
                ).aggregate(total_xp=Sum('xp_ganho'))['total_xp'] or 0
                
                xp_data.append(xp_dia)
        
        elif period == 'month':
            # Últimas 4 semanas
            labels = ['Sem 1', 'Sem 2', 'Sem 3', 'Sem 4']
            xp_data = []
            
            for i in range(4):
                semana_inicio = hoje - timedelta(days=(3-i)*7 + hoje.weekday())
                semana_fim = semana_inicio + timedelta(days=6)
                
                xp_semana = Atividade.objects.filter(
                    user=request.user,
                    data__date__range=[semana_inicio, semana_fim]
                ).aggregate(total_xp=Sum('xp_ganho'))['total_xp'] or 0
                
                xp_data.append(xp_semana)
        
        else:
            # Fallback para semana
            labels = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom']
            xp_data = [0, 0, 0, 0, 0, 0, 0]
        
        return JsonResponse({
            'labels': labels,
            'data': xp_data,
            'period': period
        })
        
    except Exception as e:
        print(f"Erro na API XP: {e}")
        # Fallback com dados estáticos em caso de erro
        if period == 'day':
            return JsonResponse({
                'labels': ['00h', '04h', '08h', '12h', '16h', '20h'],
                'data': [50, 120, 80, 200, 150, 100],
                'period': period
            })
        elif period == 'month':
            return JsonResponse({
                'labels': ['Sem 1', 'Sem 2', 'Sem 3', 'Sem 4'],
                'data': [1500, 1800, 1600, 2000],
                'period': period
            })
        else:
            return JsonResponse({
                'labels': ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom'],
                'data': [200, 450, 300, 600, 350, 500, 400],
                'period': 'week'
            })

@login_required
def api_dashboard_categorias(request):
    """API para dados do gráfico de categorias - VERSÃO CORRIGIDA"""
    try:
        # Buscar capítulos com progresso real
        capitulos = Capitulo.objects.filter(ativo=True)[:5]
        
        labels = []
        data = []
        cores = ['#1e40af', '#2563eb', '#3b82f6', '#60a5fa', '#93c5fd']
        
        for i, capitulo in enumerate(capitulos):
            labels.append(capitulo.titulo[:15])
            
            # Calcular progresso real
            total_aulas = Aula.objects.filter(
                modulo__capitulo=capitulo,
                ativo=True
            ).count()
            
            if total_aulas > 0:
                aulas_concluidas = AulaConcluida.objects.filter(
                    usuario=request.user,
                    aula__modulo__capitulo=capitulo,
                    teoria_concluida=True,
                    pratica_concluida=True
                ).count()
                
                progresso = (aulas_concluidas / total_aulas) * 100
            else:
                progresso = 0
                
            data.append(round(progresso))
        
        return JsonResponse({
            'labels': labels,
            'data': data,
            'cores': cores[:len(labels)]
        })
        
    except Exception as e:
        print(f"Erro na API categorias: {e}")
        return JsonResponse({
            'labels': ['Python', 'Django', 'Banco Dados', 'Frontend', 'APIs'],
            'data': [75, 60, 45, 30, 20],
            'cores': ['#1e40af', '#2563eb', '#3b82f6', '#60a5fa', '#93c5fd']
        })

@login_required
def api_dashboard_radar(request):
    """API para dados do gráfico radar - VERSÃO CORRIGIDA"""
    try:
        habilidades = ['Lógica', 'Funções', 'Estruturas', 'OOP', 'Projetos']
        
        # Calcular níveis baseados no progresso real
        seu_nivel = []
        
        # Lógica - baseado em questões de lógica concluídas
        questoes_logica = AulaConcluida.objects.filter(
            usuario=request.user,
            aula__questoes__tipo='multiple-choice'
        ).distinct().count()
        seu_nivel.append(min(100, questoes_logica * 10))
        
        # Funções - baseado em questões de código
        questoes_codigo = AulaConcluida.objects.filter(
            usuario=request.user,
            aula__questoes__tipo='code'
        ).distinct().count()
        seu_nivel.append(min(100, questoes_codigo * 15))
        
        # Estruturas - baseado em completar lacunas
        questoes_lacunas = AulaConcluida.objects.filter(
            usuario=request.user,
            aula__questoes__tipo='fill-blank'
        ).distinct().count()
        seu_nivel.append(min(100, questoes_lacunas * 12))
        
        # OOP - baseado em módulos avançados concluídos
        modulos_oop = ModuloConcluido.objects.filter(
            usuario=request.user,
            modulo__capitulo__dificuldade='advanced'
        ).count()
        seu_nivel.append(min(100, modulos_oop * 25))
        
        # Projetos - baseado em XP total
        xp_total = request.user.perfil.xp
        seu_nivel.append(min(100, xp_total // 50))
        
        # Média dos usuários (simplificado)
        media_usuarios = [60, 50, 65, 40, 30]
        
        return JsonResponse({
            'labels': habilidades,
            'seu_nivel': [int(n) for n in seu_nivel],
            'media_usuarios': media_usuarios
        })
        
    except Exception as e:
        print(f"Erro na API radar: {e}")
        return JsonResponse({
            'labels': ['Lógica', 'Funções', 'Estruturas', 'OOP', 'Projetos'],
            'seu_nivel': [75, 60, 45, 30, 25],
            'media_usuarios': [60, 50, 65, 40, 30]
        })

@login_required
def api_dashboard_ranking(request):
    """API para dados do gráfico de ranking - VERSÃO CORRIGIDA"""
    period = request.GET.get('period', 'week')
    
    try:
        # Buscar a posição atual do usuário
        todos_perfis = Perfil.objects.order_by('-xp')
        ids = list(todos_perfis.values_list('user_id', flat=True))
        posicao_atual = ids.index(request.user.id) + 1 if request.user.id in ids else len(ids) + 1
        
        if period == 'day':
            # Evolução ao longo do dia (simulado baseado em atividades)
            labels = ['Manhã', 'Tarde', 'Noite']
            
            # Simular variação baseada em atividades do dia
            atividades_hoje = Atividade.objects.filter(
                user=request.user,
                data__date=timezone.now().date()
            ).count()
            
            # Variação simulada baseada em atividades
            variacao_base = min(5, atividades_hoje // 2)
            data = [
                posicao_atual + variacao_base + 2,
                posicao_atual + variacao_base + 1, 
                posicao_atual
            ]
            variacao = variacao_base + 2
            
        elif period == 'week':
            # Últimos 4 pontos na semana
            labels = ['2 dias atrás', 'Ontem', 'Hoje']
            
            # Buscar atividades dos últimos dias para simular progresso
            atividades_ontem = Atividade.objects.filter(
                user=request.user,
                data__date=timezone.now().date() - timedelta(days=1)
            ).count()
            
            atividades_anteontem = Atividade.objects.filter(
                user=request.user,
                data__date=timezone.now().date() - timedelta(days=2)
            ).count()
            
            data = [
                posicao_atual + (atividades_anteontem // 3) + 2,
                posicao_atual + (atividades_ontem // 3) + 1,
                posicao_atual
            ]
            variacao = (atividades_anteontem // 3) + 2
            
        elif period == 'month':
            # Últimos 4 meses
            labels = ['Mês 1', 'Mês 2', 'Mês 3', 'Atual']
            
            # Simular progresso mensal baseado em XP total
            xp_total = request.user.perfil.xp
            progresso_mensal = xp_total // 1000  # Simplificação
            
            data = [
                posicao_atual + progresso_mensal + 3,
                posicao_atual + progresso_mensal + 2,
                posicao_atual + progresso_mensal + 1,
                posicao_atual
            ]
            variacao = progresso_mensal + 3
        
        else:
            # Fallback
            labels = ['Início', 'Meio', 'Atual']
            data = [posicao_atual + 2, posicao_atual + 1, posicao_atual]
            variacao = 2
        
        return JsonResponse({
            'labels': labels,
            'data': data,
            'posicao_atual': posicao_atual,
            'variacao': variacao,
            'period': period
        })
        
    except Exception as e:
        print(f"Erro na API ranking: {e}")
        # Fallback em caso de erro
        if period == 'day':
            return JsonResponse({
                'labels': ['Manhã', 'Tarde', 'Noite'],
                'data': [45, 43, 42],
                'posicao_atual': 42,
                'variacao': 3,
                'period': period
            })
        elif period == 'month':
            return JsonResponse({
                'labels': ['Mês 1', 'Mês 2', 'Mês 3', 'Atual'],
                'data': [50, 47, 45, 42],
                'posicao_atual': 42,
                'variacao': 8,
                'period': period
            })
        else:
            return JsonResponse({
                'labels': ['2 dias atrás', 'Ontem', 'Hoje'],
                'data': [45, 43, 42],
                'posicao_atual': 42,
                'variacao': 3,
                'period': 'week'
            })

# Adicione esta função ao views.py para melhorar a API do heatmap:

@login_required
def api_dashboard_heatmap(request):
    """API para dados do heatmap - VERSÃO MELHORADA"""
    year = int(request.GET.get('year', timezone.now().year))
    
    try:
        # Buscar atividades reais do usuário no ano especificado
        atividades = Atividade.objects.filter(
            user=request.user,
            data__year=year
        ).values('data__date').annotate(
            count=Count('id'),
            total_xp=Sum('xp_ganho')
        ).order_by('data__date')
        
        # Criar mapa de atividades por data
        activity_map = {}
        for atividade in atividades:
            date_str = atividade['data__date'].isoformat()
            count = atividade['count']
            xp_total = atividade['total_xp'] or 0
            
            # Determinar nível baseado na quantidade de atividades E XP ganho
            if count == 0:
                level = 0
            elif count == 1 and xp_total < 20:
                level = 1
            elif count <= 3 or xp_total < 50:
                level = 2
            elif count <= 5 or xp_total < 100:
                level = 3
            else:
                level = 4
                
            activity_map[date_str] = {
                'count': count,
                'level': level,
                'xp': xp_total,
                'date': atividade['data__date']
            }
        
        # Gerar dados para todos os dias do ano solicitado
        heatmap_data = []
        start_date = datetime(year, 1, 1).date()
        end_date = datetime(year, 12, 31).date()
        current_date = start_date
        
        while current_date <= end_date:
            date_str = current_date.isoformat()
            activity_info = activity_map.get(date_str, {
                'count': 0, 
                'level': 0, 
                'xp': 0,
                'date': current_date
            })
            
            heatmap_data.append({
                'date': date_str,
                'count': activity_info['count'],
                'level': activity_info['level'],
                'xp': activity_info['xp'],
                'day': current_date.day,
                'month': current_date.month,
                'year': current_date.year,
                'weekday': current_date.weekday(),  # 0=segunda, 6=domingo
                'is_today': current_date == timezone.now().date(),
                'is_weekend': current_date.weekday() in [5, 6]  # sábado, domingo
            })
            
            current_date += timedelta(days=1)
        
        # Estatísticas do ano
        dias_com_atividade = len([d for d in heatmap_data if d['level'] > 0])
        total_atividades = sum(d['count'] for d in heatmap_data)
        total_xp_ano = sum(d['xp'] for d in heatmap_data)
        
        return JsonResponse({
            'year': year,
            'data': heatmap_data,
            'stats': {
                'dias_ativos': dias_com_atividade,
                'total_atividades': total_atividades,
                'total_xp': total_xp_ano,
                'percentual_ano': int((dias_com_atividade / len(heatmap_data)) * 100)
            }
        })
        
    except Exception as e:
        print(f"Erro na API heatmap: {e}")
        # Retornar dados vazios em caso de erro
        return JsonResponse({
            'year': year,
            'data': [],
            'stats': {
                'dias_ativos': 0,
                'total_atividades': 0,
                'total_xp': 0,
                'percentual_ano': 0
            }
        })

@login_required
def api_dashboard_estatisticas(request):
    """API para estatísticas detalhadas"""
    perfil = request.user.perfil
    
    # Taxa de acertos (placeholder)
    taxa_acertos = 89
    
    # Questões respondidas
    total_questoes_respondidas = AulaConcluida.objects.filter(
        usuario=request.user,
        pratica_concluida=True
    ).count()
    
    # Dias ativos no mês atual
    hoje = timezone.now().date()
    primeiro_dia_mes = hoje.replace(day=1)
    dias_ativos = Atividade.objects.filter(
        user=request.user,
        data__date__gte=primeiro_dia_mes
    ).dates('data', 'day').distinct().count()
    
    # Ranking
    todos_perfis = Perfil.objects.order_by('-xp')
    posicao_ranking = list(todos_perfis.values_list('id', flat=True)).index(perfil.id) + 1
    total_usuarios = todos_perfis.count()
    top_percent = int((posicao_ranking / total_usuarios) * 100) if total_usuarios > 0 else 0
    
    # Conquistas
    conquistas_desbloqueadas = Conquista.objects.filter(usuarios=request.user).count()
    total_conquistas = Conquista.objects.filter(ativo=True).count()
    
    return JsonResponse({
        'taxa_acertos': taxa_acertos,
        'questoes_respondidas': total_questoes_respondidas,
        'dias_ativos_mes': dias_ativos,
        'dias_totais_mes': hoje.day,
        'melhor_sequencia': perfil.sequencia_maxima,
        'xp_total': perfil.xp,
        'sequencia_atual': perfil.sequencia,
        'ranking_posicao': posicao_ranking,
        'ranking_total': total_usuarios,
        'top_percent': top_percent,
        'conquistas_desbloqueadas': conquistas_desbloqueadas,
        'total_conquistas': total_conquistas,
    })

# Adicione estas views:

@login_required
@require_POST
def registrar_atividade_manual(request):
    """Registra uma atividade manualmente no heatmap"""
    try:
        data = json.loads(request.body)
        date_str = data.get('date')
        titulo = data.get('titulo')
        xp = data.get('xp', 10)
        
        # Converter string para data
        data_atividade = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        # Criar atividade
        atividade = Atividade.objects.create(
            user=request.user,
            titulo=titulo,
            xp_ganho=xp,
            data=timezone.make_aware(datetime.combine(data_atividade, datetime.min.time()))
        )
        
        return JsonResponse({'success': True, 'atividade_id': atividade.id})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_POST
def gerar_dados_demo(request):
    """Gera dados de demonstração para o heatmap"""
    try:
        from datetime import timedelta
        
        # Gerar atividades para os últimos 60 dias
        hoje = timezone.now().date()
        for i in range(60):
            data = hoje - timedelta(days=i)
            
            # 70% de chance de ter atividade no dia
            if random.random() < 0.7:
                # Número aleatório de atividades (1-4)
                num_atividades = random.randint(1, 4)
                
                for j in range(num_atividades):
                    tipos = ['Aula teórica', 'Exercícios práticos', 'Revisão', 'Projeto']
                    Atividade.objects.create(
                        user=request.user,
                        titulo=f"{random.choice(tipos)} - Dia {i}",
                        xp_ganho=random.randint(5, 25),
                        data=timezone.make_aware(datetime.combine(data, datetime.min.time()))
                    )
        
        return JsonResponse({'success': True, 'message': 'Dados de demonstração gerados'})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def verificar_streak_manual(request):
    """View para forçar a verificação do streak (útil para testes)"""
    perfil = request.user.perfil
    streak_anterior = perfil.sequencia
    
    # Forçar verificação
    perfil.verificar_e_atualizar_streak()
    
    messages.success(request, f"Streak verificado! Anterior: {streak_anterior}, Atual: {perfil.sequencia}")
    return redirect('dashboard')

@login_required
def api_streak_status(request):
    """API para obter status atual do streak"""
    perfil = request.user.perfil
    
    return JsonResponse({
        'success': True,
        'streak_atual': perfil.sequencia,
        'streak_maximo': perfil.sequencia_maxima,
        'ultima_atividade': perfil.ultima_atividade.isoformat() if perfil.ultima_atividade else None,
        'bonus_streak': perfil.get_bonus_streak() * 100,
    })

@login_required
def api_dashboard_xp_bar(request):
    """API específica para o gráfico de barras - XP por período"""
    period = request.GET.get('period', 'week')
    
    try:
        hoje = timezone.now().date()
        
        if period == 'day':
            # Últimas 6 horas (em períodos de 1h)
            labels = ['06h', '07h', '08h', '09h', '10h', '11h', '12h', '13h', '14h', '15h', '16h', '17h']
            xp_data = []
            
            for i in range(6, 18):  # Das 6h às 18h
                # Buscar XP ganho nessa hora
                xp_hora = Atividade.objects.filter(
                    user=request.user,
                    data__date=hoje,
                    data__hour=i
                ).aggregate(total_xp=Sum('xp_ganho'))['total_xp'] or 0
                
                xp_data.append(xp_hora)
        
        elif period == 'week':
            # Últimos 7 dias
            labels = []
            xp_data = []
            
            for i in range(6, -1, -1):
                date = hoje - timedelta(days=i)
                labels.append(date.strftime('%a'))
                
                xp_dia = Atividade.objects.filter(
                    user=request.user,
                    data__date=date
                ).aggregate(total_xp=Sum('xp_ganho'))['total_xp'] or 0
                
                xp_data.append(xp_dia)
        
        elif period == 'month':
            # Últimos 30 dias (agrupados por semana)
            labels = ['Sem 1', 'Sem 2', 'Sem 3', 'Sem 4']
            xp_data = [0, 0, 0, 0]
            
            for i in range(4):
                semana_inicio = hoje - timedelta(days=(3-i)*7 + hoje.weekday())
                semana_fim = semana_inicio + timedelta(days=6)
                
                xp_semana = Atividade.objects.filter(
                    user=request.user,
                    data__date__range=[semana_inicio, semana_fim]
                ).aggregate(total_xp=Sum('xp_ganho'))['total_xp'] or 0
                
                xp_data[i] = xp_semana
        
        else:
            # Fallback para semana
            labels = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom']
            xp_data = [0, 0, 0, 0, 0, 0, 0]
        
        return JsonResponse({
            'labels': labels,
            'data': xp_data,
            'period': period
        })
        
    except Exception as e:
        print(f"Erro na API XP Bar: {e}")
        # Fallback com dados estáticos em caso de erro
        if period == 'day':
            return JsonResponse({
                'labels': ['06h', '08h', '10h', '12h', '14h', '16h', '18h'],
                'data': [50, 120, 80, 200, 150, 100, 75],
                'period': period
            })
        elif period == 'month':
            return JsonResponse({
                'labels': ['Sem 1', 'Sem 2', 'Sem 3', 'Sem 4'],
                'data': [1500, 1800, 1600, 2000],
                'period': period
            })
        else:
            return JsonResponse({
                'labels': ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom'],
                'data': [200, 450, 300, 600, 350, 500, 400],
                'period': 'week'
            })
        
@login_required
def api_dashboard_conquistas_categorias(request):
    """API para dados do gráfico de conquistas por categoria"""
    try:
        # Buscar todas as categorias de conquistas
        categorias = Conquista.CATEGORIAS
        categorias_data = []
        
        for categoria_codigo, categoria_nome in categorias:
            # Buscar conquistas desta categoria
            conquistas_categoria = Conquista.objects.filter(
                categoria=categoria_codigo,
                ativo=True
            )
            
            # Contar conquistas desbloqueadas pelo usuário
            conquistas_desbloqueadas = conquistas_categoria.filter(
                usuarios=request.user
            ).count()
            
            total_conquistas = conquistas_categoria.count()
            
            # Calcular percentual de conclusão
            if total_conquistas > 0:
                percentual = int((conquistas_desbloqueadas / total_conquistas) * 100)
            else:
                percentual = 0
            
            categorias_data.append({
                'categoria': categoria_nome,
                'conquistas_desbloqueadas': conquistas_desbloqueadas,
                'total_conquistas': total_conquistas,
                'percentual': percentual,
                'codigo': categoria_codigo
            })
        
        # Ordenar por percentual (maior primeiro)
        categorias_data.sort(key=lambda x: x['percentual'], reverse=True)
        
        return JsonResponse({
            'categorias': [c['categoria'] for c in categorias_data],
            'percentuais': [c['percentual'] for c in categorias_data],
            'detalhes': categorias_data
        })
        
    except Exception as e:
        print(f"Erro na API conquistas categorias: {e}")
        # Fallback em caso de erro
        return JsonResponse({
            'categorias': ['Progresso', 'Habilidade', 'Precisão', 'Domínio', 'Especial'],
            'percentuais': [75, 60, 45, 30, 20],
            'detalhes': []
        })
    
@login_required
def api_dashboard_calendar(request):
    """API para dados do calendário - ATIVIDADES REAIS DO USUÁRIO"""
    year = int(request.GET.get('year', timezone.now().year))
    month = int(request.GET.get('month', timezone.now().month))
    
    try:
        # Buscar atividades do usuário no mês/ano especificado
        atividades = Atividade.objects.filter(
            user=request.user,
            data__year=year,
            data__month=month
        ).values('data__date').annotate(
            count=Count('id'),
            total_xp=Sum('xp_ganho')
        ).order_by('data__date')
        
        # Buscar também tempo de estudo diário
        tempo_estudo = TempoEstudoDiario.objects.filter(
            user=request.user,
            data__year=year,
            data__month=month
        ).values('data').annotate(
            total_tempo=Sum('tempo_segundos')
        )
        
        # Criar mapa de atividades por data
        activity_map = {}
        
        # Processar atividades
        for atividade in atividades:
            date_str = atividade['data__date'].isoformat()
            count = atividade['count']
            xp_total = atividade['total_xp'] or 0
            
            # Determinar nível de atividade baseado na quantidade e XP
            activity_level = calcular_nivel_atividade(count, xp_total)
            
            activity_map[date_str] = {
                'date': atividade['data__date'],
                'activity_level': activity_level,
                'activity_count': count,
                'xp': xp_total,
                'has_study_time': False
            }
        
        # Processar tempo de estudo
        for estudo in tempo_estudo:
            date_str = estudo['data'].isoformat()
            tempo_total = estudo['total_tempo'] or 0
            
            if date_str in activity_map:
                # Se já tem atividade, aumentar nível baseado no tempo
                if tempo_total > 1800:  # Mais de 30 minutos
                    activity_map[date_str]['activity_level'] = min(
                        activity_map[date_str]['activity_level'] + 1, 4
                    )
                activity_map[date_str]['has_study_time'] = True
                activity_map[date_str]['study_time'] = tempo_total
            else:
                # Se não tem atividade mas tem tempo de estudo
                activity_level = 1 if tempo_total > 900 else 0  # 15 minutos mínimo
                activity_map[date_str] = {
                    'date': estudo['data'],
                    'activity_level': activity_level,
                    'activity_count': 0,
                    'xp': 0,
                    'has_study_time': True,
                    'study_time': tempo_total
                }
        
        # Gerar dados para todos os dias do mês
        calendar_data = []
        days_in_month = (datetime(year, month + 1, 1) - datetime(year, month, 1)).days if month < 12 else 31
        hoje = timezone.now().date()
        
        for day in range(1, days_in_month + 1):
            current_date = datetime(year, month, day).date()
            date_str = current_date.isoformat()
            
            activity_info = activity_map.get(date_str, {
                'date': current_date,
                'activity_level': 0,
                'activity_count': 0,
                'xp': 0,
                'has_study_time': False,
                'study_time': 0
            })
            
            calendar_data.append({
                'date': date_str,
                'activity_level': activity_info['activity_level'],
                'activity_count': activity_info['activity_count'],
                'xp': activity_info['xp'],
                'study_time': activity_info.get('study_time', 0),
                'is_today': current_date == hoje,
                'has_activity': activity_info['activity_level'] > 0
            })
        
        # Estatísticas do mês
        dias_com_atividade = len([d for d in calendar_data if d['activity_level'] > 0])
        total_atividades = sum(d['activity_count'] for d in calendar_data)
        total_xp_mes = sum(d['xp'] for d in calendar_data)
        
        # Calcular sequência atual
        current_streak = calcular_sequencia_atual(calendar_data, hoje)
        
        return JsonResponse({
            'year': year,
            'month': month,
            'data': calendar_data,
            'stats': {
                'dias_ativos': dias_com_atividade,
                'total_atividades': total_atividades,
                'total_xp': total_xp_mes,
                'current_streak': current_streak,
                'percentual_mes': int((dias_com_atividade / days_in_month) * 100)
            }
        })
        
    except Exception as e:
        print(f"❌ Erro na API calendário: {e}")
        import traceback
        traceback.print_exc()
        
        # Fallback com dados vazios
        return JsonResponse({
            'year': year,
            'month': month,
            'data': [],
            'stats': {
                'dias_ativos': 0,
                'total_atividades': 0,
                'total_xp': 0,
                'current_streak': 0,
                'percentual_mes': 0
            }
        })

def calcular_nivel_atividade(count, xp):
    """Calcula o nível de atividade baseado na quantidade e XP"""
    if count == 0 and xp == 0:
        return 0  # Nenhuma atividade
    
    # Baseado na quantidade de atividades
    if count == 1 and xp < 20:
        return 1  # Atividade leve
    elif count <= 3 or xp < 50:
        return 2  # Atividade moderada
    elif count <= 5 or xp < 100:
        return 3  # Atividade intensa
    else:
        return 4  # Atividade muito intensa

def calcular_sequencia_atual(calendar_data, hoje):
    """Calcula a sequência atual de dias com atividade"""
    streak = 0
    current_date = hoje
    
    # Ordenar dados por data para facilitar
    data_map = {item['date']: item for item in calendar_data}
    
    # Verificar sequência começando de hoje para trás
    for i in range(30):  # Verificar até 30 dias
        date_str = current_date.isoformat()
        day_data = data_map.get(date_str)
        
        if day_data and day_data['activity_level'] > 0:
            streak += 1
            current_date = current_date - timedelta(days=1)
        else:
            break
    
    return streak

@login_required
def api_calendar_activity_detail(request):
    """API para detalhes das atividades de um dia específico - VERSÃO CORRIGIDA"""
    date_str = request.GET.get('date')
    
    if not date_str:
        return JsonResponse({'success': False, 'error': 'Data não especificada'})
    
    try:
        # CORREÇÃO: Usar timezone para garantir o fuso horário correto
        target_date = timezone.datetime.strptime(date_str, '%Y-%m-%d').date()
        
        print(f"🔍 Buscando atividades para: {target_date} (data recebida: {date_str})")
        
        # Buscar atividades do dia - CORREÇÃO: usar range de datas com timezone
        start_datetime = timezone.make_aware(timezone.datetime.combine(target_date, timezone.datetime.min.time()))
        end_datetime = start_datetime + timedelta(days=1)
        
        atividades = Atividade.objects.filter(
            user=request.user,
            data__gte=start_datetime,
            data__lt=end_datetime
        ).select_related('aula').order_by('-data')
        
        # Buscar tempo de estudo do dia
        tempo_estudo = TempoEstudoDiario.objects.filter(
            user=request.user,
            data=target_date
        ).first()
        
        atividades_data = []
        for atividade in atividades:
            atividades_data.append({
                'titulo': atividade.titulo,
                'xp_ganho': atividade.xp_ganho,
                'hora': atividade.data.astimezone(timezone.get_current_timezone()).strftime('%H:%M'),
                'aula': atividade.aula.titulo_aula if atividade.aula else None
            })
        
        print(f"✅ Encontradas {len(atividades_data)} atividades para {target_date}")
        
        return JsonResponse({
            'success': True,
            'date': target_date.isoformat(),
            'date_display': target_date.strftime('%d/%m/%Y'),  # Formato brasileiro para exibição
            'atividades': atividades_data,
            'total_atividades': len(atividades_data),
            'total_xp': sum(a['xp_ganho'] for a in atividades_data),
            'tempo_estudo': tempo_estudo.tempo_segundos if tempo_estudo else 0,
            'tempo_estudo_formatado': tempo_estudo.tempo_formatado() if tempo_estudo else '00:00'
        })
        
    except Exception as e:
        print(f"❌ Erro ao buscar detalhes: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)})
    
@login_required
def api_estatisticas_gerais(request):
    """API para estatísticas gerais da plataforma"""
    try:
        total_usuarios = User.objects.count()
        total_modulos = Modulo.objects.filter(ativo=True).count()
        total_conquistas = Conquista.objects.filter(ativo=True).count()
        total_posts = Post.objects.count()
        
        return JsonResponse({
            'success': True,
            'total_usuarios': total_usuarios,
            'total_modulos': total_modulos,
            'total_conquistas': total_conquistas,
            'total_posts': total_posts,
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
def api_conquistas_usuario(request):
    """API para conquistas do usuário logado"""
    try:
        conquistas_desbloqueadas = Conquista.objects.filter(usuarios=request.user).count()
        
        return JsonResponse({
            'success': True,
            'conquistas_desbloqueadas': conquistas_desbloqueadas,
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
def api_tempo_estudo_hoje(request):
    """API para tempo de estudo diário"""
    try:
        hoje = timezone.now().date()
        tempo_estudo = TempoEstudoDiario.objects.filter(
            user=request.user,
            data=hoje
        ).first()
        
        if tempo_estudo:
            tempo_segundos = tempo_estudo.tempo_segundos
            horas = tempo_segundos // 3600
            minutos = (tempo_segundos % 3600) // 60
            
            if horas > 0:
                tempo_formatado = f"{horas:02d}:{minutos:02d}"
            else:
                tempo_formatado = f"{minutos:02d} min"
        else:
            tempo_formatado = "00:00"
            
        return JsonResponse({
            'success': True,
            'tempo_formatado': tempo_formatado,
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
def api_conquistas_populares(request):
    """API para conquistas populares"""
    try:
        # Buscar conquistas mais comuns (com mais usuários)
        conquistas = Conquista.objects.filter(ativo=True).annotate(
            total_usuarios=Count('usuarios')
        ).order_by('-total_usuarios')[:4]
        
        conquistas_data = []
        for conquista in conquistas:
            conquistas_data.append({
                'titulo': conquista.titulo,
                'descricao': conquista.descricao,
                'raridade': conquista.get_raridade_display(),
                'icone': conquista.icone.url if conquista.icone else None,
            })
            
        return JsonResponse({
            'success': True,
            'conquistas': conquistas_data,
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })
    
@login_required
def testar_streak_manual(request):
    """View temporária para testar o aumento do streak"""
    perfil = request.user.perfil
    
    # Simular que a última atividade foi ontem
    from datetime import timedelta
    perfil.ultima_atividade = timezone.now() - timedelta(days=1)
    perfil.ja_fez_atividade_hoje = False  # Resetar para simular novo dia
    perfil.save()
    
    messages.success(request, f"✅ Configurado para testar! Última atividade: {perfil.ultima_atividade}")
    return redirect('home')

@login_required
@require_GET
def api_questao_respostas(request, questao_id):
    """API para obter respostas corretas de uma questão"""
    try:
        questao = Questao.objects.get(id=questao_id)
        
        respostas = []
        
        if questao.tipo == 'fill-blank':
            # Para questões de completar lacunas, buscar opções corretas
            opcoes_corretas = OpcaoQuestao.objects.filter(
                questao=questao, 
                correta=True
            ).order_by('ordem')
            
            respostas = [opcao.texto for opcao in opcoes_corretas]
            
        elif questao.tipo == 'multiple-choice':
            # Para múltipla escolha, retornar as opções corretas também
            opcoes_corretas = OpcaoQuestao.objects.filter(
                questao=questao, 
                correta=True
            ).order_by('ordem')
            
            respostas = [opcao.texto for opcao in opcoes_corretas]
        
        print(f"🔍 API Respostas - Questão {questao_id}: {respostas}")
        
        return JsonResponse({
            'success': True,
            'questao_id': questao_id,
            'tipo': questao.tipo,
            'respostas': respostas
        })
        
    except Questao.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Questão não encontrada'
        })
    except Exception as e:
        print(f"❌ Erro na API respostas: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })
    
# Adicione estas views ao views.py

@login_required
@require_GET
def api_vidas_status(request):
    """API para obter status atual das vidas"""
    try:
        perfil = request.user.perfil
        perfil.regenerar_vidas()  # Sempre verificar regeneração ao acessar
        
        return JsonResponse({
            'success': True,
            'vidas': perfil.vidas,
            'max_vidas': perfil.max_vidas,
            'tempo_para_proxima_vida': perfil.tempo_para_proxima_vida(),
            'progresso_vidas': int((perfil.vidas / perfil.max_vidas) * 100) if perfil.max_vidas > 0 else 0
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_POST
def api_usar_vida(request):
    """API para usar uma vida"""
    try:
        data = json.loads(request.body)
        aula_id = data.get('aula_id', None)
        
        perfil = request.user.perfil
        
        if perfil.usar_vida():
            # Registrar uso de vida se tiver aula associada
            if aula_id:
                try:
                    aula = Aula.objects.get(id=aula_id)
                    tentativa, created = TentativaPratica.objects.get_or_create(
                        usuario=request.user,
                        aula=aula
                    )
                    tentativa.vidas_usadas += 1
                    tentativa.vidas_restantes = perfil.vidas
                    tentativa.save()
                except Aula.DoesNotExist:
                    pass
            
            return JsonResponse({
                'success': True,
                'vidas_restantes': perfil.vidas,
                'max_vidas': perfil.max_vidas,
                'tempo_para_proxima_vida': perfil.tempo_para_proxima_vida()
            })
        else:
            return JsonResponse({
                'success': False,
                'error': 'Sem vidas disponíveis'
            })
            
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})