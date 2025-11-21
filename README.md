
## 🛠 Instalação e Configuração

### **GUIA DE INSTALAÇÃO E CONFIGURAÇÃO – Plataforma Gamificada de Ensino de Python (PyQuest)**

---

## **1. Requisitos do Sistema**

**Requisitos obrigatórios:**

* Python 3.10 ou superior
* PostgreSQL 14 ou superior
* Git
* Pip
* Virtualenv (opcional, recomendado)

**Ambiente sugerido:**

* Windows, Linux ou macOS
* Navegador atualizado (Chrome, Firefox, Edge ou Safari)

---

## **2. Clonar o Repositório do Projeto**

No terminal, execute:
git clone [https://github.com/FelipeFTS-007/Projeto_Final.git](https://github.com/FelipeFTS-007/Projeto_Final.git)
cd Projeto_Final

---

## **3. Criar e Ativar o Ambiente Virtual**

**Windows:**
python -m venv venv
venv\Scripts\activate

**Linux ou macOS:**
python3 -m venv venv
source venv/bin/activate

---

## **4. Instalar Dependências do Projeto**

pip install -r requirements.txt

---

## **5. Criar e Configurar o Banco de Dados PostgreSQL**

Abra o terminal do PostgreSQL:
psql -U postgres

Dentro do console, execute:
CREATE DATABASE projeto_python;
CREATE USER projeto_user WITH PASSWORD 'sua_senha';
GRANT ALL PRIVILEGES ON DATABASE projeto_python TO projeto_user;

(Substitua *sua_senha* pela senha desejada.)

---

## **6. Configurar Conexão no settings.py**

Abra o arquivo **settings.py** e edite a seção **DATABASES** com:

ENGINE: django.db.backends.postgresql
NAME: projeto_python
USER: projeto_user
PASSWORD: sua_senha
HOST: localhost
PORT: 5432

*(Lembre-se: no código real use aspas e a indentação correta.)*

---

## **7. Criar as Tabelas do Sistema (Migrações)**

python manage.py migrate

---

## **8. Criar Superusuário (Painel Administrativo)**

python manage.py createsuperuser
Preencha os dados solicitados.

---

## **9. Executar o Servidor de Desenvolvimento**

python manage.py runserver

A aplicação estará disponível em:
[http://127.0.0.1:8000/](http://127.0.0.1:8000/)

---

## **10. Acessar a Plataforma**

Abra no navegador:
[http://127.0.0.1:8000/](http://127.0.0.1:8000/)

---

## **11. Observações Importantes**

* A execução de código Python nas questões é feita diretamente no navegador usando **Pyodide**.
* O backend Django + PostgreSQL registra **XP, progresso, estatísticas e ranking**.
* Para produção, recomenda-se o uso de **Gunicorn + Nginx**, além de **Docker**.


