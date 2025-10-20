import pymysql
from flask import Flask, render_template, request, url_for, redirect, session, flash, g
import os
from functools import wraps

MYSQL_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '1234',
    'database': 'evaluation_system',
    'cursorclass': pymysql.cursors.DictCursor
}
SECRET_KEY = os.urandom(24)

app = Flask(__name__)
app.config.from_object(__name__)

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = pymysql.connect(**app.config['MYSQL_CONFIG'])
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    conn = pymysql.connect(
        host=app.config['MYSQL_CONFIG']['host'],
        user=app.config['MYSQL_CONFIG']['user'],
        password=app.config['MYSQL_CONFIG']['password']
    )
    
    with conn.cursor() as cursor:
        try:
            with app.open_resource('schema.sql', mode='r') as f:
                for sql_command in f.read().split(';'):
                    sql_command = sql_command.strip()
                    if sql_command:
                        cursor.execute(sql_command)
            conn.commit()
            print("Database initialized/reset successfully using MySQL.")
        except Exception as e:
            print(f"CRITICAL DB INIT ERROR: {e}")
            print("ERROR: Check your MySQL server is running and credentials are correct.")
        finally:
            conn.close()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'student_id' not in session:
            flash('You must log in to access the dashboard.', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/', methods=['GET', 'POST'])
def index():
    db = get_db()
    
    with db.cursor() as cursor:
        cursor.execute('SELECT COUNT(*) AS count FROM tbl_instructor')
        instructors_empty = cursor.fetchone()['count'] == 0

    if request.method == 'POST':
        action = request.form.get('action')
        
        if instructors_empty and action == 'setup_init':
            i_name = request.form['init_i_name'].split()
            i_first_name = i_name[0]
            i_last_name = ' '.join(i_name[1:]) if len(i_name) > 1 else ''
            i_course = request.form['init_i_course']
            
            try:
                with db.cursor() as cursor:
                    cursor.execute(
                        'INSERT INTO tbl_instructor (i_first_name, i_last_name, i_course) VALUES (%s, %s, %s)',
                        (i_first_name, i_last_name, i_course)
                    )
                db.commit()
                flash('Initial setup successful!', 'success')
                return redirect(url_for('index'))
            except Exception as e:
                flash(f'Setup failed: {e}', 'error')

        elif action == 'login':
            school_id = request.form['login_school_id']
            full_name = request.form['login_password'] 

            with db.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM tbl_student WHERE s_schoolID = %s AND CONCAT(s_first_name, ' ', s_last_name) = %s",
                    (school_id, full_name)
                )
                student = cursor.fetchone()

            if student:
                if student['s_status'] == 'Approved':
                    session['student_id'] = student['s_schoolID']
                    session['student_name'] = f"{student['s_first_name']} {student['s_last_name']}"
                    flash('Login successful!', 'success')
                    return redirect(url_for('dashboard'))
                else:
                    flash('Your account is pending approval.', 'error')
            else:
                flash('Invalid School ID or Name.', 'error')

        elif action == 'register':
            reg_school_id = request.form['reg_school_id']
            reg_first_name = request.form['reg_first_name']
            reg_last_name = request.form['reg_last_name']
            reg_email = request.form['reg_email']
            reg_year_level = request.form['reg_year_level']

            try:
                with db.cursor() as cursor:
                    cursor.execute(
                        'INSERT INTO tbl_student (s_schoolID, s_first_name, s_last_name, s_email, s_year_level) VALUES (%s, %s, %s, %s, %s)',
                        (reg_school_id, reg_first_name, reg_last_name, reg_email, reg_year_level)
                    )
                db.commit()
                flash('Registration successful! Waiting for admin approval.', 'success')

            except pymysql.err.IntegrityError:
                flash('Registration failed. School ID or Email is already in use.', 'error')
            except Exception as e:
                flash(f'Error during registration: {e}', 'error')

    return render_template('index.html', instructors_empty=instructors_empty)

@app.route('/dashboard')
@login_required
def dashboard():
    db = get_db()
    student_id = session['student_id']
    
    with db.cursor() as cursor:
        cursor.execute(
            'SELECT s_schoolID, s_email, s_year_level, s_status FROM tbl_student WHERE s_schoolID = %s',
            (student_id,)
        )
        student_record = cursor.fetchone()

        student_data = {
            'id': student_record['s_schoolID'],
            'email': student_record['s_email'],
            'year': student_record['s_year_level'],
            'status': student_record['s_status']
        }

        cursor.execute(
            'SELECT COUNT(*) AS count FROM tbl_evaluation WHERE s_schoolID = %s',
            (student_id,)
        )
        evaluations_count = cursor.fetchone()['count']

        cursor.execute('SELECT COUNT(*) AS count FROM tbl_instructor')
        total_instructors = cursor.fetchone()['count']

        cursor.execute(
            'SELECT COUNT(DISTINCT i_id) AS count FROM tbl_evaluation WHERE s_schoolID = %s',
            (student_id,)
        )
        evaluated_instructors_count = cursor.fetchone()['count']
        
        remaining_instructors = total_instructors - evaluated_instructors_count

    return render_template('dashboard.html', 
                           student=student_data,
                           evaluations_count=evaluations_count,
                           remaining_instructors=remaining_instructors,
                           total_instructors=total_instructors)

@app.route('/evaluate', methods=['GET', 'POST'])
@login_required
def evaluate():
    db = get_db()
    student_id = session['student_id']
    
    with db.cursor() as cursor:
        cursor.execute('SELECT COUNT(*) AS count FROM tbl_instructor')
        all_instructors_count = cursor.fetchone()['count']

        cursor.execute(
            """
            SELECT i_id, i_first_name, i_last_name, i_course 
            FROM tbl_instructor
            WHERE i_id NOT IN (
                SELECT i_id FROM tbl_evaluation WHERE s_schoolID = %s
            )
            """,
            (student_id,)
        )
        instructors = cursor.fetchall()

    if request.method == 'POST':
        try:
            instructor_id = request.form['instructor']
            remarks = request.form.get('remarks', '').strip()

            ratings = [int(request.form[f'q{i}']) for i in range(1, 5)]
            average_rating = round(sum(ratings) / len(ratings), 2)

            with db.cursor() as cursor:
                cursor.execute(
                    'INSERT INTO tbl_evaluation (i_id, s_schoolID, e_rating, e_remarks) VALUES (%s, %s, %s, %s)',
                    (instructor_id, student_id, average_rating, remarks)
                )
            db.commit()

            flash('Evaluation submitted successfully!', 'success')
            return redirect(url_for('dashboard'))

        except Exception as e:
            flash(f'Error: Check all fields were filled correctly. Details: {e}', 'error')

    return render_template('evaluate.html', 
                           instructors=instructors,
                           all_instructors=all_instructors_count)

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

if __name__ == '__main__':
    print("WARNING: Using MySQL. Ensure your server is running and credentials in app.py are correct.")
    # init_db() 
    print("Test Student (Approved): ID=12345, Name=John Doe")
    print("Test Student (Pending): ID=67890, Name=Jane Smith")
    app.run(debug=True)
