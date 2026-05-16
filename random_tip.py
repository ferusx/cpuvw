

import random

def load_random_tip(file_path):

    try:
        with open(file_path, "r", encoding="utf-8") as file:
            content = file.read()

        tips = [
            tip.strip()
            for tip in content.split("\n\n")
            if tip.strip()
        ]

        if not tips:
            return None

        return random.choice(tips)

    except Exception:
        return None

def random_tip():
    return load_random_tip("data/tips.txt")

def random_idle_tip():
    return load_random_tip("data/idle_tips.txt")