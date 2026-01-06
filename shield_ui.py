import os
import sys
import subprocess
import re
import json
import io
from datetime import datetime
from flask import Flask, render_template, jsonify, request, send_file

# --- Environment Bootstrapping ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USER_CONFIG = os.path.join(BASE_DIR, "user_essentials.json")
LOG_PATH = os.path.join(BASE_DIR, "logs/service.log")

app = Flask(__name__, template_folder='templates')

# --- Logic Constants ---
AUTO_UNBLOCK = {
    "android", "com.android.systemui", "com.android.settings", "com.android.shell",
    "com.android.vending", "com.android.providers.settings", "com.android.providers.telephony",
    "com.android.phone", "com.android.nfc", "com.android.bluetooth", "com.goodix.fingerprint.setting",
    "com.mediatek", "com.mediatek.ims", "com.mediatek.telephony", "com.mediatek.capctrl.service",
    "com.mediatek.datachannel.service", "com.nothing.appservice", "com.nothing.launcher",
    "com.nothing.applocker", "com.nothing.proxy", "com.google.android.gms", "com.google.android.gsf",
    "ai.x.grok", "com.deepseek.chat", "com.openai.chatgpt", "com.termux", "com.whatsapp",
    "com.google.android.apps.messaging", "com.android.chrome"
}

JUNK_PATTERNS = ['.overlay', 'auto_generated_rro', '.resources', 'com.mediatek.', 'android.overlay', 'com.android.internal']

# --- Helper Functions ---

def run_root(cmd):
    """Executes command as root via su."""
    tmp = "/data/local/tmp/echo_out.txt"
    subprocess.run(['su', '-c', f"PATH=/system/bin:/system/xbin:$PATH {cmd} > {tmp} 2>&1"], shell=False)
    res = ""
    if os.path.exists(tmp):
        with open(tmp, 'r') as f:
            res = f.read()
        os.remove(tmp)
    return res

def get_user_essentials():
    if os.path.exists(USER_CONFIG):
        try:
            with open(USER_CONFIG, 'r') as f:
                data = json.load(f)
                return set(data) if data else set()
        except: return set()
    return set()

def get_apps():
    """Aggregates app data with UID 1000-1100 filtering."""
    ipt = run_root("iptables -w -L ECHOSHIELD -n")
    blocked_uids = set(re.findall(r'(?:match|UID match)\s+(\d+)', ipt))
    user_essentials = get_user_essentials()

    raw_3p = run_root("pm list packages --user 0 -3 -U")
    raw_sys = run_root("pm list packages --user 0 -s -U")

    apps = []
    def parse(data, is_sys):
        for line in data.splitlines():
            if "package:" not in line or "uid:" not in line: 
                continue
            try:
                pkg = line.split("package:")[1].split()[0]
                uid_str = line.split("uid:")[1].strip()
                uid = int(uid_str)

                # Ignore system-critical UID range (1000-1100)
                if 1000 <= uid <= 1100:
                    continue

                is_essential = (pkg.lower() in AUTO_UNBLOCK or pkg in user_essentials)
                if any(pat in pkg for pat in JUNK_PATTERNS) and not is_essential:
                    continue

                apps.append({
                    "pkg": pkg,
                    "uid": uid_str,
                    "is_system": is_sys,
                    "is_essential": is_essential,
                    "blocked": uid_str in blocked_uids
                })
            except (IndexError, ValueError):
                continue

    parse(raw_3p, False)
    parse(raw_sys, True)
    return sorted(apps, key=lambda x: (not x['is_essential'], x['pkg']))

# --- Routes ---

@app.route('/')
def index():
    all_apps = get_apps()
    stats = {
        "total": len(all_apps),
        "blocked": len([a for a in all_apps if a['blocked']]),
        "unblocked": len([a for a in all_apps if not a['blocked']])
    }
    return render_template('index.html', apps=all_apps, stats=stats)

@app.route('/toggle')
def toggle():
    pkg = request.args.get('pkg')
    mode = request.args.get('mode') # 'on' to block, 'off' to unblock
    uid = request.args.get('uid')

    if mode == 'on':
        cmd = (f"iptables -w -A ECHOSHIELD -m owner --uid-owner {uid} -j REJECT ; "
               f"ip6tables -w -A ECHOSHIELD -m owner --uid-owner {uid} -j REJECT ; "
               f"am force-stop {pkg}")
    else:
        cmd = (f"iptables -w -D ECHOSHIELD -m owner --uid-owner {uid} -j REJECT ; "
               f"ip6tables -w -D ECHOSHIELD -m owner --uid-owner {uid} -j REJECT")

    run_root(cmd)
    return jsonify(success=True)

@app.route('/apply-defaults')
def apply_defaults():
    mode = request.args.get('mode')
    if mode == 'flush':
        run_root("iptables -w -F ECHOSHIELD; ip6tables -w -F ECHOSHIELD")
        return jsonify(success=True, message="Firewall Flushed")

    apps = get_apps()
    cmds = [
        "iptables -w -F ECHOSHIELD", 
        "ip6tables -w -F ECHOSHIELD", 
        f"echo '[$(date)] --- Smart Policy Triggered ---' >> {LOG_PATH}"
    ]

    for a in apps:
        if a['is_essential']:
            continue
        cmds.append(f"iptables -w -A ECHOSHIELD -m owner --uid-owner {a['uid']} -j REJECT")
        cmds.append(f"ip6tables -w -A ECHOSHIELD -m owner --uid-owner {a['uid']} -j REJECT")
        cmds.append(f"am force-stop {a['pkg']} >/dev/null 2>&1")

    run_root(" ; ".join(cmds))
    return jsonify(success=True)

@app.route('/toggle-all')
def toggle_all():
    mode = request.args.get('mode')
    apps = get_apps()
    cmds = []
    
    if mode == 'block':
        for a in apps:
            if not a['is_essential']:
                cmds.append(f"iptables -w -A ECHOSHIELD -m owner --uid-owner {a['uid']} -j REJECT")
                cmds.append(f"ip6tables -w -A ECHOSHIELD -m owner --uid-owner {a['uid']} -j REJECT")
                cmds.append(f"am force-stop {a['pkg']} >/dev/null 2>&1")
    
    if cmds:
        run_root(" ; ".join(cmds))
    return jsonify(success=True)

@app.route('/toggle-essential')
def toggle_essential():
    pkg = request.args.get('pkg')
    state = request.args.get('state') == 'true'
    essentials = get_user_essentials()
    if state: essentials.add(pkg)
    else: essentials.discard(pkg)
    with open(USER_CONFIG, 'w') as f:
        json.dump(list(essentials), f)
    return jsonify(success=True)

@app.route('/download-config')
def download_config():
    if os.path.exists(USER_CONFIG):
        return send_file(USER_CONFIG, as_attachment=True)
    return jsonify(success=False, error="No config found")

if __name__ == '__main__':
    # Ensure log directory exists
    log_dir = os.path.dirname(LOG_PATH)
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

if __name__ == '__main__':
    # Initialize chains on start
    for tool in ["iptables", "ip6tables"]:
        run_root(f"{tool} -N ECHOSHIELD")
        check = run_root(f"{tool} -S OUTPUT")
        if "-j ECHOSHIELD" not in check:
            run_root(f"{tool} -I OUTPUT -j ECHOSHIELD")
    
    app.run(host='0.0.0.0', port=5000, debug=False)

