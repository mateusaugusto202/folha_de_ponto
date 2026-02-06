# models.py

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import get_db, login_manager # Será necessário o app para o login_manager

# Funções que o Flask-Login precisa
@login_manager.user_loader
def load_user(user_id):
    db = get_db()
    with db.cursor() as cur:
        # Busca o usuário na tabela principal (USUARIOS)
        cur.execute("SELECT id, nome, cpf, senha_hash, tipo_usuario, status FROM usuarios WHERE id = %s", (user_id,))
        user_data = cur.fetchone()
        if user_data:
            return Usuario(user_data)
        return None

# Modelagem da tabela USUARIOS (Usuários ativos)
class Usuario(UserMixin):
    def __init__(self, data):
        self.id = data.get('id')
        self.nome = data.get('nome')
        self.cpf = data.get('cpf')
        self.senha_hash = data.get('senha_hash')
        self.tipo_usuario = data.get('tipo_usuario')
        self.status = data.get('status')
        
    @staticmethod
    def set_password(password):
        return generate_password_hash(password)

    @staticmethod
    def check_password(hashed_password, password):
        return check_password_hash(hashed_password, password)

    # Métodos estáticos de CRUD para Usuario... (a serem adicionados)


# Modelagem da tabela SOLICITACOES_CADASTRO (Usuários pendentes)
class SolicitacaoCadastro:
    def __init__(self, data):
        self.id = data.get('id')
        self.nome = data.get('nome')
        self.cpf = data.get('cpf')
        self.email = data.get('email')
        self.senha_hash = data.get('senha_hash')
        self.status = data.get('status')
        self.data_solicitacao = data.get('data_solicitacao')

    # Métodos estáticos de CRUD para SolicitacaoCadastro... (a serem adicionados)

# Modelagem da tabela REGISTROS / PONTOS
# Você já tem a lógica de API, mas se usar um model, ajuda na clareza.
class Ponto:
    # ... (Modelagem da tabela registros)
    pass