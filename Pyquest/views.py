from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils import timezone
from .models import *
from django.db.models import Count, Q
from datetime import datetime, timedelta
from django.dispatch import receiver
from django.db.models.signals import post_save
from django.http import JsonResponse
import json
from .forms import *
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST
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
        "progresso_vidas": progresso_vidas,  # Adicionado para o gráfico circular
        "proxima_vida": perfil.tempo_para_proxima_vida(),
        "nome": request.user.first_name or request.user.username,
        "xp": perfil.xp,
        "nivel": perfil.nivel,
        "progresso_nivel": progresso_nivel,
        "xp_necessario": xp_necessario,
        "conquistas": perfil.conquistas,
        "total_conquistas": perfil.total_conquistas,
        "sequencia": perfil.sequencia,
        "progresso": progresso_hoje.percentual,
        "meta": 60,
        "tempo": tempo_formatado,  # Usando o tempo formatado corretamente
        "tempo_segundos": tempo_total_segundos,  # Para o JavaScript
        "xp_diario": progresso_hoje.xp_ganho,
        "atividades": atividades,
        "perfil": perfil,  # Adicionado para acessar métodos do perfil
    }
    return render(request, "Pyquest/home.html", context)


def logout_view(request):
    logout(request)
    return redirect("login")



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
    
    # Buscar TODAS as conquistas com filtros
    conquistas_query = Conquista.objects.filter(ativo=True)
    
    # Aplicar filtros
    if raridade != 'todas':
        conquistas_query = conquistas_query.filter(raridade=raridade)
    
    if categoria != 'todas':
        conquistas_query = conquistas_query.filter(categoria=categoria)
    
    # Calcular progresso para todas as conquistas filtradas
    conquistas_com_progresso = []
    for conquista in conquistas_query.order_by('categoria', 'ordem'):
        progresso = conquista.calcular_progresso(request.user)
        conquistas_com_progresso.append({
            'conquista': conquista,
            'progresso': progresso,
            'desbloqueada': conquista.verificar_desbloqueio(request.user)
        })
    
    # Separar conquistas desbloqueadas e bloqueadas
    conquistas_desbloqueadas = [c for c in conquistas_com_progresso if c['desbloqueada']]
    conquistas_bloqueadas = [c for c in conquistas_com_progresso if not c['desbloqueada']]
    
    # Paginação das conquistas DESBLOQUEADAS (ou você pode escolher qual paginar)
    itens_por_pagina = 8  # Aumentei para 8 para melhor visualização
    paginator = Paginator(conquistas_com_progresso, itens_por_pagina)  # Paginar todas
    
    page_number = request.GET.get('page')
    
    try:
        page_obj = paginator.get_page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)
    
    # Para a paginação funcionar, precisamos usar page_obj no template
    conquistas_paginadas = list(page_obj)
    conquistas_desbloqueadas_pagina = [c for c in conquistas_paginadas if c['desbloqueada']]
    conquistas_bloqueadas_pagina = [c for c in conquistas_paginadas if not c['desbloqueada']]

    context = {
        "perfil": perfil,
        "conquistas_desbloqueadas": conquistas_desbloqueadas_pagina,
        "conquistas_bloqueadas": conquistas_bloqueadas_pagina,
        "progresso_xp": progresso_xp,
        "xp_necessario": xp_necessario,
        "desbloq_count": len(conquistas_desbloqueadas),  # Total geral, não apenas da página
        "total_conquistas": conquistas_query.count(),  # Total com filtros aplicados
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
    paginator = Paginator(capitulos, 3)  # 6 capítulos por página
    page_number = request.GET.get('page')
    
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)
    
    capitulos_com_stats = []
    
    for capitulo in page_obj:  # Usar page_obj em vez de capitulos
        total_modulos = capitulo.modulos.filter(ativo=True).count()
        total_aulas = Aula.objects.filter(modulo__capitulo=capitulo, ativo=True).count()
        
        # **PROGRESSO REAL DO USUÁRIO**
        modulos_concluidos = 0  # ModuloConcluido.objects.filter(usuario=request.user, modulo__capitulo=capitulo).count()
        
        # Calcular percentual
        if total_modulos > 0:
            progresso_percentual = int((modulos_concluidos / total_modulos) * 100)
        else:
            progresso_percentual = 0
        
        # Lógica de bloqueio
        bloqueado = False
        if capitulos_com_stats and capitulo.ordem > 1:
            capitulo_anterior = capitulos_com_stats[-1]
            if capitulo_anterior['progresso_percentual'] < 100:
                bloqueado = True
        
        capitulos_com_stats.append({
            'capitulo': capitulo,
            'total_modulos': total_modulos,
            'total_aulas': total_aulas,
            'modulos_concluidos': modulos_concluidos,
            'progresso_percentual': progresso_percentual,
            'bloqueado': bloqueado,
            'dificuldade': capitulo.dificuldade
        })
    
    # Estatísticas gerais (agora baseadas em dados reais)
    total_capitulos_concluidos = len([c for c in capitulos_com_stats if c['progresso_percentual'] == 100])
    total_capitulos_em_progresso = len([c for c in capitulos_com_stats if 0 < c['progresso_percentual'] < 100])
    total_capitulos_bloqueados = len([c for c in capitulos_com_stats if c['bloqueado']])
    
    context = {
        'capitulos_com_stats': capitulos_com_stats,
        'total_concluidos': total_capitulos_concluidos,
        'total_em_progresso': total_capitulos_em_progresso,
        'total_bloqueados': total_capitulos_bloqueados,
        'page_obj': page_obj,  # Adicionar page_obj ao contexto
        'is_paginated': paginator.num_pages > 1,  # Para controle no template
    }

    return render(request, "Pyquest/conteudo.html", context)

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
        tempo_estudado = data.get('tempo_estudado', 0)  # Ainda recebe mas não mostra
        
        aula = Aula.objects.get(id=aula_id, ativo=True)
        
        # Buscar ou criar registro de conclusão
        aula_concluida, created = AulaConcluida.objects.get_or_create(
            usuario=request.user,
            aula=aula
        )
        
        xp_ganho = 0
        redirect_url = ""
        mensagem = ""
        niveis_ganhos = 0
        
        if is_revisao:
            # LÓGICA DE REVISÃO - XP REDUZIDO (SEMPRE DISPONÍVEL)
            if tipo == 'teoria':
                xp_ganho = 5
                mensagem = "Revisão teórica concluída! +5 XP"  # REMOVIDO TEMPO
                
            elif tipo == 'pratica':
                xp_ganho = 5
                mensagem = "Revisão prática concluída! +5 XP"  # REMOVIDO TEMPO
                
        else:
            # LÓGICA ORIGINAL (primeira conclusão)
            if tipo == 'teoria' and not aula_concluida.teoria_concluida:
                aula_concluida.teoria_concluida = True
                aula_concluida.data_conclusao_teoria = timezone.now()
                aula_concluida.xp_teoria_ganho = aula.xp_teoria
                xp_ganho = aula.xp_teoria
                mensagem = f"Aula teórica concluída! +{aula.xp_teoria} XP"  # REMOVIDO TEMPO
                
            elif tipo == 'pratica' and not aula_concluida.pratica_concluida:
                aula_concluida.pratica_concluida = True
                aula_concluida.data_conclusao_pratica = timezone.now()
                aula_concluida.xp_pratica_ganho = aula.xp_pratica
                xp_ganho = aula.xp_pratica
                mensagem = f"Aula prática concluída! +{aula.xp_pratica} XP"  # REMOVIDO TEMPO
        
        redirect_url = f"/tarefas/?modulo_id={aula.modulo.id}"
        
        if xp_ganho > 0:
            # Para revisões, não precisamos salvar nada no modelo AulaConcluida
            # pois queremos permitir revisões ilimitadas
            if not is_revisao:
                aula_concluida.save()
            
            # NOVO SISTEMA: Usar o método adicionar_xp que não zera o XP
            perfil = request.user.perfil
            niveis_ganhos = perfil.adicionar_xp(xp_ganho)
            
            # Adicionar mensagem de nível se ganhou algum
            if niveis_ganhos > 0:
                mensagem += f" 🎉 Subiu para o nível {perfil.nivel}!"
            
            # Registrar atividade (aqui você pode manter o tempo se quiser no histórico)
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
        
        return JsonResponse({
            'success': True, 
            'xp_ganho': xp_ganho,
            'niveis_ganhos': niveis_ganhos,
            'nivel_atual': request.user.perfil.nivel,
            'redirect_url': redirect_url,
            'mensagem': mensagem,
            'is_revisao': is_revisao
        })
        
    except Exception as e:
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




# ===== VIEWS DO SISTEMA DE STREAK =====

@login_required
@require_POST
def registrar_atividade_streak(request):
    """
    Registra uma atividade do usuário e atualiza o streak
    Mas evita aumentar streak múltiplas vezes no mesmo dia
    """
    try:
        data = json.loads(request.body)
        tipo_atividade = data.get('tipo', 'questao')
        xp_base = data.get('xp_base', 0)
        
        print(f"🎯 Registrar atividade - Tipo: {tipo_atividade}, XP: {xp_base}")
        
        perfil = request.user.perfil
        
        # Verificar se JÁ TEVE ATIVIDADE HOJE
        ja_teve_atividade_hoje = False
        if perfil.ultima_atividade:
            data_ultima = perfil.ultima_atividade.date()
            data_hoje = timezone.now().date()
            ja_teve_atividade_hoje = (data_ultima == data_hoje)
        
        print(f"📅 Já teve atividade hoje: {ja_teve_atividade_hoje}")
        
        # Se JÁ teve atividade hoje e está tentando registrar NOVAMENTE,
        # apenas atualiza a hora mas NÃO aumenta o streak
        if ja_teve_atividade_hoje:
            print("🔄 Já teve atividade hoje - apenas atualizando hora")
            perfil.ultima_atividade = timezone.now()
            perfil.save()
            
            return JsonResponse({
                'success': True,
                'streak_anterior': perfil.sequencia,
                'streak_atual': perfil.sequencia,
                'streak_maximo': perfil.sequencia_maxima,
                'streak_zerado': False,
                'streak_aumentado': False,
                'bonus_streak': f"+{int(perfil.get_bonus_streak() * 100)}%",
                'xp_base': xp_base,
                'xp_bonus': 0,  # Não ganha bônus em atividades extras no mesmo dia
                'xp_total': xp_base,  # Apenas XP base
                'level_up': False,
                'nivel_atual': perfil.nivel,
                'xp_atual': perfil.xp,
                'conquistas_desbloqueadas': [],
                'tempo_restante': perfil.get_tempo_restante_streak(),
                'ja_teve_atividade_hoje': True
            })
        
        # Se NÃO teve atividade hoje, processar normalmente
        streak_anterior = perfil.sequencia
        novo_streak, streak_zerado, streak_aumentado = perfil.verificar_e_atualizar_streak()
        
        # ... resto do código original ...
        
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
            
            print(f"📊 Salvando tempo prática: {tempo_segundos} segundos para aula {aula_id}")
            
            user = request.user
            aula = Aula.objects.get(id=aula_id)
            perfil = Perfil.objects.get(user=user)
            
            # Salvar no TempoEstudo
            tempo_estudo, created = TempoEstudo.objects.get_or_create(
                user=user,
                aula=aula,
                tipo='pratica',
                data=timezone.now().date(),
                defaults={'tempo_segundos': tempo_segundos}
            )
            
            if not created:
                tempo_estudo.tempo_segundos += tempo_segundos
                tempo_estudo.save()
            
            # Atualizar perfil
            tempo_anterior = perfil.tempo_total_estudo
            perfil.tempo_total_estudo += tempo_segundos
            perfil.save()
            
            print(f"✅ Tempo salvo! Anterior: {tempo_anterior}, Atual: {perfil.tempo_total_estudo}")
            
            return JsonResponse({
                'success': True, 
                'tempo_salvo': tempo_segundos,
                'tempo_total': perfil.tempo_total_estudo
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
            
            print(f"📊 Salvando tempo teoria: {tempo_segundos} segundos para aula {aula_id}")
            
            user = request.user
            aula = Aula.objects.get(id=aula_id)
            perfil = Perfil.objects.get(user=user)
            
            # Salvar no TempoEstudo
            tempo_estudo, created = TempoEstudo.objects.get_or_create(
                user=user,
                aula=aula,
                tipo='teoria',
                data=timezone.now().date(),
                defaults={'tempo_segundos': tempo_segundos}
            )
            
            if not created:
                tempo_estudo.tempo_segundos += tempo_segundos
                tempo_estudo.save()
            
            # Atualizar perfil
            tempo_anterior = perfil.tempo_total_estudo
            perfil.tempo_total_estudo += tempo_segundos
            perfil.save()
            
            print(f"✅ Tempo salvo! Anterior: {tempo_anterior}, Atual: {perfil.tempo_total_estudo}")
            
            return JsonResponse({
                'success': True, 
                'tempo_salvo': tempo_segundos,
                'tempo_total': perfil.tempo_total_estudo
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
        
        # Preparar dados para o template
        questions_data = []
        for questao in aula.questoes.all().order_by('ordem'):
            questao_data = {
                'id': questao.id,
                'tipo': questao.tipo,
                'enunciado': questao.enunciado,
                'descricao': questao.descricao,
                'xp': questao.xp,
                'codigo_inicial': questao.codigo_inicial,
                'saida_esperada': questao.saida_esperada,
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
    """Usa uma vida durante a prática"""
    try:
        data = json.loads(request.body)
        aula_id = data.get('aula_id')
        
        aula = get_object_or_404(Aula, id=aula_id)
        perfil = request.user.perfil
        
        # Verificar se tem vidas disponíveis
        if perfil.vidas <= 0:
            return JsonResponse({
                'success': False, 
                'error': 'Sem vidas disponíveis',
                'vidas_restantes': 0
            })
        
        # Usar vida
        perfil.usar_vida()
        
        # Atualizar tentativa
        tentativa, created = TentativaPratica.objects.get_or_create(
            usuario=request.user,
            aula=aula
        )
        tentativa.vidas_usadas += 1
        tentativa.vidas_restantes = perfil.vidas
        tentativa.save()
        
        return JsonResponse({
            'success': True,
            'vidas_restantes': perfil.vidas,
            'max_vidas': perfil.max_vidas
        })
        
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

def dashboard(request):
    return render(request, "Pyquest/dashboard.html")



@csrf_exempt
@login_required
def salvar_tempo_estudo(request):
    """Salva o tempo de estudo do timer da home"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            tempo_segundos = int(data.get('tempo_segundos', 0))
            tipo = data.get('tipo', 'estudo_geral')
            
            print(f"⏱️ Salvando tempo de estudo: {tempo_segundos} segundos")
            
            if tempo_segundos <= 0:
                return JsonResponse({'success': False, 'error': 'Tempo inválido'})
            
            perfil = request.user.perfil
            
            # Salvar no perfil
            tempo_anterior = perfil.tempo_total_estudo
            perfil.tempo_total_estudo += tempo_segundos
            perfil.save()
            
            # Registrar atividade
            Atividade.objects.create(
                user=request.user,
                titulo=f"Estudo geral: {tempo_segundos // 60} minutos",
                xp_ganho=0  # Ou calcule XP baseado no tempo
            )
            
            # Formatar tempo para resposta
            tempo_total_segundos = perfil.tempo_total_estudo
            minutos_totais = tempo_total_segundos // 60
            segundos_restantes = tempo_total_segundos % 60
            horas = minutos_totais // 60
            minutos = minutos_totais % 60
            
            if horas > 0:
                tempo_formatado = f"{horas:02d}:{minutos:02d}:{segundos_restantes:02d}"
            else:
                tempo_formatado = f"{minutos:02d}:{segundos_restantes:02d}"
            
            print(f"✅ Tempo salvo! Anterior: {tempo_anterior}, Atual: {perfil.tempo_total_estudo}")
            
            return JsonResponse({
                'success': True, 
                'tempo_salvo': tempo_segundos,
                'tempo_total': perfil.tempo_total_estudo,
                'tempo_total_formatado': tempo_formatado,
                'message': f'Tempo de estudo registrado: {tempo_segundos // 60} minutos'
            })
            
        except Exception as e:
            print(f"❌ Erro ao salvar tempo estudo: {e}")
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
