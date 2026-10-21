# inputbridge - HDMI-входы и кнопка INPUT в сторонних лаунчерах

На этом ТВ (Franko, прошивка Cultraview) входы переключает не стандартный Android, а родное приложение
`com.cultraview.livetv`: ему передаётся целое `sourceId`. Поэтому в сторонних лаунчерах (Projectivy и т.п.):

1. **Плитки HDMI/AV не открываются**: лаунчер шлёт запросы, рассчитанные на ТВ Xiaomi/MediaTek
   (`com.xiaomi.mitv.tvplayer.EXTSRC_PLAY`, `com.fengmi.tvinput`, `com.mediatek.wwtv.tvcenter`,
   затем общий `VIEW content://android.media.tv/passthrough/...`). Никто из них здесь не отвечает, и последний
   запрос достаётся случайному приложению (ES Explorer) - появляется окно «ошибка».
2. **Кнопка INPUT не открывает меню источников**: меню открывает система (`CtvHandleKeyProvider`), но только если
   имя пакета активного приложения содержит `launcher` или `zeasn` (либо это `com.cultraview.livetv`).
   `com.spocky.projengmenu` под это правило не подходит, и нажатие игнорируется.

## Что делает приложение

- `BridgeActivity` принимает запрос `EXTSRC_PLAY` и стандартный `passthrough`-запрос и превращает его в то, что
  делает штатное меню: `com.cultraview.livetv/.MainActivity` + `sourceId`.

  | Вход | `input` у Projectivy | `sourceId` |
  |---|---|---|
  | HDMI 1 / 2 / 3 / 4 | 23 / 24 / 25 / 26 | 9 / 10 / 11 / 12 |
  | AV | 2 | 15 |

  Идентификаторы - это `android.cultraview.tv.constants.CtvSourceId` из `/system/framework/android.cultraview.tv.jar`
  (ATV 0/1, DVB-T 2, DVB-C 3, DVB-S 4, HDMI 9-12, YPbPr 13/14, AV 15/16, VGA 17, Media 18).
- `KeyService` (необязательная служба специальных возможностей) перехватывает кнопку INPUT и открывает штатное меню
  источников `com.cultraview.setting/.SourceActivity`. Нужна, если лаунчер не проходит проверку по имени пакета
  (Projectivy). Других данных служба не читает, события окон не обрабатывает.

Лаунчер этого проекта (`com.franko.launcher`) подходит под правило системы, и кнопка INPUT с ним работает без службы.

## Установка

```bash
adb -s <IP>:5555 install -r inputbridge.apk
```

Этого достаточно, чтобы плитки HDMI/AV в Projectivy заработали.

### Кнопка INPUT (только для лаунчеров, которые система не пропускает)

Включается вручную, это настройка безопасности ТВ:

1. Открыть настройки специальных возможностей Android (в меню Franko их нет): Activity Launcher ->
   `com.android.settings/.Settings$AccessibilitySettingsActivity`.
2. Найти **Input Bridge: кнопка INPUT** и включить.

То же одной командой с компьютера (заменит список включённых служб, поэтому сначала посмотрите текущий:
`adb shell settings get secure enabled_accessibility_services`):

```bash
adb -s <IP>:5555 shell settings put secure enabled_accessibility_services \
  com.franko.inputbridge/com.franko.inputbridge.KeyService
adb -s <IP>:5555 shell settings put secure accessibility_enabled 1
```

Отключить - снять переключатель в тех же настройках или удалить приложение.

## Проверка

```bash
adb -s <IP>:5555 logcat -c
# нажать в Projectivy плитку HDMI 2, затем:
adb -s <IP>:5555 logcat -d | grep InputBridge
# InputBridge: action=com.xiaomi.mitv.tvplayer.EXTSRC_PLAY data=null extras={input=24, } -> sourceId=10
```

Напрямую, без лаунчера: `adb shell am start -n com.cultraview.livetv/.MainActivity --ei sourceId 10`.

## Сборка

```bash
./build.sh      # нужны Android SDK (platforms/android-33, build-tools с d8) и JDK
```

Ключ подписи (`debug.keystore`) создаётся при первой сборке и в репозиторий не входит. Если пересобрать с новым ключом,
поверх установленной версии она не встанет: сначала `adb uninstall com.franko.inputbridge`.

## Ограничения

- Общий `VIEW content://android.media.tv/passthrough/...` от других лаунчеров мост перехватывает только если у запроса
  нет MIME-типа; Android обычно подставляет его сам, и тогда запрос достаётся ES Explorer. Для Projectivy это не важно:
  он первым шлёт `EXTSRC_PLAY`, который мост принимает.
- HDMI 4 в таблице есть, но на этом ТВ физически три входа.
