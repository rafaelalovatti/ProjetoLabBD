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
    try:
        with db.cursor() as cur:
            tipo = user["tipo"]
            if tipo == "Administrador":
                extra_info = "Administrador - acesso total"
                cur.execute("SELECT COUNT(*) FROM USERS")
                resumo = {"Total de usuários": cur.fetchone()[0]}
            elif tipo == "Escuderia":
                escuderia_id = user["idoriginal"]
                cur.execute(
                    """
                    SELECT c.Name
                    FROM Constructors c
                    WHERE c.ConstructorId = %s
                    """,
                    (escuderia_id,),
                )
                escuderia_nome = cur.fetchone()
                cur.execute(
                    """
                    SELECT COUNT(DISTINCT r.DriverId)
                    FROM Results r
                    WHERE r.ConstructorId = %s
                    """,
                    (escuderia_id,),
                )
                count_pilotos = cur.fetchone()[0]
                extra_info = f"Escuderia: {escuderia_nome[0] if escuderia_nome else escuderia_id}"
                resumo = {"Pilotos vinculados": count_pilotos}
            elif tipo == "Piloto":
                piloto = user["idoriginal"]
                cur.execute(
                    "SELECT Forename || ' ' || Surname FROM Driver WHERE DriverId = %s",
                    (piloto,),
                )
                full_name = cur.fetchone()
                extra_info = f"Piloto: {full_name[0] if full_name else piloto}"
                resumo = {}
            else:
                extra_info = "Tipo desconhecido"
                resumo = {}
    finally:
        close_db()
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

@app.route("/consultar_piloto", methods=["GET", "POST"])
def consultar_piloto():
    if "user" not in session or session["user"]["tipo"] != "Escuderia":
        return redirect("/")
    resultados = []
    msg = ""
    if request.method == "POST":
        forename = request.form["forename"].strip().lower()
        escuderia = session["user"]["idoriginal"]
        db = get_db()
        try:
            with db.cursor() as cur:
                cur.execute(
                    """
                    SELECT d.Forename, d.Surname, d.Dob, d.Nationality
                    FROM Results r
                    JOIN Driver d ON r.DriverId = d.DriverId
                    JOIN Constructors c ON r.ConstructorId = c.ConstructorId
                    WHERE LOWER(d.Forename) = %s AND c.ConstructorId = %s
                    GROUP BY d.DriverId, d.Forename, d.Surname, d.Dob, d.Nationality
                    """,
                    (forename, escuderia),
                )
                resultados = cur.fetchall()
                if not resultados:
                    msg = "Nenhum piloto encontrado com esse nome e que tenha corrido pela sua escuderia."
        finally:
            close_db()
    return render_template("consultar_forename.html", resultados=resultados, msg=msg)

@app.route("/cadastrar_escuderia", methods=["GET", "POST"])
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
    if "user" not in session or session["user"]["tipo"] != "Administrador":
        return redirect("/")
    return render_template("relatorios.html")

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

if __name__ == "__main__":
    app.run(debug=True)