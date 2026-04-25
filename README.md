# Sistema de Produção Blincards - Versão PRO

Sistema web local em Python Flask para controle de ordens de produção de gráfica rápida.

## Recursos da versão PRO

- Login e senha
- Área administrativa para usuários
- Usuário comum acessa apenas suas próprias ordens
- Cadastro de OC com número automático: OC-0001, OC-0002...
- Cliente, material, quantidade, status, descrição até 500 caracteres
- Prazo de entrega
- Upload de anexo da ordem: imagem, PDF ou arte de referência
- Status Em produção e Concluído
- Identificação automática de ordens atrasadas
- Busca rápida por OC, cliente ou material
- Dashboard com total, em produção, atrasadas e concluídas
- Ranking de usuários por ordens concluídas
- Relatórios por dia, mês e ano com filtro por usuário
- Botão de imprimir ficha de produção
- Layout responsivo com menu hamburger
- Cores da Blincards: laranja e ciano

## Como instalar no Windows

1. Instale o Python em https://www.python.org
2. Marque a opção **Add Python to PATH** durante a instalação.
3. Extraia este ZIP.
4. Abra o CMD dentro da pasta do projeto.
5. Instale as dependências:

```bash
python -m pip install -r requirements.txt
```

6. Rode o sistema:

```bash
python app.py
```

7. Abra no navegador:

```text
http://127.0.0.1:5000
```

## Login inicial

Usuário: `admin`  
Senha: `admin123`

## Observações

- O banco SQLite será criado automaticamente em `instance/grafica_producao.db`.
- Os anexos ficam na pasta `static/uploads`.
- Para colocar online depois, o projeto pode ser adaptado para PostgreSQL e servidor web.
