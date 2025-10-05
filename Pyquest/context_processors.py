from .models import Perfil

def perfil_context(request):
    if request.user.is_authenticated:
        perfil, created = Perfil.objects.get_or_create(user=request.user)
        return {'perfil': perfil}
    return {}
