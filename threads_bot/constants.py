THREADS_URL = "https://www.threads.net"
USER_DATA_DIR = "user_data"
CONFIG_FILE = "config.json"
STATS_FILE = "stats.json"
CONTROL_FILE = "bot_control.json"
DB_FILE = "crm.db"

# Selectors
SELECTORS = {
    "login_user": 'input[name="username"]',
    "login_pass": 'input[name="password"]',
    "login_btn": 'button[type="submit"]',
    "article": 'div[role="article"]',
    "like_svg": 'svg[aria-label="Like"]',
    "reply_svg": 'svg[aria-label="Reply"]',
    "post_btn": 'div[text()="Post"]',
    "follow_btn": '//button[normalize-space()="Follow"]',
}
