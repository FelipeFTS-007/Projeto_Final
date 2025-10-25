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
from django.views.decorators.http import require_http_methods
from django.db import models




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
                dificuldade=data.get('dificuldade', 'beginner')  # ← ADICIONE ESTA LINHA
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

# views.py - VIEW editar_conteudo COMPLETAMENTE REWRITTEN
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
            
            # ATUALIZAR A AULA COM OS NOVOS CAMPOS
            aula.titulo_aula = titulo_aula
            aula.titulo_teoria = titulo_teoria
            aula.descricao_breve = descricao_breve
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
    
    capitulos_com_stats = []
    
    for capitulo in capitulos:
        total_modulos = capitulo.modulos.filter(ativo=True).count()
        total_aulas = Aula.objects.filter(modulo__capitulo=capitulo, ativo=True).count()
        
        # **PROGRESSO REAL DO USUÁRIO**
        # Contar módulos concluídos pelo usuário (você precisaria criar este modelo)
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
# views.py - ATUALIZE a função modulos (CORREÇÃO DO PROGRESSO)
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
                
                # Contar aulas ativas do módulo
                total_aulas = aulas_do_modulo.count()
                
                # Contar aulas concluídas pelo usuário - VERIFICAÇÃO CORRETA
                aulas_concluidas = AulaConcluida.objects.filter(
                    usuario=request.user, 
                    aula__in=aulas_do_modulo
                ).count()
                
                # Calcular progresso - SE NÃO HÁ AULAS, PROGRESSO É 0
                if total_aulas > 0:
                    progresso_percentual = int((aulas_concluidas / total_aulas) * 100)
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
                    'total_aulas': total_aulas,
                    'aulas_concluidas': aulas_concluidas,
                    'progresso_percentual': progresso_percentual,
                    'xp_total': xp_total,
                    'tempo_total_modulo': tempo_total_modulo,
                })
            
            # Progresso geral do capítulo - CORREÇÃO
            total_modulos_capitulo = modulos.count()
            
            # Contar módulos onde TODAS as aulas foram concluídas
            modulos_concluidos_capitulo = 0
            for mod_stat in modulos_com_stats:
                if mod_stat['total_aulas'] > 0 and mod_stat['aulas_concluidas'] == mod_stat['total_aulas']:
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
    
    # Fallback se não houver capítulo específico
    capitulo = Capitulo.objects.filter(ativo=True).first()
    if capitulo:
        modulos = Modulo.objects.filter(capitulo=capitulo, ativo=True).order_by('ordem')
        
        modulos_com_stats = []
        for modulo in modulos:
            # Buscar aulas do módulo
            aulas_do_modulo = Aula.objects.filter(modulo=modulo, ativo=True)
            
            total_aulas = aulas_do_modulo.count()
            
            # Contar aulas concluídas pelo usuário - VERIFICAÇÃO CORRETA
            aulas_concluidas = AulaConcluida.objects.filter(
                usuario=request.user, 
                aula__in=aulas_do_modulo
            ).count()
            
            if total_aulas > 0:
                progresso_percentual = int((aulas_concluidas / total_aulas) * 100)
            else:
                progresso_percentual = 0
            
            # XP total do módulo
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
                'total_aulas': total_aulas,
                'aulas_concluidas': aulas_concluidas,
                'progresso_percentual': progresso_percentual,
                'xp_total': xp_total,
                'tempo_total_modulo': tempo_total_modulo,
            })
        
        total_modulos_capitulo = modulos.count()
        
        # Contar módulos onde TODAS as aulas foram concluídas
        modulos_concluidos_capitulo = 0
        for mod_stat in modulos_com_stats:
            if mod_stat['total_aulas'] > 0 and mod_stat['aulas_concluidas'] == mod_stat['total_aulas']:
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


# ---------- PÁGINAS EXISTENTES ----------

def tarefas(request):
    return render(request, "Pyquest/tarefas.html")

def teoria(request):
    return render(request, "Pyquest/teoria.html")

def pratica(request):
    return render(request, "Pyquest/pratica.html")



def dashboard(request):
    return render(request, "Pyquest/dashboard.html")




