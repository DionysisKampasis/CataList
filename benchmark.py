import time
from datetime import datetime


def timer_function(func):
    def wrapper(*args, **kwargs):
        start = time.time()
        res = func(*args, **kwargs)
        end = time.time()
        duration = end - start
        message = f"[TIMING] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {func.__name__} took {duration:.4f} sec."

        print(message)

        with open("timing_log.txt", "a") as f:
            f.write(message + "\n")

        return res

    return wrapper
