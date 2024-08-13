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
    with db.db_cursor() as cur:
        db_user = db.get_or_create_user(cur, discord_user.name)
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

app.config['DB_PW'] = config['db_password']

discord = DiscordOAuth2Session(app)

@app.route("/auth/discord-login/")
def login():
    return discord.create_session(scope=['identify'])


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

    with db.db_cursor() as cur:
        db_user = db.get_or_create_user(cur, discord_user.name)
        status = 'ALLOCATED'
        if db_user['a_panel'] is None:
            if db_user['aid'] is not None:
                # they were allocated a NULL panel; ie no panels were available
                status = 'FAILED'
            else:
                # Check if they have pending choices
                cur.execute(
                    'SELECT c.*, p.issue as p_issue FROM choices c '
                    ' LEFT JOIN panels p ON p.id = c.panel'
                    ' WHERE u = (%s) AND p.issue = 4',
                    (db_user['id'],)
                )
                choices = cur.fetchall()
                if choices:
                    status = 'PENDING'
                else:
                    status = 'NEW'

        cur.execute(
            "SELECT * FROM panels p "
            " WHERE issue = 4 "
            " AND NOT EXISTS ("
            "    SELECT * FROM allocations a WHERE a.panel = p.id"
            " )"
        ) # FIXME - this doesn't account for returned panels.
        available_panels = cur.fetchall()

    return render_template('me.html',
            available_panels=list(available_panels),
            discord_user=discord_user,
            status=status,
            db_user=db_user)


@app.route("/return", methods=('post',))
@requires_authorization
def return_panel():
    """Return a user's panel choice"""
    # internally, add a NULL allocation.

    discord_user = discord.fetch_user()
    with db.db_cursor() as cur:
        db_user = db.get_or_create_user(cur, discord_user.name)
        if not db_user['is_admin']:
            return "Admin user login required."

        cur.execute(
            "INSERT INTO allocations (u, panel) VALUES ((%s), NULL)",
            (request.form['user'],)
        )
    return "OK"

@app.route("/choose", methods=('post',))
@requires_authorization
def choose():
    """Store the user's panel choices.
    
    The task queue will process whether it's valid or not later."""
    discord_user = discord.fetch_user()

    with db.db_cursor() as cur:
        db_user = db.get_or_create_user(cur, discord_user.name)

        choices = {}
        choices[1] = tuple(map(int, (request.form['first_choice'] or '0-0').split('-')))
        choices[2] = tuple(map(int, (request.form['second_choice'] or '0-0').split('-')))
        choices[3] = tuple(map(int, (request.form['third_choice'] or '0-0').split('-')))

        now = datetime.datetime.now()
        for pref, choice in choices.items():
            cur.execute(
                "INSERT INTO choices (created, u, panel, preference)"
                "VALUES "
                "( %s, %s"
                ", (SELECT id FROM panels p WHERE p.issue = 4 AND p.page = %s AND p.panel = %s)"
                ", %s"
                ")",
                (now, db_user['id']) + choice + (pref,)
            )

    worker.async_allocate()

    # this is usually enough that redis will have alread run and the user will get a nice confirmation first try
    time.sleep(0.5)

    return redirect(url_for(".me"))


@app.route("/add-worker")
@requires_authorization
def add_worker():
    discord_user = discord.fetch_user()
    with db.db_cursor() as cur:
        db_user = db.get_or_create_user(cur, discord_user.name)
        if not db_user['is_admin']:
            return "Admin user login required."
    worker.async_allocate()
    return "OK"


@app.route("/users")
@requires_authorization
def users():
    discord_user = discord.fetch_user()
    with db.db_cursor() as cur:
        db_user = db.get_or_create_user(cur, discord_user.name)
        if not db_user['is_admin']:
            return "Admin user login required."

        cur.execute("SELECT discord_username FROM users")
        user_rows = cur.fetchall()
        users = {}
        for row in user_rows:
            users[row['discord_username']] = db.get_or_create_user(cur, row['discord_username'])

    return render_template('users.html',
            discord_user = discord_user,
            db_user = db_user,
            users = users)


@app.route("/queue")
@requires_authorization
def queue():
    discord_user = discord.fetch_user()
    with db.db_cursor() as cur:
        db_user = db.get_or_create_user(cur, discord_user.name)
        if not db_user['is_admin']:
            return "Admin user login required."

        cur.execute(
            """
            SELECT ca.*
               , u.discord_username as u_discord_username
               , p.issue as p_issue
               , p.page as p_page
               , p.panel as p_panel 
            FROM (
                (select *, 'choice' as type from choices)
                UNION ALL
                (select *, NULL as preference, 'allocation' as type from allocations)
            ) AS ca
            LEFT JOIN users u ON ca.u = u.id
            LEFT JOIN panels p ON p.id = ca.panel
            ORDER BY ca.created;
            """)
        choices = cur.fetchall()
    return render_template('queue.html',
            discord_user=discord_user,
            db_user=db_user,
            choices=choices)

