package com.f1hub.flet_home_widget;

import android.app.PendingIntent;
import android.appwidget.AppWidgetManager;
import android.appwidget.AppWidgetProvider;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Build;
import android.os.SystemClock;
import android.util.Log;
import android.view.View;
import android.widget.RemoteViews;

/** Виджет: ближайший этап, отсчёт до старта (Chronometer идёт сам), топ-3 или LIVE. */
public class F1WidgetProvider extends AppWidgetProvider {
    static final String PREFS = "flet_home_widget";

    @Override
    public void onUpdate(Context context, AppWidgetManager manager, int[] ids) {
        render(context, manager, ids);
    }

    static void render(Context context, AppWidgetManager manager, int[] ids) {
        SharedPreferences p = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        String title = p.getString("title", "");
        boolean live = p.getBoolean("live", false);
        long left = p.getLong("start_ms", 0L) - System.currentTimeMillis();
        for (int id : ids) {
            RemoteViews v = new RemoteViews(context.getPackageName(), R.layout.f1hw_widget);
            v.setTextViewText(R.id.f1hw_title, title.isEmpty() ? "Открой F1 Hub" : title);
            v.setTextViewText(R.id.f1hw_subtitle, p.getString("subtitle", ""));
            v.setTextViewText(R.id.f1hw_top, p.getString("top", ""));
            v.setTextViewText(R.id.f1hw_status, p.getString("status", ""));
            v.setViewVisibility(R.id.f1hw_live, live ? View.VISIBLE : View.GONE);
            boolean counting = !live && left > 0;
            // base — в шкале elapsedRealtime: Chronometer сам отсчитывает время до старта
            v.setChronometer(R.id.f1hw_countdown, SystemClock.elapsedRealtime() + Math.max(left, 0), null, counting);
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N) {
                v.setChronometerCountDown(R.id.f1hw_countdown, true);
            }
            v.setViewVisibility(R.id.f1hw_countdown, counting ? View.VISIBLE : View.GONE);
            v.setViewVisibility(R.id.f1hw_label, counting ? View.VISIBLE : View.GONE);
            Intent launch = context.getPackageManager().getLaunchIntentForPackage(context.getPackageName());
            if (launch != null) {
                PendingIntent open = PendingIntent.getActivity(context, 0, launch,
                        PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
                v.setOnClickPendingIntent(R.id.f1hw_root, open);
            }
            manager.updateAppWidget(id, v);
        }
        if (ids.length > 0) {
            Log.i(FletHomeWidgetPlugin.TAG, "виджет перерисован: " + ids.length);
        }
    }
}
