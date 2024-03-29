from flask import Flask, render_template, request, redirect, session, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import desc
from datetime import datetime, date
from os import environ as env
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
from collections import defaultdict

load_dotenv()

app = Flask(__name__)
app.secret_key = env.get('SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# TODO: Create a User model with id, username, password


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), nullable=False, unique=True)
    email = db.Column(db.String(100), nullable=False, unique=True)
    password = db.Column(db.String(100), nullable=False)
    expense = db.relationship('Expenses', backref='user', lazy=True)
    

    def __repr__(self):
        return f'User {self.id}'


class Expenses(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.DateTime, nullable=False, default=datetime.now())
    split_with = db.Column(db.Integer, nullable=False)
    per_person = db.Column(db.Float, nullable=False)
    completed = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f'Expense {self.id}'


with app.app_context():
    db.create_all()

admin = Admin(app)
admin.add_view(ModelView(User, db.session))
admin.add_view(ModelView(Expenses, db.session))

@app.route('/')
def index():
    if 'user_id' not in session:
        return render_template('index.html', logged_in=False)
    return render_template("index.html", logged_in=True)


@app.route('/login', methods=['GET',  'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            return redirect('/')
        else:
            print('Invalid username or password')
    return render_template('auth/login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' not in session:
        return redirect('/login')
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_pass = request.form['confirm-password']
        if password == confirm_pass:
            password = generate_password_hash(password)
            user = User(username=username, email=email, password=password)
            db.session.add(user)
            db.session.commit()
            session['user_id'] = user.id
            return redirect('/')
        else:
            flash('Passwords do not match')
            return render_template('auth/signup.html')
    return render_template('auth/signup.html')

@app.route('/logout')
def logout():
    if 'user_id' not in session:
        return redirect('/login')
    session.pop('user_id', None)
    return redirect('/')

import calendar

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect('/login')

    current_year = date.today().year
    current_month = date.today().month
    num_days = calendar.monthrange(current_year, current_month)[1]

    # Initialize lists to store expenses for each day
    daily_expenses = [0] * num_days

    # Query expenses recorded for each day within the current month
    for day in range(1, num_days + 1):
        daily_expense = db.session.query(db.func.sum(Expenses.amount)).\
            filter(db.extract('day', Expenses.date) == day).\
            filter(db.extract('month', Expenses.date) == current_month).\
            filter(db.extract('year', Expenses.date) == current_year).\
            filter_by(user_id=session['user_id']).scalar()
        daily_expenses[day - 1] = daily_expense if daily_expense else 0

    # Prepare labels for the x-axis (days of the month)
    labels = [str(day) for day in range(1, num_days + 1)]

    total_expense_month = db.session.query(db.func.sum(Expenses.amount)).\
        filter(db.extract('month', Expenses.date) == current_month).\
        filter(db.extract('year', Expenses.date) == current_year).\
        filter_by(user_id=session['user_id']).scalar()

    total_expense_all = db.session.query(db.func.sum(Expenses.amount)).\
        filter_by(user_id=session['user_id']).scalar()
    total_people = db.session.query(db.func.sum(Expenses.split_with)).filter_by(user_id=session['user_id']).scalar()
    curr_user = User.query.filter_by(id=session['user_id']).first()

    expenses = Expenses.query.filter_by(user_id=session['user_id']).order_by(desc(Expenses.id)).all()

    return render_template('dashboard.html', logged_in=True, total_expense_month=total_expense_month, total_expense_all=total_expense_all, total_people=total_people, curr_user=curr_user, expenses=expenses, labels=labels, daily_expenses=daily_expenses)


@app.route('/expenses')
def expenses():
    if 'user_id' not in session:
        return redirect('/login')
    expenses = Expenses.query.filter_by(user_id=session['user_id']).order_by(desc(Expenses.id)).all()
    return render_template('expenses.html', expenses = expenses, logged_in=True)

@app.route('/add_expense', methods=['GET', 'POST'])
def add_expense():
    if 'user_id' not in session:
        return redirect('/login')
    if request.method == 'POST':
        title = request.form['title']
        amount = request.form['amount']
        split_with = request.form['split']
        per_person = float(amount) / float(split_with)
        expense = Expenses(title=title, amount=amount, user_id=session['user_id'], split_with=split_with, per_person=per_person)
        db.session.add(expense)
        db.session.commit()
        return redirect('/expenses')
    return render_template('create_expense.html', logged_in=True)


@app.route('/delete_expense/<int:id>')
def delete_expense(id):
    if 'user_id' not in session:
        return redirect('/login')
    expense = Expenses.filter_by(id).first()
    db.session.remove(expense)
    db.session.commit()
    return redirect('/expenses')

@app.route('/edit_expense/<int:id>')
def edit_expense(id):
    if 'user_id' not in session:
        return redirect('/login')
    expense = Expenses.query.filter_by(id=id).first()
    return render_template('edit_expense.html', expense=expense, logged_in=True)

@app.route('/update_expense/<int:id>', methods=['GET', 'POST'])
def update_expense(id):
    if 'user_id' not in session:
        return redirect('/login')
    expense = Expenses.query.filter_by(id=id).first()
    if request.method == 'POST':
        expense.title = request.form['title']
        expense.amount = request.form['amount']
        expense.split_with = request.form['split']
        expense.per_person = float(expense.amount) / float(expense.split_with)
        db.session.commit()
        return redirect('/expenses')
    return render_template('edit_expense.html', expense=expense, logged_in=True)

# @app.route('/history')
# def history():
#     if 'user_id' not in session:
#         return redirect('/login')
#     history = History.query.filter_by(user_id=session['user_id']).order_by(desc(History.id)).all()
#     return render_template('history.html', histories = history, logged_in=True)

# @app.route('/clear_history', methods=['GET', 'POST'])
# def clear_history():
#     if request.method == 'POST':
#         History.query.filter_by(user_id=session['user_id']).delete()
#         db.session.commit()
#         return redirect('/history')
#     return render_template('history.html', logged_in=True)

@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect('/login')
    curr_user = User.query.filter_by(id=session['user_id']).first()
    return render_template('profile.html', curr_user=curr_user, logged_in=True)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=80)
