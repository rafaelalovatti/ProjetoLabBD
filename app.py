from flask import Flask, render_template, request, redirect, session, g
from datetime import datetime
from io import StringIO
import csv
import random
import bcrypt
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)
app.secret_key = "segredo"

DATABASE = {
    "dbname": "atividade2",
    "user": "jpdm",
    "password": "jp2202",
    "host": "localhost",
    "port": "5432",
}

def get_db():
    if 'db' not in g:
        g.db = psycopg2.connect(**DATABASE)
        g.db.autocommit = True
    return g.db

def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

@app.route("/", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        db = get_db()
        try:
            with db.cursor() as cur:
                cur.execute(
                    "SELECT * FROM USERS WHERE Login = %s AND Password = crypt(%s, Password)",
                    (request.form["login"], request.form["password"]),
                )
                user = cur.fetchone()
                if user:
                    session["user"] = dict(zip([col[0] for col in cur.description], user))
                    cur.execute(
                        "INSERT INTO Users_Log (Userid, LoginTime) VALUES (%s, %s)",
                        (user[0], datetime.now()),
                    )
                    return redirect("/dashboard")
                else:
                    error = "Login inválido"
        except Exception as e:
            print(f"Erro no login: {e}")
        finally:
            close_db()
    return render_template("login.html", error=error)

@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        print("Redirecionando: sessão não encontrada")
        return redirect("/")
    
    user = session["user"]
    print(f"Sessão: {user}")
    db = get_db()
    extra_info = ""
    resumo = {}
    
    try:
        with db.cursor(cursor_factory=RealDictCursor) as cur:
            tipo = user["tipo"]
            print(f"Tipo de usuário (raw): '{tipo}'")  # Log para depuração
            
            if tipo == "Piloto":
                piloto_id = user["idoriginal"]
                print(f"Piloto ID: {piloto_id}")
                cur.execute(
                    """
                    SELECT CONCAT(Forename, ' ', Surname) AS full_name
                    FROM Driver
                    WHERE DriverId = %s
                    """,
                    (piloto_id,),
                )
                full_name = cur.fetchone()
                extra_info = f"Piloto: {full_name['full_name'] if full_name else 'ID ' + str(piloto_id)}"
                
                # Get first and last year
                cur.execute("SELECT FirstYear, LastYear FROM Public.ReportDriverYears(%s)", (piloto_id,))
                years = cur.fetchone()
                first_year = years['firstyear'] if years else 0
                last_year = years['lastyear'] if years else 0
                
                # Get detailed performance
                cur.execute("SELECT * FROM Public.ReportDriverPerformance(%s)", (piloto_id,))
                performance = cur.fetchall()
                
                resumo = {
                    "Primeiro ano de dados": first_year,
                    "Último ano de dados": last_year,
                    "Desempenho detalhado": [
                        {
                            "Ano": row['year'],
                            "Circuito": row['circuitname'],
                            "Pontos": row['totalpoints'],
                            "Vitórias": row['totalwins'],
                            "Corridas": row['totalraces']
                        } for row in performance
                    ]
                }
            
            elif tipo == "Escuderia":
                escuderia_id = user["idoriginal"]
                print(f"Escuderia ID: {escuderia_id}")
                cur.execute(
                    """
                    SELECT name
                    FROM Constructors
                    WHERE ConstructorId = %s
                    """,
                    (escuderia_id,),
                )
                escuderia_nome = cur.fetchone()
                extra_info = f"Escuderia: {escuderia_nome['name'] if escuderia_nome else 'ID ' + str(escuderia_id)}"
                
                cur.execute("SELECT Public.ReportConstructorWins(%s) AS wins", (escuderia_id,))
                wins = cur.fetchone()['wins'] or 0
                
                cur.execute("SELECT Public.ReportDistinctDrivers(%s) AS driver_count", (escuderia_id,))
                driver_count = cur.fetchone()['driver_count'] or 0
                
                cur.execute("SELECT FirstYear, LastYear FROM Public.ReportConstructorYears(%s)", (escuderia_id,))
                years = cur.fetchone()
                first_year = years['firstyear'] if years else 0
                last_year = years['lastyear'] if years else 0
                
                resumo = {
                    "Vitórias da escuderia": wins,
                    "Quantidade de pilotos diferentes": driver_count,
                    "Primeiro ano de dados": first_year,
                    "Último ano de dados": last_year
                }
            
            elif tipo == "Administrador":
                extra_info = "Administrador - acesso total"
                try:
                    # 1. Quantidade total de pilotos
                    cur.execute("SELECT COUNT(*) AS total_pilotos FROM Driver")
                    total_pilotos = cur.fetchone()['total_pilotos']

                    # Quantidade total de escuderias
                    cur.execute("SELECT COUNT(*) AS total_escuderias FROM Constructors")
                    total_escuderias = cur.fetchone()['total_escuderias']

                    # Quantidade total de temporadas
                    cur.execute("SELECT COUNT(*) AS total_temporadas FROM Seasons")
                    total_temporadas = cur.fetchone()['total_temporadas']

                    # Ano corrente
                    cur.execute("SELECT MAX(year) AS ano_corrente FROM Races")
                    ano_corrente = cur.fetchone()['ano_corrente']

                    # 2. Corridas do ano corrente com voltas e tempo
                    cur.execute("""
                        SELECT r.name, MAX(res.laps) AS total_voltas, ROUND(MIN(res.milliseconds)/1000.0, 2) AS tempo_segundos
                        FROM Races r
                        JOIN Results res ON r.raceid = res.raceid
                        WHERE r.year = %s
                        GROUP BY r.raceid, r.name
                        ORDER BY r.name
                    """, (ano_corrente,))
                    corridas_ano = cur.fetchall()

                    # 3. Escuderias e pontos no ano corrente
                    cur.execute("""
                        SELECT c.name, COALESCE(SUM(res.points), 0) AS total_pontos
                        FROM Constructors c
                        LEFT JOIN Results res ON c.constructorid = res.constructorid
                        LEFT JOIN Races r ON res.raceid = r.raceid
                        WHERE r.year = %s OR r.year IS NULL
                        GROUP BY c.constructorid, c.name
                        ORDER BY total_pontos DESC
                    """, (ano_corrente,))
                    escuderias_pontos = cur.fetchall()

                    # 4. Pilotos e pontos no ano corrente
                    cur.execute("""
                        SELECT CONCAT(d.forename, ' ', d.surname) AS piloto, COALESCE(SUM(res.points), 0) AS total_pontos
                        FROM Driver d
                        LEFT JOIN Results res ON d.driverid = res.driverid
                        LEFT JOIN Races r ON res.raceid = r.raceid
                        WHERE r.year = %s OR r.year IS NULL
                        GROUP BY d.driverid, d.forename, d.surname
                        ORDER BY total_pontos DESC
                    """, (ano_corrente,))
                    pilotos_pontos = cur.fetchall()

                    resumo = {
                        "Total de pilotos": total_pilotos,
                        "Total de escuderias": total_escuderias,
                        "Total de temporadas": total_temporadas,
                        "Ano corrente": ano_corrente,
                        "Corridas do ano corrente": corridas_ano,
                        "Escuderias e pontos": escuderias_pontos,
                        "Pilotos e pontos": pilotos_pontos,
                    }
                    print(f"Resumo Administrador: {resumo}")
                except Exception as e:
                    print(f"Erro nas consultas do administrador: {e}")
                    extra_info = f"Erro ao carregar dados: {str(e)}"
                    resumo = {}
            
            else:
                print("Tipo de usuário desconhecido")
                extra_info = "Tipo desconhecido"
                resumo = {}
    
    except Exception as e:
        print(f"Erro na consulta: {e}")
        extra_info = f"Erro ao carregar dados: {str(e)}"
    
    finally:
        close_db()
    
    print(f"Renderizando dashboard com resumo: {resumo}")
    return render_template("dashboard.html", user=user, extra_info=extra_info, resumo=resumo)

@app.route("/relatorios")
def relatorios():
    if "user" not in session:
        return redirect("/")  # usuário não logado, redireciona para home/login

    user = session["user"]
    # qualquer tipo de usuário pode acessar relatorios, mas no HTML mostra condicionalmente

    return render_template("relatorios.html", user=user)
# ----------------------------------ADMIN ---------------------

@app.route("/admin/cadastrar_piloto", methods=["GET", "POST"])
def cadastrar_piloto():
    print("Sessão atual:", session)
    if "user" not in session or session["user"]["tipo"] != "Administrador":
        print("Redirecionando: usuário não logado ou não administrador")
        return redirect("/")

    msg = ""
    if request.method == "POST":
        driver_ref = request.form["driverref"].strip()
        number = request.form.get("number") or None
        code = request.form.get("code").strip() or None
        forename = request.form["forename"].strip()
        surname = request.form["surname"].strip()
        dob = request.form["dob"].strip()
        nationality = request.form.get("nationality").strip() or None

        db = get_db()
        try:
            with db.cursor(cursor_factory=RealDictCursor) as cur:
                # Gerar um DriverId aleatório único
                max_attempts = 10  # Limite de tentativas para evitar loops infinitos
                for _ in range(max_attempts):
                    driver_id = random.randint(1, 9999999)  # Intervalo arbitrário
                    cur.execute("SELECT 1 FROM Driver WHERE DriverId = %s", (driver_id,))
                    if not cur.fetchone():  # Se não existe, o ID é único
                        break
                else:
                    raise Exception("Não foi possível gerar um DriverId único após várias tentativas")

                # Insere na tabela Driver, incluindo o DriverId gerado
                cur.execute(
                    """
                    INSERT INTO Driver 
                    (driverid, driverref, number, code, forename, surname, dob, nationality)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING driverid
                    """,
                    (driver_id, driver_ref, number, code, forename, surname, dob, nationality),
                )
                driver_id = cur.fetchone()['driverid']
                print(f"Piloto inserido com DriverId: {driver_id}")

                # A inserção em users é feita automaticamente pelo trigger sync_driver_user
                # Não é necessário inserir manualmente aqui

            db.commit()
            msg = "Piloto cadastrado com sucesso!"
            print(f"Sucesso: {msg}")
        except Exception as e:
            db.rollback()
            msg = f"Erro ao cadastrar piloto: {str(e)}"
            print(f"Erro: {msg}")
        finally:
            close_db()

    return render_template("cadastrar_piloto.html", msg=msg)

@app.route("/admin/cadastrar_escuderia", methods=["GET", "POST"])
def cadastrar_escuderia():
    if "user" not in session or session["user"]["tipo"] != "Administrador":
        print("Redirecionando: usuário não logado ou não administrador")
        return redirect("/")

    msg = ""
    if request.method == "POST":
        ref = request.form["ref"].strip()
        name = request.form["name"].strip()
        nationality = request.form["nationality"].strip()
        url = request.form.get("url", "").strip()

        if not ref or not name or not nationality:
            msg = "Erro: Todos os campos obrigatórios (Referência, Nome, Nacionalidade) devem ser preenchidos."
        else:
            db = get_db()
            try:
                with db.cursor(cursor_factory=RealDictCursor) as cur:
                    # Gerar um ConstructorId aleatório único
                    max_attempts = 10
                    for _ in range(max_attempts):
                        constructor_id = random.randint(1, 9999999)
                        cur.execute("SELECT 1 FROM Constructors WHERE ConstructorId = %s", (constructor_id,))
                        if not cur.fetchone():
                            break
                    else:
                        raise Exception("Não foi possível gerar um ConstructorId único após várias tentativas")

                    # Inserir na tabela Constructors
                    cur.execute(
                        """
                        INSERT INTO Constructors (ConstructorId, ConstructorRef, Name, Nationality, Url)
                        VALUES (%s, %s, %s, %s, %s)
                        RETURNING ConstructorId
                        """,
                        (constructor_id, ref, name, nationality, url),
                    )
                    constructor_id = cur.fetchone()['constructorid']
                    print(f"Escuderia inserida com ConstructorId: {constructor_id}")

                db.commit()
                msg = "Escuderia cadastrada com sucesso!"
            except psycopg2.IntegrityError as e:
                db.rollback()
                if "constructors_constructorref_key" in str(e):
                    msg = f"Erro: Referência '{ref}' já existe."
                elif "constructors_name_key" in str(e):
                    msg = f"Erro: Nome '{name}' já existe."
                elif "users_login_key" in str(e):
                    msg = f"Erro: Login '{ref}_c' já existe na tabela de usuários."
                else:
                    msg = f"Erro: Não foi possível cadastrar a escuderia. Detalhe: {str(e)}"
                print(f"Erro de integridade: {e}")
            except Exception as e:
                db.rollback()
                msg = f"Erro inesperado: {str(e)}"
                print(f"Erro inesperado: {e}")
            finally:
                close_db()

    return render_template("cadastrar_escuderia.html", msg=msg)

@app.route("/relatorio1")
def relatorio1():
    if "user" not in session or session["user"]["tipo"] != "Administrador":
        return redirect("/")
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                """
                SELECT s.Status, COUNT(*) as total
                FROM Results r
                JOIN Status s ON r.StatusId = s.StatusId
                GROUP BY s.Status
                ORDER BY total DESC
                """
            )
            resultados = cur.fetchall()
    finally:
        close_db()
    return render_template("relatorio1.html", resultados=resultados)

@app.route("/relatorio2")
def relatorio2():
    if "user" not in session or session["user"]["tipo"] != "Administrador":
        return redirect("/")
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                """
                SELECT r.RaceId, c.Name as circuit, COUNT(*) AS qtd_pilotos, AVG(r.Points) as media_pontos
                FROM Results r
                JOIN Races ra ON r.RaceId = ra.RaceId
                JOIN Circuits c ON ra.CircuitId = c.CircuitId
                GROUP BY r.RaceId, c.Name
                ORDER BY r.RaceId DESC
                LIMIT 20
                """
            )
            data = cur.fetchall()
    finally:
        close_db()
    return render_template("relatorio2.html", data=data)

@app.route("/relatorio3")
def relatorio3():
    if "user" not in session or session["user"]["tipo"] != "Administrador":
        return redirect("/")
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                """
                SELECT c.Name, COUNT(DISTINCT u.Userid) as qtd_pilotos, COALESCE(SUM(r.Points), 0) as total_pontos
                FROM Constructors c
                LEFT JOIN USERS u ON u.Tipo = 'Piloto' AND u.IdOriginal = c.ConstructorId
                LEFT JOIN Results r ON r.ConstructorId = c.ConstructorId
                GROUP BY c.Name
                ORDER BY total_pontos DESC
                """
            )
            escuderias = cur.fetchall()
            cur.execute("SELECT COUNT(*) FROM Races")
            total_corridas = cur.fetchone()[0]
            cur.execute(
                """
                SELECT ci.Name as circuito, MIN(r.Laps) as min_laps, AVG(r.Laps) as avg_laps, MAX(r.Laps) as max_laps
                FROM Races r
                JOIN Circuits ci ON r.CircuitId = ci.CircuitId
                GROUP BY ci.Name
                """
            )
            voltas_por_circuito = cur.fetchall()
            cur.execute(
                """
                SELECT ci.Name as circuito, r.Name as corrida, r.Laps, r.Time
                FROM Races r
                JOIN Circuits ci ON r.CircuitId = ci.CircuitId
                ORDER BY ci.Name, r.Name
                """
            )
            detalhes_corridas = cur.fetchall()
            detalhes_por_circuito = {}
            for row in detalhes_corridas:
                circuito = row[0]
                if circuito not in detalhes_por_circuito:
                    detalhes_por_circuito[circuito] = {"nome": circuito, "corridas": []}
                detalhes_por_circuito[circuito]["corridas"].append(
                    {
                        "corrida_nome": row[1],
                        "laps": row[2],
                        "time": row[3],
                    }
                )
    finally:
        close_db()
    return render_template(
        "relatorio3.html",
        escuderias=escuderias,
        total_corridas=total_corridas,
        voltas=voltas_por_circuito,
        detalhes_por_circuito=detalhes_por_circuito,
    )

# ----------------------------------ESCUDERIA ---------------------
@app.route("/escuderia/consultar_piloto", methods=["GET", "POST"])
def escuderia_consultar_piloto():
    if "user" not in session or session["user"]["tipo"] != "Escuderia":
        return redirect("/")
    
    user = session["user"]
    db = get_db()
    resultados = []
    try:
        with db.cursor() as cur:
            if request.method == "POST":
                forename = request.form.get("forename")
                escuderia_id = user["idoriginal"]
                if forename:
                    cur.execute(
                        """
                        SELECT 
                            d.Forename || ' ' || d.Surname AS Nome_Completo, 
                            d.Dob, 
                            d.Nationality
                        FROM Results r
                        JOIN Driver d ON r.DriverId = d.DriverId
                        WHERE r.ConstructorId = %s AND LOWER(d.Forename) = LOWER(%s)
                        GROUP BY d.DriverId, d.Forename, d.Surname, d.Dob, d.Nationality
                        ORDER BY Nome_Completo
                        """,
                        (escuderia_id, forename),
                    )
                    resultados = cur.fetchall()
                else:
                    print("forename vazio ou não fornecido")
    finally:
        close_db()
    
    return render_template("consultar_piloto.html", user=user, resultados=resultados)

@app.route("/escuderia/relatorio4")
def escuderia_relatorio4():
    if "user" not in session or session["user"]["tipo"] != "Escuderia":
        return redirect("/")
    
    user = session["user"]
    escuderia_id = user["idoriginal"]
    db = get_db()
    pilotos = []
    try:
        with db.cursor() as cur:
            cur.execute(
                """
                SELECT FullName AS piloto, Wins AS vitorias
                FROM Public.ReportDriverWinsByConstructor(%s)
                """,
                (escuderia_id,),
            )
            pilotos = cur.fetchall()
    finally:
        close_db()
    
    return render_template("relatorio4.html", user=user, pilotos=pilotos)

@app.route("/escuderia/relatorio5")
def escuderia_relatorio5():
    if "user" not in session or session["user"]["tipo"] != "Escuderia":
        print(f"Redirecionando: sessão inválida - {session.get('user')}")
        return redirect("/")
    
    user = session["user"]
    escuderia_id = user["idoriginal"]
    print(f"Escuderia ID: {escuderia_id}")
    db = get_db()
    resultados = []
    try:
        with db.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT Status AS status_name, ResultCount AS total
                FROM Public.ReportResultsByStatus(%s)
                """,
                (escuderia_id,),
            )
            resultados = cur.fetchall()
            print(f"Resultados: {resultados}")
    except Exception as e:
        print(f"Erro na consulta: {e}")
    finally:
        close_db()
    
    return render_template("relatorio5.html", user=user, resultados=resultados)

@app.route("/escuderia/upload_pilotos", methods=["GET", "POST"])
def escuderia_upload_pilotos():
    if "user" not in session or session["user"]["tipo"] != "Escuderia":
        print(f"Redirecionando: sessão inválida - {session.get('user')}")
        return redirect("/")
    
    user = session["user"]
    escuderia_id = user["idoriginal"]
    print(f"Escuderia ID: {escuderia_id}")
    msg = ""
    
    if request.method == "POST":
        file = request.files.get("arquivo")
        if not file:
            msg = "Nenhum arquivo enviado."
        else:
            db = get_db()
            try:
                with db.cursor(cursor_factory=RealDictCursor) as cur:
                    csvfile = file.stream.read().decode("utf-8")
                    csv_reader = csv.reader(StringIO(csvfile))
                    inseridos = 0
                    ignorados = []
                    
                    for linha in csv_reader:
                        if len(linha) < 7:
                            print(f"Linha inválida: {linha}")
                            continue
                        
                        driver_ref, number, code, forename, surname, dob, nationality = linha[:7]
                        number = number.strip() if number.strip() else None
                        code = code.strip() if code.strip() else None
                        dob = dob.strip()
                        
                        # Verifica se o piloto já existe
                        cur.execute(
                            """
                            SELECT 1 FROM Driver 
                            WHERE Forename = %s AND Surname = %s
                            """,
                            (forename, surname),
                        )
                        existe = cur.fetchone()
                        
                        if existe:
                            ignorados.append(f"{forename} {surname}")
                            print(f"Piloto ignorado: {forename} {surname}")
                            continue
                        
                        try:
                            # Insere na tabela Driver
                            cur.execute(
                                """
                                INSERT INTO Driver (DriverRef, Number, Code, Forename, Surname, Dob, Nationality)
                                VALUES (%s, %s, %s, %s, %s, %s, %s)
                                RETURNING DriverId
                                """,
                                (driver_ref, number, code, forename, surname, dob, nationality),
                            )
                            driver_id = cur.fetchone()['DriverId']
                            print(f"Piloto inserido: {forename} {surname}, DriverId: {driver_id}")
                            
                            # Insere na tabela Users com senha criptografada
                            cur.execute(
                                """
                                INSERT INTO Users (login, password, tipo, idoriginal)
                                VALUES (%s, crypt(%s, gen_salt('bf')), %s, %s)
                                """,
                                (f"{driver_ref}_d", driver_ref, "Piloto", driver_id),
                            )
                            db.commit()
                            inseridos += 1
                        except Exception as e:
                            db.rollback()
                            ignorados.append(f"{forename} {surname}")
                            print(f"Erro ao inserir {forename} {surname}: {e}")
                    
                    msg = f"{inseridos} pilotos inseridos com sucesso."
                    if ignorados:
                        msg += " Já existentes: " + ", ".join(ignorados)
                    print(f"Mensagem final: {msg}")
            except Exception as e:
                msg = f"Erro ao processar o arquivo: {e}"
                print(f"Erro geral: {e}")
            finally:
                close_db()
    
    return render_template("upload_pilotos.html", user=user, msg=msg)

# ----------------------------------Piloto ---------------------
@app.route("/piloto/relatorio6")
def piloto_relatorio6():
    if "user" not in session or session["user"]["tipo"] != "Piloto":
        print("Redirecionando: sessão não encontrada ou tipo inválido")
        return redirect("/")
    
    piloto_id = session["user"]["idoriginal"]
    print(f"Piloto ID: {piloto_id}")
    db = get_db()
    
    try:
        with db.cursor(cursor_factory=RealDictCursor) as cur:
            # Relatório 6: Pontos por ano e corrida
            cur.execute("SELECT * FROM Public.ReportDriverPointsByYearAndRace(%s)", (piloto_id,))
            resultados = cur.fetchall()
            print(f"Relatório 6 resultados: {resultados}")
    
    except Exception as e:
        print(f"Erro na consulta do Relatório 6: {e}")
        resultados = []
    
    finally:
        close_db()
    
    return render_template("relatorio6.html", resultados=resultados)

@app.route("/piloto/relatorio7")
def piloto_relatorio7():
    if "user" not in session or session["user"]["tipo"] != "Piloto":
        print("Redirecionando: sessão não encontrada ou tipo inválido")
        return redirect("/")
    
    piloto_id = session["user"]["idoriginal"]
    print(f"Piloto ID: {piloto_id}")
    db = get_db()
    
    try:
        with db.cursor(cursor_factory=RealDictCursor) as cur:
            # Relatório 7: Quantidade de resultados por status
            cur.execute("SELECT * FROM Public.ReportDriverResultsByStatus(%s)", (piloto_id,))
            resultados = cur.fetchall()
            print(f"Relatório 7 resultados: {resultados}")
    
    except Exception as e:
        print(f"Erro na consulta do Relatório 7: {e}")
        resultados = []
    
    finally:
        close_db()
    
    return render_template("relatorio7.html", resultados=resultados)

if __name__ == "__main__":
    app.run(debug=True)