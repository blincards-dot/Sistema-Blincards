# Sistema Blincards - Versão Online Corrigida

## Configuração no Render

Use estas configurações:

- Root Directory: deixe vazio
- Build Command: `pip install -r requirements.txt`
- Start Command: `gunicorn app:app`

## Banco de dados

O sistema funciona de duas formas:

1. Sem DATABASE_URL: usa SQLite automaticamente para testar online.
2. Com DATABASE_URL: usa PostgreSQL.

Para usar PostgreSQL no Render:

1. Crie um banco PostgreSQL no Render.
2. Copie a Internal Database URL.
3. No Web Service, vá em Environment e adicione:
   - DATABASE_URL = sua URL do PostgreSQL
   - SECRET_KEY = uma senha/chave qualquer segura

## Login inicial

Usuário: admin
Senha: admin123

## Observação importante

Ao enviar para o GitHub, envie os arquivos desta pasta na raiz do repositório. O arquivo `app.py` precisa ficar diretamente na raiz, junto com `requirements.txt` e `Procfile`.
