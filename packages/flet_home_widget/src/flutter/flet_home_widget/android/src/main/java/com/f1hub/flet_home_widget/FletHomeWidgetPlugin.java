package com.f1hub.flet_home_widget;

import android.appwidget.AppWidgetManager;
import android.content.ComponentName;
import android.content.Context;
import android.content.SharedPreferences;
import android.util.Log;

import androidx.annotation.NonNull;

import java.util.Map;

import io.flutter.embedding.engine.plugins.FlutterPlugin;
import io.flutter.plugin.common.MethodCall;
import io.flutter.plugin.common.MethodChannel;

/** Принимает данные виджета из приложения (канал flet_home_widget) и перерисовывает виджеты. */
public class FletHomeWidgetPlugin implements FlutterPlugin, MethodChannel.MethodCallHandler {
    static final String TAG = "F1Widget";
    private MethodChannel channel;
    private Context context;

    @Override
    public void onAttachedToEngine(@NonNull FlutterPluginBinding binding) {
        context = binding.getApplicationContext();
        channel = new MethodChannel(binding.getBinaryMessenger(), "flet_home_widget");
        channel.setMethodCallHandler(this);
    }

    @Override
    public void onDetachedFromEngine(@NonNull FlutterPluginBinding binding) {
        channel.setMethodCallHandler(null);
        channel = null;
    }

    @Override
    public void onMethodCall(@NonNull MethodCall call, @NonNull MethodChannel.Result result) {
        if (!"update".equals(call.method)) {
            result.notImplemented();
            return;
        }
        try {
            Map<?, ?> args = (Map<?, ?>) call.arguments;
            SharedPreferences.Editor e =
                    context.getSharedPreferences(F1WidgetProvider.PREFS, Context.MODE_PRIVATE).edit();
            e.putString("title", str(args.get("title")));
            e.putString("subtitle", str(args.get("subtitle")));
            e.putString("top", str(args.get("top")));
            e.putString("status", str(args.get("status")));
            e.putBoolean("live", Boolean.TRUE.equals(args.get("live")));
            Object start = args.get("start_ms");
            e.putLong("start_ms", start instanceof Number ? ((Number) start).longValue() : 0L);
            e.apply();
            AppWidgetManager manager = AppWidgetManager.getInstance(context);
            int[] ids = manager.getAppWidgetIds(new ComponentName(context, F1WidgetProvider.class));
            F1WidgetProvider.render(context, manager, ids);
            Log.i(TAG, "данные виджета обновлены, виджетов на экране: " + ids.length);
            result.success(ids.length);
        } catch (Exception ex) {
            Log.w(TAG, "виджет не обновлён", ex);
            result.error("update_failed", ex.toString(), null);
        }
    }

    private static String str(Object value) {
        return value == null ? "" : value.toString();
    }
}
