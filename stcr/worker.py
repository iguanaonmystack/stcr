import os

import redis
import rq

from . import db

redis_url = os.getenv('STCR_REDIS_URL', 'redis://localhost:6379')

redis_conn = redis.from_url(redis_url)

# each queue processes sequentially, ie no concurrency within queues.
q = rq.Queue('stcr', connection=redis_conn)

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
        allocate_id = None
        for use in ['first', 'second', 'third']:
            choice_id = choice[use+'_choice']
            if not choice_id:
                continue
            res = conn.execute(
                "SELECT id FROM users WHERE confirmed_choice = (?)",
                (choice_id,)
            ).fetchone()
            if not res:
                # if no users have this as choice, allocate it
                allocate = use
                allocate_id = choice_id
                break
                
        if not allocate:
            debug = "no choices available for %s" % (choice['discord_username'])

            conn.execute(
                "UPDATE users SET confirmed_choice = NULL, no_choices_available = TRUE WHERE id = (?)",
                (choice['uid'],)
            )
        else:
            debug = "allocating %s choice for %s" % (allocate, choice['discord_username'])
            conn.execute(
                "UPDATE users SET confirmed_choice = (?), no_choices_available = FALSE WHERE id = (?)",
                (allocate_id, choice['uid']))

        conn.execute(
            "UPDATE choices SET status = 'PROCESSED', confirmed_choice = (?) WHERE id = (?)",
            (allocate_id, choice['id']))

        conn.commit()
        return debug
