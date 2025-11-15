from django.utils import timezone
from django.contrib.auth.models import User

class StreakMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Verificar streak ANTES de processar a requisição
        if request.user.is_authenticated:
            try:
                perfil = request.user.perfil
                # Verificar automaticamente o streak
                perfil.verificar_streak_automatico()
            except Exception as e:
                # Log do erro mas não quebra a aplicação
                print(f"❌ Erro ao verificar streak: {e}")
        
        response = self.get_response(request)
        return response