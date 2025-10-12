from django import forms
from django.core.exceptions import ValidationError

class ChapterForm(forms.Form):
    title = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
            'placeholder': 'Título do Capítulo'
        })
    )
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'w-full p-3 border border-gray-300 rounded-lg',
            'placeholder': 'Descrição do Capítulo',
            'rows': 3
        })
    )
    order = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(attrs={
            'class': 'w-full p-3 border border-gray-300 rounded-lg',
            'placeholder': 'Ordem (1, 2, 3...)'
        })
    )

class ModuleForm(forms.Form):
    title = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
            'placeholder': 'Título do Módulo'
        })
    )
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'w-full p-3 border border-gray-300 rounded-lg',
            'placeholder': 'Descrição do Módulo',
            'rows': 3
        })
    )
    order_in_chapter = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(attrs={
            'class': 'w-full p-3 border border-gray-300 rounded-lg',
            'placeholder': 'Ordem no Capítulo'
        })
    )

class TaskForm(forms.Form):
    title = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
            'placeholder': 'Título da Tarefa'
        })
    )
    has_theory = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'rounded border-gray-300 text-blue-600 focus:ring-blue-500'
        })
    )
    has_practice = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'rounded border-gray-300 text-blue-600 focus:ring-blue-500'
        })
    )

class TheoryContentForm(forms.Form):
    title = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
            'placeholder': 'Ex: Introdução ao Python'
        })
    )
    content = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'w-full p-4 border-0 focus:ring-0 resize-none',
            'rows': 12,
            'placeholder': 'Escreva o conteúdo teórico da aula aqui...\n\nVocê pode usar:\n- Títulos e subtítulos\n- Códigos de exemplo\n- Imagens ilustrativas\n- Listas e tópicos'
        })
    )
    estimated_time = forms.IntegerField(
        min_value=1,
        max_value=120,
        widget=forms.NumberInput(attrs={
            'class': 'w-full p-3 border border-gray-300 rounded-lg',
            'placeholder': 'Ex: 45'
        })
    )
    difficulty = forms.ChoiceField(
        choices=[
            ('beginner', 'Iniciante'),
            ('intermediate', 'Intermediário'),
            ('advanced', 'Avançado'),
        ],
        widget=forms.Select(attrs={
            'class': 'w-full p-3 border border-gray-300 rounded-lg'
        })
    )

class MultipleChoiceQuestionForm(forms.Form):
    question_text = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'w-full p-3 border border-gray-300 rounded-lg',
            'placeholder': 'Digite a pergunta...'
        })
    )
    option_1 = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'flex-1 p-2 border border-gray-300 rounded',
            'placeholder': 'Opção 1'
        })
    )
    option_2 = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'flex-1 p-2 border border-gray-300 rounded',
            'placeholder': 'Opção 2'
        })
    )
    option_3 = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'flex-1 p-2 border border-gray-300 rounded',
            'placeholder': 'Opção 3'
        })
    )
    option_4 = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'flex-1 p-2 border border-gray-300 rounded',
            'placeholder': 'Opção 4'
        })
    )
    correct_option = forms.ChoiceField(
        choices=[('1', 'Opção 1'), ('2', 'Opção 2'), ('3', 'Opção 3'), ('4', 'Opção 4')],
        widget=forms.RadioSelect(attrs={'class': 'text-blue-600'})
    )
    xp_value = forms.IntegerField(
        min_value=5,
        max_value=50,
        initial=10,
        widget=forms.NumberInput(attrs={
            'class': 'w-24 p-2 border border-gray-300 rounded'
        })
    )

class CodeQuestionForm(forms.Form):
    instructions = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'w-full p-3 border border-gray-300 rounded-lg',
            'placeholder': 'Descreva o que o aluno deve programar...',
            'rows': 3
        })
    )
    example_code = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'w-full p-3 border border-gray-300 rounded-lg font-mono text-sm',
            'placeholder': '// Código de exemplo\nprint(\"Hello World\")',
            'rows': 4
        })
    )
    expected_answer = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'w-full p-3 border border-gray-300 rounded-lg font-mono text-sm',
            'placeholder': '// Resposta correta\nprint(\"Hello World\")',
            'rows': 4
        })
    )
    xp_value = forms.IntegerField(
        min_value=10,
        max_value=100,
        initial=30,
        widget=forms.NumberInput(attrs={
            'class': 'w-24 p-2 border border-gray-300 rounded'
        })
    )

class FillBlankQuestionForm(forms.Form):
    text_with_blanks = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'w-full p-3 border border-gray-300 rounded-lg',
            'placeholder': 'Escreva o texto e use [lacuna] para criar lacunas...',
            'rows': 4
        })
    )
    blank_1 = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'flex-1 p-2 border border-gray-300 rounded',
            'placeholder': 'Resposta correta'
        })
    )
    blank_2 = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'flex-1 p-2 border border-gray-300 rounded',
            'placeholder': 'Resposta correta'
        })
    )
    blank_3 = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'flex-1 p-2 border border-gray-300 rounded',
            'placeholder': 'Resposta correta'
        })
    )
    xp_value = forms.IntegerField(
        min_value=5,
        max_value=50,
        initial=20,
        widget=forms.NumberInput(attrs={
            'class': 'w-24 p-2 border border-gray-300 rounded'
        })
    )

class PublishSettingsForm(forms.Form):
    publish_immediately = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'toggle-switch'})
    )
    allow_comments = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'toggle-switch'})
    )
    track_progress = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'toggle-switch'})
    )
    total_xp = forms.IntegerField(
        min_value=0,
        max_value=1000,
        initial=100,
        widget=forms.NumberInput(attrs={
            'class': 'w-full p-3 border border-gray-300 rounded-lg'
        })
    )