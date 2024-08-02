import os
import sys
import time
import sqlite3
import datetime

from flask import Flask, redirect, url_for, request
from flask import render_template
from flask_discord import DiscordOAuth2Session, requires_authorization, Unauthorized

import rq_dashboard

from . import worker
from . import db

app = Flask(__name__)
app.config.from_object('stcr.default_settings')
try:
    app.config.from_envvar('STCR_SETTINGS')  # path to config file.
except RuntimeError:
    print("No STCR_SETTINGS env var, using no custom settings file.", file=sys.stderr)

app.config.from_object(rq_dashboard.default_settings)
app.config["RQ_DASHBOARD_REDIS_URL"] = "redis://127.0.0.1:6379"
rq_dashboard.web.setup_rq_connection(app)

@rq_dashboard.blueprint.before_request
def dashboard_auth():
    discord_user = discord.fetch_user()
    conn = db.get_db_connection()
    db_user = db.get_or_create_user(conn, discord_user)
    if not db_user['is_admin']:
        return "Admin user login required."


app.register_blueprint(rq_dashboard.blueprint, url_prefix="/rq")

exec(open(os.path.dirname(__file__) + '/../secrets.py').read())  # provides `config`

app.secret_key = config['flask_secret_key']
# OAuth2 must make use of HTTPS in production environment.
#os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "true"      # !! Only in development environment.

app.config["DISCORD_CLIENT_ID"] = config['client_id']    # Discord client ID.
app.config["DISCORD_CLIENT_SECRET"] = config['client_secret']                # Discord client secret.
app.config["DISCORD_REDIRECT_URI"] = "https://stcr.nevira.net/app/auth/discord-redirect"                 # URL to your callback endpoint.
app.config["DISCORD_BOT_TOKEN"] = ""                    # Required to access BOT resources.


discord = DiscordOAuth2Session(app)

@app.route("/auth/discord-login/")
def login():
    return discord.create_session(scope=['identify', 'email'])


@app.route("/auth/discord-redirect")
def callback():
    discord.callback()
    user = discord.fetch_user()
    #welcome_user(user)
    return redirect(url_for(".me"))


@app.route("/auth/discord-revoke/")
def logout():
    discord.revoke()
    return "Logged Out"


@app.errorhandler(Unauthorized)
def redirect_unauthorized(e):
    return redirect(url_for("login"))


@app.route("/")
@requires_authorization
def me():
    discord_user = discord.fetch_user()

    conn = db.get_db_connection()
    db_user = db.get_or_create_user(conn, discord_user)
    status = 'ALLOCATED'
    if db_user['a_panel'] is None:
        if db_user['aid'] is not None:
            # they were allocated a NULL panel; ie no panels were available
            status = 'FAILED'
        else:
            # Check if they have pending choices
            choices = conn.execute(
                'SELECT c.*, p.page as p_issue FROM choices c '
                ' LEFT JOIN panels p ON p.id = c.panel'
                ' WHERE user = (?) AND p_issue != 4',
                (db_user['id'],)
            ).fetchall()
            if choices:
                status = 'PENDING'
            else:
                status = 'NEW'

    available_panels = conn.execute(
        "SELECT * FROM panels p "
        " WHERE issue = 4 "
        " AND NOT EXISTS ("
        "    SELECT * FROM allocations a WHERE a.panel == p.id"
        " )"
    ).fetchall()

    conn.close()
    return render_template('me.html',
            available_panels=list(available_panels),
            discord_user=discord_user,
            status=status,
            db_user=db_user)


@app.route("/choose", methods=('POST',))
@requires_authorization
def choose():
    """Store the user's panel choices.
    
    The task queue will process whether it's valid or not later."""
    discord_user = discord.fetch_user()

    conn = db.get_db_connection()
    db_user = db.get_or_create_user(conn, discord_user)

    choices = {}
    choices[1] = tuple(map(int, (request.form['first_choice'] or '0-0').split('-')))
    choices[2] = tuple(map(int, (request.form['second_choice'] or '0-0').split('-')))
    choices[3] = tuple(map(int, (request.form['third_choice'] or '0-0').split('-')))

    now = datetime.datetime.now()
    for pref, choice in choices.items():
        conn.execute(
            "INSERT INTO choices (created, user, panel, preference)"
            "VALUES "
            "( ?, ?"
            ", (SELECT id FROM panels p WHERE p.issue == 4 AND p.page = ? AND p.panel = ?)"
            ", ?"
            ")",
            (now, db_user['id']) + choice + (pref,)
        )
    conn.commit()

    worker.async_allocate()

    # this is usually enough that redis will have alread run and the user will get a nice confirmation first try
    time.sleep(0.5)

    return redirect(url_for(".me"))


@app.route("/add-worker")
@requires_authorization
def add_worker():
    discord_user = discord.fetch_user()
    conn = db.get_db_connection()
    db_user = db.get_or_create_user(conn, discord_user)
    if not db_user['is_admin']:
        return "Admin user login required."
    worker.async_allocate()
    return "OK"


@app.route("/queue")
@requires_authorization
def queue():
    discord_user = discord.fetch_user()
    conn = db.get_db_connection()
    db_user = db.get_or_create_user(conn, discord_user)
    if not db_user['is_admin']:
        return "Admin user login required."

    choices = conn.execute(
        "SELECT "
        "  c.*"
        ", u.discord_username as discord_username"
        ", p1.issue as p1_issue"
        ", p1.page as p1_page"
        ", p1.panel as p1_panel"
        ", p2.issue as p2_issue"
        ", p2.page as p2_page"
        ", p2.panel as p2_panel"
        ", p3.issue as p3_issue"
        ", p3.page as p3_page"
        ", p3.panel as p3_panel"
        ", pc.issue as pc_issue"
        ", pc.page as pc_page"
        ", pc.panel as pc_panel"
        " FROM choices c "
        " LEFT JOIN users u ON c.user=u.id"
        " LEFT JOIN panels p1 ON p1.id=c.first_choice "
        " LEFT JOIN panels p2 ON p2.id=c.second_choice "
        " LEFT JOIN panels p3 ON p3.id=c.third_choice "
        " LEFT JOIN panels pc ON pc.id=c.confirmed_choice "
        " ORDER BY created"
    ).fetchall()
    return render_template('queue.html',
            discord_user=discord_user,
            db_user=db_user,
            choices=choices)

