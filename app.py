import pymysql
from flask import Flask, render_template, request, url_for, redirect, session, flash, g
import os
from functools import wraps

# --- CONFIGURATION ---
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

# --- DATABASE CONNECTION ---
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
                sql_script = f.read().decode('utf8')
                for statement in sql_script.split(';'):
                    if statement.strip():
                        cursor.execute(statement)
            conn.commit()
            print("Database initialized successfully!")
        except Exception as e:
            print(f"Error during database initialization: {e}")
        finally:
            conn.close()

# --- DECORATORS (Authorization) ---

def login_required(role):
    def wrapper(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if role == 'student' and not session.get('student_id'):
                flash('Please log in to access this page.', 'info')
                return redirect(url_for('index'))
            if role == 'admin' and not session.get('admin_id'):
                flash('Please log in as an administrator.', 'info')
                return redirect(url_for('admin_login'))
            if role == 'teacher' and not session.get('teacher_id'):
                flash('Please log in to access this page.', 'info')
                return redirect(url_for('teacher_login'))
            return f(*args, **kwargs)
        return decorated_function
    return wrapper

# --- HELPER FUNCTIONS ---

def get_total_instructors():
    db = get_db()
    with db.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) as count FROM tbl_instructor")
        return cursor.fetchone()['count'] or 0

def get_student_evaluation_progress(school_id):
    db = get_db()
    total_instructors = get_total_instructors()
    
    with db.cursor() as cursor:
        cursor.execute("""
            SELECT COUNT(DISTINCT i_id) as count 
            FROM tbl_evaluation 
            WHERE s_schoolID = %s
        """, (school_id,))
        evaluated_count = cursor.fetchone()['count'] or 0
        
        cursor.execute("""
            SELECT DISTINCT i_id
            FROM tbl_evaluation 
            WHERE s_schoolID = %s
        """, (school_id,))
        evaluated_ids = [item['i_id'] for item in cursor.fetchall()]
        
        if total_instructors > 0:
            placeholders = ', '.join(['%s'] * len(evaluated_ids))
            if evaluated_ids:
                cursor.execute(f"""
                    SELECT i_id, i_first_name, i_last_name, i_course 
                    FROM tbl_instructor 
                    WHERE i_id NOT IN ({placeholders})
                """, evaluated_ids)
            else:
                cursor.execute("SELECT i_id, i_first_name, i_last_name, i_course FROM tbl_instructor")

            remaining_instructors_data = cursor.fetchall()
        else:
            remaining_instructors_data = []

    return {
        'total_instructors': total_instructors,
        'evaluated_count': evaluated_count,
        'remaining_instructors': total_instructors - evaluated_count,
        'remaining_instructors_data': remaining_instructors_data
    }

# --- PUBLIC ROUTES (Student) ---

@app.route('/', methods=['GET', 'POST'])
def index():
    db = get_db()
    progress = {}
    
    with db.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) AS count FROM tbl_instructor")
        instructors_empty = cursor.fetchone()['count'] == 0

    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'login':
            school_id = request.form.get('login_school_id')
            password = request.form.get('login_password')
            
            with db.cursor() as cursor:
                cursor.execute("SELECT *, s_password FROM tbl_student WHERE s_schoolID = %s", (school_id,))
                student = cursor.fetchone()
                
            if student:
                if student['s_status'] != 'Approved':
                    flash('Your account is pending approval by an administrator.', 'info')
                    return redirect(url_for('index'))
                
                if student['s_password'] == password:
                    session['student_id'] = student['s_schoolID']
                    session['student_name'] = f"{student['s_first_name']} {student['s_last_name']}"
                    flash(f'Welcome back, {student["s_first_name"]}!', 'success')
                    return redirect(url_for('dashboard'))
                else:
                    flash('Invalid School ID or Password.', 'error')
            else:
                flash('Invalid School ID or Password.', 'error')
                
        elif action == 'register':
            school_id = request.form.get('reg_school_id')
            password = request.form.get('reg_password')
            first_name = request.form.get('reg_first_name')
            last_name = request.form.get('reg_last_name')
            email = request.form.get('reg_email')
            year_level = request.form.get('reg_year_level')
            
            if not all([school_id, password, first_name, last_name, email, year_level]):
                flash('All fields are required.', 'error')
                return redirect(url_for('index'))
            
            plain_password = password 
            
            try:
                with db.cursor() as cursor:
                    cursor.execute(
                        "INSERT INTO tbl_student (s_schoolID, s_password, s_first_name, s_last_name, s_email, s_year_level, s_status) VALUES (%s, %s, %s, %s, %s, %s, 'Pending')",
                        (school_id, plain_password, first_name, last_name, email, year_level)
                    )
                db.commit()
                flash('Registration successful! Your account is pending administrator approval.', 'success')
                return redirect(url_for('index', tab='login')) 
            except pymysql.err.IntegrityError:
                flash('School ID is already registered.', 'error')
            except Exception as e:
                flash(f'An error occurred during registration: {e}', 'error')
                
    return render_template('index.html', instructors_empty=instructors_empty)

@app.route('/dashboard')
@login_required('student')
def dashboard():
    db = get_db()
    school_id = session['student_id']
    
    with db.cursor() as cursor:
        cursor.execute("SELECT * FROM tbl_student WHERE s_schoolID = %s", (school_id,))
        student_data = cursor.fetchone()

    progress = get_student_evaluation_progress(school_id)
    
    student_status = student_data.get('s_status', 'Pending')

    return render_template('dashboard.html',
        student={
            'id': student_data['s_schoolID'],
            'status': student_status,
            'email': student_data['s_email'],
            'year': student_data['s_year_level']
        },
        evaluations_count=progress['evaluated_count'],
        remaining_instructors=progress['remaining_instructors'],
        total_instructors=progress['total_instructors']
    )

@app.route('/evaluate', methods=['GET', 'POST'])
@login_required('student')
def evaluate():
    db = get_db()
    school_id = session['student_id']
    
    with db.cursor() as cursor:
        cursor.execute("SELECT q_id, q_text FROM tbl_evaluation_questions ORDER BY q_order")
        questions = cursor.fetchall()
        
    progress = get_student_evaluation_progress(school_id)
    
    if request.method == 'POST':
        instructor_id = request.form.get('instructor')
        remarks = request.form.get('remarks') 
        
        ratings = {}
        for q in questions:
            rating = request.form.get(f'q_{q["q_id"]}') 
            if not rating:
                flash(f'Please ensure all questions are rated. Missing rating for question ID {q["q_id"]}.', 'error')
                return redirect(url_for('evaluate'))
            ratings[q['q_id']] = int(rating)
            
        if not instructor_id:
            flash('Please select an instructor to evaluate.', 'error')
            return redirect(url_for('evaluate'))
            
        try:
            with db.cursor() as cursor:
                cursor.execute("""
                    SELECT COUNT(*) as count 
                    FROM tbl_evaluation 
                    WHERE s_schoolID = %s AND i_id = %s
                """, (school_id, instructor_id))
                if cursor.fetchone()['count'] > 0:
                    flash('You have already evaluated this instructor.', 'error')
                    return redirect(url_for('evaluate'))
                    
                cursor.execute("""
                    INSERT INTO tbl_evaluation (i_id, s_schoolID, remarks)
                    VALUES (%s, %s, %s)
                """, (instructor_id, school_id, remarks))
                
                evaluation_id = cursor.lastrowid
                
                for q_id, rating in ratings.items():
                    cursor.execute("""
                        INSERT INTO tbl_evaluation_details (e_id, q_id, rating_value)
                        VALUES (%s, %s, %s)
                    """, (evaluation_id, q_id, rating))
            
            db.commit()
            flash('Evaluation submitted successfully! Thank you for your feedback.', 'success')
            return redirect(url_for('dashboard'))
            
        except Exception as e:
            db.rollback()
            flash(f'Error submitting evaluation: {e}', 'error')
            return redirect(url_for('evaluate'))

    return render_template('evaluate.html',
        instructors=progress['remaining_instructors_data'],
        all_instructors=progress['total_instructors'],
        questions=questions
    )


@app.route('/logout')
def logout():
    session.pop('student_id', None)
    session.pop('student_name', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

# --- TEACHER ROUTES ---

@app.route('/teacher_login', methods=['GET', 'POST'])
def teacher_login():
    if session.get('teacher_id'):
        return redirect(url_for('teacher_dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        db = get_db()
        
        with db.cursor() as cursor:
            cursor.execute("SELECT *, t_password FROM tbl_teacher WHERE t_username = %s", (username,))
            teacher = cursor.fetchone()
            
        if teacher and teacher['t_password'] == password:
            session['teacher_id'] = teacher['t_id']
            session['teacher_name'] = f"{teacher['t_first_name']} {teacher['t_last_name']}"
            flash('Teacher login successful!', 'success')
            return redirect(url_for('teacher_dashboard'))
        else:
            flash('Invalid username or password.', 'error')
            
    return render_template('teacher_login.html')


@app.route('/teacher_dashboard')
@login_required('teacher')
def teacher_dashboard():
    db = get_db()
    teacher_id = session['teacher_id']
    
    with db.cursor() as cursor:
        cursor.execute("""
            SELECT 
                i.i_id, 
                i.i_course, 
                CONCAT(i.i_first_name, ' ', i.i_last_name) AS instructor_name,
                COUNT(DISTINCT e.e_id) AS evaluation_count,
                AVG(ed.rating_value) AS average_rating
            FROM tbl_instructor i
            LEFT JOIN tbl_evaluation e ON i.i_id = e.i_id
            LEFT JOIN tbl_evaluation_details ed ON e.e_id = ed.e_id
            WHERE i.t_id = %s
            GROUP BY i.i_id, i.i_course, instructor_name
        """, (teacher_id,))
        courses = cursor.fetchall()
        
        cursor.execute("SELECT COUNT(*) AS count FROM tbl_student WHERE s_status = 'Approved'")
        total_approved_students = cursor.fetchone()['count']
        
    return render_template('teacher_dashboard.html', 
                           courses=courses, 
                           total_approved_students=total_approved_students)


@app.route('/teacher_view_results/<int:instructor_id>')
@login_required('teacher')
def teacher_view_results(instructor_id):
    db = get_db()
    teacher_id = session['teacher_id']
    
    with db.cursor() as cursor:
        cursor.execute("SELECT * FROM tbl_instructor WHERE i_id = %s AND t_id = %s", 
                       (instructor_id, teacher_id))
        instructor = cursor.fetchone()
        
        if not instructor:
            flash('You are not authorized to view results for this instructor.', 'error')
            return redirect(url_for('teacher_dashboard'))
            
        cursor.execute("SELECT q_id, q_text FROM tbl_evaluation_questions ORDER BY q_order")
        questions = cursor.fetchall()

        question_stats = []
        for q in questions:
            cursor.execute("""
                SELECT 
                    AVG(ed.rating_value) AS avg_rating,
                    COUNT(ed.rating_value) AS total_responses
                FROM tbl_evaluation_details ed
                JOIN tbl_evaluation e ON ed.e_id = e.e_id
                WHERE ed.q_id = %s AND e.i_id = %s
            """, (q['q_id'], instructor_id))
            stats = cursor.fetchone()
            question_stats.append({
                'q_text': q['q_text'],
                'avg_rating': f"{stats['avg_rating']:.2f}" if stats['avg_rating'] else "N/A",
                'total_responses': stats['total_responses']
            })
            
        cursor.execute("""
            SELECT remarks, e_date_submitted 
            FROM tbl_evaluation 
            WHERE i_id = %s AND remarks IS NOT NULL AND remarks != ''
            ORDER BY e_date_submitted DESC
        """, (instructor_id,))
        remarks = cursor.fetchall()
        
    return render_template('teacher_view_results.html', 
                           instructor=instructor, 
                           stats=question_stats, 
                           remarks=remarks)


@app.route('/teacher_logout')
def teacher_logout():
    session.pop('teacher_id', None)
    session.pop('teacher_name', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))


# --- ADMIN ROUTES ---

@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if session.get('admin_id'):
        return redirect(url_for('admin_dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        db = get_db()
        
        with db.cursor() as cursor:
            cursor.execute("SELECT *, a_password FROM tbl_admin WHERE a_username = %s", (username,))
            admin = cursor.fetchone()
            
        if admin and admin['a_password'] == password:
            session['admin_id'] = admin['a_id']
            session['admin_name'] = admin['a_username']
            flash('Admin login successful!', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid Username or Password.', 'error')
            
    return render_template('admin_login.html')

@app.route('/admin_dashboard')
@login_required('admin')
def admin_dashboard():
    db = get_db()
    
    with db.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) AS pending FROM tbl_student WHERE s_status = 'Pending'")
        pending_students = cursor.fetchone()['pending']
        cursor.execute("SELECT COUNT(*) AS total FROM tbl_student")
        total_students = cursor.fetchone()['total']
        cursor.execute("SELECT COUNT(*) AS teachers FROM tbl_teacher")
        total_teachers = cursor.fetchone()['teachers']
        cursor.execute("SELECT COUNT(*) AS instructors FROM tbl_instructor")
        total_instructors = cursor.fetchone()['instructors']
        
        cursor.execute("SELECT s_schoolID, s_first_name, s_last_name, s_email, s_year_level FROM tbl_student WHERE s_status = 'Pending' ORDER BY s_schoolID")
        students = cursor.fetchall()
        
    return render_template('admin_dashboard.html', 
                           pending_students=pending_students,
                           total_students=total_students,
                           total_teachers=total_teachers,
                           total_instructors=total_instructors,
                           students=students)

@app.route('/approve_student/<string:student_id>')
@login_required('admin')
def approve_student(student_id):
    db = get_db()
    try:
        with db.cursor() as cursor:
            cursor.execute(
                "UPDATE tbl_student SET s_status = 'Approved' WHERE s_schoolID = %s",
                (student_id,)
            )
        db.commit()
        flash(f'Student {student_id} has been approved.', 'success')
    except Exception as e:
        flash(f'Error approving student: {e}', 'error')
        
    return redirect(url_for('admin_dashboard'))

# --- ADMIN: Manage Teachers (Teacher Login Accounts) ---

@app.route('/admin_manage_teachers', methods=['GET', 'POST'])
@login_required('admin')
def admin_manage_teachers():
    db = get_db()
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'add':
            username = request.form.get('t_username')
            password = request.form.get('t_password')
            first_name = request.form.get('t_first_name')
            last_name = request.form.get('t_last_name')
            
            if not all([username, password, first_name, last_name]):
                flash('All fields are required to add a teacher.', 'error')
            else:
                plain_password = password
                try:
                    with db.cursor() as cursor:
                        cursor.execute(
                            "INSERT INTO tbl_teacher (t_username, t_password, t_first_name, t_last_name) VALUES (%s, %s, %s, %s)",
                            (username, plain_password, first_name, last_name)
                        )
                    db.commit()
                    flash('New teacher account added successfully!', 'success')
                except pymysql.err.IntegrityError:
                    flash('Username already exists.', 'error')
                except Exception as e:
                    flash(f'Error adding teacher: {e}', 'error')

        elif action == 'delete':
            teacher_id = request.form.get('t_id')
            try:
                with db.cursor() as cursor:
                    cursor.execute("SELECT COUNT(*) AS count FROM tbl_instructor WHERE t_id = %s", (teacher_id,))
                    if cursor.fetchone()['count'] > 0:
                        flash('Cannot delete teacher. Please unassign all instructors first.', 'error')
                    else:
                        cursor.execute("DELETE FROM tbl_teacher WHERE t_id = %s", (teacher_id,))
                        db.commit()
                        flash('Teacher account deleted successfully!', 'success')
            except Exception as e:
                flash(f'Error deleting teacher: {e}', 'error')
            
        return redirect(url_for('admin_manage_teachers'))
        
    with db.cursor() as cursor:
        cursor.execute("SELECT t_id, t_username, t_first_name, t_last_name FROM tbl_teacher ORDER BY t_last_name")
        teachers = cursor.fetchall()
        
    return render_template('admin_manage_teachers.html', teachers=teachers)


# --- ADMIN: Manage Instructors (Courses/Subjects) ---

@app.route('/admin_manage_instructors', methods=['GET', 'POST'])
@login_required('admin')
def admin_manage_instructors():
    db = get_db()
    
    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'add':
            i_first_name = request.form.get('i_first_name')
            i_last_name = request.form.get('i_last_name')
            i_course = request.form.get('i_course')
            
            try:
                with db.cursor() as cursor:
                    cursor.execute(
                        "INSERT INTO tbl_instructor (i_first_name, i_last_name, i_course, t_id) VALUES (%s, %s, %s, NULL)",
                        (i_first_name, i_last_name, i_course)
                    )
                db.commit()
                flash('New instructor added successfully!', 'success')
            except Exception as e:
                flash(f'Error adding instructor: {e}', 'error')

        elif action == 'delete':
            i_id = request.form.get('i_id')
            try:
                with db.cursor() as cursor:
                    cursor.execute("SELECT COUNT(*) AS count FROM tbl_evaluation WHERE i_id = %s", (i_id,))
                    if cursor.fetchone()['count'] > 0:
                        flash('Cannot delete instructor. Evaluations exist.', 'error')
                    else:
                        cursor.execute("DELETE FROM tbl_instructor WHERE i_id = %s", (i_id,))
                        db.commit()
                        flash('Instructor deleted successfully!', 'success')
            except Exception as e:
                flash(f'Error deleting instructor: {e}', 'error')

        elif action == 'assign_teacher':
            i_id = request.form.get('i_id')
            t_id = request.form.get('t_id')
            
            try:
                new_t_id = int(t_id) if t_id and t_id.lower() != 'none' else None
                with db.cursor() as cursor:
                    cursor.execute(
                        "UPDATE tbl_instructor SET t_id = %s WHERE i_id = %s",
                        (new_t_id, i_id)
                    )
                db.commit()
                flash('Teacher assignment updated successfully!', 'success')
            except Exception as e:
                flash(f'Error assigning teacher: {e}', 'error')
                
        return redirect(url_for('admin_manage_instructors'))
        
    with db.cursor() as cursor:
        cursor.execute("""
            SELECT 
                i.*, 
                CONCAT(t.t_first_name, ' ', t.t_last_name) AS teacher_name,
                t.t_id AS assigned_teacher_id
            FROM tbl_instructor i
            LEFT JOIN tbl_teacher t ON i.t_id = t.t_id
            ORDER BY i.i_last_name
        """)
        instructors = cursor.fetchall()
        
        cursor.execute("SELECT t_id, t_first_name, t_last_name FROM tbl_teacher ORDER BY t_last_name")
        teachers = cursor.fetchall()
        
    return render_template('admin_manage_instructors.html', 
                           instructors=instructors, 
                           teachers=teachers)

@app.route('/admin_view_evaluations/<int:instructor_id>')
@login_required('admin')
def admin_view_evaluations(instructor_id):
    db = get_db()

    with db.cursor() as cursor:
        cursor.execute("SELECT * FROM tbl_instructor WHERE i_id = %s", (instructor_id,))
        instructor = cursor.fetchone()
        
        if not instructor:
            flash('Instructor not found.', 'error')
            return redirect(url_for('admin_manage_instructors'))
            
        cursor.execute("SELECT q_id, q_text FROM tbl_evaluation_questions ORDER BY q_order")
        questions = cursor.fetchall()

        question_stats = []
        for q in questions:
            cursor.execute("""
                SELECT 
                    AVG(ed.rating_value) AS avg_rating,
                    COUNT(ed.rating_value) AS total_responses
                FROM tbl_evaluation_details ed
                JOIN tbl_evaluation e ON ed.e_id = e.e_id
                WHERE ed.q_id = %s AND e.i_id = %s
            """, (q['q_id'], instructor_id))
            stats = cursor.fetchone()
            question_stats.append({
                'q_text': q['q_text'],
                'avg_rating': f"{stats['avg_rating']:.2f}" if stats['avg_rating'] else "N/A",
                'total_responses': stats['total_responses']
            })
            
        cursor.execute("""
            SELECT e.remarks, e.e_date_submitted, s.s_year_level 
            FROM tbl_evaluation e
            JOIN tbl_student s ON e.s_schoolID = s.s_schoolID
            WHERE e.i_id = %s AND e.remarks IS NOT NULL AND e.remarks != ''
            ORDER BY e.e_date_submitted DESC
        """, (instructor_id,))
        remarks = cursor.fetchall()
        
    return render_template('admin_view_evaluations.html', 
                           instructor=instructor, 
                           stats=question_stats, 
                           remarks=remarks)


# --- ADMIN: Manage Questions ---

@app.route('/admin_manage_questions', methods=['GET', 'POST'])
@login_required('admin')
def admin_manage_questions():
    db = get_db()
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'update_questions':
            question_data = request.form.to_dict()
            try:
                with db.cursor() as cursor:
                    for key, text in question_data.items():
                        if key.startswith('q_text_'):
                            q_id = key.split('_')[-1]
                            text = text.strip()
                            if text:
                                cursor.execute(
                                    'UPDATE tbl_evaluation_questions SET q_text = %s WHERE q_id = %s',
                                    (text, q_id)
                                )
                db.commit()
                flash('Evaluation questions updated successfully!', 'success')
            except Exception as e:
                flash(f'Error updating questions: {e}', 'error')
            
            return redirect(url_for('admin_manage_questions'))
            
        elif action == 'add_question':
            q_text = request.form.get('new_q_text')
            try:
                with db.cursor() as cursor:
                    cursor.execute("SELECT MAX(q_order) AS max_order FROM tbl_evaluation_questions")
                    max_order = cursor.fetchone()['max_order']
                    new_order = (max_order or 0) + 1
                    
                    cursor.execute(
                        "INSERT INTO tbl_evaluation_questions (q_text, q_order) VALUES (%s, %s)",
                        (q_text, new_order)
                    )
                db.commit()
                flash('New question added successfully!', 'success')
            except Exception as e:
                flash(f'Error adding question: {e}', 'error')
            
            return redirect(url_for('admin_manage_questions'))

        elif action == 'delete_question':
            q_id = request.form.get('q_id_to_delete')
            try:
                with db.cursor() as cursor:
                    cursor.execute("SELECT COUNT(*) AS count FROM tbl_evaluation_details WHERE q_id = %s", (q_id,))
                    if cursor.fetchone()['count'] > 0:
                        flash('Cannot delete question. Existing evaluations use it.', 'error')
                    else:
                        cursor.execute("DELETE FROM tbl_evaluation_questions WHERE q_id = %s", (q_id,))
                        db.commit()
                        flash('Question deleted successfully!', 'success')
            except Exception as e:
                flash(f'Error deleting question: {e}', 'error')
            
            return redirect(url_for('admin_manage_questions'))

            
    with db.cursor() as cursor:
        cursor.execute("SELECT q_id, q_text, q_order FROM tbl_evaluation_questions ORDER BY q_order")
        questions = cursor.fetchall()
        
    return render_template('admin_manage_questions.html', questions=questions)


@app.route('/admin_logout')
def admin_logout():
    session.pop('admin_id', None)
    session.pop('admin_name', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/init_db')
def initial_setup():
    init_db()
    flash('Database setup complete. All passwords are now set to "password".', 'info')
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)