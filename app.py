import pymysql
import pdfkit
import calendar
import platform
import os
import re
from datetime import datetime, date # Importado apenas uma vez

from flask import Flask, render_template, request, redirect, url_for, flash, session, g, jsonify
from flask_login import LoginManager, UserMixin, login_required, current_user, login_user, logout_user
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

# ==================== CONFIGURAÇÃO DA APLICAÇÃO ====================
app = Flask(__name__)

# Configuração Inteligente do Motor de PDF (Windows vs Linux)
if platform.system() == "Windows":
    WKHTMLTOPDF_PATH = r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe'
    PDF_CONFIG = pdfkit.configuration(wkhtmltopdf=WKHTMLTOPDF_PATH)
else:
    # No Render (Linux), ele tentará usar o executável instalado no sistema
    PDF_CONFIG = pdfkit.configuration()

PDF_OPTIONS = {
    'page-size': 'A4',
    'margin-top': '0.5in',
    'margin-right': '0.5in',
    'margin-bottom': '0.5in',
    'margin-left': '0.5in',
    'encoding': "UTF-8",
    'no-outline': None
}
# ... resto do código continua igual ...

# ==================== CONFIGURAÇÃO DA APLICAÇÃO ====================
app = Flask(__name__)

# Configuração Inteligente: Windows vs Nuvem (Linux)
if platform.system() == "Windows":
    # No seu computador, usa o caminho do C:
    WKHTMLTOPDF_PATH = r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe'
    PDF_CONFIG = pdfkit.configuration(wkhtmltopdf=WKHTMLTOPDF_PATH)
else:
    # No Render (Linux), não passamos caminho, ele usa o padrão do sistema
    PDF_CONFIG = pdfkit.configuration()

PDF_OPTIONS = {
    'page-size': 'A4',
    'margin-top': '0.5in',
    'margin-right': '0.5in',
    'margin-bottom': '0.5in',
    'margin-left': '0.5in',
    'encoding': "UTF-8",
    'no-outline': None
}

# Chave secreta necessária para sessões e Flask-Login
app.config['SECRET_KEY'] = 'uma_chave_muito_secreta_e_complexa'

# ==================== INICIALIZAÇÃO DO FLASK-LOGIN ====================
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'  # Redireciona para login se não autenticado
login_manager.login_message = "Por favor, faça login para acessar esta página."
login_manager.login_message_category = "warning"


# ==================== DECORADORES DE AUTORIZAÇÃO ====================

def rh_required(f):
    """
    Decorador que garante que o usuário logado seja do tipo 'rh' ou 'admin'.
    Usado para proteger rotas administrativas.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Verifica se o usuário está autenticado
        if not current_user.is_authenticated:
            flash('Acesso negado. Por favor, faça login.', 'danger')
            return redirect(url_for('login'))
        
        # Verifica se o cargo é permitido (rh OU admin)
        if current_user.tipo_usuario not in ['rh', 'admin']:
            flash('Você não tem permissão administrativa para acessar esta área.', 'danger')
            return redirect(url_for('area_funcionario'))
            
        return f(*args, **kwargs)
    return decorated_function


def funcionario_required(f):
    """
    Decorador que garante que o usuário logado seja do tipo 'funcionario'.
    Usado para proteger rotas exclusivas de funcionários.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Acesso negado. Por favor, faça login.', 'danger')
            return redirect(url_for('login'))
        
        if current_user.tipo_usuario != 'funcionario':
            flash('Você não tem permissão de Funcionário para acessar esta área.', 'danger')
            return redirect(url_for('login'))
        
        return f(*args, **kwargs)
    return decorated_function


# ==================== MODELO DE USUÁRIO PARA FLASK-LOGIN ====================
    
class Usuario(UserMixin):
    def __init__(self, data):
        self.id = data.get('id')
        self.nome = data.get('nome')
        self.cpf = data.get('cpf')
        self.email = data.get('email')
        self.senha_hash = data.get('senha_hash')
        self.tipo_usuario = data.get('tipo_usuario')
        self.status = data.get('status')
        # Forçamos a carga horária para 8.0 para garantir cálculos precisos no PDF [cite: 2026-01-08]
        self.carga_horaria = float(8.0) 
        self.tempo_intervalo = data.get('tempo_intervalo', 60)

    def get_id(self):
        return str(self.id)


@login_manager.user_loader
def load_user(user_id):
    """
    Função exigida pelo Flask-Login para carregar um usuário a partir do ID.
    Chamada automaticamente em cada requisição para usuários autenticados.
    """
    db = get_db()
    # DictCursor faz com que os resultados sejam dicionários em vez de tuplas
    with db.cursor(pymysql.cursors.DictCursor) as cur:
        cur.execute("""
            SELECT id, nome, cpf, email, senha_hash, tipo_usuario, status, carga_horaria 
            FROM usuarios 
            WHERE id = %s
        """, (user_id,))
        
        user_data = cur.fetchone()
        
        if user_data:
            return Usuario(user_data)
        return None


# ==================== FUNÇÕES AUXILIARES ====================

def calcular_horas(h1, h2):
    """
    Calcula a diferença em horas entre dois horários.
    Args:
        h1: Horário inicial (formato HH:MM:SS)
        h2: Horário final (formato HH:MM:SS)
    Returns:
        float: Diferença em horas
    """
    if not h1 or not h2:
        return 0
    
    # Formato de hora
    fmt = '%H:%M:%S'
    # Calcula a diferença
    tdelta = datetime.strptime(str(h2), fmt) - datetime.strptime(str(h1), fmt)
    # Retorna em horas
    return tdelta.total_seconds() / 3600


# ==================== CONFIGURAÇÃO DO BANCO DE DADOS ====================


import os

DB_CONFIG = {
    'host': 'mysql-seu-host.aivencloud.com',
    'port': 15998,
    'user': 'avnadmin',
    'password': 'AVNS_WzPp-efbewZnJbNuIM5',
    'database': 'defaultdb',
    'cursorclass': pymysql.cursors.DictCursor
}

def get_db():
    """
    Obtém a conexão com o banco de dados.
    Armazena a conexão no contexto 'g' do Flask para reutilização na mesma requisição.
    """
    if "db" not in g:
        # Agora o pymysql usará os dados dinâmicos da DB_CONFIG
        g.db = pymysql.connect(**DB_CONFIG)
    return g.db


@app.teardown_appcontext
def close_db(exc):
    """
    Fecha a conexão com o banco ao final de cada requisição.
    """
    db = g.pop("db", None)
    if db is not None:
        db.close()


# ==================== ROTAS DE AUTENTICAÇÃO ====================

@app.route("/")
def index():
    """
    Rota inicial que redireciona conforme o tipo de usuário logado.
    """
    if current_user.is_authenticated:
        # Admin e RH vão para o painel administrativo
        if current_user.tipo_usuario in ['admin', 'rh']:
            return redirect(url_for('rh_solicitacoes'))
        else:
            # Funcionários vão para sua área
            return redirect(url_for('area_funcionario'))
    
    # Não autenticado: vai para login
    return redirect(url_for("login"))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Limpa o CPF que o usuário digitou para comparar com o banco
        cpf_digitado = re.sub(r'\D', '', request.form.get('cpf', ''))
        senha_digitada = request.form.get('senha')

        db = get_db()
        with db.cursor(pymysql.cursors.DictCursor) as cur:
            # Busca o usuário pelo CPF limpo
            cur.execute("SELECT * FROM usuarios WHERE cpf = %s", (cpf_digitado,))
            user = cur.fetchone()

        if user and check_password_hash(user['senha_hash'], senha_digitada):
            # Se a senha estiver certa, cria a sessão
            user_obj = User(user['id'], user['nome'], user['tipo_usuario'])
            login_user(user_obj)
            
            # Redireciona conforme o cargo
            if user['tipo_usuario'] == 'admin':
                return redirect(url_for('dashboard_rh'))
            return redirect(url_for('area_funcionario'))
        
        flash('CPF ou senha incorretos.', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    """
    Rota para fazer logout do sistema.
    """
    logout_user()
    session.clear()  # Limpa a sessão do Flask
    flash("Você saiu do sistema.", "info")
    return redirect(url_for('login'))


@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if request.method == 'POST':
        nome = request.form.get('nome')
        # --- AQUI ESTÁ A CORREÇÃO ---
        # Pega o CPF e remove tudo que não for número antes de salvar
        cpf_sujo = request.form.get('cpf', '')
        cpf = re.sub(r'\D', '', cpf_sujo) 
        # ----------------------------
        
        email = request.form.get('email')
        senha = request.form.get('senha')
        
        senha_hash = generate_password_hash(senha)

        db = get_db()
        try:
            with db.cursor() as cur:
                # Agora o 'cpf' aqui terá apenas os 11 números
                cur.execute(
                    "INSERT INTO solicitacoes_cadastro (nome, cpf, email, senha_hash, status) VALUES (%s, %s, %s, %s, %s)",
                    (nome, cpf, email, senha_hash, 'pendente')
                )
            db.commit()
            
            flash('Solicitação de cadastro enviada com sucesso! Aguarde a aprovação do RH.', 'success')
            return redirect(url_for('login'))

        except pymysql.err.IntegrityError as e:
            db.rollback()
            if 'Duplicate entry' in str(e):
                flash('Erro: CPF ou E-mail já estão cadastrados ou pendentes.', 'danger')
            else:
                flash('Erro ao processar sua solicitação de cadastro.', 'danger')
            return render_template('cadastro.html', nome=nome, cpf=cpf_sujo, email=email)

    return render_template('cadastro.html')


# ==================== ROTAS DE FUNCIONÁRIO ====================

@app.route('/area_funcionario')
@login_required
def area_funcionario():
    db = get_db()
    hoje = datetime.now().date()
    
    with db.cursor(pymysql.cursors.DictCursor) as cur:
        # 1. Dados do usuário e Carga Horária
        cur.execute("SELECT * FROM usuarios WHERE id = %s", (current_user.id,))
        user_data = cur.fetchone()
        
        # 2. NOVO: Busca alertas de assinatura pendente
        cur.execute("""
            SELECT id, mes, ano 
            FROM folhas_assinadas 
            WHERE usuario_id = %s AND status = 'pendente'
        """, (current_user.id,))
        assinaturas_pendentes = cur.fetchall()

        # 3. Saldo acumulado
        cur.execute("SELECT SUM(saldo_dia) as total FROM registros_ponto WHERE usuario_id = %s", (current_user.id,))
        resultado_saldo = cur.fetchone()
        saldo_acumulado = resultado_saldo['total'] if resultado_saldo['total'] else 0.0

        # 4. Ponto de hoje
        cur.execute("SELECT * FROM registros_ponto WHERE usuario_id = %s AND data_registro = %s", 
                    (current_user.id, hoje))
        ponto_hoje = cur.fetchone()
        
        # 5. Histórico recente
        cur.execute("SELECT * FROM registros_ponto WHERE usuario_id = %s ORDER BY data_registro DESC LIMIT 7", 
                    (current_user.id,))
        historico = cur.fetchall()
 
        carga_segundos = converter_carga_para_segundos(user_data['carga_horaria'])

    return render_template('area_funcionario.html', 
                            assinaturas_pendentes=assinaturas_pendentes, # Não esqueça de passar isso!
                            carga_horaria_segundos=carga_segundos,
                            ponto_hoje=ponto_hoje, 
                            historico=historico, 
                            saldo=saldo_acumulado,
                            hoje=hoje,
                            hoje_formatada=hoje.strftime('%d/%m/%Y'))


import calendar
from datetime import datetime

def gerar_lista_dias(usuario_id, mes, ano):
    db = get_db()
    with db.cursor(pymysql.cursors.DictCursor) as cur:
        # Busca todos os registros do funcionário naquele mês
        cur.execute("""
            SELECT * FROM registros_ponto 
            WHERE usuario_id = %s AND MONTH(data_registro) = %s AND YEAR(data_registro) = %s
        """, (usuario_id, mes, ano))
        registros = {r['data_registro'].day: r for r in cur.fetchall()}

    dias_do_mes = []
    # calendar.monthrange retorna (dia_da_semana_da_estreia, total_de_dias)
    _, num_dias = calendar.monthrange(ano, mes)

    for dia in range(1, num_dias + 1):
        data_atual = datetime(ano, mes, dia)
        nome_dia = data_atual.strftime('%a') # Ex: Seg, Ter...
        
        info_dia = registros.get(dia, {})
        
        # Lógica de Observação Automática
        observacao = ""
        if data_atual.weekday() == 5: observacao = "SÁBADO"
        elif data_atual.weekday() == 6: observacao = "DOMINGO"
        # Aqui você poderia adicionar uma lista de feriados também
        
        dias_do_mes.append({
            'data': data_atual.strftime('%d/%m/%Y'),
            'semana': nome_dia,
            'entrada': info_dia.get('entrada'),
            'saida_almoco': info_dia.get('saida_almoco'),
            'retorno_almoco': info_dia.get('retorno_almoco'),
            'saida': info_dia.get('saida'),
            'total': info_dia.get('total_horas', '00:00'),
            'obs': observacao
        })
    
    return dias_do_mes


import pdfkit

@app.route('/gerar_pdf_final/<int:folha_id>')
@login_required
def gerar_pdf_final(folha_id):
    # 1. Busca os dados da folha e do funcionário no banco
    # 2. Chama a função gerar_lista_dias(...)
    dias = gerar_lista_dias(folha.usuario_id, folha.mes, folha.ano)
    
    # 3. Renderiza o HTML para string
    html_renderizado = render_template('folha_ponto_pdf.html', 
                                       dias_do_mes=dias, 
                                       funcionario=funcionario,
                                       assinatura_img=folha.assinatura_base64)

    # 4. Transforma em PDF
    caminho_arquivo = f"static/folhas/folha_{folha_id}.pdf"
    pdfkit.from_string(html_renderizado, caminho_arquivo)
    
    return send_file(caminho_arquivo)


@app.route('/rh/solicitar_assinatura', methods=['POST'])
@rh_required
def solicitar_assinatura():
    usuario_id = request.form.get('usuario_id')
    mes = request.form.get('mes')
    ano = request.form.get('ano')
    
    if not usuario_id or not mes or not ano:
        flash('Preencha todos os campos para solicitar a assinatura.', 'danger')
        return redirect(url_for('painel_rh'))

    db = get_db()
    try:
        with db.cursor() as cur:
            # Verifica se já existe uma solicitação para esse mês/ano para evitar duplicidade
            cur.execute("""
                SELECT id FROM folhas_assinadas 
                WHERE usuario_id = %s AND mes = %s AND ano = %s
            """, (usuario_id, mes, ano))
            
            if cur.fetchone():
                flash('Já existe uma solicitação de assinatura para este mês/ano.', 'warning')
            else:
                cur.execute("""
                    INSERT INTO folhas_assinadas (usuario_id, mes, ano, status)
                    VALUES (%s, %s, %s, 'pendente')
                """, (usuario_id, mes, ano))
                db.commit()
                flash('Solicitação de assinatura enviada com sucesso!', 'success')
    except Exception as e:
        db.rollback()
        flash(f'Erro ao solicitar assinatura: {e}', 'danger')
        
    return redirect(url_for('painel_rh'))


def obter_dados_mensais_completos(usuario_id, mes, ano):
    """
    Gera uma lista de dicionários contendo todos os dias do mês,
    mesclando com as batidas reais do banco de dados.
    """
    db = get_db()
    with db.cursor(pymysql.cursors.DictCursor) as cur:
        # Busca batidas reais
        cur.execute("""
            SELECT * FROM registros_ponto 
            WHERE usuario_id = %s AND MONTH(data_registro) = %s AND YEAR(data_registro) = %s
        """, (usuario_id, mes, ano))
        batidas = {b['data_registro'].day: b for b in cur.fetchall()}

    _, total_dias = calendar.monthrange(ano, mes)
    lista_final = []

    for dia in range(1, total_dias + 1):
        dt = date(ano, mes, dia)
        registro = batidas.get(dia, {})
        
        # Lógica de observação automática para o layout profissional
        obs = ""
        if dt.weekday() == 5: obs = "SÁBADO"
        elif dt.weekday() == 6: obs = "DOMINGO"
        
        lista_final.append({
            'data': dt.strftime('%d/%m/%Y'),
            'dia_semana': dt.strftime('%a').upper(),
            'entrada': registro.get('entrada', ''),
            'saida_almoco': registro.get('saida_almoco', ''),
            'retorno_almoco': registro.get('retorno_almoco', ''),
            'saida': registro.get('saida', ''),
            'total': registro.get('total_horas', '00:00'),
            'obs': obs
        })
    return lista_final


@app.route('/rh/decidir_folha/<int:folha_id>', methods=['POST'])
@login_required
def decidir_folha(folha_id):
    acao = request.form.get('acao') # 'aprovar' ou 'recusar'
    motivo = request.form.get('motivo', '') # Caso seja recusado
    
    status = 'aprovado' if acao == 'aprovar' else 'recusado'
    
    db = get_db()
    with db.cursor() as cur:
        cur.execute("""
            UPDATE folhas_assinadas 
            SET status = %s, motivo_recusa = %s 
            WHERE id = %s
        """, (status, motivo, folha_id))
    db.commit()
    
    flash(f"Folha {status} com sucesso!", "info")
    return redirect(url_for('painel_rh'))


@app.route('/admin/painel_folhas')
@login_required
def painel_folhas_admin():
    # Segurança: Só permite se for admin
    if current_user.role != 'admin':
        flash("Acesso negado!", "danger")
        return redirect(url_for('index'))
    
    db = get_db()
    with db.cursor(pymysql.cursors.DictCursor) as cur:
        # Busca folhas assinadas cruzando com dados do usuário
        cur.execute("""
            SELECT f.id, f.mes, f.ano, f.status, f.data_assinatura, u.nome 
            FROM folhas_assinadas f
            JOIN usuarios u ON f.usuario_id = u.id
            ORDER BY f.data_assinatura DESC
        """)
        folhas = cur.fetchall()
        
    return render_template('admin_painel.html', folhas=folhas)


import pdfkit
from flask import make_response, render_template, flash, redirect, url_for

@app.route('/gerar_pdf_folha/<int:folha_id>')
@login_required
def gerar_pdf_folha(folha_id):
    # --- AJUSTE PARA FUNCIONAR NO WINDOWS E NO RENDER (LINUX) ---
    if platform.system() == "Windows":
        path_wkhtmltopdf = r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe'
        config = pdfkit.configuration(wkhtmltopdf=path_wkhtmltopdf)
    else:
        # No Linux (Render), o wkhtmltopdf precisa ser instalado via buildscript
        # ou estar no PATH. Se estiver instalado, o pdfkit acha sozinho:
        config = pdfkit.configuration() 
    # -----------------------------------------------------------

    db = get_db()
    # ... resto da sua função igual ...
    with db.cursor(pymysql.cursors.DictCursor) as cur:
        # 1. Busca os dados da folha
        cur.execute("""
            SELECT f.*, u.nome, u.tipo_usuario, u.cpf 
            FROM folhas_assinadas f
            JOIN usuarios u ON f.usuario_id = u.id
            WHERE f.id = %s
        """, (folha_id,))
        folha = cur.fetchone()

        if not folha:
            flash("Folha não encontrada.", "danger")
            return redirect(url_for('painel_folhas_admin'))

        # Mapeamento do mês
        meses_map = {
            'Janeiro': 1, 'Fevereiro': 2, 'Março': 3, 'Abril': 4,
            'Maio': 5, 'Junho': 6, 'Julho': 7, 'Agosto': 8,
            'Setembro': 9, 'Outubro': 10, 'Novembro': 11, 'Dezembro': 12
        }
        mes_num = meses_map.get(folha['mes'], folha['mes'])

        # 2. Busca os pontos
        cur.execute("""
            SELECT * FROM registros_ponto 
            WHERE usuario_id = %s 
            AND MONTH(data_registro) = %s 
            AND YEAR(data_registro) = %s
            ORDER BY data_registro ASC
        """, (folha['usuario_id'], mes_num, folha['ano']))
        pontos = cur.fetchall()

    # 3. Renderiza o HTML
    html = render_template('pdf_template.html', 
                           folha=folha, 
                           funcionario=folha, 
                           pontos=pontos)
    
    # 4. Converte para PDF usando a configuração 'config'
    options = {
        'enable-local-file-access': None,
        'encoding': "UTF-8",
        'quiet': '' # Limpa o log do console
    }
    
    try:
        # Importante: adicionamos configuration=config aqui
        pdf = pdfkit.from_string(html, False, options=options, configuration=config)
    except Exception as e:
        return f"Erro técnico ao gerar PDF: {str(e)}. Verifique se o caminho do wkhtmltopdf está correto."
    
    # 5. Retorna o arquivo
    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=folha_{folha["nome"]}.pdf'
    
    return response


@app.after_request
def add_header(response):
    # Força o navegador a não fazer cache das páginas
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response


@app.route('/admin/ver_folha/<int:folha_id>')
@login_required
def admin_ver_folha(folha_id):
    if current_user.tipo_usuario != 'admin':
        flash("Acesso restrito a administradores.", "danger")
        return redirect(url_for('index'))
    
    db = get_db()
    with db.cursor(pymysql.cursors.DictCursor) as cur:
        # 1. Busca os dados da folha e do usuário (Colunas garantidas pela sua classe)
        cur.execute("""
            SELECT f.*, u.nome, u.tipo_usuario, u.cpf 
            FROM folhas_assinadas f
            JOIN usuarios u ON f.usuario_id = u.id
            WHERE f.id = %s
        """, (folha_id,))
        folha = cur.fetchone()

        if not folha:
            flash("Folha não encontrada.", "warning")
            return redirect(url_for('painel_folhas_admin'))

        # 1. Primeiro, vamos descobrir como o mês está salvo
        mes_valor = folha['mes']
        
        # Se o seu 'mes' for o nome (Janeiro, Fevereiro...), precisamos converter para número
        # Caso já seja número, o código abaixo lida com isso:
        meses_map = {
            'Janeiro': 1, 'Fevereiro': 2, 'Março': 3, 'Abril': 4,
            'Maio': 5, 'Junho': 6, 'Julho': 7, 'Agosto': 8,
            'Setembro': 9, 'Outubro': 10, 'Novembro': 11, 'Dezembro': 12
        }
        
        # Converte se for string, senão usa o valor direto
        mes_num = meses_map.get(mes_valor, mes_valor)

        # 2. Agora buscamos os pontos com o número correto do mês
        cur.execute("""
            SELECT * FROM registros_ponto 
            WHERE usuario_id = %s 
            AND MONTH(data_registro) = %s 
            AND YEAR(data_registro) = %s
            ORDER BY data_registro ASC
        """, (folha['usuario_id'], mes_num, folha['ano']))
        pontos = cur.fetchall()

    # Verifica se o admin quer imprimir (modo_impressao)
    modo_impressao = request.args.get('print') == 'true'

    return render_template('admin_ver_folha.html', 
                            folha=folha, 
                            funcionario=folha,  # Adicione esta linha
                            pontos=pontos, 
                            modo_impressao=modo_impressao)


@app.route('/salvar_assinatura/<int:folha_id>', methods=['POST'])
@login_required
def salvar_assinatura(folha_id):
    metodo = request.form.get('metodo')
    assinatura_b64 = request.form.get('assinatura_b64')
    
    db = get_db()
    with db.cursor() as cur:
        # Lógica de Update (Manual ou Automática)
        if metodo == 'manual':
            cur.execute("""
                UPDATE folhas_assinadas 
                SET status = 'assinada', data_assinatura = NOW(), assinatura_imagem = %s, tipo_assinatura = 'manual'
                WHERE id = %s AND usuario_id = %s
            """, (assinatura_b64, folha_id, current_user.id))
        else:
            cur.execute("""
                UPDATE folhas_assinadas 
                SET status = 'assinada', data_assinatura = NOW(), tipo_assinatura = 'automatica'
                WHERE id = %s AND usuario_id = %s
            """, (folha_id, current_user.id))
        db.commit()

    flash("Folha assinada com sucesso!", "success")
    # ISSO AQUI resolve o erro da imagem (PRG Pattern)
    return redirect(url_for('area_funcionario'))


@app.route('/registrar_ponto', methods=['POST'])
@login_required
def registrar_ponto():
    """
    Rota principal para registro de ponto.
    Gerencia entrada, saída para almoço, retorno do almoço e saída final.
    Calcula automaticamente as horas trabalhadas e o saldo do dia.
    """
    db = get_db()
    agora = datetime.now()
    hoje = agora.date()
    hora_atual = agora.strftime('%H:%M:%S')

    with db.cursor(pymysql.cursors.DictCursor) as cur:
        # Busca se já existe registro de hoje
        cur.execute("SELECT * FROM registros_ponto WHERE usuario_id = %s AND data_registro = %s", 
                   (current_user.id, hoje))
        ponto = cur.fetchone()

        # CASO 1: Primeira marcação do dia (ENTRADA)
        if not ponto:
            cur.execute("INSERT INTO registros_ponto (usuario_id, data_registro, entrada) VALUES (%s, %s, %s)", 
                       (current_user.id, hoje, hora_atual))
            flash("Entrada registrada!", "success")

        # CASO 2: Saída para almoço (apenas se carga horária > 6h)
        elif not ponto['saida_almoco'] and current_user.carga_horaria > 6:
            cur.execute("UPDATE registros_ponto SET saida_almoco = %s WHERE id = %s", 
                       (hora_atual, ponto['id']))
            flash("Almoço iniciado!", "info")

        # CASO 3: Retorno do almoço
        elif ponto['saida_almoco'] and not ponto['retorno_almoco']:
            cur.execute("UPDATE registros_ponto SET retorno_almoco = %s WHERE id = %s", 
                       (hora_atual, ponto['id']))
            flash("Retorno do almoço registrado!", "success")

        # CASO 4: Saída final (calcula horas e saldo)
        elif not ponto['saida']:
            hora_saida = hora_atual
            
            # Se teve intervalo de almoço, calcula em dois períodos
            if ponto['saida_almoco'] and ponto['retorno_almoco']:
                t1 = calcular_horas(ponto['entrada'], ponto['saida_almoco'])
                t2 = calcular_horas(ponto['retorno_almoco'], hora_saida)
                total_dia = t1 + t2
            else:
                # Sem almoço: calcula direto entrada -> saída
                total_dia = calcular_horas(ponto['entrada'], hora_saida)

            # Saldo = horas trabalhadas - carga horária esperada
            saldo_do_dia = float(total_dia) - float(current_user.carga_horaria)

            # Atualiza o registro com saída, total e saldo
            cur.execute("""
                UPDATE registros_ponto 
                SET saida = %s, total_trabalhado = %s, saldo_dia = %s 
                WHERE id = %s
            """, (hora_saida, round(total_dia, 2), round(saldo_do_dia, 2), ponto['id']))
            flash("Saída registrada. Saldo calculado!", "primary")
        
        db.commit()
    
    return redirect(url_for('area_funcionario'))


# No topo do seu app.py ou junto com suas outras funções de auxílio
def formatar_horas_decimal(decimal_horas):
    """
    Transforma 8.6 em '8h 36min' e lida com saldos negativos.
    Também aceita valores em formato HH:MM ou HH:MM:SS.
    """
    if decimal_horas is None:
        return "0h 00min"
    
    # Se já vier como string no formato HH:MM ou HH:MM:SS, retorna formatado
    if isinstance(decimal_horas, str) and ':' in decimal_horas:
        partes = decimal_horas.split(':')
        horas = int(partes[0])
        minutos = int(partes[1])
        return f"{horas}h {minutos:02d}min"
        
    try:
        valor = float(decimal_horas)
        sinal = "-" if valor < 0 else ""
        valor_abs = abs(valor)
        
        horas = int(valor_abs)
        # Multiplica a parte decimal por 60 para obter os minutos reais
        minutos = round((valor_abs - horas) * 60)
        
        # Ajuste caso o arredondamento resulte em 60 minutos
        if minutos == 60:
            horas += 1
            minutos = 0
            
        return f"{sinal}{horas}h {minutos:02d}min"
    except (ValueError, TypeError):
        return "0h 00min"

# Registra a função no Jinja2
@app.context_processor
def utility_processor():
    return dict(formatar_horas_decimal=formatar_horas_decimal)


@app.route('/reset_meu_ponto')
@login_required
def reset_meu_ponto():
    """
    Rota de desenvolvimento para resetar o ponto do dia.
    ATENÇÃO: Remover em produção!
    """
    db = get_db()
    hoje = datetime.now().date()
    with db.cursor() as cur:
        # Deleta o registro de ponto de hoje do usuário logado
        cur.execute("DELETE FROM registros_ponto WHERE usuario_id = %s AND data_registro = %s", 
                   (current_user.id, hoje))
        db.commit()
    
    flash("Seu ponto de hoje foi resetado! Pode testar novamente.", "warning")
    return redirect(url_for('area_funcionario'))


# ==================== ROTAS ADMINISTRATIVAS (RH/ADMIN) ====================

@app.route('/rh/solicitacoes')
@login_required
def rh_solicitacoes():
    """
    Painel principal do RH.
    Exibe solicitações de cadastro pendentes e lista de funcionários ativos.
    """
    # Restringe acesso apenas a admins
    if current_user.tipo_usuario != 'admin':
        return redirect(url_for('area_funcionario'))
        
    db = get_db()
    with db.cursor(pymysql.cursors.DictCursor) as cur:
        # Busca solicitações pendentes de aprovação
        cur.execute("SELECT * FROM solicitacoes_cadastro WHERE status = 'pendente'")
        solicitacoes = cur.fetchall()
        
        print(f">>> SOLICITACOES ENCONTRADAS: {solicitacoes}")

        # Busca todos os funcionários ativos
        cur.execute("SELECT id, nome, email, tipo_usuario FROM usuarios WHERE status = 'ativo'")
        funcionarios = cur.fetchall()
        
    return render_template('painel_rh.html', solicitacoes=solicitacoes, usuarios=funcionarios)


@app.route('/aprovar_solicitacao/<int:solicitacao_id>', methods=['POST'])
@login_required
def aprovar_solicitacao(solicitacao_id):
    # --- ALTERAÇÃO COMEÇA AQUI ---
    tipo_contrato = request.form.get('tipo_contrato')

    # Define a carga horária baseada no texto que vem do formulário
    if tipo_contrato == 'Estagiário':
        carga_horaria = 4.0
    else:
        carga_horaria = 8.0

    db = get_db()
    try:
        with db.cursor() as cur:
            # Busca os dados da solicitação
            cur.execute("SELECT nome, cpf, email, senha_hash FROM solicitacoes_cadastro WHERE id = %s AND status = 'pendente'", 
                       (solicitacao_id,))
            data = cur.fetchone()

            if not data:
                flash('Solicitação não encontrada.', 'danger')
                return redirect(url_for('rh_solicitacoes'))

            # Cria o funcionário na tabela de usuários
            cur.execute(
                """INSERT INTO usuarios (nome, cpf, email, senha_hash, tipo_usuario, status, tipo_contrato, carga_horaria) 
                   VALUES (%s, %s, %s, %s, 'funcionario', 'ativo', %s, %s)""",
                (data['nome'], data['cpf'], data['email'], data['senha_hash'], tipo_contrato, carga_horaria)
            )
            
            # Marca a solicitação como aprovada
            cur.execute("UPDATE solicitacoes_cadastro SET status = 'aprovado' WHERE id = %s", (solicitacao_id,))

        db.commit()
        flash(f"Usuário {data['nome']} aprovado como {tipo_contrato}!", 'success')
        
    except Exception as e:
        db.rollback()
        flash(f'Erro ao aprovar: {e}', 'danger')
        
    return redirect(url_for('rh_solicitacoes'))


@app.route('/rh/negar/<int:solicitacao_id>', methods=['GET', 'POST'])
@login_required
def negar_solicitacao(solicitacao_id):
    """
    Nega uma solicitação de cadastro.
    """
    db = get_db()
    try:
        with db.cursor() as cur:
            # Muda o status para 'reprovado'
            cur.execute("UPDATE solicitacoes_cadastro SET status = 'reprovado' WHERE id = %s", (solicitacao_id,))
        db.commit()
        flash('Solicitação negada com sucesso.', 'info')
    except Exception as e:
        db.rollback()
        flash(f'Erro ao negar: {e}', 'danger')
    
    return redirect(url_for('rh_solicitacoes'))


def converter_carga_para_segundos(carga):
    """
    Converte a carga horária do banco (int ou float) para segundos.
    Ex: 8 -> 28800 | 8.6 -> 30960
    """
    try:
        return int(float(carga) * 3600)
    except (ValueError, TypeError):
        # Caso o campo esteja vazio ou inválido, retorna 8h padrão
        return 28800


@app.route('/assinar_folha/<int:folha_id>')
@login_required
def assinar_folha(folha_id):
    db = get_db()
    with db.cursor(pymysql.cursors.DictCursor) as cur:
        # Busca os detalhes da folha
        cur.execute("SELECT * FROM folhas_assinadas WHERE id = %s", (folha_id,))
        folha = cur.fetchone()

        # Busca os dados do usuário (para pegar Cargo, Horário e Admissão)
        cur.execute("SELECT * FROM usuarios WHERE id = %s", (current_user.id,))
        dados_usuario = cur.fetchone()

        # Busca os pontos (registros_ponto)
        cur.execute("""
            SELECT * FROM registros_ponto 
            WHERE usuario_id = %s 
            AND MONTH(data_registro) = %s AND YEAR(data_registro) = %s
            ORDER BY data_registro ASC
        """, (current_user.id, folha['mes'], folha['ano']))
        pontos = cur.fetchall()

    return render_template('assinar_folha.html', 
                           folha=folha, 
                           pontos=pontos, 
                           dados_usuario=dados_usuario) # Enviamos os dados reais aqui


@app.route('/rh/painel')
@rh_required
def painel_rh():
    db = get_db()
    agora = datetime.now()
    hoje = agora.date()
    
    with db.cursor(pymysql.cursors.DictCursor) as cur:
        # 1. CONSULTA GLOBAL DE ALERTAS (Não depende de ID nenhum)
        # Ela busca todos os ativos que NÃO bateram ponto hoje
        cur.execute("""
            SELECT id, nome FROM usuarios 
            WHERE status = 'ativo' AND tipo_usuario = 'funcionario'
            AND id NOT IN (SELECT usuario_id FROM registros_ponto WHERE data_registro = %s)
        """, (hoje,))
        
        # Aqui capturamos a lista de TODOS os que estão faltando
        todos_atrasados = cur.fetchall()

        alertas_atraso = []
        # Só exibe se já for tarde (ex: após 08:15)
        if agora.hour >= 8 and agora.minute >= 15:
            alertas_atraso = todos_atrasados 

        # 2. Busca o restante dos dados normalmente
        cur.execute("SELECT * FROM usuarios WHERE status = 'ativo'")
        usuarios = cur.fetchall()
        
        cur.execute("SELECT * FROM solicitacoes_cadastro WHERE status = 'pendente'")
        solicitacoes = cur.fetchall()

        cur.execute("""
            SELECT f.*, u.nome FROM folhas_assinadas f 
            JOIN usuarios u ON f.usuario_id = u.id 
            ORDER BY f.id DESC
        """)
        folhas_status = cur.fetchall()

    # O segredo: enviar a lista completa 'alertas_atraso' para o template
    return render_template('painel_rh.html', 
                           usuarios=usuarios, 
                           solicitacoes=solicitacoes, 
                           folhas_status=folhas_status,
                           alertas_atraso=alertas_atraso)


@app.route('/painel_rh')   
@login_required
def dashboard_rh():
    """
    Dashboard completo do RH com:
    - Solicitações pendentes
    - Lista de funcionários
    - Status online/offline
    - Saldo total de cada funcionário
    - Alertas de atraso
    """
    # Restringe acesso apenas a admins
    if current_user.tipo_usuario != 'admin':
        return redirect(url_for('area_funcionario'))

    db = get_db()
    hoje = datetime.now().date()
    hora_agora = datetime.now().strftime('%H:%M:%S')
    horario_limite = "08:00:00"  # Horário limite de entrada

    alertas_atraso = []

    with db.cursor(pymysql.cursors.DictCursor) as cur:
        # Busca solicitações pendentes
        cur.execute("SELECT * FROM solicitacoes_cadastro WHERE status = 'pendente'")
        solicitacoes = cur.fetchall()

        # Busca todos os usuários ativos
        cur.execute("SELECT * FROM usuarios WHERE status = 'ativo'")
        usuarios_dados = cur.fetchall()

        lista_final_usuarios = []

        for user in usuarios_dados:
            # Calcula o saldo total acumulado do funcionário
            cur.execute("SELECT SUM(saldo_dia) as total FROM registros_ponto WHERE usuario_id = %s", (user['id'],))
            res_saldo = cur.fetchone()
            user['saldo_total'] = res_saldo['total'] or 0.0

            # Verifica se o funcionário bateu ponto hoje
            cur.execute("SELECT id, entrada, saida FROM registros_ponto WHERE usuario_id = %s AND data_registro = %s", 
                        (user['id'], hoje))
            ponto_hoje = cur.fetchone()

            # Define status: Online (bateu entrada e não saiu) ou Offline
            user['esta_trabalhando'] = True if (ponto_hoje and ponto_hoje['entrada'] and not ponto_hoje['saida']) else False

            # LÓGICA DO ALERTA: Se não bateu ponto e já passou do horário
            if not ponto_hoje and hora_agora > horario_limite:
                alertas_atraso.append({
                    'id': user['id'],
                    'nome': user['nome'],
                    'entrada_esperada': '08:00'
                })

            lista_final_usuarios.append(user)

    return render_template('painel_rh.html', 
                           solicitacoes=solicitacoes, 
                           usuarios=lista_final_usuarios,
                           alertas_atraso=alertas_atraso)


@app.route('/rh/promover/<int:usuario_id>')
@login_required
def promover_admin(usuario_id):
    """
    Promove um funcionário a administrador.
    Apenas admins podem promover outros usuários.
    """
    # Segurança: Apenas admins podem promover
    if current_user.tipo_usuario != 'admin':
        flash("Acesso negado.", "danger")
        return redirect(url_for('area_funcionario'))

    db = get_db()
    try:
        with db.cursor() as cur:
            # Muda o tipo_usuario para 'admin'
            cur.execute("UPDATE usuarios SET tipo_usuario = 'admin' WHERE id = %s", (usuario_id,))
        db.commit()
        flash("Usuário promovido a Administrador com sucesso!", "success")
    except Exception as e:
        db.rollback()
        flash(f"Erro ao promover: {e}", "danger")
    
    return redirect(url_for('rh_solicitacoes'))


@app.route('/rh/historico/<int:usuario_id>')
@login_required
def historico_individual(usuario_id):
    """
    Exibe o histórico completo de ponto de um funcionário específico.
    Acesso restrito a admin e RH.
    """
    # Trava de segurança
    if current_user.tipo_usuario not in ['admin', 'rh']:
        return redirect(url_for('area_funcionario'))

    db = get_db()
    with db.cursor() as cur:
        # Busca o nome do funcionário
        cur.execute("SELECT nome FROM usuarios WHERE id = %s", (usuario_id,))
        funcionario = cur.fetchone()

        # Caso o ID não exista
        if not funcionario:
            flash("Funcionário não encontrado.", "danger")
            return redirect(url_for('rh_solicitacoes'))
        
        # Busca todos os registros de ponto do funcionário
        cur.execute("""
            SELECT data_registro, entrada, saida, total_trabalhado, saldo_dia, criado_em 
            FROM registros_ponto 
            WHERE usuario_id = %s 
            ORDER BY data_registro DESC
        """, (usuario_id,))
        pontos = cur.fetchall()

    return render_template('historico_individual.html', registros=pontos, funcionario=funcionario)


@app.route('/historico_geral')
@login_required
def historico_geral():
    """
    Exibe o histórico de todos os funcionários.
    Acesso exclusivo para admins.
    """
    # Garante que só admins acessem
    if current_user.tipo_usuario != 'admin':
        return redirect(url_for('area_funcionario'))

    db = get_db()
    with db.cursor() as cur:
        # Busca todos os registros, juntando com a tabela de usuários para pegar o nome
        cur.execute("""
            SELECT r.*, u.nome 
            FROM registros_ponto r 
            JOIN usuarios u ON r.usuario_id = u.id 
            ORDER BY r.data_registro DESC
        """)
        todos_registros = cur.fetchall()

    return render_template('historico_geral.html', registros=todos_registros)


@app.route('/editar_ponto/<int:user_id>', methods=['GET', 'POST'])
@login_required
def editar_ponto(user_id):
    if current_user.tipo_usuario != 'admin':
        return redirect(url_for('area_funcionario'))

    db = get_db()
    # Usamos o DictCursor para facilitar o acesso no HTML
    cur = db.cursor(pymysql.cursors.DictCursor)

    if request.method == 'POST':
        data_alvo = request.form.get('data')
        entrada = request.form.get('entrada')
        saida_almoco = request.form.get('saida_almoco')
        # Ajustado para o nome real da sua coluna no banco:
        retorno_almoco = request.form.get('volta_almoco') 
        saida = request.form.get('saida')

        # Busca carga horária para cálculo preciso
        cur.execute("SELECT carga_horaria FROM usuarios WHERE id = %s", (user_id,))
        user_info = cur.fetchone()
        carga_h = float(user_info['carga_horaria']) if user_info else 8.0
        
        # Cálculos (h1: manhã, h2: tarde)
        h1 = calcular_horas(entrada, saida_almoco)
        h2 = calcular_horas(retorno_almoco, saida)
        total_t = h1 + h2
        saldo = total_t - carga_h

        # UPDATE usando nomes de colunas da imagem
        sql_update = """
            UPDATE registros_ponto 
            SET entrada = %s, saida_almoco = %s, retorno_almoco = %s, 
                saida = %s, total_trabalhado = %s, saldo_dia = %s
            WHERE usuario_id = %s AND data_registro = %s
        """
        cur.execute(sql_update, (entrada, saida_almoco, retorno_almoco, 
                                 saida, total_t, saldo, user_id, data_alvo))
        
        if cur.rowcount == 0:
            # INSERT usando nomes de colunas da imagem
            sql_insert = """
                INSERT INTO registros_ponto (usuario_id, data_registro, entrada, 
                saida_almoco, retorno_almoco, saida, total_trabalhado, saldo_dia)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """
            cur.execute(sql_insert, (user_id, data_alvo, entrada, saida_almoco, 
                                     retorno_almoco, saida, total_t, saldo))
            
        db.commit()
        return redirect(url_for('dashboard_rh'))

    # --- ESTA PARTE DEVE ESTAR FORA DO IF POST (Alinhada à esquerda) ---
    cur.execute("SELECT * FROM usuarios WHERE id = %s", (user_id,))
    funcionario = cur.fetchone()

    cur.execute("""
        SELECT * FROM registros_ponto 
        WHERE usuario_id = %s 
        ORDER BY data_registro DESC 
        LIMIT 30
    """, (user_id,))
    historico = cur.fetchall()

    return render_template('editar_ponto.html', 
                           funcionario=funcionario, 
                           historico=historico,
                           hoje=datetime.now().date())

# ==================== ROTAS EXPERIMENTAIS/DE DESENVOLVIMENTO ====================
# ATENÇÃO: As rotas abaixo são experimentais ou estão incompletas

@app.route('/gestao_total')
@app.route('/gestao_total/<int:funcionario_id>')
@login_required
def gestao_total(funcionario_id=None):
    """
    Painel estilo WhatsApp: lista de funcionários à esquerda,
    histórico selecionado à direita.
    """
    db = get_db()
    with db.cursor() as cur:
        # LADO ESQUERDO: Lista de funcionários ativos
        cur.execute("SELECT id, nome FROM usuarios WHERE status = 'ativo'")
        lista_funcionarios = cur.fetchall()

        historico_selecionado = []
        funcionario_nome = ""

        # LADO DIREITO: Histórico do funcionário selecionado
        if funcionario_id:
            cur.execute("SELECT nome FROM usuarios WHERE id = %s", (funcionario_id,))
            res = cur.fetchone()
            funcionario_nome = res['nome'] if res else ""

            # Busca o histórico completo
            cur.execute("""
                SELECT id, data_registro, entrada, saida, criado_em 
                FROM registros 
                WHERE usuario_id = %s 
                ORDER BY data_registro DESC
            """, (funcionario_id,))
            historico_selecionado = cur.fetchall()

    return render_template('painel_estilo_wpp.html', 
                           funcionarios=lista_funcionarios, 
                           historico=historico_selecionado,
                           nome_selecionado=funcionario_nome)


@app.route('/historico_admin')
@app.route('/historico_admin/<int:usuario_id>')
@login_required
def historico_admin(usuario_id=None):
    """
    Versão alternativa do painel estilo WhatsApp.
    """
    db = get_db()
    cur = db.cursor()
    
    # Lista de funcionários (barra lateral)
    cur.execute("SELECT id, nome FROM usuarios WHERE status = 'ativo'")
    lista_usuarios = cur.fetchall()
    
    # Histórico do funcionário selecionado
    historico = []
    usuario_selecionado = None
    if usuario_id:
        cur.execute("SELECT nome FROM usuarios WHERE id = %s", (usuario_id,))
        usuario_selecionado = cur.fetchone()
        
        cur.execute("""
            SELECT id, data_registro, entrada, saida, criado_em 
            FROM pontos 
            WHERE usuario_id = %s 
            ORDER BY data_registro DESC
        """, (usuario_id,))
        historico = cur.fetchall()
        
    return render_template('historico_estilo_wpp.html', 
                           usuarios=lista_usuarios, 
                           historico=historico, 
                           selecionado=usuario_selecionado)


# ==================== ROTAS OBSOLETAS ====================
# As rotas abaixo estão aqui para compatibilidade, mas podem estar obsoletas

@app.route('/funcionario/bater_entrada', methods=['POST'])
@login_required
def bater_ponto_entrada():
    """
    OBSOLETA: Use /registrar_ponto
    Rota antiga para bater entrada (mantida para compatibilidade).
    """
    db = get_db()
    user_id = current_user.id
    agora = datetime.now()
    hoje = agora.date()

    with db.cursor() as cur:
        # Verifica se já existe ponto hoje
        cur.execute("SELECT id FROM registros_ponto WHERE usuario_id = %s AND data_registro = %s", (user_id, hoje))
        if cur.fetchone():
            flash('Você já registrou a entrada hoje!', 'warning')
        else:
            cur.execute("""
                INSERT INTO registros_ponto (usuario_id, data_registro, horario_entrada, status)
                VALUES (%s, %s, %s, 'aberto')
            """, (user_id, hoje, agora))
            db.commit()
            flash('Entrada registrada com sucesso!', 'success')
            
    return redirect(url_for('area_funcionario'))


@app.route('/funcionario/bater_saida', methods=['POST'])
@login_required
def bater_ponto_saida():
    """
    OBSOLETA: Use /registrar_ponto
    Rota antiga para bater saída (mantida para compatibilidade).
    """
    db = get_db()
    user_id = current_user.id
    agora = datetime.now()
    hoje = agora.date()

    with db.cursor() as cur:
        cur.execute("""
            UPDATE registros_ponto 
            SET horario_saida = %s, status = 'fechado'
            WHERE usuario_id = %s AND data_registro = %s AND status = 'aberto'
        """, (agora, user_id, hoje))
        db.commit()
        flash('Saída registrada com sucesso! Bom descanso.', 'success')
            
    return redirect(url_for('area_funcionario'))


# ==================== API REST ====================

@app.route("/api/historico/<int:usuario_id>", methods=["GET"])
def historico(usuario_id):
    """
    API REST para buscar histórico de ponto de um funcionário.
    Retorna JSON com os últimos N dias de registros.
    
    Parâmetros de query:
        dias (int): Número de dias para retornar (padrão: 30)
    
    Exemplo de uso:
        GET /api/historico/5?dias=7
        Retorna os últimos 7 dias do funcionário com ID 5
    """
    dias = int(request.args.get("dias", 30))
    db = get_db()
    
    with db.cursor() as cur:
        cur.execute(
            """SELECT id, data, entrada, inicio_almoco, fim_almoco, saida, horas_trabalhadas 
               FROM registros 
               WHERE usuario_id=%s 
               ORDER BY data DESC 
               LIMIT %s""",
            (usuario_id, dias)
        )
        rows = cur.fetchall()
    
    # Converte datetimes para string para serialização JSON
    for r in rows:
        for k in ("entrada", "inicio_almoco", "fim_almoco", "saida"):
            if r.get(k):
                r[k] = r[k].strftime("%Y-%m-%d %H:%M:%S")
    
    return jsonify(rows)


# ==================== INICIALIZAÇÃO DA APLICAÇÃO ====================

if __name__ == '__main__':
    # Pega a porta que o Render fornece, ou usa 5000 se estiver no PC
    port = int(os.environ.get("PORT", 5000))
    # Rodamos com debug=True para você conseguir ver o erro na tela agora
    app.run(host='0.0.0.0', port=port, debug=True)


# ==================== NOTAS DE DESENVOLVIMENTO ====================
"""
PRÓXIMOS PASSOS SUGERIDOS:

1. SEGURANÇA:
   - Mudar SECRET_KEY para variável de ambiente
   - Implementar rate limiting para login
   - Adicionar HTTPS obrigatório em produção
   - Implementar tokens CSRF

2. FUNCIONALIDADES:
   - Sistema de relatórios (PDF/Excel)
   - Justificativas para atrasos/faltas
   - Notificações por email
   - Dashboard com gráficos

3. BANCO DE DADOS:
   - Implementar migrations (Alembic)
   - Adicionar índices para otimização
   - Backup automático
   - Pool de conexões

4. MELHORIAS DE CÓDIGO:
   - Separar rotas em Blueprints
   - Criar service layer para lógica de negócio
   - Implementar testes unitários
   - Adicionar logging estruturado

5. UI/UX:
   - Tornar responsivo para mobile
   - Adicionar modo escuro
   - Melhorar feedback visual
   - Implementar PWA para acesso offline

6. REMOVER ANTES DE PRODUÇÃO:
   - Rota /reset_meu_ponto
   - Prints de debug
   - Senhas hardcoded no DB_CONFIG
"""
