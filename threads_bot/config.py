import json
import os
from .constants import CONFIG_FILE

DEFAULT_CONFIG = {
    "keywords": ["tech"],
    "negative_keywords": [],
    "max_likes": 50,
    "max_follows": 20,
    "speed_multiplier": 1.0,
    "probabilities": {
        "like_range": [0.4, 0.8],
        "follow_range": [0.1, 0.3]
    },
    "delays": {"min": 2, "max": 5},
    "target_accounts": [],
    "comment_templates": [],
    "comment_probability": 0.0,
    "enable_like": True,
    "enable_follow": True,
    "enable_comment": True
}

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading config: {e}")
    return DEFAULT_CONFIG.copy()

def save_config(config):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=4)
    except Exception as e:
        print(f"Error saving config: {e}")
