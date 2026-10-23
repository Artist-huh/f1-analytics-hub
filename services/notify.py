"""Уведомления: за час до квалификации, спринта и гонки, итоги гонки для избранных пилотов.

Что и когда отправлять — чистые функции (due_reminders, favorites_result). Как отправлять:
  * Windows / macOS / Linux — системное уведомление (desktop-notifier);
  * Android — NotificationManager через pyjnius (канал уведомлений, запрос разрешения на Android 13+);
  * иначе (или при ошибке) — плашка внутри приложения.
Уведомления проверяются, пока приложение запущено (в том числе свёрнуто): фонового сервиса
у приложения нет.
"""
import os
import time

from . import log

try:   # статический импорт — чтобы PyInstaller (flet pack) включил пакет в .exe
    from desktop_notifier import DesktopNotifier
except Exception:   # нет пакета (Android, тесты) — системных уведомлений на компьютере не будет
    DesktopNotifier = None

LEAD = 3600                    # за сколько секунд до старта напоминать
REMIND_KEYS = {"Qualifying": "Квалификация", "SprintQualifying": "Спринт-квалификация",
               "SprintShootout": "Спринт-квалификация", "Sprint": "Спринт", "Race": "Гонка"}
CHANNEL = "f1hub_sessions"

logger = log.get("notify")


def is_android():
    return "ANDROID_DATA" in os.environ or "ANDROID_ARGUMENT" in os.environ


# ---------------------------------------------------------------- что отправлять
def due_reminders(schedule, now=None, lead=LEAD, sent=()):
    """Сессии, до старта которых осталось не больше lead секунд и о которых ещё не напоминали.
    -> [(id, заголовок, текст)]"""
    from ui.fmt import fmt_clock, fmt_day   # форматирование дат — общее с интерфейсом
    now = time.time() if now is None else now
    out = []
    for race in schedule:
        for s in race["sessions"]:
            name = REMIND_KEYS.get(s["key"])
            nid = f"{race.get('season', '')}:{race['round']}:{s['key']}"
            if not name or nid in sent or not 0 < s["ts"] - now <= lead:
                continue
            minutes = max(1, round((s["ts"] - now) / 60))
            out.append((nid, f"{name} через {minutes} мин",
                        f"{race['race_name']} · старт {fmt_day(s['ts'])} в {fmt_clock(s['ts'])}"))
    return out


def favorites_result(favorites, standings, season_results):
    """Итог последней гонки для избранных. -> (id, заголовок, текст) или None."""
    if not favorites or not season_results:
        return None
    last = max(int(r["round"]) for r in season_results)
    rows = [r for r in season_results if int(r["round"]) == last and r["driver_id"] in favorites]
    if not rows:
        return None
    names = {d["driver_id"]: d["name"].split()[-1] for d in standings}
    parts = []
    for r in sorted(rows, key=lambda r: int(r["position"]) if r["position"].isdigit() else 99):
        place = f"P{r['position']}" if r["position"].isdigit() else "сход"
        pts = f" (+{r['points']})" if r["points"] not in ("0", "") else ""
        parts.append(f"{names.get(r['driver_id'], r['driver_id'])} — {place}{pts}")
    race = rows[0]
    return (f"{race.get('season', '')}:{last}:result", f"Итоги: {race['race_name']}", ", ".join(parts))


# ---------------------------------------------------------------- как отправлять
def _android_activity():
    from jnius import autoclass
    host = os.environ.get("MAIN_ACTIVITY_HOST_CLASS_NAME")
    if not host:
        raise RuntimeError("MAIN_ACTIVITY_HOST_CLASS_NAME не задан")
    return autoclass(host).mActivity


def android_request_permission():
    """Android 13+: разрешение POST_NOTIFICATIONS спрашивается во время работы."""
    try:
        from jnius import autoclass
        if autoclass("android.os.Build$VERSION").SDK_INT >= 33:
            _android_activity().requestPermissions(["android.permission.POST_NOTIFICATIONS"], 1301)
        return True
    except Exception as exc:
        logger.warning("разрешение на уведомления не запрошено: %r", exc)
        return False


def _android_send(title, text, nid):
    from jnius import autoclass, cast
    activity = _android_activity()
    Context = autoclass("android.content.Context")
    NotificationManager = autoclass("android.app.NotificationManager")
    Builder = autoclass("android.app.Notification$Builder")
    PendingIntent = autoclass("android.app.PendingIntent")
    sdk = autoclass("android.os.Build$VERSION").SDK_INT
    manager = cast(NotificationManager, activity.getSystemService(Context.NOTIFICATION_SERVICE))
    if sdk >= 26:
        NotificationChannel = autoclass("android.app.NotificationChannel")
        manager.createNotificationChannel(
            NotificationChannel(CHANNEL, "Гонки и результаты", NotificationManager.IMPORTANCE_DEFAULT))
        builder = Builder(activity, CHANNEL)
    else:
        builder = Builder(activity)
    intent = activity.getPackageManager().getLaunchIntentForPackage(activity.getPackageName())
    builder.setSmallIcon(activity.getApplicationInfo().icon)
    builder.setContentTitle(title)
    builder.setContentText(text)
    builder.setAutoCancel(True)
    builder.setContentIntent(PendingIntent.getActivity(activity, 0, intent, PendingIntent.FLAG_IMMUTABLE))
    manager.notify(abs(hash(nid)) % 100000, builder.build())


class Notifier:
    """run_async(coroutine_function) — запустить корутину в цикле событий Flet (page.run_task);
    fallback(title, text) — показать плашку в приложении."""

    def __init__(self, run_async=None, fallback=None):
        self.run_async = run_async
        self.fallback = fallback
        self._desktop = None

    def send(self, nid, title, text):
        try:
            if is_android():
                _android_send(title, text, nid)
                return "android"
            if DesktopNotifier is not None and self.run_async is not None:
                if self._desktop is None:
                    self._desktop = DesktopNotifier(app_name="F1 Analytics Hub")

                async def job():
                    try:
                        await self._desktop.send(title=title, message=text)
                    except Exception as exc:
                        logger.warning("системное уведомление не показано: %r", exc)
                        if self.fallback:
                            self.fallback(title, text)

                self.run_async(job)
                return "desktop"
        except Exception as exc:
            logger.warning("уведомление не отправлено: %r", exc)
        if self.fallback:
            self.fallback(title, text)
            return "in-app"
        return None
