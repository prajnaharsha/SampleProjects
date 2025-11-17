from flask import Flask, flash, render_template, request, redirect
import sqlite3

app = Flask(__name__)
app.secret_key = "12312321"

DATABASE = "students.db"

# Function to connect to database
def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------- HOME PAGE ----------------
@app.route("/")
def home():
    return render_template("index.html")


# ---------------- VIEW ALL STUDENTS ----------------
@app.route("/view")
def view_students():
    conn = get_db()
    students = conn.execute("SELECT * FROM students").fetchall()
    conn.close()
    return render_template("view.html", students=students)


# ---------------- ADD STUDENT (GET) ----------------
@app.route("/add", methods=["GET"])
def show_add_form():
    return render_template("add.html")


# ---------------- ADD STUDENT (POST) ----------------
@app.route("/add", methods=["POST"])
def save_student():
    roll = request.form["roll"]
    name = request.form["name"]
    dept = request.form["department"]
    marks = request.form["marks"]

    conn = get_db()
    try:
        conn.execute("INSERT INTO students VALUES (?, ?, ?, ?)",
                     (roll, name, dept, marks))
        conn.commit()
        flash("Student added successfully!", "success")
    except sqlite3.IntegrityError:
        conn.close()
        flash("Roll number already exists!", "danger")
        return "❌ Roll number already exists!"
    
    conn.close()
    return redirect("/view")


# ---------------- UPDATE STUDENT (GET) ----------------
@app.route("/update/<int:roll>", methods=["GET"])
def show_update_form(roll):
    conn = get_db()
    student = conn.execute("SELECT * FROM students WHERE roll=?", (roll,)).fetchone()
    conn.close()

    if student is None:
        return "❌ Student not found!"

    return render_template("update.html", student=student)


# ---------------- UPDATE STUDENT (POST) ----------------
@app.route("/update/<int:roll>", methods=["POST"])
def save_update(roll):
    name = request.form["name"]
    dept = request.form["department"]
    marks = request.form["marks"]

    conn = get_db()
    conn.execute("UPDATE students SET name=?, department=?, marks=? WHERE roll=?",
                 (name, dept, marks, roll))
    conn.commit()
    conn.close()

    return redirect("/view")


# ---------------- DELETE STUDENT ----------------
@app.route("/delete/<int:roll>")
def delete_student(roll):
    conn = get_db()
    conn.execute("DELETE FROM students WHERE roll=?", (roll,))
    conn.commit()
    conn.close()

    return redirect("/view")


# ---------------- START SERVER ----------------
if __name__ == "__main__":
    app.run(debug=True)
