# run with venv/bin/python -m scripts.redisworker

from rq import Worker, Queue, Connection

from stcr.worker import q

if __name__ == "__main__":
    worker = Worker([q], connection=q.connection)
    worker.work()

