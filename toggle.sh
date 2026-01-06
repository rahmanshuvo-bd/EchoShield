#!/system/bin/sh
# EchoShield Toggle v1.7 - Optimized for Wait-Locking

PKG="$1"    # Package Name
MODE="$2"   # on/off
UID_VAL="$3" # Single UID passed from UI

# 1. Fallback if UID wasn't passed (Manual CLI usage)
if [ -z "$UID_VAL" ]; then
    UID_VAL=$(awk -v p="$PKG" '$1==p {print $2}' /data/system/packages.list)
fi

[ -z "$UID_VAL" ] && { echo "❌ UID not found for $PKG"; exit 1; }

# 2. Execute Rules with -w (Wait for xtables lock)
# This is critical to prevent "Another app is currently holding the xtables lock"
if [ "$MODE" = "on" ]; then
    # Check if rule exists first (-C) to avoid duplicates
    iptables -w -C ECHOSHIELD -m owner --uid-owner "$UID_VAL" -j REJECT >/dev/null 2>&1 || \
    iptables -w -A ECHOSHIELD -m owner --uid-owner "$UID_VAL" -j REJECT
    
    ip6tables -w -C ECHOSHIELD -m owner --uid-owner "$UID_VAL" -j REJECT >/dev/null 2>&1 || \
    ip6tables -w -A ECHOSHIELD -m owner --uid-owner "$UID_VAL" -j REJECT
    
    echo "🛡️ Shielded: $PKG"
else
    iptables -w -D ECHOSHIELD -m owner --uid-owner "$UID_VAL" -j REJECT >/dev/null 2>&1
    ip6tables -w -D ECHOSHIELD -m owner --uid-owner "$UID_VAL" -j REJECT >/dev/null 2>&1
    echo "🔓 Unblocked: $PKG"
fi

# 3. Connection Termination
if [ "$MODE" = "on" ]; then
    case "$PKG" in
        android|com.android.*|com.nothing.*|com.google.android.gms*)
            pkill -9 -f "$PKG" >/dev/null 2>&1
            ;;
        *)
            am force-stop "$PKG" >/dev/null 2>&1
            ;;
    esac
fi
