#!/bin/bash
# Launch Claude CLI in this project folder.
cd "$(dirname "$0")" || exit 1
# Resize the terminal window to 24 rows x 138 columns (ESC[8;rows;cols t).
printf '\e[8;24;138t'
exec claude "$@"
