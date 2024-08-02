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
        # SELECT...
        "SELECT c.* "
        ", u.id as uid"
        ", u.discord_username as discord_username"
        # the latest choices for each user...
        " FROM "
        "  (SELECT user, MAX(created) AS created FROM choices GROUP BY user) "
        "  AS latest_choices"
        " INNER JOIN choices c "
        "  ON c.user = latest_choices.user"
        "  AND c.created = latest_choices.created"
        # joined with the users table...
        " LEFT JOIN users u "
        "  ON u.id = c.user "
        # where the user doesn't have any STC:R 4 allocations yet...
        "  WHERE c.user NOT IN "
        "   (SELECT user FROM allocations a LEFT JOIN panels p on p.id = a.panel WHERE p.issue = 4)"
        # ordered by preference 1, then 2, then 3...
        " ORDER BY preference ASC"
    ).fetchall()

    print(list(pending))
    allocated_users = set()
    for choice in pending:
        debug = "processing " + str(dict(choice))
        print(debug)
        if choice['panel'] is not None:
            # check if this panel is taken (res evals true if so)
            res = conn.execute(
                "SELECT user FROM allocations WHERE panel = (?)",
                (choice['panel'],)
            ).fetchone()

            if res:
                debug = "panel already taken: " + str(dict(res))
                print(debug)
            else:
                debug = "allocating %s preference for %s" % (choice['preference'], choice['discord_username'])
                print(debug)
                conn.execute(
                    "INSERT INTO allocations (user, panel) VALUES ((?), (?))",
                    (choice['uid'], choice['panel'])
                )
                allocated_users.add(choice['uid'])

        elif choice['preference'] == 3 and choice['uid'] not in allocated_users:
            # reached third choice and still no unallocated panels;
            # no panels available; assign NULL to allocations table.
            debug = "no choices available for %s" % (choice['discord_username'])
            print(debug)

            conn.execute(
                "INSERT INTO allocations (user, panel) VALUES ((?), NULL)",
                (choice['uid'], )
            )

    conn.commit()
    return debug
