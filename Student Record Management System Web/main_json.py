import json
import os

DATA_FILE = "students.json"

# Load data from JSON file if exists
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return []  # return empty list if file does not exist


# Save data back to JSON file
def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)


def add_student():
    data = load_data()
    try:
        roll = int(input("Enter roll number: "))
        
        # check if roll already exists
        for student in data:
            if student["roll"] == roll:
                print("Error: roll number already exists!\n")
                return

        name = input("Enter name: ")
        dept = input("Enter department: ")
        marks = float(input("Enter marks: "))

        data.append({"roll": roll, "name": name, "department": dept, "marks": marks})
        save_data(data)
        print("Student added successfully!\n")
    except ValueError:
        print("Invalid input! Try again.\n")


def view_students():
    data = load_data()
    if not data:
        print("No student records found.\n")
        return
    for student in data:
        print(f"Roll: {student['roll']}, Name: {student['name']}, Dept: {student['department']}, Marks: {student['marks']}")
    print()


def search_student():
    data = load_data()
    roll = input("Enter roll number to search: ")
    for student in data:
        if str(student["roll"]) == roll:
            print(f"Roll: {student['roll']}, Name: {student['name']}, Dept: {student['department']}, Marks: {student['marks']}\n")
            return
    print("Student not found!\n")


def update_student():
    data = load_data()
    roll = input("Enter roll number to update: ")
    for student in data:
        if str(student["roll"]) == roll:
            student["name"] = input("Enter new name: ")
            student["department"] = input("Enter new department: ")
            student["marks"] = float(input("Enter new marks: "))
            save_data(data)
            print("Record updated successfully!\n")
            return
    print("Student not found!\n")


def delete_student():
    data = load_data()
    roll = input("Enter roll number to delete: ")
    new_data = [student for student in data if str(student["roll"]) != roll]
    if len(new_data) == len(data):
        print("Student not found!\n")
        return
    save_data(new_data)
    print("Record deleted successfully!\n")


# Main Menu Loop
while True:
    print("""
========= STUDENT MANAGEMENT SYSTEM (JSON) =========
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
