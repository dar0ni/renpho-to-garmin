#!/bin/bash
# Sendet eine Telegram-Nachricht ueber einen Telegram-Bot.
# Token + Ziel-Chat-ID liegen in einer eigenen Datei (notify.env), damit hier
# nichts an einer bestehenden Bot-Konfiguration (z.B. eines Coaching-Bots) haengt.
set -euo pipefail

ENV_FILE="$(dirname "$(readlink -f "$0")")/notify.env"

if [ ! -f "$ENV_FILE" ]; then
  echo "Telegram-Config nicht gefunden: $ENV_FILE (siehe notify.env.example)" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

if [ -z "${TELEGRAM_TOKEN:-}" ] || [ -z "${TELEGRAM_CHAT_ID:-}" ]; then
  echo "TELEGRAM_TOKEN und/oder TELEGRAM_CHAT_ID nicht in $ENV_FILE gefunden" >&2
  exit 1
fi

TEXT="${1:?Usage: notify_telegram.sh \"Nachricht\"}"

curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_TOKEN}/sendMessage" \
  -d chat_id="${TELEGRAM_CHAT_ID}" \
  --data-urlencode "text=${TEXT}" \
  -o /dev/null
