from django.core.management.base import BaseCommand
from django.utils import timezone
from Pyquest.models import Perfil

class Command(BaseCommand):
    help = 'Reseta o status de atividade diária de todos os usuários'
    
    def handle(self, *args, **options):
        perfis = Perfil.objects.all()
        for perfil in perfis:
            perfil.resetar_atividade_diaria()
        
        self.stdout.write(
            self.style.SUCCESS(f'Resetada atividade diária para {perfis.count()} usuários')
        )