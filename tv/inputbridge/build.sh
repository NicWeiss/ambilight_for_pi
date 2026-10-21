#!/bin/sh
# Собирает inputbridge.apk. Нужен Android SDK (build-tools и platforms/android-33), JDK 8+.
set -e
cd "$(dirname "$0")"
SDK=${ANDROID_HOME:-$HOME/Android/Sdk}
BT=${BUILD_TOOLS:-$SDK/build-tools/34.0.0}
D8=${D8:-$SDK/build-tools/31.0.0/d8}    # d8 есть не во всех версиях build-tools
JAR=$SDK/platforms/android-33/android.jar
rm -rf build && mkdir -p build/classes

[ -f debug.keystore ] || keytool -genkeypair -keystore debug.keystore -storepass android -keypass android \
  -alias debug -keyalg RSA -keysize 2048 -validity 10000 -dname "CN=Input Bridge" >/dev/null 2>&1

"$BT/aapt2" compile --dir res -o build/res.zip
"$BT/aapt2" link -o build/base.apk -I "$JAR" --manifest AndroidManifest.xml build/res.zip \
  --min-sdk-version 21 --target-sdk-version 33 --version-code 1 --version-name 1.0
javac -source 1.8 -target 1.8 -Xlint:-options -cp "$JAR" -d build/classes $(find src -name '*.java')
"$D8" --release --min-api 21 --lib "$JAR" --output build $(find build/classes -name '*.class')
(cd build && zip -q -j base.apk classes.dex)
"$BT/zipalign" -f 4 build/base.apk build/aligned.apk
"$BT/apksigner" sign --ks debug.keystore --ks-pass pass:android --key-pass pass:android \
  --out inputbridge.apk build/aligned.apk
ls -l inputbridge.apk
