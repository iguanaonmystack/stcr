from contextlib import contextmanager
import flask
import psycopg2
import psycopg2.extras
import os

@contextmanager
def db_cursor(env_pw=None):
    if env_pw:
        pw = os.getenv(env_pw)
    else:
        pw = flask.current_app.config['DB_PW']
    conn = psycopg2.connect('dbname=stcr user=stcr password=%s' % pw)
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        yield cur
        conn.commit()
    finally:
        cur.close()
        conn.close()

def get_or_create_user(cur, discord_username):
    db_user = None
    while db_user is None:
        cur.execute(
                'SELECT u.* '
                ', al.id as aid'
                ', al.created as acreated'
                ', pa.issue as a_issue'
                ', pa.page as a_page'
                ', pa.panel as a_panel'
                ' FROM users u '
                '  LEFT JOIN allocations al ON al.u = u.id'
                '  LEFT JOIN panels pa ON pa.id = al.panel AND pa.issue = 4 '
                ' WHERE discord_username = %s'
                ' ORDER BY acreated DESC'
                , (discord_username,))
        db_user = cur.fetchone()
        if db_user is None:
            db_user = cur.execute(
                'INSERT INTO users (discord_username, is_admin) VALUES (%s, %s)',
                (discord_username, False))
    return db_user

