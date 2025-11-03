from django.core.management.base import BaseCommand
from django.core.files import File
import os
from Pyquest.models import Conquista

class Command(BaseCommand):
    help = 'Popula o banco com conquistas iniciais com imagens - LIMPA E RECRIA TUDO'

    def handle(self, *args, **options):
        # PERGUNTAR SE QUER LIMPAR TUDO
        self.stdout.write(self.style.WARNING('⚠️  Isso vai APAGAR TODAS as conquistas existentes e criar novas!'))
        confirm = input('Digite "SIM" para continuar: ')
        
        if confirm != 'SIM':
            self.stdout.write(self.style.ERROR('❌ Operação cancelada.'))
            return

        # LIMPAR TODAS AS CONQUISTAS EXISTENTES
        total_antigas = Conquista.objects.count()
        Conquista.objects.all().delete()
        self.stdout.write(self.style.SUCCESS(f'🗑️  {total_antigas} conquistas antigas removidas.'))

        # Caminho base para as imagens
        MEDIA_BASE = 'media/conquistas'
        
        conquistas = [
            # ========== CONQUISTAS COMUNS ==========
            {
                'titulo': 'Primeiros Passos', 
                'descricao': 'Alcance 100 XP', 
                'tipo_evento': 'xp_total', 
                'valor_requerido': 100, 
                'xp_recompensa': 10, 
                'raridade': 'comum', 
                'categoria': 'progresso',
                'ordem': 1,
                'icone_path': f'{MEDIA_BASE}/comum/first-steps.png'
            },
            {
                'titulo': 'Curioso', 
                'descricao': 'Conclua sua primeira aula', 
                'tipo_evento': 'aulas_concluidas', 
                'valor_requerido': 1, 
                'xp_recompensa': 10, 
                'raridade': 'comum', 
                'categoria': 'progresso',
                'ordem': 2,
                'icone_path': f'{MEDIA_BASE}/comum/programming.png'
            },
            {
                'titulo': 'Primeira Postagem', 
                'descricao': 'Faça sua primeira postagem no fórum', 
                'tipo_evento': 'postagens_forum', 
                'valor_requerido': 1, 
                'xp_recompensa': 10, 
                'raridade': 'comum', 
                'categoria': 'especial',
                'ordem': 3,
                'icone_path': f'{MEDIA_BASE}/comum/online-discussion.png'
            },
            {
                'titulo': 'Iniciante', 
                'descricao': 'Alcance o nível 5', 
                'tipo_evento': 'nivel_atingido', 
                'valor_requerido': 5, 
                'xp_recompensa': 15, 
                'raridade': 'comum', 
                'categoria': 'progresso',
                'ordem': 4,
                'icone_path': f'{MEDIA_BASE}/comum/up-arrow.png'
            },

            # ========== CONQUISTAS RARAS ==========
            {
                'titulo': 'Aprendiz', 
                'descricao': 'Alcance 500 XP', 
                'tipo_evento': 'xp_total', 
                'valor_requerido': 500, 
                'xp_recompensa': 25, 
                'raridade': 'rara', 
                'categoria': 'progresso',
                'ordem': 5,
                'icone_path': f'{MEDIA_BASE}/rara/education.png'
            },
            {
                'titulo': 'Intermediário', 
                'descricao': 'Alcance o nível 10', 
                'tipo_evento': 'nivel_atingido', 
                'valor_requerido': 10, 
                'xp_recompensa': 30, 
                'raridade': 'rara', 
                'categoria': 'progresso',
                'ordem': 6,
                'icone_path': f'{MEDIA_BASE}/rara/growth.png'
            },
            {
                'titulo': 'Estudante', 
                'descricao': 'Conclua 10 aulas', 
                'tipo_evento': 'aulas_concluidas', 
                'valor_requerido': 10, 
                'xp_recompensa': 25, 
                'raridade': 'rara', 
                'categoria': 'progresso',
                'ordem': 7,
                'icone_path': f'{MEDIA_BASE}/rara/books.png'
            },
            {
                'titulo': 'Comentarista', 
                'descricao': 'Faça 10 comentários', 
                'tipo_evento': 'comentarios', 
                'valor_requerido': 10, 
                'xp_recompensa': 15, 
                'raridade': 'rara', 
                'categoria': 'especial',
                'ordem': 8,
                'icone_path': f'{MEDIA_BASE}/rara/cost-effective.png'
            },
            {
                'titulo': 'Dedicado', 
                'descricao': 'Estude por 3 dias consecutivos', 
                'tipo_evento': 'sequencia_dias', 
                'valor_requerido': 3, 
                'xp_recompensa': 20, 
                'raridade': 'rara', 
                'categoria': 'dominio',
                'ordem': 9,
                'icone_path': f'{MEDIA_BASE}/rara/calendar.png'
            },
            {
                'titulo': 'Colecionador', 
                'descricao': 'Desbloqueie 5 conquistas', 
                'tipo_evento': 'conquistas_desbloqueadas', 
                'valor_requerido': 5, 
                'xp_recompensa': 20, 
                'raridade': 'rara', 
                'categoria': 'especial',
                'ordem': 10,
                'icone_path': f'{MEDIA_BASE}/rara/medal.png'
            },

            # ========== CONQUISTAS ÉPICAS ==========
            {
                'titulo': 'Estudante Dedicado', 
                'descricao': 'Alcance 1000 XP', 
                'tipo_evento': 'xp_total', 
                'valor_requerido': 1000, 
                'xp_recompensa': 50, 
                'raridade': 'epica', 
                'categoria': 'progresso',
                'ordem': 11,
                'icone_path': f'{MEDIA_BASE}/epica/graduated.png'
            },
            {
                'titulo': 'Viciado em Python', 
                'descricao': 'Estude por 7 dias consecutivos', 
                'tipo_evento': 'sequencia_dias', 
                'valor_requerido': 7, 
                'xp_recompensa': 50, 
                'raridade': 'epica', 
                'categoria': 'dominio',
                'ordem': 12,
                'icone_path': f'{MEDIA_BASE}/epica/fire.png'
            },
            {
                'titulo': 'Mestre do Fórum', 
                'descricao': 'Faça 50 postagens no fórum', 
                'tipo_evento': 'postagens_forum', 
                'valor_requerido': 50, 
                'xp_recompensa': 40, 
                'raridade': 'epica', 
                'categoria': 'especial',
                'ordem': 13,
                'icone_path': f'{MEDIA_BASE}/epica/conference.png'
            },
            {
                'titulo': 'Especialista', 
                'descricao': 'Alcance o nível 20', 
                'tipo_evento': 'nivel_atingido', 
                'valor_requerido': 20, 
                'xp_recompensa': 60, 
                'raridade': 'epica', 
                'categoria': 'progresso',
                'ordem': 14,
                'icone_path': f'{MEDIA_BASE}/epica/computer-specialist.png'
            },

            # ========== CONQUISTAS LENDÁRIAS ==========
            {
                'titulo': 'Lenda do Python', 
                'descricao': 'Alcance 5000 XP', 
                'tipo_evento': 'xp_total', 
                'valor_requerido': 5000, 
                'xp_recompensa': 100, 
                'raridade': 'lendaria', 
                'categoria': 'progresso',
                'ordem': 15,
                'icone_path': f'{MEDIA_BASE}/lendaria/snake.png'
            },
            {
                'titulo': 'Mestre Supremo', 
                'descricao': 'Alcance o nível 30', 
                'tipo_evento': 'nivel_atingido', 
                'valor_requerido': 30, 
                'xp_recompensa': 100, 
                'raridade': 'lendaria', 
                'categoria': 'progresso',
                'ordem': 16,
                'icone_path': f'{MEDIA_BASE}/lendaria/crown.png'
            },
            {
                'titulo': 'Deus do Código', 
                'descricao': 'Conclua 100 aulas', 
                'tipo_evento': 'aulas_concluidas', 
                'valor_requerido': 100, 
                'xp_recompensa': 100, 
                'raridade': 'lendaria', 
                'categoria': 'progresso',
                'ordem': 17,
                'icone_path': f'{MEDIA_BASE}/lendaria/binary.png'
            },
            {
                'titulo': 'Lenda Viva', 
                'descricao': 'Estude por 30 dias consecutivos', 
                'tipo_evento': 'sequencia_dias', 
                'valor_requerido': 30, 
                'xp_recompensa': 150, 
                'raridade': 'lendaria', 
                'categoria': 'dominio',
                'ordem': 18,
                'icone_path': f'{MEDIA_BASE}/lendaria/coin.png'
            },
            {
                'titulo': 'Completista', 
                'descricao': 'Desbloqueie todas as conquistas', 
                'tipo_evento': 'conquistas_desbloqueadas', 
                'valor_requerido': 18,  # Total de conquistas
                'xp_recompensa': 200, 
                'raridade': 'lendaria', 
                'categoria': 'especial',
                'ordem': 19,
                'icone_path': f'{MEDIA_BASE}/lendaria/trophy.png'
            },
        ]
        
        criadas = 0
        com_erro_icone = 0
        
        for conquista_data in conquistas:
            # Criar conquista
            conquista = Conquista.objects.create(
                titulo=conquista_data['titulo'],
                descricao=conquista_data['descricao'],
                tipo_evento=conquista_data['tipo_evento'],
                valor_requerido=conquista_data['valor_requerido'],
                xp_recompensa=conquista_data['xp_recompensa'],
                raridade=conquista_data['raridade'],
                categoria=conquista_data['categoria'],
                ordem=conquista_data['ordem'],
                ativo=True
            )
            
            # Tentar adicionar ícone
            if 'icone_path' in conquista_data:
                icone_path = conquista_data['icone_path']
                if os.path.exists(icone_path):
                    try:
                        with open(icone_path, 'rb') as f:
                            conquista.icone.save(
                                os.path.basename(icone_path),
                                File(f),
                                save=True
                            )
                        self.stdout.write(self.style.SUCCESS(f'✅ {conquista.raridade.upper()}: {conquista.titulo}'))
                    except Exception as e:
                        self.stdout.write(self.style.WARNING(f'⚠️  {conquista.titulo} (sem ícone): {e}'))
                        com_erro_icone += 1
                else:
                    self.stdout.write(self.style.WARNING(f'⚠️  {conquista.titulo} (arquivo não encontrado: {icone_path})'))
                    com_erro_icone += 1
            else:
                self.stdout.write(self.style.SUCCESS(f'✅ {conquista.raridade.upper()}: {conquista.titulo}'))
            
            criadas += 1
        
        # Estatísticas finais
        self.stdout.write(self.style.SUCCESS(f'\n🎉 CONCLUÍDO!'))
        self.stdout.write(f'📊 Total criadas: {criadas} conquistas')
        self.stdout.write(f'🏆 Comuns: {Conquista.objects.filter(raridade="comum").count()}')
        self.stdout.write(f'🔵 Raras: {Conquista.objects.filter(raridade="rara").count()}')
        self.stdout.write(f'🟣 Épicas: {Conquista.objects.filter(raridade="epica").count()}')
        self.stdout.write(f'🟡 Lendárias: {Conquista.objects.filter(raridade="lendaria").count()}')
        
        if com_erro_icone > 0:
            self.stdout.write(self.style.WARNING(f'⚠️  {com_erro_icone} conquistas sem ícones (arquivos não encontrados)'))