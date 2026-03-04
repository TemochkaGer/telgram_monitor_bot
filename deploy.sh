#!/bin/bash

set -euo pipefail

echo "Начинаем установку пакетов и зависимостей!"

way_to_directory="$(pwd)/Python/test_telegram_bot"

echo "$way_to_directory"

sudo apt update && sudo apt install -y python3-venv

python3 -m venv "$way_to_directory/monitoring_bot_venv" && source "$way_to_directory/monitoring_bot_venv/bin/activate"

pip install -r "$way_to_directory/requirements.txt"