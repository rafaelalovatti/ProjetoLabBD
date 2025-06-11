from flask import Flask, render_template, request, redirect, session, g
from datetime import datetime
import psycopg2

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
        return redirect("/")
    user = session["user"]
    db = get_db()
    tipo = user["tipo"]

    if tipo == "Administrador":
        extra_info = "Administrador - acesso total"

        # 1. Quantidade total de pilotos, escuderias, temporadas
        total_pilotos = db.execute("SELECT COUNT(*) FROM drivers").fetchone()[0]
        total_escuderias = db.execute("SELECT COUNT(*) FROM constructors").fetchone()[0]
        total_temporadas = db.execute(
            "SELECT COUNT(DISTINCT year) FROM races"
        ).fetchone()[0]

        # Ano corrente
        ano_corrente = db.execute("SELECT MAX(year) FROM races").fetchone()[0]

        # 2. Corridas do ano corrente com total de voltas e tempo (race lap count and time)
        corridas_ano = db.execute(
            """
            SELECT name, laps, round(milliseconds/1000.0,2) as tempo_segundos
            FROM races
            WHERE year = ?
            ORDER BY name
        """,
            (ano_corrente,),
        ).fetchall()

        # 3. Escuderias que correram no ano corrente e total de pontos
        escuderias_pontos = db.execute(
            """
            SELECT c.name, SUM(r.points) as total_pontos
            FROM results r
            JOIN constructors c ON r.constructorid = c.constructorid
            JOIN races ra ON r.raceid = ra.raceid
            WHERE ra.year = ?
            GROUP BY c.constructorid
            ORDER BY total_pontos DESC
        """,
            (ano_corrente,),
        ).fetchall()

        # 4. Pilotos que correram no ano corrente e total de pontos
        pilotos_pontos = db.execute(
            """
            SELECT d.forename || ' ' || d.surname as piloto, SUM(r.points) as total_pontos
            FROM results r
            JOIN drivers d ON r.driverid = d.driverid
            JOIN races ra ON r.raceid = ra.raceid
            WHERE ra.year = ?
            GROUP BY d.driverid
            ORDER BY total_pontos DESC
        """,
            (ano_corrente,),
        ).fetchall()

        resumo = {
            "Total de pilotos": total_pilotos,
            "Total de escuderias": total_escuderias,
            "Total de temporadas": total_temporadas,
            "Ano corrente": ano_corrente,
            "Corridas do ano corrente": corridas_ano,
            "Escuderias e pontos": escuderias_pontos,
            "Pilotos e pontos": pilotos_pontos,
        }

    elif tipo == "Escuderia":
        escuderia = user["idoriginal"]

        # 1. Quantidade de vitórias da escuderia
        vitórias = db.execute(
            """
            SELECT COUNT(*)
            FROM results r
            JOIN constructors c ON r.constructorid = c.constructorid
            WHERE c.constructorref = ?
            AND r.position = 1
        """,
            (escuderia,),
        ).fetchone()[0]

        # 2. Quantidade de pilotos diferentes que já correram pela escuderia
        pilotos_distintos = db.execute(
            """
            SELECT COUNT(DISTINCT r.driverid)
            FROM results r
            JOIN constructors c ON r.constructorid = c.constructorid
            WHERE c.constructorref = ?
        """,
            (escuderia,),
        ).fetchone()[0]

        # 3. Primeiro e último ano com dados da escuderia (pela tabela results -> joined races)
        primeiro_ano = db.execute(
            """
            SELECT MIN(ra.year)
            FROM results r
            JOIN races ra ON r.raceid = ra.raceid
            JOIN constructors c ON r.constructorid = c.constructorid
            WHERE c.constructorref = ?
        """,
            (escuderia,),
        ).fetchone()[0]

        ultimo_ano = db.execute(
            """
            SELECT MAX(ra.year)
            FROM results r
            JOIN races ra ON r.raceid = ra.raceid
            JOIN constructors c ON r.constructorid = c.constructorid
            WHERE c.constructorref = ?
        """,
            (escuderia,),
        ).fetchone()[0]

        resumo = {
            "Vitórias da escuderia": vitórias,
            "Pilotos diferentes": pilotos_distintos,
            "Primeiro ano de dados": primeiro_ano,
            "Último ano de dados": ultimo_ano,
        }
        extra_info = f"Escuderia: {escuderia}"

    elif tipo == "Piloto":
        piloto = user["idoriginal"]

        # 1. Primeiro e último ano com dados do piloto
        primeiro_ano = db.execute(
            """
            SELECT MIN(ra.year)
            FROM results r
            JOIN races ra ON r.raceid = ra.raceid
            WHERE r.driverid = ?
        """,
            (piloto,),
        ).fetchone()[0]

        ultimo_ano = db.execute(
            """
            SELECT MAX(ra.year)
            FROM results r
            JOIN races ra ON r.raceid = ra.raceid
            WHERE r.driverid = ?
        """,
            (piloto,),
        ).fetchone()[0]

        # 2. Para cada ano e circuito: quantidade de pontos, vitórias e total de corridas
        desempenho = db.execute(
            """
            SELECT ra.year, ci.name as circuito,
                   SUM(r.points) as pontos,
                   SUM(CASE WHEN r.position = 1 THEN 1 ELSE 0 END) as vitorias,
                   COUNT(*) as total_corridas
            FROM results r
            JOIN races ra ON r.raceid = ra.raceid
            JOIN circuits ci ON ra.circuitid = ci.circuitid
            WHERE r.driverid = ?
            GROUP BY ra.year, ci.circuitid
            ORDER BY ra.year, ci.name
        """,
            (piloto,),
        ).fetchall()

        resumo = {
            "Primeiro ano de dados": primeiro_ano,
            "Último ano de dados": ultimo_ano,
            "Desempenho detalhado": desempenho,
        }
        extra_info = f"Piloto ID: {piloto}"

    else:
        extra_info = "Tipo desconhecido"
        resumo = {}

    return render_template("dashboard.html", user=user, extra=extra_info, resumo=resumo)


@app.route("/cadastrar_piloto", methods=["GET", "POST"])
def cadastrar_piloto():
    if "user" not in session or session["user"]["tipo"] != "Administrador":
        return redirect("/")
    msg = ""
    if request.method == "POST":
        driverref = request.form["driverref"]
        number = request.form.get("number")
        code = request.form.get("code")
        forename = request.form["forename"]
        surname = request.form["surname"]
        dob = request.form["dob"]
        nationality = request.form["nationality"]
        login = f"{driverref}_d"
        password = driverref
        tipo = "Piloto"
        db = get_db()
        try:
            with db.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO Driver 
                    (DriverRef, Number, Code, Forename, Surname, Dob, Nationality)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING DriverId
                    """,
                    (driverref, number, code, forename, surname, dob, nationality),
                )
                driver_id = cur.fetchone()[0]
                cur.execute(
                    """
                    INSERT INTO USERS (Login, Password, Tipo, IdOriginal)
                    VALUES (%s, crypt(%s, gen_salt('bf')), %s, %s)
                    """,
                    (login, password, tipo, driver_id),
                )
                msg = "Piloto cadastrado com sucesso!"
        except psycopg2.IntegrityError:
            msg = "Erro: já existe piloto com esse driverref ou login."
        finally:
            close_db()
    return render_template("cadastrar_piloto.html", msg=msg)


@app.route("/admin/cadastrar_escuderia", methods=["GET", "POST"])
def cadastrar_escuderia():
    if "user" not in session or session["user"]["tipo"] != "Administrador":
        return redirect("/")
    msg = ""
    if request.method == "POST":
        ref = request.form["ref"]
        name = request.form["name"]
        nationality = request.form["nationality"]
        url = request.form.get("url", "")
        login = f"{ref}_c"
        password = ref
        tipo = "Escuderia"
        db = get_db()
        try:
            with db.cursor() as cur:
                cur.execute(
                    "INSERT INTO Constructors (ConstructorRef, Name, Nationality, Url) VALUES (%s, %s, %s, %s) RETURNING ConstructorId",
                    (ref, name, nationality, url),
                )
                constructor_id = cur.fetchone()[0]
                cur.execute(
                    "INSERT INTO USERS (Login, Password, Tipo, IdOriginal) VALUES (%s, crypt(%s, gen_salt('bf')), %s, %s)",
                    (login, password, tipo, constructor_id),
                )
                msg = "Escuderia cadastrada com sucesso!"
        except psycopg2.IntegrityError:
            msg = "Erro: Escuderia já existe."
        finally:
            close_db()
    return render_template("cadastrar_escuderia.html", msg=msg)

@app.route("/relatorios")
def relatorios():
    if "user" not in session:
        return redirect("/")  # usuário não logado, redireciona para home/login

    user = session["user"]
    # qualquer tipo de usuário pode acessar relatorios, mas no HTML mostra condicionalmente

    return render_template("relatorios.html", user=user)

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

from psycopg2.extras import RealDictCursor

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

from psycopg2.extras import RealDictCursor
import csv
from io import StringIO

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
            escuderia_ref = session["user"]["idoriginal"]
            csvfile = file.stream.read().decode("utf-8").splitlines()
            reader = csv.reader(csvfile)

            inseridos = 0
            ignorados = []

            for linha in reader:
                if len(linha) < 7:
                    continue
                driverref, number, code, forename, surname, dob, nationality = linha[:7]
                number = number if number.strip() else None
                code = code if code.strip() else None
                dob = dob.strip()

                # Verifica se nome e sobrenome já existem
                existe = db.execute(
                    "SELECT 1 FROM drivers WHERE forename = ? AND surname = ?",
                    (forename, surname),
                ).fetchone()

                if existe:
                    ignorados.append(f"{forename} {surname}")
                    continue

                try:
                    db.execute(
                        """
                        INSERT INTO drivers (driverref, number, code, forename, surname, dob, nationality)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (driverref, number, code, forename, surname, dob, nationality),
                    )

                    db.execute(
                        """
                        INSERT INTO users (login, password, tipo, idoriginal)
                        VALUES (?, ?, ?, ?)
                        """,
                        (f"{driverref}_d", driverref, "Piloto", driverref),
                    )

                    db.commit()
                    inseridos += 1
                except sqlite3.IntegrityError:
                    ignorados.append(f"{forename} {surname}")

            msg = f"{inseridos} pilotos inseridos com sucesso."
            if ignorados:
                msg += " Já existentes: " + ", ".join(ignorados)

    return render_template("upload_pilotos.html", msg=msg)


# Relatório 4: pilotos da escuderia com contagem de vitórias
@app.route("/escuderia/relatorio4")
def escuderia_relatorio4():
    if "user" not in session or session["user"]["tipo"] != "Escuderia":
        return redirect("/")
    escuderia = session["user"]["idoriginal"]
    db = get_db()

    # SQL para contar vitórias (posição = 1)
    pilotos = db.execute(
        """
        SELECT d.forename || ' ' || d.surname AS piloto,
               COUNT(*) AS vitorias
        FROM results r
        JOIN drivers d ON r.driverid = d.driverid
        JOIN constructors c ON r.constructorid = c.constructorid
        WHERE c.constructorref = ?
          AND r.position = 1
        GROUP BY d.driverid
        ORDER BY vitorias DESC
    """,
        (escuderia,),
    ).fetchall()

    return render_template("relatorio4.html", pilotos=pilotos)


# Relatório 5: resultados por status na escuderia
@app.route("/escuderia/relatorio5")
def escuderia_relatorio5():
    if "user" not in session or session["user"]["tipo"] != "Escuderia":
        return redirect("/")
    escuderia = session["user"]["idoriginal"]
    db = get_db()

    resultados = db.execute(
        """
        SELECT s.status_name, COUNT(*) AS total
        FROM results r
        JOIN status s ON r.statusid = s.statusid
        JOIN constructors c ON r.constructorid = c.constructorid
        WHERE c.constructorref = ?
        GROUP BY s.status_name
        ORDER BY total DESC
    """,
        (escuderia,),
    ).fetchall()

    return render_template("relatorio5.html", resultados=resultados)


# -------------------------------PILOTO--------------------------
@app.route("/piloto/relatorio6")
def piloto_relatorio6():
    if "user" not in session or session["user"]["tipo"] != "Piloto":
        return redirect("/")
    piloto_id = session["user"]["idoriginal"]
    db = get_db()

    # Relatório 6: Pontos por ano e corrida
    resultados = db.execute(
        """
        SELECT r.year,
               ra.name AS corrida,
               SUM(res.points) AS pontos
        FROM results res
        JOIN races ra ON res.raceId = ra.raceId
        JOIN races r ON ra.raceId = r.raceId
        WHERE res.driverId = ?
        GROUP BY r.year, ra.name
        ORDER BY r.year, pontos DESC
        """,
        (piloto_id,),
    ).fetchall()

    return render_template("relatorio6.html", resultados=resultados)


@app.route("/piloto/relatorio7")
def piloto_relatorio7():
    if "user" not in session or session["user"]["tipo"] != "Piloto":
        return redirect("/")
    piloto_id = session["user"]["idoriginal"]
    db = get_db()

    # Relatório 7: Quantidade de resultados por status para o piloto
    resultados = db.execute(
        """
        SELECT s.status,
               COUNT(*) AS total
        FROM results res
        JOIN status s ON res.statusId = s.statusId
        WHERE res.driverId = ?
        GROUP BY s.status
        ORDER BY total DESC
        """,
        (piloto_id,),
    ).fetchall()

    return render_template("relatorio7.html", resultados=resultados)


if __name__ == "__main__":
    app.run(debug=True)