import os
import sys

# CRITICAL: Force Playwright to use global path, not the frozen temp dir
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.join(os.getenv("LOCALAPPDATA"), "ms-playwright")

from flask import Flask, render_template, jsonify, request, redirect, url_for
from threads_bot.licensing import license_manager
from threads_bot import db as database
from threads_bot.config import load_config, save_config
from threads_bot.constants import CONTROL_FILE
import json
import subprocess
import sqlite3

from threads_bot.version import __version__
from threads_bot.updater import update_manager
from threads_bot.pods import fetch_cloud_pod, fetch_available_pods


def is_frozen():
    return getattr(sys, 'frozen', False)

if is_frozen():
    # If frozen, MEIPASS is where resources are bundled
    template_folder = os.path.join(sys._MEIPASS, 'templates')
    static_folder = os.path.join(sys._MEIPASS, 'static')
    app = Flask(__name__, template_folder=template_folder, static_folder=static_folder)
else:
    app = Flask(__name__)

# Inject version into all templates
@app.context_processor
def inject_version():
    return dict(version=__version__)

# Enable CORS manually
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

CONTROL_FILE = "bot_control.json"

# --- HELPERS ---
def set_bot_control(status):
    with open(CONTROL_FILE, "w") as f:
        json.dump({"status": status}, f)

def load_stats():
    if os.path.exists("stats.json"):
        with open("stats.json", "r") as f:
            return json.load(f)
    return {"likes": 0, "follows": 0}



# --- MIDDLEWARE ---
@app.before_request
def check_license():
    # List of endpoints accessible without license
    allowed_endpoints = ['activate_page', 'api_activate', 'static']
    if request.endpoint in allowed_endpoints:
        return

    # Check validity (light check against local file first, real check done by manager logic)
    if not license_manager.has_valid_license():
        return redirect(url_for('activate_page'))

# --- ROUTES ---



@app.route('/activate')
def activate_page():
    return render_template('activate.html')

@app.route('/api/activate', methods=['POST'])
def api_activate():
    data = request.json
    key = data.get('key')
    
    success, message = license_manager.validate_key(key)
    if success:
        license_manager.save_key(key)
        return jsonify({"status": "success"})
    else:
        return jsonify({"status": "error", "message": message})

@app.route('/api/check_update', methods=['GET'])
def check_update():
    """Endpoint to check if a new version exists."""
    info, error = update_manager.check_for_update()
    if info:
        return jsonify({"status": "success", "data": info})
    return jsonify({"status": "error", "message": error})

@app.route('/api/perform_update', methods=['POST'])
def perform_update():
    """
    Launches the external updater script and closes the app.
    """
    try:
        # Check if we are in git env (dev mode)
        if os.path.isdir('.git') and not is_frozen():
            print("[Updater] Git repo detected. Attempting git pull...")
            result = subprocess.run(['git', 'pull'], capture_output=True, text=True)
            if result.returncode == 0:
                print(f"[Updater] Update successful: {result.stdout}")
                return jsonify({"status": "success", "message": "Updated successfully! Restarting..."})
            else:
                return jsonify({"status": "error", "message": f"Git Pull Failed: {result.stderr}"})
        
        else:
            # PRODUCTION MODE: Launch independent updater script
            # First, fetch the URL again to be sure
            info, err = update_manager.check_for_update()
            if not info or not info.get("download_url"):
                 return jsonify({"status": "error", "message": "Could not retrieve download URL."})

            download_url = info["download_url"]
            print(f"[Updater] Launching external updater with URL: {download_url}")
            
            updater_executable = "Updater.exe" if is_frozen() else "updater_tool.py"
            
            # Windows-specific flag to open new window
            CREATE_NEW_CONSOLE = 0x00000010
            
            if is_frozen():
                # Launch EXE
                subprocess.Popen([updater_executable, download_url], creationflags=CREATE_NEW_CONSOLE, close_fds=True)
            else:
                 # Launch Python Script
                subprocess.Popen([sys.executable, updater_executable, download_url], creationflags=CREATE_NEW_CONSOLE, close_fds=True)
            
            # Kill current app gracefully-ish
            def kill_self():
                import time
                time.sleep(1)
                print("[Shutdown] Exiting application via os._exit(0)")
                os._exit(0)
            
            from threading import Thread
            Thread(target=kill_self).start()
            
            return jsonify({"status": "success", "message": "Updater launched. Closing..."})
            
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/api/shutdown', methods=['POST'])
def shutdown_app():
    """Explicitly shuts down the server."""
    def kill_self():
        import time
        time.sleep(1)
        print("[Shutdown] Manual shutdown requested.")
        os._exit(0)
    
    from threading import Thread
    Thread(target=kill_self).start()
    return jsonify({"status": "success", "message": "Shutting down..."})


@app.route('/')
def index():
    stats = load_stats()
    return render_template('dashboard.html', stats=stats)

@app.route('/api/leads', methods=['GET', 'POST'])
def api_leads():
    if request.method == 'POST':
        data = request.json
        username = data.get('username')
        if username:
            # Add to DB
            database.add_lead(username)
            # Optional: Log manual entry interaction?
            database.log_interaction(username, "Manual Add", "Added via Dashboard")
            return jsonify({"status": "success"})
        return jsonify({"status": "error", "error": "Missing username"}), 400

    conn = database.get_connection()
    # Convert row objects to dicts
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM leads ORDER BY last_interaction_date DESC LIMIT 100")
    columns = [column[0] for column in cursor.description]
    results = []
    for row in cursor.fetchall():
        results.append(dict(zip(columns, row)))
    conn.close()
    return jsonify(results)

@app.route('/api/leads/<username>')
def api_lead_details(username):
    data = database.get_lead_details(username)
    if data:
        lead, interactions = data
        return jsonify({"lead": lead, "interactions": interactions})
    return jsonify({"error": "Lead not found"}), 404

@app.route('/api/leads/<username>/status', methods=['POST'])
def api_update_status(username):
    status = request.json.get('status')
    if status:
        # Update Status
        database.update_lead_status(username, status)
        
        # Check for Trigger Actions
        if status == "Unfollowed":
            database.add_task('unfollow', username)
            
        return jsonify({"status": " success"})
    return jsonify({"error": "No status provided"}), 400

# --- CRM ROUTES Removed ---

@app.route('/api/config', methods=['GET', 'POST'])
def api_config():
    if request.method == 'POST':
        new_config = request.json
        # Load existing to preserve other fields if needed, but here we overwrite strictly what's passed + defaults
        current = load_config()
        current.update(new_config)
        save_config(current)
        return jsonify({"status": "success"})
    return jsonify(load_config())

@app.route('/api/start_bot', methods=['POST'])
def start_bot():
    try:
        data = request.json or {}
        mode = data.get('mode', 'keyword') # Default to keyword if not specified

        # 1. Set control status to running
        set_bot_control("running")
        
        # 2. Launch Process with Mode Argument
        if is_frozen():
             cmd = f"Bot.exe {mode}"
        else:
             cmd = f"python bot.py {mode}"

        if os.name == 'nt':
            subprocess.Popen(["start", "cmd", "/k", cmd], shell=True)
        else:
            subprocess.Popen(["open", "-a", "Terminal", cmd])
            
        return jsonify({"status": "started", "mode": mode})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/api/stop_bot', methods=['POST'])
def stop_bot():
    try:
        # Set control status to stopping
        set_bot_control("stopping")
        return jsonify({"status": "stopping"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/api/pod/list', methods=['GET'])
def list_pods():
    """Returns list of available pods."""
    pods = fetch_available_pods()
    return jsonify({"status": "success", "pods": pods})

@app.route('/api/pod/sync', methods=['POST'])
def sync_pod():
    """Fetches the latest pod list for a specific pod."""
    try:
        data = request.json or {}
        pod_id = data.get('pod_id', 'default')
        
        members = fetch_cloud_pod(pod_id)
        if members is None:
            return jsonify({"status": "error", "message": "Failed to fetch from cloud."})
        
        # Update Config
        cfg = load_config()
        cfg['pod_members'] = members
        # Also save which pod is active
        cfg['active_pod_id'] = pod_id 
        save_config(cfg)
        
        return jsonify({"status": "success", "count": len(members), "members": members, "pod_id": pod_id})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

def ensure_playwright_browsers():
    """
    Checks and installs Playwright browsers synchronously.
    """
    print("[Startup] Checking Playwright Browsers...")
    try:
        # Check if browser dir exists to avoid unnecessary import load if possible?
        # But we need 'playwright install' logic to be sure version matches.
        
        if getattr(sys, 'frozen', False):
            print(f"[Startup] Frozen mode. Browser Path overrides to: {os.environ.get('PLAYWRIGHT_BROWSERS_PATH')}")
            from playwright.__main__ import main
            old_argv = sys.argv
            sys.argv = ["playwright", "install", "chromium"]
            print("[Startup] Ensuring Chromium is installed (this may take a moment)...")
            try:
                main()
            except SystemExit:
                pass
            sys.argv = old_argv
            print("[Startup] Browser check complete.")
        else:
            # Dev mode
            subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"])
    except Exception as e:
        print(f"[Startup] Warning: Could not run playwright install: {e}")

if __name__ == '__main__':
    # Run dependency check SYNCHRONOUSLY before starting server
    ensure_playwright_browsers()

    print("Starting Dashboard on http://127.0.0.1:5000")
    
    # Auto-open browser (only on first launch, not reloads)
    from threading import Timer
    import webbrowser
    def open_browser():
        webbrowser.open_new("http://127.0.0.1:5000")
        
    if not os.environ.get("WERKZEUG_RUN_MAIN"):
        Timer(1.5, open_browser).start()

    app.run(debug=True, port=5000)
