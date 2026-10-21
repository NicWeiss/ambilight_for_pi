#!/system/bin/sh
# usage: cap.sh [W] [H] [TYPE 0=video 1=video+osd] [N]
W=${1:-160}; H=${2:-90}; T=${3:-1}; N=${4:-5000}
D=/data/local/tmp/capf
mkdir -p $D; cd $D
if [ ! -p argb8888-${W}x${H}-$N.bin ]; then
  rm -f argb8888-*
  seq 1 $N | while read i; do echo argb8888-${W}x${H}-$i.bin; done | xargs mkfifo
fi
/data/local/tests/vendor/screencatch_p -b -t $T -c $N 0 0 1280 720 $W $H >/dev/null 2>&1 &
i=1
while [ $i -le $N ]; do cat argb8888-${W}x${H}-$i.bin; i=$((i+1)); done
wait
