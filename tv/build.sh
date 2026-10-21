#!/bin/sh
# Собирает tv/vcap из vcap.c. Нужны clang и lld (кросс-компиляция под ARMv7 Android, без libc и NDK).
set -e
cd "$(dirname "$0")"
clang --target=armv7a-linux-androideabi21 -nostdlib -static -ffreestanding -fno-builtin \
  -fno-stack-protector -O2 -fuse-ld=lld -Wl,--build-id=none vcap.c -o vcap
ls -l vcap
