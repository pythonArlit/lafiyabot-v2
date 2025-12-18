# utils.py
import time

SPAM_DELAY = 25  # secondes

def is_spam(sender: str, last_used: dict) -> bool:
    now = time.time()
    last = last_used.get(sender, 0)
    return (now - last) < SPAM_DELAY

def update_last_used(sender: str, last_used: dict) -> None:
    last_used[sender] = time.time()
