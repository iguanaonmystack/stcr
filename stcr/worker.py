import os

import redis
import rq

from . import db

redis_url = os.getenv('STCR_REDIS_URL', 'redis://localhost:6379')

redis_conn = redis.from_url(redis_url)
q = rq.Queue(connection=redis_conn)

def async_allocate():
    q.enqueue_call(func=allocate, args=(), result_ttl=5000)

def allocate():
    conn = db.get_db_connection()
    
    pending = conn.execute(
        "SELECT c.* "
        ", u.id as uid"
        ", u.discord_username as discord_username"
        " FROM choices c"
        " LEFT JOIN users u ON u.id = c.from_user"
        " WHERE c.status == 'PENDING'"
        " ORDER BY created"
    ).fetchall()

    for choice in pending:
        allocate = None
        for use in ['first', 'second', 'third']:
            res = conn.execute(
                "SELECT id FROM users WHERE confirmed_choice = (?)",
                (choice[use+'_choice'],)).fetchone()
            if not res:
                # if no users have this as choice, allocate it
                allocate = use
                break
                
        print("allocate %s choice for %s", allocate, choice['discord_username'])
        conn.execute(
            "UPDATE users SET confirmed_choice = (?) WHERE id = (?)",
            (choice[allocate+'_choice'], choice['uid']))
        conn.execute(
            "UPDATE choices SET status = 'PROCESSED', confirmed_choice = (?) WHERE id = (?)",
            (choice[allocate+'_choice'], choice['id']))

        conn.commit()
