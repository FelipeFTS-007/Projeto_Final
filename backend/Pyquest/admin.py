from django.contrib import admin
from .models import Atividade

@admin.register(Atividade)
class AtividadeAdmin(admin.ModelAdmin):
    list_display = ("titulo", "user", "xp_ganho", "data")
    search_fields = ("titulo", "user__username")
    list_filter = ("data",)


from django.contrib import admin
from .models import Conquista

@admin.register(Conquista)
class ConquistaAdmin(admin.ModelAdmin):
    list_display = ("titulo", "raridade", "categoria")
    list_filter = ("raridade", "categoria")
    search_fields = ("titulo", "descricao")
