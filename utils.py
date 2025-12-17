import time
def is_spam(sender: str, last_used: dict) -> bool:
    if sender in last_used and time.time() - last_used[sender] < 25:
        return True
    return False

def update_last_used(sender: str, last_used: dict):
    last_used[sender] = time.time()
