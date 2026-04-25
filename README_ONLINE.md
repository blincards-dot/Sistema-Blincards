# Produção Blincards - Versão Online

Sistema Flask pronto para rodar localmente ou online com PostgreSQL.

## Acesso inicial

- Usuário: `admin`
- Senha: `admin123`

Troque essa senha depois do primeiro acesso.

## Rodar localmente no Windows

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Abra:

```text
http://127.0.0.1:5000
```

Localmente, se você não configurar `DATABASE_URL`, o sistema usa SQLite automaticamente.

## Publicar online no Render

1. Crie um banco em **New + > PostgreSQL**.
2. Copie a **Internal Database URL**.
3. Crie um **Web Service** conectado ao GitHub.
4. Configure:

Build Command:

```bash
pip install -r requirements.txt
```

Start Command:

```bash
gunicorn app:app
```

Environment Variables:

```text
SECRET_KEY=uma_chave_forte_qualquer
DATABASE_URL=cole_a_internal_database_url_do_postgresql
UPLOAD_FOLDER=static/uploads
```

## Publicar online no Railway

Variáveis:

```text
SECRET_KEY=uma_chave_forte_qualquer
DATABASE_URL=${{Postgres.DATABASE_URL}}
UPLOAD_FOLDER=static/uploads
```

Start Command:

```bash
gunicorn app:app
```

## Observação sobre upload de arquivos

Em hospedagens gratuitas, arquivos enviados podem ser perdidos em redeploy ou reinício do servidor. Para uso profissional definitivo, o ideal é usar armazenamento externo, como Cloudinary, S3 ou Supabase Storage.
