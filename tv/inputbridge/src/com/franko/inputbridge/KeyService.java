package com.franko.inputbridge;

import android.accessibilityservice.AccessibilityService;
import android.content.ComponentName;
import android.content.Intent;
import android.util.Log;
import android.view.KeyEvent;
import android.view.accessibility.AccessibilityEvent;

/**
 * Необязательная служба. Система открывает меню источников по кнопке INPUT только когда на переднем плане
 * лаунчер с "launcher" или "zeasn" в имени пакета; для остальных (например, Projectivy) нажатие игнорируется.
 * Служба перехватывает кнопку сама и открывает штатное меню источников. Включается пользователем в
 * настройках специальных возможностей.
 */
public class KeyService extends AccessibilityService {
    private static final String TAG = "InputBridge";

    @Override
    protected boolean onKeyEvent(KeyEvent e) {
        if (e.getKeyCode() != KeyEvent.KEYCODE_TV_INPUT) return false;
        if (e.getAction() == KeyEvent.ACTION_DOWN && e.getRepeatCount() == 0) {
            try {
                startActivity(new Intent()
                        .setComponent(new ComponentName("com.cultraview.setting", "com.cultraview.setting.SourceActivity"))
                        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
            } catch (RuntimeException ex) {
                Log.e(TAG, "cannot open the source menu", ex);
            }
        }
        return true;
    }

    @Override
    public void onAccessibilityEvent(AccessibilityEvent event) {
    }

    @Override
    public void onInterrupt() {
    }
}
