from flask import Flask, render_template, request, redirect, session
import sqlite3
import os
import boto3
from werkzeug.utils import secure_filename
from datetime import datetime
from botocore.exceptions import NoCredentialsError, ClientError

app = Flask(__name__)
app.secret_key = "electrohogar_secret_key"

# =========================
# RUTAS BASE DEL PROYECTO
# =========================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")

# =========================
# CONFIGURACIÓN AMAZON S3
# =========================

S3_BUCKET = "electro-hogar-inventario"
S3_REGION = "us-east-1"

s3 = boto3.client("s3", region_name=S3_REGION)

# =========================
# BASE DE DATOS (SQLITE)
# =========================

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# =========================
# AUTENTICACIÓN
# =========================

@app.route("/")
def index():
    return redirect("/login")

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None

    if request.method == "POST":
        usuario = request.form["usuario"]
        password = request.form["password"]

        db = get_db()
        cur = db.cursor()
        cur.execute(
            "SELECT * FROM usuarios WHERE usuario=? AND password=?",
            (usuario, password)
        )
        user = cur.fetchone()
        db.close()

        if user:
            session["usuario"] = usuario
            return redirect("/dashboard")
        else:
            error = "Usuario o contraseña incorrectos"

    return render_template("login.html", error=error)

@app.route("/register", methods=["GET", "POST"])
def register():
    error = None

    if request.method == "POST":
        usuario = request.form["usuario"]
        password = request.form["password"]

        try:
            db = get_db()
            cur = db.cursor()
            cur.execute(
                "INSERT INTO usuarios (usuario, password) VALUES (?, ?)",
                (usuario, password)
            )
            db.commit()
            db.close()
            return redirect("/login")
        except:
            error = "El usuario ya existe"

    return render_template("register.html", error=error)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# =========================
# DASHBOARD
# =========================

@app.route("/dashboard")
def dashboard():
    if "usuario" not in session:
        return redirect("/login")
    return render_template("dashboard.html")

# =========================
# CREATE - AGREGAR PRODUCTO (S3 REAL)
# =========================

@app.route("/productos/nuevo", methods=["GET", "POST"])
def producto_nuevo():
    if "usuario" not in session:
        return redirect("/login")

    if request.method == "POST":
        archivo = request.files.get("archivo")
        archivo_url = None

        if archivo and archivo.filename:
            nombre_original = secure_filename(archivo.filename)
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            nombre_s3 = f"{timestamp}_{nombre_original}"

            try:
                s3.upload_fileobj(
                    archivo,
                    S3_BUCKET,
                    nombre_s3,
                    ExtraArgs={"ACL": "public-read"}
                )

                archivo_url = (
                    f"https://{S3_BUCKET}.s3.{S3_REGION}.amazonaws.com/{nombre_s3}"
                )

            except (NoCredentialsError, ClientError) as e:
                return f"Error al subir archivo a S3: {e}"

        db = get_db()
        cur = db.cursor()
        cur.execute("""
            INSERT INTO productos
            (nombre, categoria, marca, precio, stock, descripcion, archivo)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            request.form["nombre"],
            request.form["categoria"],
            request.form["marca"],
            request.form["precio"],
            request.form["stock"],
            request.form["descripcion"],
            archivo_url
        ))
        db.commit()
        db.close()

        return redirect("/productos")

    return render_template("producto_nuevo.html")

# =========================
# READ - VER INVENTARIO
# =========================

@app.route("/productos")
def ver_productos():
    if "usuario" not in session:
        return redirect("/login")

    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT * FROM productos")
    productos = cur.fetchall()
    db.close()

    return render_template("productos.html", productos=productos)

# =========================
# UPDATE - EDITAR PRODUCTO
# =========================

@app.route("/productos/editar/<int:id>", methods=["GET", "POST"])
def editar_producto(id):
    if "usuario" not in session:
        return redirect("/login")

    db = get_db()
    cur = db.cursor()

    if request.method == "POST":
        cur.execute("""
            UPDATE productos
            SET nombre=?, categoria=?, marca=?, precio=?, stock=?, descripcion=?
            WHERE id=?
        """, (
            request.form["nombre"],
            request.form["categoria"],
            request.form["marca"],
            request.form["precio"],
            request.form["stock"],
            request.form["descripcion"],
            id
        ))
        db.commit()
        db.close()
        return redirect("/productos")

    cur.execute("SELECT * FROM productos WHERE id=?", (id,))
    producto = cur.fetchone()
    db.close()

    return render_template("producto_editar.html", producto=producto)

# =========================
# DELETE - ELIMINAR PRODUCTO
# =========================

@app.route("/productos/eliminar/<int:id>")
def eliminar_producto(id):
    if "usuario" not in session:
        return redirect("/login")

    db = get_db()
    cur = db.cursor()
    cur.execute("DELETE FROM productos WHERE id=?", (id,))
    db.commit()
    db.close()

    return redirect("/productos")

# =========================
# EJECUCIÓN
# =========================

if __name__ == "__main__":
    app.run(debug=True)
