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
    with db.db_cursor('STCRDBPW') as cur:
        return _allocate(cur)

def _allocate(cur):
    cur.execute(
        # SELECT...
        "SELECT c.* "
        ", u.id as uid"
        ", u.discord_username as discord_username"
        # the latest choices for each user...
        " FROM "
        "  (SELECT u, MAX(created) AS created FROM choices GROUP BY u) "
        "  AS latest_choices"
        " INNER JOIN choices c "
        "  ON c.u = latest_choices.u"
        "  AND c.created = latest_choices.created"
        # joined with the users table...
        " LEFT JOIN users u "
        "  ON u.id = c.u "
        # where the user's most recent STCR:4 allocation is not null...
        "  WHERE c.u NOT IN "
        "   (SELECT a.u FROM (SELECT u, MAX(created) AS created FROM allocations GROUP BY u) AS latest_allocations INNER JOIN allocations a ON latest_allocations.created = a.created LEFT JOIN panels p ON p.id = a.panel WHERE p.issue = 4)"
        # ordered by preference 1, then 2, then 3...
        " ORDER BY preference ASC"
    )
    pending = cur.fetchall()

    print(list(pending))
    allocated_users = set()
    debug = "no choices to process"
    for choice in pending:
        debug = "processing " + str(dict(choice))
        print(debug)
        if choice['panel'] is not None:
            # check if this panel is taken (res evals true if so)
            cur.execute(
                "SELECT u FROM allocations WHERE panel = (%s)",
                (choice['panel'],)
            )
            res = cur.fetchone()

            if res:
                debug = "panel already taken: " + str(dict(res))
                print(debug)
            else:
                debug = "allocating %s preference for %s" % (choice['preference'], choice['discord_username'])
                print(debug)
                cur.execute(
                    "INSERT INTO allocations (u, panel) VALUES ((%s), (%s))",
                    (choice['uid'], choice['panel'])
                )
                allocated_users.add(choice['uid'])

        elif choice['preference'] == 3 and choice['uid'] not in allocated_users:
            # reached third choice and still no unallocated panels;
            # no panels available; assign NULL to allocations table.
            debug = "no choices available for %s" % (choice['discord_username'])
            print(debug)

            cur.execute(
                "INSERT INTO allocations (u, panel) VALUES ((%s), NULL)",
                (choice['uid'], )
            )

    return debug
