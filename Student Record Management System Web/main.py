import sqlite3

# Create / connect to database
conn = sqlite3.connect("students.db")
cursor = conn.cursor()

# Create table if not exists
cursor.execute("""
CREATE TABLE IF NOT EXISTS students (
    roll INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    department TEXT NOT NULL,
    marks REAL NOT NULL
)
""")
conn.commit()


def add_student():
    try:
        roll = int(input("Enter roll number: "))
        name = input("Enter name: ")
        dept = input("Enter department: ")
        marks = float(input("Enter marks: "))
        cursor.execute("INSERT INTO students VALUES (?, ?, ?, ?)", (roll, name, dept, marks))
        conn.commit()
        print("Student added successfully!\n")
    except sqlite3.IntegrityError:
        print("Error: Roll number already exists!\n")
    except ValueError:
        print("Invalid input! Please enter correct data.\n")


def view_students():
    cursor.execute("SELECT * FROM students")
    rows = cursor.fetchall()
    if not rows:
        print("No student records found.\n")
        return
    for row in rows:
        print(f"Roll: {row[0]}, Name: {row[1]}, Dept: {row[2]}, Marks: {row[3]}")
    print()


def search_student():
    roll = input("Enter roll number to search: ")
    cursor.execute("SELECT * FROM students WHERE roll=?", (roll,))
    row = cursor.fetchone()
    if row:
        print(f"Roll: {row[0]}, Name: {row[1]}, Dept: {row[2]}, Marks: {row[3]}\n")
    else:
        print("Student not found!\n")


def update_student():
    roll = input("Enter roll number to update: ")
    cursor.execute("SELECT * FROM students WHERE roll=?", (roll,))
    if not cursor.fetchone():
        print("Student not found!\n")
        return
    name = input("Enter new name: ")
    dept = input("Enter new department: ")
    marks = input("Enter new marks: ")
    cursor.execute("UPDATE students SET name=?, department=?, marks=? WHERE roll=?", (name, dept, marks, roll))
    conn.commit()
    print("Record updated successfully!\n")


def delete_student():
    roll = input("Enter roll number to delete: ")
    cursor.execute("DELETE FROM students WHERE roll=?", (roll,))
    conn.commit()
    print("Record deleted successfully!\n")


while True:
    print("""
========= STUDENT MANAGEMENT SYSTEM =========
1. Add Student
2. View Students
3. Search Student
4. Update Student
5. Delete Student
6. Exit
""")

    choice = input("Enter your choice: ")

    if choice == "1":
        add_student()
    elif choice == "2":
        view_students()
    elif choice == "3":
        search_student()
    elif choice == "4":
        update_student()
    elif choice == "5":
        delete_student()
    elif choice == "6":
        print("Exiting program...")
        break
    else:
        print("Invalid choice! Try again.\n")

conn.close()
