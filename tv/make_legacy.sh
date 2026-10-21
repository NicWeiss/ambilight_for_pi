#!/bin/sh
# Пересоздаёт tv/screencatch_p (запасной режим) из штатной программы самого телевизора.
# usage: make_legacy.sh IP:5555
# Штатный /vendor/bin/screencatch (Amlogic) пишет кадры в жёстко прописанную /data/temp, куда нельзя
# писать без root; здесь эта строка заменяется на "." (текущая папка).
set -e
TV=${1:?usage: make_legacy.sh IP:5555}
cd "$(dirname "$0")"
adb -s "$TV" pull /vendor/bin/screencatch screencatch.orig >/dev/null
python3 - <<'PY'
d = open('screencatch.orig', 'rb').read()
needle = b'\x00/data/temp\x00'
assert d.count(needle) == 1, "unexpected binary layout"
i = d.find(needle)
open('screencatch_p', 'wb').write(d[:i] + b'\x00.' + b'\x00' * (len(needle) - 2) + d[i + len(needle):])
PY
rm -f screencatch.orig
chmod 755 screencatch_p
ls -l screencatch_p
