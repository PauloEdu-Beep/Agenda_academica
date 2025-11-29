# app.py
from flask import Flask, render_template, request, redirect, url_for, flash, session
import pymysql.cursors
from functools import wraps
from db_config import db_config
# --- SEGURANÇA: Importação para criar e verificar Hashes de senha ---
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'chave_super_secreta_para_sessao'

# Configuração Global
SEMESTRE_ATUAL = "2024.1"

# --- Conexão com o Banco de Dados ---
def get_db_connection():
    try:
        conn = pymysql.connect(host=db_config['host'],
                             user=db_config['user'],
                             password=db_config['password'],
                             database=db_config['database'],
                             cursorclass=pymysql.cursors.DictCursor)
        return conn
    except pymysql.MySQLError as err:
        print(f"Erro de conexão com o banco: {err}")
        return None

# --- Decorators de Segurança ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'usuario_id' not in session:
            flash("Por favor, faça login para acessar.", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('tipo') != 'ADMIN':
            flash("Acesso negado. Requer privilégios de Administrador.", "danger")
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

# --- Rotas de Autenticação ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        senha_digitada = request.form['senha']
        
        conn = get_db_connection()
        if not conn:
            flash("Erro ao conectar ao banco de dados.", "danger")
            return render_template('login.html')
            
        cursor = conn.cursor()
        
        # --- SEGURANÇA: Busca usuário APENAS pelo e-mail ---
        cursor.execute("SELECT * FROM Usuario WHERE email = %s", (email,))
        user = cursor.fetchone()
        
        cursor.close()
        conn.close()

        # --- SEGURANÇA: Verifica se a senha bate com o Hash ---
        if user and check_password_hash(user['senha_hash'], senha_digitada):
            session['usuario_id'] = user['usuario_id']
            session['nome'] = user['nome_completo']
            session['tipo'] = user['tipo_usuario']
            return redirect(url_for('dashboard'))
        else:
            flash('Email ou senha inválidos', 'danger')
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- Dashboard ---
@app.route('/')
@login_required
def dashboard():
    return render_template('dashboard.html')

# ==============================================================================
#      LÓGICA ACADÊMICA (ALUNO, PROFESSOR, AGENDA)
# ==============================================================================

# --- Matrícula (Aluno) ---
@app.route('/matriculas', methods=['GET', 'POST'])
@login_required
def gerenciar_matriculas():
    if session['tipo'] != 'ALUNO':
         flash("Apenas alunos podem realizar matrículas.", "info")
         return redirect(url_for('dashboard'))

    conn = get_db_connection()
    if not conn: return redirect(url_for('dashboard'))
    cursor = conn.cursor()

    if request.method == 'POST':
        disciplina_id = request.form['disciplina_id']
        
        try:
            cursor.execute("INSERT INTO Matricula (usuario_id, disciplina_id, semestre) VALUES (%s, %s, %s)",
                           (session['usuario_id'], disciplina_id, SEMESTRE_ATUAL))
            conn.commit()
            flash('Matrícula realizada com sucesso!', 'success')
        except pymysql.MySQLError as e:
            conn.rollback()
            flash(f'Erro na matrícula (você já está matriculado?): {e}', 'danger')

    cursor.execute("""
        SELECT d.*, 
            (SELECT COUNT(*) FROM Matricula m 
             WHERE m.disciplina_id = d.disciplina_id 
             AND m.usuario_id = %s 
             AND m.semestre = %s) as matriculado
        FROM Disciplina d
    """, (session['usuario_id'], SEMESTRE_ATUAL))
    disciplinas = cursor.fetchall()
    
    cursor.close()
    conn.close()
    return render_template('matriculas.html', disciplinas=disciplinas)

# --- Agenda (Compromissos) ---
@app.route('/compromissos')
@login_required
def list_compromissos():
    conn = get_db_connection()
    if not conn: return redirect(url_for('dashboard'))
    cursor = conn.cursor()
    
    uid = session['usuario_id']
    tipo = session['tipo']

    if tipo == 'ALUNO':
        query = """
            SELECT c.*, d.nome_disciplina, u_prof.nome_completo as professor_nome,
                   u_prof.usuario_id as prof_id_dono
            FROM Compromisso c
            LEFT JOIN Disciplina d ON c.turma_disciplina_id = d.disciplina_id
            LEFT JOIN Usuario u_prof ON c.turma_usuario_id = u_prof.usuario_id
            LEFT JOIN Matricula m ON m.disciplina_id = c.turma_disciplina_id 
                                  AND m.usuario_id = %s 
                                  AND m.semestre = %s
            WHERE c.aluno_usuario_id = %s 
               OR (c.turma_usuario_id IS NOT NULL AND m.usuario_id IS NOT NULL)
            ORDER BY c.data_hora_inicio ASC
        """
        cursor.execute(query, (uid, SEMESTRE_ATUAL, uid))
        
    elif tipo == 'PROFESSOR':
        query = """
            SELECT c.*, d.nome_disciplina, 'Você' as professor_nome,
                   c.turma_usuario_id as prof_id_dono
            FROM Compromisso c
            JOIN Disciplina d ON c.turma_disciplina_id = d.disciplina_id
            WHERE c.turma_usuario_id = %s
            ORDER BY c.data_hora_inicio ASC
        """
        cursor.execute(query, (uid,))
        
    else: # ADMIN
        query = """
            SELECT c.*, d.nome_disciplina, u.nome_completo as professor_nome
            FROM Compromisso c
            LEFT JOIN Disciplina d ON c.turma_disciplina_id = d.disciplina_id
            LEFT JOIN Usuario u ON c.turma_usuario_id = u.usuario_id
            ORDER BY c.data_hora_inicio DESC
        """
        cursor.execute(query)

    compromissos = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('compromissos.html', compromissos=compromissos)

@app.route('/compromissos/add', methods=['GET', 'POST'])
@login_required
def add_compromisso():
    conn = get_db_connection()
    if not conn: return redirect(url_for('dashboard'))
    cursor = conn.cursor()

    tipo_usuario = session['tipo']

    if request.method == 'POST':
        titulo = request.form['titulo']
        descricao = request.form['descricao']
        inicio = request.form['data_hora_inicio']
        fim = request.form.get('data_hora_fim') or None
        tipo_comp = request.form['tipo_compromisso']
        
        aluno_id = None
        turma_prof_id = None
        turma_disc_id = None

        if tipo_usuario == 'ALUNO':
            aluno_id = session['usuario_id']
            if tipo_comp not in ['TAREFA', 'OUTRO']: 
                tipo_comp = 'OUTRO'

        elif tipo_usuario == 'PROFESSOR':
            turma_str = request.form.get('turma_id')
            if not turma_str:
                flash('Erro: Selecione uma turma.', 'danger')
                return redirect(url_for('add_compromisso'))
            
            p_id, d_id = turma_str.split('-')
            
            cursor.execute("SELECT * FROM Professor_Disciplina WHERE usuario_id=%s AND disciplina_id=%s", (p_id, d_id))
            alocacao = cursor.fetchone()
            
            if not alocacao or int(p_id) != session['usuario_id']:
                flash('Acesso negado: Disciplina inválida.', 'danger')
                return redirect(url_for('add_compromisso'))
            
            turma_prof_id = p_id
            turma_disc_id = d_id

        try:
            cursor.execute("""
                INSERT INTO Compromisso 
                (titulo, descricao, data_hora_inicio, data_hora_fim, tipo_compromisso, aluno_usuario_id, turma_usuario_id, turma_disciplina_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (titulo, descricao, inicio, fim, tipo_comp, aluno_id, turma_prof_id, turma_disc_id))
            conn.commit()
            flash('Compromisso agendado com sucesso!', 'success')
        except pymysql.MySQLError as err:
            conn.rollback()
            flash(f'Erro ao salvar: {err}', 'danger')
        
        cursor.close()
        conn.close()
        return redirect(url_for('list_compromissos'))

    turmas_professor = []
    if tipo_usuario == 'PROFESSOR':
        cursor.execute("""
            SELECT pd.usuario_id, pd.disciplina_id, d.nome_disciplina
            FROM Professor_Disciplina pd
            JOIN Disciplina d ON pd.disciplina_id = d.disciplina_id
            WHERE pd.usuario_id = %s
        """, (session['usuario_id'],))
        turmas_professor = cursor.fetchall()

    cursor.close()
    conn.close()
    return render_template('compromisso_form.html', turmas=turmas_professor, action='add', compromisso=None)

@app.route('/compromissos/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_compromisso(id):
    conn = get_db_connection()
    if not conn: return redirect(url_for('list_compromissos'))
    cursor = conn.cursor()
    
    uid = session['usuario_id']
    tipo = session['tipo']
    
    query_base = "SELECT * FROM Compromisso WHERE compromisso_id = %s"
    params = [id]
    
    if tipo == 'ALUNO':
        query_base += " AND aluno_usuario_id = %s"
        params.append(uid)
    elif tipo == 'PROFESSOR':
        query_base += " AND turma_usuario_id = %s"
        params.append(uid)

    cursor.execute(query_base, tuple(params))
    compromisso = cursor.fetchone()

    if not compromisso:
        flash("Compromisso não encontrado ou você não tem permissão para editá-lo.", "danger")
        cursor.close()
        conn.close()
        return redirect(url_for('list_compromissos'))

    if request.method == 'POST':
        titulo = request.form['titulo']
        descricao = request.form['descricao']
        inicio = request.form['data_hora_inicio']
        
        try:
            cursor.execute("""
                UPDATE Compromisso 
                SET titulo=%s, descricao=%s, data_hora_inicio=%s
                WHERE compromisso_id=%s
            """, (titulo, descricao, inicio, id))
            conn.commit()
            flash('Compromisso atualizado!', 'success')
            return redirect(url_for('list_compromissos'))
        except pymysql.MySQLError as err:
            conn.rollback()
            flash(f'Erro ao atualizar: {err}', 'danger')

    turmas_professor = [] 
    
    cursor.close()
    conn.close()
    return render_template('compromisso_form.html', action='edit', compromisso=compromisso, turmas=turmas_professor)

@app.route('/compromissos/delete/<int:id>', methods=['POST'])
@login_required
def delete_compromisso(id):
    conn = get_db_connection()
    if not conn: return redirect(url_for('list_compromissos'))
    cursor = conn.cursor()
    try:
        if session['tipo'] == 'ALUNO':
            cursor.execute("DELETE FROM Compromisso WHERE compromisso_id = %s AND aluno_usuario_id = %s", (id, session['usuario_id']))
        elif session['tipo'] == 'PROFESSOR':
             cursor.execute("DELETE FROM Compromisso WHERE compromisso_id = %s AND turma_usuario_id = %s", (id, session['usuario_id']))
        else:
            cursor.execute("DELETE FROM Compromisso WHERE compromisso_id = %s", (id,))
        
        if cursor.rowcount == 0:
             flash('Ação negada ou item não encontrado.', 'warning')
        else:
             conn.commit()
             flash('Compromisso removido.', 'success')
             
    except pymysql.MySQLError as err:
        flash(f'Erro ao remover: {err}', 'danger')
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('list_compromissos'))

# ==============================================================================
#      ÁREA DO ADMINISTRADOR
# ==============================================================================

@app.route('/admin/alocacao', methods=['GET', 'POST'])
@login_required
@admin_required
def alocacao_professor():
    conn = get_db_connection()
    if not conn: return redirect(url_for('dashboard'))
    cursor = conn.cursor()

    if request.method == 'POST':
        prof_id = request.form['professor_id']
        disc_id = request.form['disciplina_id']
        
        try:
            cursor.execute("INSERT INTO Professor_Disciplina (usuario_id, disciplina_id, semestre) VALUES (%s, %s, %s)",
                           (prof_id, disc_id, SEMESTRE_ATUAL))
            conn.commit()
            flash('Vínculo criado com sucesso!', 'success')
        except pymysql.MySQLError as e:
            conn.rollback()
            flash(f'Erro: {e}', 'danger')

    cursor.execute("SELECT u.usuario_id, u.nome_completo FROM Usuario u WHERE u.tipo_usuario = 'PROFESSOR'")
    professores = cursor.fetchall()
    
    cursor.execute("SELECT * FROM Disciplina ORDER BY nome_disciplina")
    disciplinas = cursor.fetchall()
    
    cursor.execute("""
        SELECT pd.*, u.nome_completo, d.nome_disciplina 
        FROM Professor_Disciplina pd
        JOIN Usuario u ON pd.usuario_id = u.usuario_id
        JOIN Disciplina d ON pd.disciplina_id = d.disciplina_id
        WHERE pd.semestre = %s
        ORDER BY d.nome_disciplina
    """, (SEMESTRE_ATUAL,))
    alocacoes = cursor.fetchall()
    
    cursor.close()
    conn.close()
    return render_template('admin_alocacao.html', professores=professores, disciplinas=disciplinas, alocacoes=alocacoes)

# --- CRUD ALUNOS ---
@app.route('/alunos')
@login_required
@admin_required
def list_alunos():
    conn = get_db_connection()
    if not conn: return redirect(url_for('dashboard'))
    cursor = conn.cursor()
    cursor.execute("""
        SELECT u.usuario_id, u.nome_completo, u.email, a.matricula
        FROM Usuario u
        JOIN Aluno a ON u.usuario_id = a.usuario_id
        WHERE u.tipo_usuario = 'ALUNO' ORDER BY u.nome_completo
    """)
    alunos = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('alunos.html', alunos=alunos)

@app.route('/alunos/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_aluno():
    if request.method == 'POST':
        nome = request.form['nome_completo']
        email = request.form['email']
        matricula = request.form['matricula']
        
        # --- SEGURANÇA: GERA HASH DA SENHA PADRÃO ---
        senha_hash = generate_password_hash("123456") 

        conn = get_db_connection()
        if not conn: return redirect(url_for('list_alunos'))
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO Usuario (nome_completo, email, senha_hash, tipo_usuario) VALUES (%s, %s, %s, 'ALUNO')", (nome, email, senha_hash))
            usuario_id = cursor.lastrowid
            cursor.execute("INSERT INTO Aluno (usuario_id, matricula) VALUES (%s, %s)", (usuario_id, matricula))
            conn.commit()
            flash('Aluno adicionado! Senha padrão: 123456', 'success')
        except pymysql.MySQLError as err:
            conn.rollback()
            flash(f'Erro: {err}', 'danger')
        finally:
            cursor.close()
            conn.close()
        return redirect(url_for('list_alunos'))
    return render_template('aluno_form.html', action='add')

@app.route('/alunos/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_aluno(id):
    conn = get_db_connection()
    if not conn: return redirect(url_for('list_alunos'))
    cursor = conn.cursor()

    if request.method == 'POST':
        nome = request.form['nome_completo']
        email = request.form['email']
        matricula = request.form['matricula']
        try:
            cursor.execute("UPDATE Usuario SET nome_completo=%s, email=%s WHERE usuario_id=%s", (nome, email, id))
            cursor.execute("UPDATE Aluno SET matricula=%s WHERE usuario_id=%s", (matricula, id))
            conn.commit()
            flash('Aluno atualizado!', 'success')
        except pymysql.MySQLError as err:
            conn.rollback()
            flash(f'Erro: {err}', 'danger')
        finally:
            cursor.close()
            conn.close()
        return redirect(url_for('list_alunos'))
    
    cursor.execute("SELECT u.usuario_id, u.nome_completo, u.email, a.matricula FROM Usuario u JOIN Aluno a ON u.usuario_id = a.usuario_id WHERE u.usuario_id = %s", (id,))
    aluno = cursor.fetchone()
    cursor.close()
    conn.close()
    return render_template('aluno_form.html', action='edit', aluno=aluno)

@app.route('/alunos/delete/<int:id>', methods=['POST'])
@login_required
@admin_required
def delete_aluno(id):
    conn = get_db_connection()
    if not conn: return redirect(url_for('list_alunos'))
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM Usuario WHERE usuario_id = %s", (id,))
        conn.commit()
        flash('Aluno removido!', 'success')
    except pymysql.MySQLError as err:
        flash(f'Erro: {err}', 'danger')
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('list_alunos'))

# --- CRUD PROFESSORES ---
@app.route('/professores')
@login_required
@admin_required
def list_professores():
    conn = get_db_connection()
    if not conn: return redirect(url_for('dashboard'))
    cursor = conn.cursor()
    cursor.execute("""
        SELECT u.usuario_id, u.nome_completo, u.email, p.departamento
        FROM Usuario u
        JOIN Professor p ON u.usuario_id = p.usuario_id
        WHERE u.tipo_usuario = 'PROFESSOR' ORDER BY u.nome_completo
    """)
    professores = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('professores.html', professores=professores)

@app.route('/professores/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_professor():
    if request.method == 'POST':
        nome = request.form['nome_completo']
        email = request.form['email']
        departamento = request.form['departamento']
        
        # --- SEGURANÇA: GERA HASH DA SENHA PADRÃO ---
        senha_hash = generate_password_hash("123456")

        conn = get_db_connection()
        if not conn: return redirect(url_for('list_professores'))
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO Usuario (nome_completo, email, senha_hash, tipo_usuario) VALUES (%s, %s, %s, 'PROFESSOR')", (nome, email, senha_hash))
            usuario_id = cursor.lastrowid
            cursor.execute("INSERT INTO Professor (usuario_id, departamento) VALUES (%s, %s)", (usuario_id, departamento))
            conn.commit()
            flash('Professor adicionado! Senha padrão: 123456', 'success')
        except pymysql.MySQLError as err:
            conn.rollback()
            flash(f'Erro: {err}', 'danger')
        finally:
            cursor.close()
            conn.close()
        return redirect(url_for('list_professores'))
    return render_template('professor_form.html', action='add')

@app.route('/professores/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_professor(id):
    conn = get_db_connection()
    if not conn: return redirect(url_for('list_professores'))
    cursor = conn.cursor()
    if request.method == 'POST':
        nome = request.form['nome_completo']
        email = request.form['email']
        departamento = request.form['departamento']
        try:
            cursor.execute("UPDATE Usuario SET nome_completo=%s, email=%s WHERE usuario_id=%s", (nome, email, id))
            cursor.execute("UPDATE Professor SET departamento=%s WHERE usuario_id=%s", (departamento, id))
            conn.commit()
            flash('Professor atualizado!', 'success')
        except pymysql.MySQLError as err:
            conn.rollback()
            flash(f'Erro: {err}', 'danger')
        finally:
            cursor.close()
            conn.close()
        return redirect(url_for('list_professores'))
    
    cursor.execute("SELECT u.usuario_id, u.nome_completo, u.email, p.departamento FROM Usuario u JOIN Professor p ON u.usuario_id = p.usuario_id WHERE u.usuario_id = %s", (id,))
    professor = cursor.fetchone()
    cursor.close()
    conn.close()
    return render_template('professor_form.html', action='edit', professor=professor)

@app.route('/professores/delete/<int:id>', methods=['POST'])
@login_required
@admin_required
def delete_professor(id):
    conn = get_db_connection()
    if not conn: return redirect(url_for('list_professores'))
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM Usuario WHERE usuario_id = %s", (id,))
        conn.commit()
        flash('Professor removido!', 'success')
    except pymysql.MySQLError as err:
        flash(f'Erro: {err}', 'danger')
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('list_professores'))

# --- CRUD DISCIPLINAS ---
@app.route('/disciplinas')
@login_required
@admin_required
def list_disciplinas():
    conn = get_db_connection()
    if not conn: return redirect(url_for('dashboard'))
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM Disciplina ORDER BY nome_disciplina")
    disciplinas = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('disciplinas.html', disciplinas=disciplinas)

@app.route('/disciplinas/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_disciplina():
    if request.method == 'POST':
        nome = request.form['nome_disciplina']
        codigo = request.form['codigo_disciplina']
        carga = request.form.get('carga_horaria') or None
        
        conn = get_db_connection()
        if not conn: return redirect(url_for('list_disciplinas'))
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO Disciplina (nome_disciplina, codigo_disciplina, carga_horaria) VALUES (%s, %s, %s)", (nome, codigo, carga))
            conn.commit()
            flash('Disciplina adicionada!', 'success')
        except pymysql.MySQLError as err:
            flash(f'Erro: {err}', 'danger')
        finally:
            cursor.close()
            conn.close()
        return redirect(url_for('list_disciplinas'))
    return render_template('disciplina_form.html', action='add')

@app.route('/disciplinas/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_disciplina(id):
    conn = get_db_connection()
    if not conn: return redirect(url_for('list_disciplinas'))
    cursor = conn.cursor()
    
    if request.method == 'POST':
        nome = request.form['nome_disciplina']
        codigo = request.form['codigo_disciplina']
        carga = request.form.get('carga_horaria') or None
        try:
            cursor.execute("UPDATE Disciplina SET nome_disciplina=%s, codigo_disciplina=%s, carga_horaria=%s WHERE disciplina_id=%s", (nome, codigo, carga, id))
            conn.commit()
            flash('Disciplina atualizada!', 'success')
        except pymysql.MySQLError as err:
            flash(f'Erro: {err}', 'danger')
        finally:
            cursor.close()
            conn.close()
        return redirect(url_for('list_disciplinas'))

    cursor.execute("SELECT * FROM Disciplina WHERE disciplina_id = %s", (id,))
    disciplina = cursor.fetchone()
    cursor.close()
    conn.close()
    return render_template('disciplina_form.html', action='edit', disciplina=disciplina)

@app.route('/disciplinas/delete/<int:id>', methods=['POST'])
@login_required
@admin_required
def delete_disciplina(id):
    conn = get_db_connection()
    if not conn: return redirect(url_for('list_disciplinas'))
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM Disciplina WHERE disciplina_id = %s", (id,))
        conn.commit()
        flash('Disciplina removida!', 'success')
    except pymysql.MySQLError as err:
        conn.rollback()
        flash(f'Erro: {err}', 'danger')
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('list_disciplinas'))

if __name__ == '__main__':
    app.run(debug=True)