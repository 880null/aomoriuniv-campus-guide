#!/bin/zsh
cd -- "$(dirname -- "$0")" || exit 1
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3.10以上をインストールしてください。"
  read -r "reply?Enterキーで終了します。"
  exit 1
fi
python3 scripts/bootstrap.py "$@"
campus_exit=$?
if [ "$campus_exit" -ne 0 ] && [ -t 0 ]; then
  read -r "reply?起動に失敗しました。上のメッセージを確認してEnterキーを押してください。"
fi
exit "$campus_exit"
