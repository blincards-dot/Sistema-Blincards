from datetime import datetime, date
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect, text
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "troque-esta-chave-secreta")

# Banco online: use DATABASE_URL do PostgreSQL.
# Banco local: se não existir DATABASE_URL, usa SQLite automaticamente.
database_url = os.environ.get("DATABASE_URL", "sqlite:///grafica_producao.db")
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = os.environ.get("UPLOAD_FOLDER", os.path.join(app.root_path, "static", "uploads"))
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024

db = SQLAlchemy(app)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    usuario = db.Column(db.String(80), unique=True, nullable=False)
    senha_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    ativo = db.Column(db.Boolean, default=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    ordens = db.relationship("Order", backref="responsavel", lazy=True)

    def set_password(self, senha):
        self.senha_hash = generate_password_hash(senha)

    def check_password(self, senha):
        return check_password_hash(self.senha_hash, senha)


class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    numero_oc = db.Column(db.String(30), unique=True, nullable=True)
    cliente = db.Column(db.String(160), nullable=False)
    material = db.Column(db.String(160), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False, default=1)
    descricao = db.Column(db.String(500), nullable=True)
    prazo_entrega = db.Column(db.Date, nullable=True)
    arquivo = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(30), nullable=False, default="Em produção")
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    concluido_em = db.Column(db.DateTime, nullable=True)

    @property
    def atrasada(self):
        return bool(self.prazo_entrega and self.status != "Concluído" and self.prazo_entrega < date.today())


def gerar_numero_oc():
    ultima = Order.query.order_by(Order.id.desc()).first()
    proximo = (ultima.id + 1) if ultima else 1
    return f"OC-{proximo:04d}"


def salvar_upload(arquivo):
    if not arquivo or not arquivo.filename:
        return None
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    nome_seguro = secure_filename(arquivo.filename)
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    nome_final = f"{timestamp}_{nome_seguro}"
    arquivo.save(os.path.join(app.config["UPLOAD_FOLDER"], nome_final))
    return nome_final


def parse_data(valor):
    if not valor:
        return None
    try:
        return datetime.strptime(valor, "%Y-%m-%d").date()
    except ValueError:
        return None


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            flash("Faça login para continuar.", "warning")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped_view


def admin_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if not session.get("is_admin"):
            flash("Acesso permitido apenas para administradores.", "danger")
            return redirect(url_for("dashboard"))
        return view(*args, **kwargs)
    return wrapped_view


def usuario_logado():
    if "user_id" not in session:
        return None
    return User.query.get(session["user_id"])


@app.context_processor
def inject_user():
    return {"usuario_logado": usuario_logado()}


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = request.form.get("usuario", "").strip()
        senha = request.form.get("senha", "")
        user = User.query.filter_by(usuario=usuario, ativo=True).first()
        if user and user.check_password(senha):
            session.clear()
            session["user_id"] = user.id
            session["nome"] = user.nome
            session["is_admin"] = user.is_admin
            flash(f"Bem-vindo, {user.nome}!", "success")
            return redirect(url_for("dashboard"))
        flash("Usuário ou senha inválidos.", "danger")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Você saiu do sistema.", "info")
    return redirect(url_for("login"))


@app.route("/")
@login_required
def dashboard():
    if session.get("is_admin"):
        base = Order.query
    else:
        base = Order.query.filter_by(user_id=session["user_id"])

    total = base.count()
    em_producao = base.filter_by(status="Em produção").count()
    concluidas = base.filter_by(status="Concluído").count()
    atrasadas = base.filter(Order.status != "Concluído", Order.prazo_entrega < date.today()).count()

    ranking = (
        db.session.query(User.nome, db.func.count(Order.id).label("total"))
        .join(Order, User.id == Order.user_id)
        .filter(Order.status == "Concluído")
        .group_by(User.id)
        .order_by(db.desc("total"))
        .limit(10)
        .all()
    )

    ultimas = base.order_by(Order.criado_em.desc()).limit(8).all()
    return render_template("dashboard.html", total=total, em_producao=em_producao,
                           concluidas=concluidas, atrasadas=atrasadas, ranking=ranking, ultimas=ultimas)


@app.route("/ordens")
@login_required
def ordens():
    status = request.args.get("status", "")
    busca = request.args.get("busca", "").strip()

    query = Order.query if session.get("is_admin") else Order.query.filter_by(user_id=session["user_id"])
    if status:
        query = query.filter_by(status=status)
    if busca:
        query = query.filter(db.or_(Order.cliente.ilike(f"%{busca}%"), Order.material.ilike(f"%{busca}%"), Order.numero_oc.ilike(f"%{busca}%")))

    ordens_lista = query.order_by(Order.criado_em.desc()).all()
    return render_template("ordens.html", ordens=ordens_lista, status=status, busca=busca)


@app.route("/ordens/nova", methods=["GET", "POST"])
@login_required
def nova_ordem():
    if request.method == "POST":
        status = request.form.get("status", "Em produção")
        ordem = Order(
            numero_oc=gerar_numero_oc(),
            cliente=request.form.get("cliente", "").strip(),
            material=request.form.get("material", "").strip(),
            quantidade=int(request.form.get("quantidade") or 1),
            descricao=request.form.get("descricao", "").strip()[:500],
            prazo_entrega=parse_data(request.form.get("prazo_entrega")),
            arquivo=salvar_upload(request.files.get("arquivo")),
            status=status,
            user_id=session["user_id"],
            concluido_em=datetime.utcnow() if status == "Concluído" else None
        )
        db.session.add(ordem)
        db.session.commit()
        flash("Ordem cadastrada com sucesso.", "success")
        return redirect(url_for("ordens"))
    return render_template("ordem_form.html", ordem=None)


@app.route("/ordens/<int:ordem_id>/editar", methods=["GET", "POST"])
@login_required
def editar_ordem(ordem_id):
    ordem = Order.query.get_or_404(ordem_id)
    if not session.get("is_admin") and ordem.user_id != session["user_id"]:
        flash("Você não pode editar esta ordem.", "danger")
        return redirect(url_for("ordens"))

    if request.method == "POST":
        status_antigo = ordem.status
        ordem.cliente = request.form.get("cliente", "").strip()
        ordem.material = request.form.get("material", "").strip()
        ordem.quantidade = int(request.form.get("quantidade") or 1)
        ordem.descricao = request.form.get("descricao", "").strip()[:500]
        ordem.prazo_entrega = parse_data(request.form.get("prazo_entrega"))
        novo_arquivo = salvar_upload(request.files.get("arquivo"))
        if novo_arquivo:
            ordem.arquivo = novo_arquivo
        ordem.status = request.form.get("status", "Em produção")
        if ordem.status == "Concluído" and status_antigo != "Concluído":
            ordem.concluido_em = datetime.utcnow()
        elif ordem.status == "Em produção":
            ordem.concluido_em = None
        db.session.commit()
        flash("Ordem atualizada.", "success")
        return redirect(url_for("ordens"))
    return render_template("ordem_form.html", ordem=ordem)


@app.route("/uploads/<path:nome>")
@login_required
def arquivo_upload(nome):
    return send_from_directory(app.config["UPLOAD_FOLDER"], nome)


@app.route("/ordens/<int:ordem_id>/imprimir")
@login_required
def imprimir_ordem(ordem_id):
    ordem = Order.query.get_or_404(ordem_id)
    if not session.get("is_admin") and ordem.user_id != session["user_id"]:
        flash("Você não pode imprimir esta ordem.", "danger")
        return redirect(url_for("ordens"))
    return render_template("imprimir_ordem.html", ordem=ordem)


@app.route("/ordens/<int:ordem_id>/concluir")
@login_required
def concluir_ordem(ordem_id):
    ordem = Order.query.get_or_404(ordem_id)
    if not session.get("is_admin") and ordem.user_id != session["user_id"]:
        flash("Você não pode concluir esta ordem.", "danger")
        return redirect(url_for("ordens"))
    ordem.status = "Concluído"
    ordem.concluido_em = datetime.utcnow()
    db.session.commit()
    flash("Ordem marcada como concluída.", "success")
    return redirect(url_for("ordens"))


@app.route("/ordens/<int:ordem_id>/excluir", methods=["POST"])
@login_required
def excluir_ordem(ordem_id):
    ordem = Order.query.get_or_404(ordem_id)
    if not session.get("is_admin") and ordem.user_id != session["user_id"]:
        flash("Você não pode excluir esta ordem.", "danger")
        return redirect(url_for("ordens"))
    db.session.delete(ordem)
    db.session.commit()
    flash("Ordem excluída.", "info")
    return redirect(url_for("ordens"))


@app.route("/usuarios")
@login_required
@admin_required
def usuarios():
    return render_template("usuarios.html", usuarios=User.query.order_by(User.nome).all())


@app.route("/usuarios/novo", methods=["GET", "POST"])
@login_required
@admin_required
def novo_usuario():
    if request.method == "POST":
        user = User(
            nome=request.form.get("nome", "").strip(),
            usuario=request.form.get("usuario", "").strip(),
            is_admin=bool(request.form.get("is_admin")),
            ativo=True
        )
        user.set_password(request.form.get("senha", "123456"))
        db.session.add(user)
        try:
            db.session.commit()
            flash("Usuário cadastrado.", "success")
            return redirect(url_for("usuarios"))
        except Exception:
            db.session.rollback()
            flash("Esse nome de usuário já existe.", "danger")
    return render_template("usuario_form.html", user=None)


@app.route("/usuarios/<int:user_id>/editar", methods=["GET", "POST"])
@login_required
@admin_required
def editar_usuario(user_id):
    user = User.query.get_or_404(user_id)
    if request.method == "POST":
        user.nome = request.form.get("nome", "").strip()
        user.usuario = request.form.get("usuario", "").strip()
        user.is_admin = bool(request.form.get("is_admin"))
        user.ativo = bool(request.form.get("ativo"))
        nova_senha = request.form.get("senha", "").strip()
        if nova_senha:
            user.set_password(nova_senha)
        db.session.commit()
        flash("Usuário atualizado.", "success")
        return redirect(url_for("usuarios"))
    return render_template("usuario_form.html", user=user)


@app.route("/usuarios/<int:user_id>/excluir", methods=["POST"])
@login_required
@admin_required
def excluir_usuario(user_id):
    if user_id == session["user_id"]:
        flash("Você não pode excluir seu próprio usuário.", "warning")
        return redirect(url_for("usuarios"))
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    flash("Usuário excluído.", "info")
    return redirect(url_for("usuarios"))


@app.route("/relatorios")
@login_required
@admin_required
def relatorios():
    periodo = request.args.get("periodo", "dia")
    hoje = date.today()
    data_ref_txt = request.args.get("data_ref", hoje.strftime("%Y-%m-%d"))
    data_ref = parse_data(data_ref_txt) or hoje
    status_filtro = request.args.get("status", "Concluído")
    usuario_id = request.args.get("usuario_id", type=int)

    # Quando o relatório é de concluídos, a data usada é a data de conclusão.
    # Para outros status, a data usada é a data de cadastro da OC.
    campo_data = Order.concluido_em if status_filtro == "Concluído" else Order.criado_em

    query = db.session.query(User.nome, db.func.count(Order.id).label("total")).join(Order)

    if status_filtro:
        query = query.filter(Order.status == status_filtro)
        if status_filtro == "Concluído":
            query = query.filter(Order.concluido_em.isnot(None))

    if usuario_id:
        query = query.filter(User.id == usuario_id)

    if periodo == "dia":
        inicio = datetime(data_ref.year, data_ref.month, data_ref.day, 0, 0, 0)
        fim = datetime(data_ref.year, data_ref.month, data_ref.day, 23, 59, 59)
        query = query.filter(campo_data.between(inicio, fim))
        titulo = f"Relatório do dia {data_ref.strftime('%d/%m/%Y')}"
    elif periodo == "mes":
        inicio = datetime(data_ref.year, data_ref.month, 1)
        fim = datetime(data_ref.year + 1, 1, 1) if data_ref.month == 12 else datetime(data_ref.year, data_ref.month + 1, 1)
        query = query.filter(campo_data >= inicio, campo_data < fim)
        titulo = f"Relatório do mês {data_ref.strftime('%m/%Y')}"
    else:
        inicio = datetime(data_ref.year, 1, 1)
        fim = datetime(data_ref.year + 1, 1, 1)
        query = query.filter(campo_data >= inicio, campo_data < fim)
        titulo = f"Relatório do ano {data_ref.year}"

    dados = query.group_by(User.id).order_by(db.desc("total")).all()
    total_geral = sum(item.total for item in dados)
    usuarios = User.query.filter_by(ativo=True).order_by(User.nome).all()
    return render_template("relatorios.html", dados=dados, total_geral=total_geral, titulo=titulo,
                           periodo=periodo, data_ref=data_ref.strftime("%Y-%m-%d"),
                           usuarios=usuarios, usuario_id=usuario_id, status_filtro=status_filtro)


def atualizar_banco():
    """Cria colunas novas quando o sistema já possui um banco antigo."""
    if "postgresql" in str(db.engine.url):
        return
    inspector = inspect(db.engine)
    if "order" in inspector.get_table_names():
        colunas = [col["name"] for col in inspector.get_columns("order")]
        novas_colunas = {
            "descricao": 'ALTER TABLE "order" ADD COLUMN descricao VARCHAR(500)',
            "numero_oc": 'ALTER TABLE "order" ADD COLUMN numero_oc VARCHAR(30)',
            "prazo_entrega": 'ALTER TABLE "order" ADD COLUMN prazo_entrega DATE',
            "arquivo": 'ALTER TABLE "order" ADD COLUMN arquivo VARCHAR(255)',
        }
        with db.engine.connect() as conn:
            for nome, sql in novas_colunas.items():
                if nome not in colunas:
                    conn.execute(text(sql))
            conn.commit()
        for ordem in Order.query.filter((Order.numero_oc == None) | (Order.numero_oc == "")).order_by(Order.id).all():
            ordem.numero_oc = f"OC-{ordem.id:04d}"
        db.session.commit()


def criar_admin_padrao():
    if not User.query.filter_by(usuario="admin").first():
        admin = User(nome="Administrador", usuario="admin", is_admin=True, ativo=True)
        admin.set_password("admin123")
        db.session.add(admin)
        db.session.commit()


def inicializar_sistema():
    """Inicializa banco e usuário admin tanto localmente quanto em hospedagem online."""
    with app.app_context():
        os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
        db.create_all()
        atualizar_banco()
        criar_admin_padrao()


inicializar_sistema()


if __name__ == "__main__":
    porta = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=porta, debug=os.environ.get("FLASK_DEBUG", "0") == "1")
