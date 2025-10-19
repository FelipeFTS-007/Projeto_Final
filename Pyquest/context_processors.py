from .models import Perfil
from django.contrib import messages

def custom_messages(request):
    """
    Filtra mensagens que não devem aparecer em páginas específicas
    """
    filtered_messages = []
    
    # Mensagens que NÃO devem aparecer no login
    blocked_in_login = [
        'Login realizado com sucesso!',
        'Perfil atualizado com sucesso!',
        'Conta criada com sucesso!'
    ]
    
    # Mensagens que NÃO devem aparecer no cadastro
    blocked_in_cadastro = [
        'Login realizado com sucesso!'
    ]
    
    for message in messages.get_messages(request):
        message_text = str(message)
        
        # Verifica se está na página de login
        if 'login' in request.path and any(blocked in message_text for blocked in blocked_in_login):
            continue  # Pula esta mensagem
            
        # Verifica se está na página de cadastro
        if 'cadastro' in request.path and any(blocked in message_text for blocked in blocked_in_cadastro):
            continue  # Pula esta mensagem
            
        filtered_messages.append(message)
    
    return {'custom_messages': filtered_messages}
def perfil_context(request):
    if request.user.is_authenticated:
        perfil, created = Perfil.objects.get_or_create(user=request.user)
        return {'perfil': perfil}
    return {}
