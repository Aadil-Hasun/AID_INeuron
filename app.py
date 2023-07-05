from flask import Flask, render_template, redirect, url_for, request
import os
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from sqlalchemy.orm import backref
from flask_bootstrap import Bootstrap
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, DateTimeField, IntegerField
from wtforms.validators import InputRequired, Email, Length
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import datetime

from src.scheduler import create_cloudwatch_event_rule
from src.scraper_s3 import ScrapData
from src.utils import is_email_verified, verify_email

app = Flask(__name__)

basedir = os.path.abspath(os.path.dirname(__file__))
path = 'sqlite:///' + os.path.join(basedir, 'data.sqlite')
app.config['SECRET_KEY'] = 'This_is_a_secret'
app.config['SQLALCHEMY_DATABASE_URI'] = path
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'This_is_a_secret'

bootstrap = Bootstrap(app)
db = SQLAlchemy(app)
Migrate(app, db)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

with app.app_context():
    class SigninForm(FlaskForm):
        username = StringField('username', validators=[InputRequired(), Length(min=5, max=9)])
        password = PasswordField('password', validators=[InputRequired(), Length(min=8, max=24)])


    class SignupForm(FlaskForm):
        username = StringField('username', validators=[InputRequired(), Length(min=5, max=9)])
        email = StringField('email', validators=[InputRequired(), Email(message='Invalid Email')])
        password = PasswordField('password', validators=[InputRequired(), Length(min=8, max=24)])


    class ScrapeForm(FlaskForm):
        category_name = StringField('category_name', validators=[InputRequired()])
        date_time = DateTimeField("""Select date and time to schedule the job. \n
                                Example, 2023-06-20T11:59:59""", format='%Y-%m-%dT%H:%M:%S',
                                  validators=[InputRequired()])
        email = StringField('email', validators=[InputRequired(), Email(message='Invalid Email')])
        max_images = IntegerField('maximum images to fetch', validators=[InputRequired()])


    class VerifyForm(FlaskForm):
        email = StringField('email', validators=[InputRequired(), Email(message='Invalid Email')])


    class Users(UserMixin, db.Model):
        __tablename__ = 'users'
        id = db.Column(db.Integer, primary_key=True)
        name = db.Column(db.String(), unique=True)
        email = db.Column(db.String())
        password = db.Column(db.String())

        def __init__(self, name, email, password):
            self.name = name
            self.email = email
            self.password = password


    class UsageDetails(db.Model):
        __tablename__ = 'usage_details'
        id = db.Column(db.Integer(), primary_key=True)
        date_time = db.Column(db.DateTime())
        schedule_time = db.Column(db.DateTime())
        category_name = db.Column(db.String())
        user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
        users = db.relationship("Users", backref=backref("users", uselist=False))

        def __init__(self, category_name, schedule_time, date_time, user_id):
            self.category_name = category_name
            self.schedule_time = schedule_time
            self.date_time = date_time
            self.user_id = user_id


    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(Users, int(user_id))


    @app.route("/")
    def index():
        return render_template("index.html")


    @app.route('/signup', methods=['GET', 'POST'])
    def signup():
        form = SignupForm()

        if request.method == 'POST':
            if form.validate_on_submit():
                user = Users.query.filter_by(name=form.username.data).first()
                if user:
                    return render_template("signup.html", form=form, error="This username already exists…")
                else:
                    new_user = Users(name=form.username.data, email=form.email.data, password=form.password.data)
                    db.session.add(new_user)
                    db.session.commit()
                    return render_template("signin.html", form=SigninForm())
            else:
                return render_template("signup.html", form=form, error="Please, try again..")
        else:
            return render_template("signup.html", form=form, error=None)


    @app.route('/signin', methods=['GET', 'POST'])
    def signin():
        form = SigninForm()
        if form.validate_on_submit():
            user = Users.query.filter_by(name=form.username.data).first()
            if user:
                if user.password == form.password.data:
                    login_user(user)
                    return redirect(url_for('scrape'))
            return render_template("signin.html", form=form, error="Username or Password entered is invalid")
        return render_template("signin.html", form=form)


    @app.route('/scrape', methods=['GET', 'POST'])
    @login_required
    def scrape():
        form = ScrapeForm()
        verify_form = VerifyForm()
        if request.method == 'POST':
            if form.validate_on_submit():
                category_name = form.category_name.data
                schedule_time = form.date_time.data
                send_to_email = form.email.data
                max_images = form.max_images.data
                minute = schedule_time.minute
                hour = schedule_time.hour
                day = schedule_time.day
                month = schedule_time.month
                year = schedule_time.year
                scheduled_time = datetime(year, month, day, hour, minute, 0)
                if not is_email_verified(send_to_email):
                    verify_email(send_to_email)
                    return render_template('verify.html', form=verify_form,
                                           verification_info="This email ID is not verified. "
                                                             "We've sent you a verification "
                                                             "email on the same email ID. "
                                                             "Please verify the email and then"
                                                             " click on the button.")

                if scheduled_time < datetime.utcnow():
                    return render_template("scrape.html", form=form, msg="The time specified has already"
                                                                         " passed. Enter a valid UTC time and date")
                else:
                    # Format the cron expression
                    schedule_expression = f'{minute} {hour} {day} {month} ? {year}'
                    print(schedule_expression)
                    s_obj = ScrapData()
                    zipfile_name = s_obj.scrap_data(category_name, max_images, current_user.name)
                    print(f"Zipfile: {zipfile_name}")

                    if scheduled_time < datetime.utcnow():
                        current_time = datetime.utcnow()
                        year = current_time.year
                        month = current_time.month
                        day = current_time.day
                        hour = current_time.hour
                        minute = current_time.minute
                        schedule_expression = f'{minute+5} {hour} {day} {month} ? {year}'

                    rule = create_cloudwatch_event_rule(zipfile_name, current_user.name, schedule_expression,
                                                        send_to_email)

                    return render_template('scrape.html', form=form, name=current_user.name, myrule=rule)
        return render_template('scrape.html', form=form, name=current_user.name)


    @app.route('/verify', methods=['GET', 'POST'])
    @login_required
    def verify():
        verify_form = VerifyForm()
        form = ScrapeForm()
        if request.method == 'POST':
            if verify_form.validate_on_submit():
                email = verify_form.email.data
                if is_email_verified(email):
                    return render_template("scrape.html", form=form, verification_info="Your email has been verified"
                                                                                       " with us. Please schedule your"
                                                                                       " job.")
                else:
                    return render_template("verify.html", form=verify_form,
                                           verification_info="Your email is not verified. Please check your inbox "
                                                             "and verify your email.")
            else:
                return render_template("verify.html", form=verify_form,
                                       verification_info="Please enter a valid response")

    @app.route('/logout')
    @login_required
    def logout():
        logout_user()
        return redirect(url_for('index'))


    if __name__ == '__main__':
        db.create_all()
        app.run("localhost", port=5006, debug=True)

