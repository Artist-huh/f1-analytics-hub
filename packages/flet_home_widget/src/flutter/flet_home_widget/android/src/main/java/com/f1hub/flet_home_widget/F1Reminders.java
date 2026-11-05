package com.f1hub.flet_home_widget;

import android.app.AlarmManager;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Build;
import android.util.Log;

import org.json.JSONArray;
import org.json.JSONObject;

import java.nio.charset.StandardCharsets;
import java.util.zip.CRC32;

/**
 * Уведомления, которые приходят и при закрытом приложении: напоминания о сессиях, старт сессии,
 * напоминание о прогнозе. Время всех этих событий известно заранее, поэтому сервер не нужен — приложение
 * передаёт список (schedule), а системный будильник AlarmManager показывает уведомление в нужный момент.
 * Список хранится в SharedPreferences: после перезагрузки телефона будильники ставятся заново.
 */
public class F1Reminders extends BroadcastReceiver {
    static final String TAG = "F1Reminders";
    static final String PREFS = "flet_home_widget_reminders";
    static final String ACTION_SHOW = "com.f1hub.flet_home_widget.SHOW_REMINDER";
    static final String CHANNEL = "f1hub_sessions";          // тот же канал, что у уведомлений из Python

    /** id уведомления — как в Python (services/notify.notification_id): одно событие не придёт дважды. */
    static int notificationId(String id) {
        CRC32 crc = new CRC32();
        crc.update(id.getBytes(StandardCharsets.UTF_8));
        return (int) (crc.getValue() % 100000L);
    }

    /** Заменить запланированные уведомления новым списком [{id, at_ms, title, text}]. -> сколько поставлено. */
    static int schedule(Context context, String json) throws Exception {
        SharedPreferences prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        cancelAll(context, new JSONArray(prefs.getString("items", "[]")));
        prefs.edit().putString("items", json).apply();
        return arm(context, new JSONArray(json));
    }

    private static int arm(Context context, JSONArray items) throws Exception {
        AlarmManager alarms = (AlarmManager) context.getSystemService(Context.ALARM_SERVICE);
        long now = System.currentTimeMillis();
        int count = 0;
        for (int i = 0; i < items.length(); i++) {
            JSONObject item = items.getJSONObject(i);
            long at = item.getLong("at_ms");
            if (at <= now) {
                continue;
            }
            PendingIntent pi = pending(context, item, PendingIntent.FLAG_UPDATE_CURRENT);
            setAlarm(alarms, at, pi);
            count++;
        }
        Log.i(TAG, "запланировано уведомлений: " + count);
        return count;
    }

    /** Точный будильник там, где система разрешает его без отдельного разрешения (до Android 12 или если
     *  пользователь его дал), иначе — неточный: в режиме сна он может сдвинуться на несколько минут (аудит, XP-9). */
    static void setAlarm(AlarmManager alarms, long at, PendingIntent pi) {
        boolean exact = Build.VERSION.SDK_INT < Build.VERSION_CODES.S || alarms.canScheduleExactAlarms();
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            if (exact) {
                alarms.setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, at, pi);
            } else {
                alarms.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, at, pi);
            }
        } else if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.KITKAT) {
            alarms.setExact(AlarmManager.RTC_WAKEUP, at, pi);
        } else {
            alarms.set(AlarmManager.RTC_WAKEUP, at, pi);
        }
    }

    private static void cancelAll(Context context, JSONArray items) {
        AlarmManager alarms = (AlarmManager) context.getSystemService(Context.ALARM_SERVICE);
        for (int i = 0; i < items.length(); i++) {
            try {
                alarms.cancel(pending(context, items.getJSONObject(i), PendingIntent.FLAG_UPDATE_CURRENT));
            } catch (Exception ex) {
                Log.w(TAG, "будильник не снят", ex);
            }
        }
    }

    private static PendingIntent pending(Context context, JSONObject item, int flags) throws Exception {
        String id = item.getString("id");
        Intent intent = new Intent(context, F1Reminders.class).setAction(ACTION_SHOW)
                .putExtra("id", id).putExtra("title", item.optString("title"))
                .putExtra("text", item.optString("text"));
        return PendingIntent.getBroadcast(context, notificationId(id), intent, flags | PendingIntent.FLAG_IMMUTABLE);
    }

    @Override
    public void onReceive(Context context, Intent intent) {
        String action = intent.getAction();
        try {
            if (ACTION_SHOW.equals(action)) {
                show(context, intent.getStringExtra("id"), intent.getStringExtra("title"),
                     intent.getStringExtra("text"));
            } else if (Intent.ACTION_BOOT_COMPLETED.equals(action)
                    || Intent.ACTION_MY_PACKAGE_REPLACED.equals(action)) {
                SharedPreferences prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
                arm(context, new JSONArray(prefs.getString("items", "[]")));      // будильники после перезагрузки
            }
        } catch (Exception ex) {
            Log.w(TAG, "уведомление не обработано: " + action, ex);
        }
    }

    private static void show(Context context, String id, String title, String text) {
        NotificationManager manager = (NotificationManager) context.getSystemService(Context.NOTIFICATION_SERVICE);
        Notification.Builder builder;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            manager.createNotificationChannel(
                    new NotificationChannel(CHANNEL, "Гонки и результаты", NotificationManager.IMPORTANCE_DEFAULT));
            builder = new Notification.Builder(context, CHANNEL);
        } else {
            builder = new Notification.Builder(context);
        }
        Intent launch = context.getPackageManager().getLaunchIntentForPackage(context.getPackageName());
        // монохромная иконка: значок в строке состояния — только силуэт, цветная иконка там серый квадрат (XP-2)
        builder.setSmallIcon(R.drawable.f1hw_notify)
                .setContentTitle(title)
                .setContentText(text)
                .setAutoCancel(true);
        if (launch != null) {
            builder.setContentIntent(PendingIntent.getActivity(context, 0, launch, PendingIntent.FLAG_IMMUTABLE));
        }
        manager.notify(notificationId(id), builder.build());
        Log.i(TAG, "показано: " + title);
    }
}
