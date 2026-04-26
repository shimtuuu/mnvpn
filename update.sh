#!/bin/bash
# MNVPN Safe Update Script
# Обновляет файлы с GitHub, НЕ трогая .env (токен бота сохраняется)
# Запуск: bash update.sh

set -e

MNVPN_DIR="/opt/mnvpn"
REPO_URL="https://github.com/shimtuuu/mnvpn.git"
ENV_BACKUP="/tmp/.env.mnvpn.backup"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

print_ok()   { echo -e "${GREEN}[✓]${NC} $1"; }
print_info() { echo -e "${YELLOW}[i]${NC} $1"; }
print_err()  { echo -e "${RED}[✗]${NC} $1"; }

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║     MNVPN — Безопасное обновление        ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# 1. Бэкап .env
if [ -f "$MNVPN_DIR/.env" ]; then
    cp "$MNVPN_DIR/.env" "$ENV_BACKUP"
    print_ok ".env сохранён в $ENV_BACKUP"
else
    print_info ".env не найден — после обновления создайте его вручную из .env.example"
fi

# 2. Обновление файлов
if [ -d "$MNVPN_DIR/.git" ]; then
    print_info "Репозиторий уже склонирован — выполняем git fetch + reset..."
    cd "$MNVPN_DIR"
    git fetch origin main
    git reset --hard origin/main
    print_ok "Файлы обновлены с GitHub"
else
    print_info "Репозиторий не найден — клонируем..."
    rm -rf "$MNVPN_DIR"
    git clone "$REPO_URL" "$MNVPN_DIR"
    print_ok "Репозиторий склонирован в $MNVPN_DIR"
fi

# 3. Восстановление .env
if [ -f "$ENV_BACKUP" ]; then
    cp "$ENV_BACKUP" "$MNVPN_DIR/.env"
    print_ok ".env восстановлен — токен бота не изменён"
else
    print_info "Создайте .env:"
    print_info "  cp $MNVPN_DIR/.env.example $MNVPN_DIR/.env"
    print_info "  nano $MNVPN_DIR/.env"
fi

# 4. Установка/обновление зависимостей
cd "$MNVPN_DIR"
if [ -d ".venv" ]; then
    print_info "Обновляем зависимости..."
    .venv/bin/pip install -q -r requirements.txt
    print_ok "Зависимости обновлены"
else
    print_info "Виртуальное окружение не найдено, создаём..."
    python3 -m venv .venv
    .venv/bin/pip install -q --upgrade pip
    .venv/bin/pip install -q -r requirements.txt
    print_ok "Виртуальное окружение создано и зависимости установлены"
fi

# 5. Перезапуск бота (если сервис существует)
if systemctl list-units --type=service 2>/dev/null | grep -q "mnvpn-bot"; then
    systemctl restart mnvpn-bot.service
    sleep 2
    if systemctl is-active --quiet mnvpn-bot.service; then
        print_ok "Бот перезапущен и работает"
    else
        print_err "Бот не запустился. Проверьте логи:"
        echo "  journalctl -u mnvpn-bot.service -n 30"
    fi
else
    print_info "Systemd-сервис mnvpn-bot не найден. Запустите бота вручную:"
    print_info "  cd $MNVPN_DIR && .venv/bin/python3 bot.py"
fi

echo ""
print_ok "Обновление завершено!"
echo ""
echo "📋 Полезные команды:"
echo "  Логи бота:       journalctl -u mnvpn-bot.service -f"
echo "  Статус сервиса:  systemctl status mnvpn-bot.service"
echo "  Перезапуск:      systemctl restart mnvpn-bot.service"
echo ""
