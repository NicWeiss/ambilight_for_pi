package com.franko.inputbridge;

import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.ComponentName;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.util.Log;

import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Лаунчеры (Projectivy и др.) открывают входы ТВ запросами, рассчитанными на ТВ Xiaomi/MediaTek.
 * На этом ТВ их никто не обслуживает, и запрос достаётся случайному приложению (например, ES Explorer).
 * Здесь они переводятся в то, что делает штатное меню источников: com.cultraview.livetv/.MainActivity
 * с целочисленным extra "sourceId".
 */
public class BridgeActivity extends Activity {
    private static final String TAG = "InputBridge";
    static final String LIVETV_PACKAGE = "com.cultraview.livetv";
    static final String LIVETV_ACTIVITY = "com.cultraview.livetv.MainActivity";

    private static final Pattern HDMI = Pattern.compile("Hdmi(\\d)InputService");
    private static final Pattern AV = Pattern.compile("AV(\\d)InputService");

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        Intent in = getIntent();
        int id = sourceIdFor(in);
        Log.i(TAG, "action=" + in.getAction() + " data=" + in.getData() + " extras=" + dump(in.getExtras())
                + " -> sourceId=" + id);

        Intent out = new Intent()
                .setComponent(new ComponentName(LIVETV_PACKAGE, LIVETV_ACTIVITY))
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        if (id >= 0) out.putExtra("sourceId", id);
        try {
            startActivity(out);
        } catch (ActivityNotFoundException | SecurityException e) {
            Log.e(TAG, "cannot open live tv", e);
        }
        finish();
    }

    /** Идентификаторы из android.cultraview.tv.constants.CtvSourceId; -1 - вход не распознан. */
    static int sourceIdFor(Intent in) {
        if ("com.xiaomi.mitv.tvplayer.EXTSRC_PLAY".equals(in.getAction())) {
            // Projectivy: HDMI1..4 = 23..26, AV = 2
            int input = in.getIntExtra("input", -1);
            if (input >= 23 && input <= 26) return 9 + (input - 23);
            if (input == 2) return 15;
            return -1;
        }
        Uri data = in.getData();
        if (data != null) {
            // content://android.media.tv/passthrough/<id входа>
            String input = data.getLastPathSegment();
            if (input != null) {
                Matcher m = HDMI.matcher(input);
                if (m.find()) return 8 + Integer.parseInt(m.group(1));
                m = AV.matcher(input);
                if (m.find()) return m.group(1).equals("2") ? 16 : 15;
            }
        }
        return -1;
    }

    private static String dump(Bundle ex) {
        if (ex == null) return "null";
        StringBuilder sb = new StringBuilder("{");
        for (String k : ex.keySet()) sb.append(k).append('=').append(ex.get(k)).append(", ");
        return sb.append('}').toString();
    }
}
