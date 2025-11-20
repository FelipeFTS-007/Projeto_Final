## 🛠 Instalação e Configuração
GUIA DE INSTALAÇÃO E CONFIGURAÇÃO – Plataforma Gamificada de Ensino de Python PyQuest
________________________________________
1. Requisitos do Sistema
Requisitos obrigatórios:
•	Python versão 3.10 ou superior
•	PostgreSQL versão 14 ou superior
•	Git
•	Pip
•	Virtualenv (opcional, recomendado)
Ambiente sugerido:
•	Windows, Linux ou macOS
•	Navegador atualizado (Chrome, Firefox, Edge ou Safari)
________________________________________
2. Clonar o Repositório do Projeto
No terminal, digite:
git clone https://github.com/FelipeFTS-007/Projeto_Final.git
cd Projeto_Final
________________________________________
3. Criar e Ativar o Ambiente Virtual
Para Windows:
python -m venv venv
venv\Scripts\activate
Para Linux ou macOS:
python3 -m venv venv
source venv/bin/activate
________________________________________
4. Instalar Dependências do Projeto
Com o ambiente virtual ativo, execute:
pip install -r requeriments.txt
________________________________________
5. Criar e Configurar o Banco de Dados PostgreSQL
Abra o terminal do PostgreSQL digitando:
psql -U postgres
Dentro do PostgreSQL, execute os seguintes comandos:
CREATE DATABASE projeto_python;
CREATE USER projeto_user WITH PASSWORD 'sua_senha';
GRANT ALL PRIVILEGES ON DATABASE projeto_python TO projeto_user;
Substitua o texto sua_senha pela senha que desejar.
________________________________________
6. Configurar Conexão no settings.py
Abra o arquivo settings.py e localize a seção DATABASES.
Preencha com as seguintes informações:
ENGINE: django.db.backends.postgresql
NAME: projeto_python
USER: projeto_user
PASSWORD: sua_senha
HOST: localhost
PORT: 5432
(O texto acima é para o documento; no código real, mantenha as aspas e indentação do Django.)
________________________________________
7. Criar as Tabelas do Sistema (Migrações)
No terminal, execute:
python manage.py migrate
Isso irá criar todas as tabelas do banco PostgreSQL.
________________________________________
8. Criar Superusuário para Acessar o Painel Administrativo
Execute:
python manage.py createsuperuser
Preencha usuário, e-mail e senha conforme solicitado.
________________________________________
9. Executar o Servidor de Desenvolvimento
Use o comando:
python manage.py runserver
Se funcionar, o terminal exibirá um endereço semelhante a:
http://127.0.0.1:8000/
________________________________________
10. Acessar a Plataforma
Abra o navegador e digite:
http://127.0.0.1:8000/
________________________________________
11. Observações Importantes
•	A execução de código Python nas questões é feita diretamente no navegador usando Pyodide.
•	O backend Django, com PostgreSQL, é responsável apenas por registrar XP, progresso, estatísticas e ranking.
•	Para ambientes de produção, recomenda-se usar servidores como Gunicorn e Nginx, e preferencialmente Docker.
