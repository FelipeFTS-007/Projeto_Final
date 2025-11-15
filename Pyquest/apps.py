# apps.py (da sua app PyQuest)
from django.apps import AppConfig

class PyquestConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'Pyquest'
    
    def ready(self):
        import Pyquest.signals  # Importe os signals