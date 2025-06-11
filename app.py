import os
import sqlite3
from flask import Flask, render_template, request, redirect, session, g
from datetime import datetime
import math
import csv

app = Flask(__name__)
app.secret_key = "segredo"
DATABASE = "f1.db"


def init_db():
    if not os.path.exists(DATABASE):
        with sqlite3.connect(DATABASE) as conn:
            c = conn.cursor()
            c.executescript(open("schema.sql", "r").read())


def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()


@app.route("/", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        db = get_db()
        cur = db.execute(
            "SELECT * FROM users WHERE login = ? AND password = ?",
            (request.form["login"], request.form["password"]),
        )
        user = cur.fetchone()
        if user:
            session["user"] = dict(user)
            db.execute(
                "INSERT INTO users_log (userid, login_time) VALUES (?, ?)",
                (user["userid"], datetime.now()),
            )
            db.commit()
            return redirect("/dashboard")
        else:
            error = "Login inválido"
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
        resumo = {
            "Total de usuários": db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        }
    elif tipo == "Escuderia":
        escuderia = user["idoriginal"]
        count = db.execute(
            "SELECT COUNT(*) FROM users WHERE tipo = 'Piloto' AND idoriginal = ?",
            (escuderia,),
        ).fetchone()[0]
        extra_info = f"Escuderia: {escuderia}"
        resumo = {"Pilotos vinculados": count}
    elif tipo == "Piloto":
        piloto = user["idoriginal"]
        full_name = db.execute(
            "SELECT forename || ' ' || surname FROM pilotos WHERE driverref = ?",
            (piloto,),
        ).fetchone()
        extra_info = f"Piloto: {full_name[0] if full_name else piloto}"
        resumo = {}
    else:
        extra_info = "Tipo desconhecido"
        resumo = {}
    return render_template("dashboard.html", user=user, extra=extra_info, resumo=resumo)


@app.route("/admin/cadastrar_piloto", methods=["GET", "POST"])
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
        password = driverref  # senha padrão
        tipo = "Piloto"

        db = get_db()
        try:
            db.execute(
                """
                INSERT INTO drivers 
                (driverref, number, code, forename, surname, dob, nationality)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (driverref, number, code, forename, surname, dob, nationality),
            )

            db.execute(
                """
                INSERT INTO users (login, password, tipo, idoriginal)
                VALUES (?, ?, ?, ?)
            """,
                (login, password, tipo, driverref),
            )

            db.commit()
            msg = "Piloto cadastrado com sucesso!"
        except sqlite3.IntegrityError:
            msg = "Erro: já existe piloto com esse driverref ou login."

    return render_template("cadastrar_piloto.html", msg=msg)


@app.route("/admin/consultar_piloto", methods=["GET", "POST"])
def consultar_piloto():
    if "user" not in session or session["user"]["tipo"] != "Escuderia":
        return redirect("/")

    resultados = []
    msg = ""
    if request.method == "POST":
        forename = request.form["forename"].strip().lower()
        escuderia = session["user"]["idoriginal"]
        db = get_db()

        resultados = db.execute(
            """
            SELECT d.forename, d.surname, d.dob, d.nationality
            FROM results r
            JOIN drivers d ON r.driverid = d.driverid
            JOIN constructors c ON r.constructorid = c.constructorid
            WHERE LOWER(d.forename) = ? AND c.constructorref = ?
            GROUP BY d.driverid
        """,
            (forename, escuderia),
        ).fetchall()

        if not resultados:
            msg = "Nenhum piloto encontrado com esse nome e que tenha corrido pela sua escuderia."

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
            db.execute(
                "INSERT INTO constructors (constructorref, name, nationality, url) VALUES (?, ?, ?, ?)",
                (ref, name, nationality, url),
            )
            db.execute(
                "INSERT INTO users (login, password, tipo, idoriginal) VALUES (?, ?, ?, ?)",
                (login, password, tipo, ref),
            )
            db.commit()
            msg = "Escuderia cadastrada com sucesso!"
        except sqlite3.IntegrityError:
            msg = "Erro: Escuderia já existe."

    return render_template("cadastrar_escuderia.html", msg=msg)


# ROTAS RELATÓRIOS


@app.route("/relatorios")
def relatorios():
    if "user" not in session:
        return redirect("/")  # usuário não logado, redireciona para home/login

    user = session["user"]
    # qualquer tipo de usuário pode acessar relatorios, mas no HTML mostra condicionalmente

    return render_template("relatorios.html", user=user)


@app.route("/admin/relatorio1")
def relatorio1():
    if "user" not in session or session["user"]["tipo"] != "Administrador":
        return redirect("/")
    db = get_db()
    resultados = db.execute(
        """
        SELECT s.status_name, COUNT(*) as total
        FROM results r
        JOIN status s ON r.statusid = s.statusid
        GROUP BY s.status_name
        ORDER BY total DESC
        """
    ).fetchall()
    return render_template("relatorio1.html", resultados=resultados)


@app.route("/admin/relatorio2")
def relatorio2():
    if "user" not in session or session["user"]["tipo"] != "Administrador":
        return redirect("/")
    db = get_db()
    # Exemplo: média de pontos por corrida
    data = db.execute(
        """
        SELECT r.raceid, c.name as circuit, COUNT(*) AS qtd_pilotos, AVG(r.points) as media_pontos
        FROM results r
        JOIN races ra ON r.raceid = ra.raceid
        JOIN circuits c ON ra.circuitid = c.circuitid
        GROUP BY r.raceid
        ORDER BY r.raceid DESC
        LIMIT 20
        """
    ).fetchall()
    return render_template("relatorio2.html", data=data)


@app.route("/admin/relatorio3")
def relatorio3():
    if "user" not in session or session["user"]["tipo"] != "Administrador":
        return redirect("/")
    db = get_db()

    escuderias = db.execute(
        """
        SELECT c.name, COUNT(DISTINCT u.userid) as qtd_pilotos, COALESCE(SUM(r.points), 0) as total_pontos
        FROM constructors c
        LEFT JOIN users u ON u.tipo = 'Piloto' AND u.idoriginal = c.constructorref
        LEFT JOIN results r ON r.constructorid = c.constructorid
        GROUP BY c.name
        ORDER BY total_pontos DESC
        """
    ).fetchall()

    total_corridas = db.execute("SELECT COUNT(*) FROM races").fetchone()[0]

    voltas_por_circuito = db.execute(
        """
        SELECT ci.name as circuito, MIN(r.laps) as min_laps, AVG(r.laps) as avg_laps, MAX(r.laps) as max_laps
        FROM races r
        JOIN circuits ci ON r.circuitid = ci.circuitid
        GROUP BY ci.name
        """
    ).fetchall()

    detalhes_corridas = db.execute(
        """
        SELECT ci.name as circuito, r.name as corrida, r.laps, r.time
        FROM races r
        JOIN circuits ci ON r.circuitid = ci.circuitid
        ORDER BY ci.name, r.name
        """
    ).fetchall()

    # Agrupar corridas por circuito
    detalhes_por_circuito = {}
    for row in detalhes_corridas:
        circuito = row["circuito"]
        if circuito not in detalhes_por_circuito:
            detalhes_por_circuito[circuito] = {"nome": circuito, "corridas": []}
        detalhes_por_circuito[circuito]["corridas"].append(
            {
                "corrida_nome": row["corrida"],
                "laps": row["laps"],
                "time": row["time"],
            }
        )

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

    resultados = []
    if request.method == "POST":
        forename = request.form.get("forename")
        constructorref = session["user"]["idoriginal"]

        resultados = (
            get_db()
            .execute(
                """
            SELECT d.forename, d.surname, d.dob, d.nationality
            FROM drivers d
            JOIN results r ON d.driverid = r.driverid
            JOIN constructors c ON r.constructorid = c.constructorid
            WHERE d.forename = ? AND c.constructorref = ?
            GROUP BY d.driverid
        """,
                (forename, constructorref),
            )
            .fetchall()
        )

    return render_template("consultar_piloto.html", resultados=resultados)

@app.route("/escuderia/upload_pilotos", methods=["GET", "POST"])
def escuderia_upload_pilotos():
    if "user" not in session or session["user"]["tipo"] != "Escuderia":
        return redirect("/")

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


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
