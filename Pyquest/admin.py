from django.contrib import admin
from .models import *
@admin.register(Atividade)
class AtividadeAdmin(admin.ModelAdmin):
    list_display = ("titulo", "user", "xp_ganho", "data")
    search_fields = ("titulo", "user__username")
    list_filter = ("data",)


@admin.register(Conquista)
class ConquistaAdmin(admin.ModelAdmin):
    list_display = ("titulo", "raridade", "categoria")
    list_filter = ("raridade", "categoria")
    search_fields = ("titulo", "descricao")





@admin.register(Perfil)
class PerfilAdmin(admin.ModelAdmin):
    list_display = ("user", "xp", "nivel", "vidas", "sequencia", "licoes")
    search_fields = ("user__username",)
    list_filter = ("nivel",)


@admin.register(Progresso)
class ProgressoAdmin(admin.ModelAdmin):
    list_display = ("user", "data", "percentual", "xp_ganho", "missoes_concluidas")
    search_fields = ("user__username",)
    list_filter = ("data",)



class ModuloInline(admin.TabularInline):
    model = Modulo
    extra = 1


@admin.register(Capitulo)
class CapituloAdmin(admin.ModelAdmin):
    list_display = ("titulo", "ordem", "ativo", "criado_em")
    search_fields = ("titulo",)
    inlines = [ModuloInline]


class AulaInline(admin.TabularInline):
    model = Aula
    extra = 1


@admin.register(Modulo)
class ModuloAdmin(admin.ModelAdmin):
    list_display = ("titulo", "capitulo", "ordem", "ativo")
    search_fields = ("titulo", "capitulo__titulo")
    inlines = [AulaInline]




@admin.register(Notificacao)
class NotificacaoAdmin(admin.ModelAdmin):
    list_display = ("usuario", "mensagem", "lida", "enviada_em")
    search_fields = ("usuario__username", "mensagem")
    list_filter = ("lida", "enviada_em")



