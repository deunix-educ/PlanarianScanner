#!/bin/bash
# Fait fonctionner <nom>.local (mDNS/Avahi) sur Raspberry Pi OS / Debian Trixie.
# usage: sudo hostname.sh [nom]   (défaut: scanner)
#        hostname.sh --check [nom]
# Causes habituelles d'échec traitées ici :
#  - hostname réel différent de scanner / /etc/hosts 127.0.1.1 incohérent
#  - cloud-init qui réécrit hostname et /etc/hosts au reboot
#  - avahi/libnss-mdns absents, nsswitch sans mdns
#  - systemd-resolved qui entre en conflit avec avahi sur le port 5353
#  - collision de nom (scanner-2.local) : ancien hôte encore annoncé
#  - interface VPN wg0 qui publie des adresses mDNS inutilisables
#  - Wi-Fi en économie d'énergie : paquets multicast perdus
NAME="scanner"
CHECK=0
for a in "$@"; do
    case "$a" in --check) CHECK=1 ;; *) NAME="$a" ;; esac
done

check() {
    local rc=0
    echo "== hostname           : $(hostname) (attendu: $NAME)"; [ "$(hostname)" = "$NAME" ] || rc=1
    echo "== avahi-daemon       : $(systemctl is-active avahi-daemon)"; systemctl is-active -q avahi-daemon || rc=1
    echo "== /etc/hosts 127.0.1.1: $(grep '^127.0.1.1' /etc/hosts)"
    echo "== nsswitch hosts     : $(grep '^hosts:' /etc/nsswitch.conf)"
    echo "== avahi publie       : $(avahi-resolve -n "$NAME.local" 2>&1 | head -1)"
    echo "== getent             : $(getent hosts "$NAME.local" | head -1)"
    getent hosts "$NAME.local" >/dev/null || rc=1
    if journalctl -u avahi-daemon -b --no-pager 2>/dev/null | grep -qi "collision\|already in use"; then
        echo "!! collision de nom détectée dans le journal avahi (un autre hôte annonce '$NAME')"; rc=1
    fi
    echo "== IP                 : $(hostname -I)"
    [ $rc = 0 ] && echo "OK : http://$NAME.local" || echo "ECHEC : voir ci-dessus"
    return $rc
}

[ $CHECK = 1 ] && { check; exit $?; }
[ "$(id -u)" = 0 ] || { echo "lancer avec sudo"; exit 1; }
set -e

echo "== paquets"
apt-get install -y avahi-daemon avahi-utils libnss-mdns

echo "== hostname = $NAME"
hostnamectl set-hostname "$NAME"
if grep -q '^127.0.1.1' /etc/hosts; then
    sed -i "s/^127\.0\.1\.1.*/127.0.1.1\t$NAME/" /etc/hosts
else
    printf '127.0.1.1\t%s\n' "$NAME" >> /etc/hosts
fi
if [ -d /etc/cloud ]; then
    mkdir -p /etc/cloud/cloud.cfg.d
    printf 'preserve_hostname: true\nmanage_etc_hosts: false\n' > /etc/cloud/cloud.cfg.d/99-scanner-hostname.cfg
fi

echo "== avahi-daemon.conf"
CONF=/etc/avahi/avahi-daemon.conf
setkey() {  # setkey clé valeur  (section [server])
    if grep -qE "^#?$1=" "$CONF"; then sed -i -E "s|^#?$1=.*|$1=$2|" "$CONF"
    else sed -i "/^\[server\]/a $1=$2" "$CONF"; fi
}
setkey host-name "$NAME"
setkey domain-name local
setkey use-ipv4 yes
setkey deny-interfaces "wg0,docker0"
# la résolution reste fiable même si l'IPv6 link-local est capricieux côté client
setkey publish-aaaa-on-ipv4 no

echo "== nsswitch"
if ! grep -q '^hosts:.*mdns' /etc/nsswitch.conf; then
    sed -i -E 's/^(hosts:.*)files/\1files mdns4_minimal [NOTFOUND=return]/' /etc/nsswitch.conf
fi

echo "== conflit systemd-resolved"
if systemctl is-active -q systemd-resolved; then
    mkdir -p /etc/systemd/resolved.conf.d
    printf '[Resolve]\nMulticastDNS=no\n' > /etc/systemd/resolved.conf.d/10-no-mdns.conf
    systemctl restart systemd-resolved
fi

echo "== annonce du service web"
cat > /etc/avahi/services/scanner-http.service <<XML
<?xml version="1.0" standalone='no'?>
<!DOCTYPE service-group SYSTEM "avahi-service.dtd">
<service-group>
  <name replace-wildcards="yes">PlanarianScanner sur %h</name>
  <service><type>_http._tcp</type><port>80</port></service>
  <service><type>_ssh._tcp</type><port>22</port></service>
</service-group>
XML

echo "== Wi-Fi : pas d'économie d'énergie (sinon le multicast est perdu)"
if command -v nmcli >/dev/null; then
    nmcli -t -f NAME,TYPE connection show | awk -F: '$2 ~ /wireless/ {print $1}' | while read -r c; do
        nmcli connection modify "$c" 802-11-wireless.powersave 2 || true
    done
fi

systemctl enable avahi-daemon
systemctl restart avahi-daemon
sleep 3
check
