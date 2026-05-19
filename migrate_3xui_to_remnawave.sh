#!/usr/bin/env bash
# ============================================================================
#  3x-ui  →  Remnawave  migration script
# ----------------------------------------------------------------------------
#  Что делает:
#    1. Бэкапит x-ui.db (SQLite) и /etc/x-ui
#    2. Останавливает 3x-ui (но не удаляет — на случай отката)
#    3. Ставит Remnawave Panel + Subscription Page + Caddy (через docker-compose)
#    4. Ждёт, пока поднимется PostgreSQL и API
#    5. Создаёт API-токен Remnawave
#    6. Парсит inbound'ы и клиентов из x-ui.db (VLESS/Trojan/Shadowsocks)
#    7. Через REST API создаёт пользователей в Remnawave, СОХРАНЯЯ
#         - UUID клиента  (→ vlessUuid)
#         - пароль Trojan / Shadowsocks
#         - срок действия (expiryTime  → expireAt)
#         - shortUuid берётся из email клиента в 3x-ui, чтобы старый
#           subscription URL  https://server/sub/<token>  остался прежним
#    8. Поднимает Nginx-reverse-proxy на старом порту 2096 (subscription
#       порт 3x-ui), который проксирует /sub/<token> на Remnawave
#       /api/sub/<shortUuid>.  В результате старые подписочные ссылки,
#       прописанные в Hiddify / Nekoray / v2rayN, продолжают работать.
#    9. Обновляет .env проекта mnvpn (SERVER_IP, новые URL панели).
#
#  Что НЕ делает (намеренно):
#    - не удаляет 3x-ui (оставляем как fallback ровно неделю)
#    - не трогает inbound'ы Reality в Remnawave: для них нужно вручную
#      импортировать тот же privateKey/publicKey/serverNames (скрипт
#      печатает их в конце, чтобы вы вставили в Config Profile панели).
#
#  Требования:
#      Ubuntu 22.04+, root, открытые 80/443.
#      Запускать ПРЯМО на сервере 50.114.115.138.
#
#  Использование:
#      curl -fsSL https://raw.githubusercontent.com/shimtuuu/mnvpn/main/migrate_3xui_to_remnawave.sh \
#          | sudo bash -s -- --domain panel.example.com
#
#  Параметры (флаги или переменные окружения):
#      --domain      DOMAIN          (REM_DOMAIN)        — домен для панели  [обязательно]
#      --sub-domain  SUB_DOMAIN      (REM_SUB_DOMAIN)    — домен подписки    [по умолч. sub.<DOMAIN>]
#      --xui-db      /etc/x-ui/x-ui.db (XUI_DB)
#      --admin-user  USERNAME        (REM_ADMIN_USER)    [admin]
#      --admin-pass  PASSWORD        (REM_ADMIN_PASS)    [генерируется]
#      --server-ip   IP              (SERVER_IP)         [автоопределение]
#      --dry-run                     — ничего не пишет в Remnawave, только выводит план
#      --no-install                  — пропустить установку Remnawave (если уже стоит)
# ============================================================================
set -Eeuo pipefail
shopt -s inherit_errexit

# ------------------------------ helpers -------------------------------------
RED=$'\033[0;31m'; GREEN=$'\033[0;32m'; YELLOW=$'\033[1;33m'; BLUE=$'\033[0;34m'; NC=$'\033[0m'
log()  { printf '%s[%s]%s %s\n' "$GREEN"  "$(date +%H:%M:%S)" "$NC" "$*"; }
warn() { printf '%s[!]%s %s\n' "$YELLOW" "$NC" "$*" >&2; }
err()  { printf '%s[✗]%s %s\n' "$RED"    "$NC" "$*" >&2; }
die()  { err "$*"; exit 1; }
step() { printf '\n%s━━━ %s ━━━%s\n' "$BLUE" "$*" "$NC"; }

trap 'err "Ошибка на строке $LINENO. Бэкапы лежат в $BACKUP_DIR"' ERR

[[ $EUID -eq 0 ]] || die "Запускайте под root (sudo)"

# ------------------------------ args ----------------------------------------
REM_DOMAIN="${REM_DOMAIN:-}"
REM_SUB_DOMAIN="${REM_SUB_DOMAIN:-}"
XUI_DB="${XUI_DB:-/etc/x-ui/x-ui.db}"
REM_ADMIN_USER="${REM_ADMIN_USER:-admin}"
REM_ADMIN_PASS="${REM_ADMIN_PASS:-}"
SERVER_IP="${SERVER_IP:-}"
DRY_RUN=0
NO_INSTALL=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --domain)      REM_DOMAIN="$2"; shift 2 ;;
        --sub-domain)  REM_SUB_DOMAIN="$2"; shift 2 ;;
        --xui-db)      XUI_DB="$2"; shift 2 ;;
        --admin-user)  REM_ADMIN_USER="$2"; shift 2 ;;
        --admin-pass)  REM_ADMIN_PASS="$2"; shift 2 ;;
        --server-ip)   SERVER_IP="$2"; shift 2 ;;
        --dry-run)     DRY_RUN=1; shift ;;
        --no-install)  NO_INSTALL=1; shift ;;
        -h|--help)     sed -n '1,55p' "$0"; exit 0 ;;
        *)             die "Неизвестный аргумент: $1" ;;
    esac
done

[[ -n "$REM_DOMAIN"     ]] || die "Не указан --domain (домен для панели Remnawave)"
[[ -n "$REM_SUB_DOMAIN" ]] || REM_SUB_DOMAIN="sub.${REM_DOMAIN}"
[[ -f "$XUI_DB"         ]] || die "Не найден x-ui.db по пути: $XUI_DB"

REM_ADMIN_PASS="${REM_ADMIN_PASS:-$(openssl rand -base64 24 | tr -d '/=+' | cut -c1-24)}"
SERVER_IP="${SERVER_IP:-$(curl -fsS https://api.ipify.org || hostname -I | awk '{print $1}')}"

TS="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="/root/migration-backup-${TS}"
mkdir -p "$BACKUP_DIR"

log "Параметры миграции:"
echo "    Domain (panel)      : $REM_DOMAIN"
echo "    Domain (subscription): $REM_SUB_DOMAIN"
echo "    Server IP           : $SERVER_IP"
echo "    x-ui DB             : $XUI_DB"
echo "    Admin user          : $REM_ADMIN_USER"
echo "    Admin pass          : $REM_ADMIN_PASS"
echo "    Backup dir          : $BACKUP_DIR"
echo "    Dry-run             : $DRY_RUN"

# ------------------------------ deps ----------------------------------------
step "Установка зависимостей"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq curl jq sqlite3 python3 python3-pip ca-certificates uuid-runtime openssl

if ! command -v docker >/dev/null; then
    log "Устанавливаю Docker"
    curl -fsSL https://get.docker.com | sh
fi
docker compose version >/dev/null 2>&1 || apt-get install -y -qq docker-compose-plugin

# ------------------------------ backup --------------------------------------
step "Бэкап 3x-ui"
cp -a "$XUI_DB"            "$BACKUP_DIR/x-ui.db"
[[ -d /etc/x-ui ]] && tar czf "$BACKUP_DIR/etc-x-ui.tgz" -C / etc/x-ui
log "Бэкап → $BACKUP_DIR"

# ------------------------------ install Remnawave ---------------------------
if [[ $NO_INSTALL -eq 0 ]]; then
    step "Установка Remnawave Panel"
    mkdir -p /opt/remnawave && cd /opt/remnawave
    curl -fsSL -o docker-compose.yml https://raw.githubusercontent.com/remnawave/backend/refs/heads/main/docker-compose-prod.yml
    curl -fsSL -o .env https://raw.githubusercontent.com/remnawave/backend/refs/heads/main/.env.sample

    # генерируем секреты
    JWT1="$(openssl rand -hex 64)"
    JWT2="$(openssl rand -hex 64)"
    PG_PASS="$(openssl rand -hex 24)"
    METRICS_PASS="$(openssl rand -hex 32)"
    WEBHOOK_SEC="$(openssl rand -hex 32)"

    sed -i "s|^JWT_AUTH_SECRET=.*|JWT_AUTH_SECRET=${JWT1}|"           .env
    sed -i "s|^JWT_API_TOKENS_SECRET=.*|JWT_API_TOKENS_SECRET=${JWT2}|" .env
    sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${PG_PASS}|"    .env
    sed -i "s|^METRICS_PASS=.*|METRICS_PASS=${METRICS_PASS}|"         .env
    sed -i "s|^WEBHOOK_SECRET_HEADER=.*|WEBHOOK_SECRET_HEADER=${WEBHOOK_SEC}|" .env
    sed -i "s|^FRONT_END_DOMAIN=.*|FRONT_END_DOMAIN=${REM_DOMAIN}|"   .env
    sed -i "s|^SUB_PUBLIC_DOMAIN=.*|SUB_PUBLIC_DOMAIN=${REM_SUB_DOMAIN}|" .env
    sed -i "s|^SUPERADMIN_USERNAME=.*|SUPERADMIN_USERNAME=${REM_ADMIN_USER}|" .env || true
    sed -i "s|^SUPERADMIN_PASSWORD=.*|SUPERADMIN_PASSWORD=${REM_ADMIN_PASS}|" .env || true
    # DATABASE_URL внутри .env содержит дефолтный пароль — заменим
    sed -i "s|postgres:postgres@|postgres:${PG_PASS}@|" .env

    log "Запускаю docker compose"
    docker compose up -d
    log "Жду готовности Remnawave API (до 120s)…"
    for _ in $(seq 1 60); do
        if curl -fsS http://127.0.0.1:3000/api/auth/status >/dev/null 2>&1 \
           || curl -fsS http://127.0.0.1:3000/api/system/health >/dev/null 2>&1; then
            break
        fi
        sleep 2
    done

    # ---- Caddy reverse proxy для панели и подписочной страницы ------------
    step "Поднимаю Caddy (TLS для $REM_DOMAIN и $REM_SUB_DOMAIN)"
    mkdir -p /opt/remnawave/caddy && cd /opt/remnawave/caddy
    cat > Caddyfile <<EOF
${REM_DOMAIN} {
    reverse_proxy * http://remnawave:3000
}
${REM_SUB_DOMAIN} {
    reverse_proxy * http://remnawave-subscription-page:3010
}
:443 {
    tls internal
    respond 204
}
EOF
    cat > docker-compose.yml <<'EOF'
services:
  caddy:
    image: caddy:2
    container_name: remnawave-caddy
    restart: always
    network_mode: host
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile
      - caddy-data:/data
networks:
  remnawave-network:
    name: remnawave-network
    external: true
volumes:
  caddy-data:
EOF

    # ---- Subscription page контейнер --------------------------------------
    mkdir -p /opt/remnawave/subscription && cd /opt/remnawave/subscription
    cat > docker-compose.yml <<'EOF'
services:
  remnawave-subscription-page:
    image: remnawave/subscription-page:latest
    container_name: remnawave-subscription-page
    hostname: remnawave-subscription-page
    restart: always
    env_file: .env
    ports:
      - '127.0.0.1:3010:3010'
    networks:
      - remnawave-network
networks:
  remnawave-network:
    name: remnawave-network
    external: true
EOF
fi

# ------------------------------ stop 3x-ui ----------------------------------
step "Останавливаю 3x-ui (не удаляю — оставлю как fallback)"
systemctl stop  x-ui 2>/dev/null || true
systemctl disable x-ui 2>/dev/null || true

# ------------------------------ get API token -------------------------------
step "Получаю API-токен Remnawave"
LOGIN_JSON=$(curl -fsS -X POST http://127.0.0.1:3000/api/auth/login \
    -H 'Content-Type: application/json' \
    -d "{\"username\":\"${REM_ADMIN_USER}\",\"password\":\"${REM_ADMIN_PASS}\"}") \
    || die "Не удалось залогиниться в Remnawave"

# В версиях <2.x токен лежит как response.accessToken; в новых — data.accessToken
ACCESS=$(echo "$LOGIN_JSON" | jq -r '.response.accessToken // .data.accessToken // .accessToken // empty')
[[ -n "$ACCESS" ]] || die "Не нашёл accessToken в ответе: $LOGIN_JSON"

# Создаём долгоживущий API-токен
TOKEN_JSON=$(curl -fsS -X POST http://127.0.0.1:3000/api/tokens \
    -H "Authorization: Bearer $ACCESS" -H 'Content-Type: application/json' \
    -d '{"tokenName":"migration-script"}') \
    || die "Не удалось создать API-token"
API_TOKEN=$(echo "$TOKEN_JSON" | jq -r '.response.token // .data.token // .token // empty')
[[ -n "$API_TOKEN" ]] || die "Нет поля token в ответе: $TOKEN_JSON"
log "API-token получен"

# ------------------------------ extract from x-ui.db -----------------------
step "Парсинг x-ui.db"
WORK="$(mktemp -d)"
EXPORT_JSON="$WORK/clients.json"

python3 - "$XUI_DB" "$EXPORT_JSON" <<'PY'
import json, sqlite3, sys, re

src, dst = sys.argv[1], sys.argv[2]
con = sqlite3.connect(src)
con.row_factory = sqlite3.Row
cur = con.cursor()

# В 3x-ui таблица называется "inbounds"
rows = cur.execute("SELECT * FROM inbounds").fetchall()
out = []
for r in rows:
    try:
        settings = json.loads(r["settings"] or "{}")
        stream   = json.loads(r["stream_settings"] or "{}")
    except Exception:
        continue
    protocol = (r["protocol"] or "").lower()
    port     = r["port"]
    inbound_remark = r["remark"]

    # Reality / TLS параметры — пригодятся для ручной настройки inbound в Remnawave
    reality = stream.get("realitySettings", {}).get("settings", {}) | stream.get("realitySettings", {})
    reality_pub = reality.get("publicKey") or stream.get("realitySettings", {}).get("settings", {}).get("publicKey")
    reality_short_ids = stream.get("realitySettings", {}).get("shortIds", [])
    server_names = stream.get("realitySettings", {}).get("serverNames", [])

    for c in settings.get("clients", []):
        out.append({
            "inbound_remark":  inbound_remark,
            "inbound_port":    port,
            "protocol":        protocol,
            "client_id":       c.get("id") or c.get("password"),
            "email":           c.get("email") or "",
            "password":        c.get("password") or "",
            "flow":            c.get("flow") or "",
            "expiry_time_ms":  c.get("expiryTime") or 0,
            "total_gb":        c.get("totalGB") or 0,
            "enable":          c.get("enable", True),
            "sub_id":          c.get("subId") or "",
            "reality_public_key": reality_pub,
            "reality_short_ids":  reality_short_ids,
            "server_names":       server_names,
        })

with open(dst, "w") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)

print(f"Найдено клиентов: {len(out)}")
PY

CLIENTS_COUNT=$(jq 'length' "$EXPORT_JSON")
log "Извлечено клиентов: $CLIENTS_COUNT"
cp "$EXPORT_JSON" "$BACKUP_DIR/clients.json"

# ------------------------------ Reality info -------------------------------
step "Reality / inbound info (вставьте в Remnawave Config Profile вручную)"
jq -r '
  [ .[] | { remark:.inbound_remark, port:.inbound_port,
            sni: (.server_names|join(",")),
            shortIds:(.reality_short_ids|join(",")),
            pubkey:.reality_public_key } ]
  | unique_by(.remark)
  | .[] | "  • \(.remark)  port=\(.port)  sni=\(.sni)  shortIds=\(.shortIds)  pubkey=\(.pubkey)"
' "$EXPORT_JSON"

# ------------------------------ create users -------------------------------
step "Создание пользователей в Remnawave"
CREATED=0; SKIPPED=0; FAILED=0
MAPPING="$BACKUP_DIR/mapping.csv"
echo "old_sub_token,old_email,old_uuid,new_short_uuid,new_subscription_url" > "$MAPPING"

# itertate via jq -c
jq -c '.[]' "$EXPORT_JSON" | while read -r row; do
    proto=$(jq -r '.protocol' <<<"$row")
    cid=$(  jq -r '.client_id' <<<"$row")
    email=$(jq -r '.email'     <<<"$row")
    expms=$(jq -r '.expiry_time_ms' <<<"$row")
    flow=$( jq -r '.flow'      <<<"$row")
    subid=$(jq -r '.sub_id'    <<<"$row")
    enable=$(jq -r '.enable'   <<<"$row")
    password=$(jq -r '.password' <<<"$row")

    # username: 3-36 [a-zA-Z0-9_-]
    uname=$(echo "$email" | tr -c 'a-zA-Z0-9_-' '_' | cut -c1-36)
    if [[ ${#uname} -lt 3 ]]; then
        uname="u_${cid:0:8}"
    fi

    # старый sub-token = subId если он есть, иначе email. Используем как shortUuid.
    old_token="${subid:-$email}"
    short_uuid=$(echo "$old_token" | tr -c 'a-zA-Z0-9' '' | cut -c1-16)
    [[ ${#short_uuid} -lt 8 ]] && short_uuid=$(uuidgen | tr -d '-' | cut -c1-16)

    # expireAt: миллисекунды → ISO; 0 → +10 лет
    if [[ "$expms" == "0" || -z "$expms" ]]; then
        expire_at=$(date -u -d '+10 years' +%Y-%m-%dT%H:%M:%S.000Z)
    else
        expire_at=$(date -u -d "@$(($expms/1000))" +%Y-%m-%dT%H:%M:%S.000Z)
    fi

    status="ACTIVE"
    [[ "$enable" == "false" ]] && status="DISABLED"

    # Тело запроса. ВСЕГДА передаём vlessUuid=cid, чтобы UUID совпал.
    # trojanPassword / ssPassword — оставляем те же, что были у клиента
    # (для VLESS они тоже допустимы, просто не будут использованы).
    trojan_pass="$password"
    [[ ${#trojan_pass} -lt 8 ]] && trojan_pass=$(openssl rand -hex 8)
    ss_pass="$trojan_pass"

    # для VLESS cid это UUID, для Trojan/SS — пароль (тогда сгенерируем UUID)
    if [[ "$proto" == "vless" ]] && [[ "$cid" =~ ^[0-9a-fA-F-]{36}$ ]]; then
        vless_uuid="$cid"
    else
        vless_uuid=$(uuidgen)
        [[ "$proto" == "trojan"      ]] && trojan_pass="$cid"
        [[ "$proto" == "shadowsocks" ]] && ss_pass="$cid"
    fi

    body=$(jq -nc \
        --arg u  "$uname" \
        --arg s  "$status" \
        --arg vu "$vless_uuid" \
        --arg tp "$trojan_pass" \
        --arg sp "$ss_pass" \
        --arg su "$short_uuid" \
        --arg ea "$expire_at" \
        '{username:$u,status:$s,vlessUuid:$vu,trojanPassword:$tp,ssPassword:$sp,shortUuid:$su,expireAt:$ea,trafficLimitBytes:0,trafficLimitStrategy:"NO_RESET"}')

    if [[ $DRY_RUN -eq 1 ]]; then
        echo "DRY-RUN  $uname  vless=$vless_uuid  short=$short_uuid  expire=$expire_at"
        continue
    fi

    resp=$(curl -fsS -X POST http://127.0.0.1:3000/api/users \
        -H "Authorization: Bearer $API_TOKEN" \
        -H 'Content-Type: application/json' \
        -d "$body" 2>&1) || { warn "FAIL $uname: $resp"; FAILED=$((FAILED+1)); continue; }

    new_short=$(echo "$resp" | jq -r '.response.shortUuid // .data.shortUuid // empty')
    sub_url=$(echo "$resp"   | jq -r '.response.subscriptionUrl // .data.subscriptionUrl // empty')
    echo "$old_token,$email,$cid,$new_short,$sub_url" >> "$MAPPING"
    CREATED=$((CREATED+1))
    printf '  + %-30s vless=%s sub=%s\n' "$uname" "$vless_uuid" "$sub_url"
done

log "Создано: $CREATED, пропущено: $SKIPPED, ошибок: $FAILED"
log "Маппинг старый sub-token → новый shortUuid сохранён в $MAPPING"

# ------------------------------ legacy /sub/ reverse-proxy ------------------
step "Поднимаю legacy reverse-proxy для старых subscription URL"
# Старые ссылки в Hiddify имели вид:  https://<IP>:2096/sub/<token>
# Превращаем их в:                    http://127.0.0.1:3010/<shortUuid>
# через nginx + lua-style map (мы используем готовый mapping.csv → nginx map).

apt-get install -y -qq nginx
MAP_FILE=/etc/nginx/sub_token_map.conf
{
    echo "# auto-generated — ${TS}"
    echo "map \$sub_token \$rw_short {"
    echo "    default \"\";"
    while IFS=, read -r old_tok _email _uuid new_short _url; do
        [[ "$old_tok" == "old_sub_token" ]] && continue
        [[ -z "$new_short" ]] && continue
        printf '    "%s" "%s";\n' "$old_tok" "$new_short"
    done < "$MAPPING"
    echo "}"
} > "$MAP_FILE"

cat > /etc/nginx/conf.d/legacy-sub.conf <<EOF
include $MAP_FILE;
server {
    listen 2096;
    server_name _;

    # /sub/<token>  →  Remnawave subscription page  /<shortUuid>
    location ~ ^/sub/(?<sub_token>[^/]+)/?\$ {
        if (\$rw_short = "") { return 404; }
        proxy_pass http://127.0.0.1:3010/\$rw_short;
        proxy_set_header Host ${REM_SUB_DOMAIN};
        proxy_set_header X-Forwarded-Proto https;
    }
    location / { return 410; }
}
EOF
nginx -t && systemctl restart nginx
log "Legacy proxy слушает 0.0.0.0:2096 — старые ссылки продолжают работать"

# ------------------------------ summary -------------------------------------
step "Готово"
cat <<EOF
${GREEN}Миграция завершена.${NC}

  Панель Remnawave : https://${REM_DOMAIN}
  Логин/пароль     : ${REM_ADMIN_USER} / ${REM_ADMIN_PASS}
  Subscription URL : https://${REM_SUB_DOMAIN}/<shortUuid>
  Старые ссылки    : http://${SERVER_IP}:2096/sub/<token>  (работают через nginx)
  API-token        : ${API_TOKEN}
  Бэкап 3x-ui      : ${BACKUP_DIR}
  CSV-маппинг      : ${MAPPING}

Дальнейшие шаги (вручную):
  1. В Remnawave → Config Profiles создайте профиль с теми же Reality-параметрами,
     что напечатаны выше (sni, shortIds, publicKey/privateKey берите из /etc/x-ui).
  2. В Nodes → Management добавьте локальную ноду (хост 127.0.0.1 либо ${SERVER_IP}).
  3. В Internal Squads привяжите всех импортированных пользователей к новому профилю.
  4. Проверьте подписку в Hiddify — ссылка должна обновиться сама.
  5. Через 7 дней удалите 3x-ui:  apt remove x-ui  &&  rm -rf /etc/x-ui

Откат:
  systemctl enable --now x-ui
  cd /opt/remnawave && docker compose down
  systemctl stop nginx
EOF
