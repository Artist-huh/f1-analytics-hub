"""Разбор гонки, вкладка «Радио»: лента переговоров пилотов с инженерами, проигрывание и перевод на русский"""
import flet as ft

from design_system import *
from services import archive, live, log, radio
from ui.components import *
from ui.fmt import plural
from ui.widgets import button, pill, retry_block

logger = log.get("radio-ui")
PAGE = 30                     # записей за раз: «Показать ещё» добавляет следующую порцию


def radio_section(state, race):
    key = radio.radio_key(race)
    fetch = lambda: radio.fetch_radio(int(race["season"]), race["date"])
    data = archive.get(key, fetch, None, state.render)
    if not data:
        if archive.loading(key):
            return [skeleton("Загружаем записи радио…", "rows", 5)]
        err = archive.error(key)
        hint = (live.LOCKED_TEXT if err == live.LOCKED_TEXT else
                "OpenF1 не отдал записи этой гонки — возможно, они ещё не опубликованы." if err else
                "Нужен интернет: список записей загружается один раз.")
        return [retry_block("Радио не загружено", hint,
                            lambda e: (archive.get(key, fetch, None, state.render, force=True), state.render()))]

    drivers = data["drivers"]
    who = state.ui.get("radio_driver")
    present = []
    for m in data["messages"]:
        if m["driver"] not in present:
            present.append(m["driver"])
    order = {code: i for i, code in enumerate(_finish_codes(state, race))}
    present.sort(key=lambda n: order.get(drivers.get(n, {}).get("code"), 99))

    def pick(number):
        state.ui["radio_driver"] = number
        state.ui["radio_shown"] = PAGE
        state.render()

    chips = [pill("Все", who is None, lambda e: pick(None))]
    chips += [pill(drivers.get(n, {}).get("code") or n, who == n, lambda e, n=n: pick(n)) for n in present]
    messages = [m for m in data["messages"] if who is None or m["driver"] == who]
    shown = state.ui.get("radio_shown", PAGE)
    feed = [_message(state, m, drivers.get(m["driver"], {}), data.get("start")) for m in messages[:shown]]
    if len(messages) > shown:
        feed.append(button(f"Показать ещё ({len(messages) - shown})",
                           lambda e: (state.ui.__setitem__("radio_shown", shown + PAGE), state.render()),
                           primary=False))
    count = ft.Text(f"{len(messages)} {plural(len(messages), 'запись', 'записи', 'записей')}", size=FONT_CAPTION,
                    color=TEXT_MUTED, expand=True)
    can_translate = radio.supported() and radio.models_ready()
    waiting = [m["url"] for m in messages[:shown]
               if can_translate and not radio.status(m["url"]) and not radio.cached(m["url"])]

    def translate_all(e):
        for url in waiting:
            radio.request(url, state.render)
        state.render()

    return [
        _translate_card(state),
        ft.Row(chips, spacing=SPACE_XS, scroll=ft.ScrollMode.AUTO),
        ft.Row([count] + ([ft.TextButton(f"Перевести все на экране ({len(waiting)})", icon=ft.Icons.TRANSLATE_ROUNDED,
                                         on_click=translate_all)] if waiting else []),
               vertical_alignment=ft.CrossAxisAlignment.CENTER),
        ft.Column(feed, spacing=SPACE_XS),
        ft.Text("Записи — OpenF1 (публикуются не все переговоры). Расшифровка и перевод — на этом устройстве, "
                "моделями Whisper и Argos Translate; возможны неточности.", size=FONT_CAPTION, color=TEXT_DIM),
    ]


def _finish_codes(state, race):
    codes = {d["driver_id"]: d["code"] for d in state.standings}
    rows = sorted((r for r in state.season_results if r["round"] == race["round"]),
                  key=lambda r: int(r["position"]) if r["position"].isdigit() else 99)
    return [codes.get(r["driver_id"], "") for r in rows]


# ---------------------------------------------------------------- перевод: модели
def _translate_card(state):
    if not radio.supported():
        return AnimatedCard(ft.Text("Перевод радио работает в версии для компьютера. Здесь — запись в оригинале.",
                                    size=FONT_BODY_SMALL, color=TEXT_SECONDARY))
    if radio.models_ready():
        return ft.Container()
    dl = radio.download_state()
    if dl["state"] == "running":
        body = [ft.Text("Скачиваем модели расшифровки и перевода…", size=FONT_BODY_SMALL, color=TEXT_PRIMARY),
                progress_bar(dl["progress"], F1_RED, height=6),
                ft.Text(f"{round(100 * dl['progress'])} %", size=FONT_CAPTION, color=TEXT_MUTED)]
    else:
        body = [ft.Text("Перевод на русский", size=FONT_BODY, color=TEXT_PRIMARY, weight=ft.FontWeight.W_600),
                ft.Text("Расшифровка и перевод работают без интернета и бесплатно. Модели скачиваются один раз: "
                        "точная лучше разбирает шумное радио, лёгкая занимает меньше места.",
                        size=FONT_BODY_SMALL, color=TEXT_SECONDARY)]
        if dl["state"] == "error":
            body.append(ft.Text(f"Не получилось: {dl['error']}", size=FONT_CAPTION, color=DANGER))
        body.append(ft.Row([
            button(f"{label} (~{size} МБ)", lambda e, m=model: (radio.download_models(state.render, m), state.render()),
                   primary=model == radio.DEFAULT_WHISPER, icon=ft.Icons.DOWNLOAD_ROUNDED)
            for model, (label, size) in radio.WHISPER_MODELS.items()], wrap=True, spacing=SPACE_XS,
            run_spacing=SPACE_XS))
    return AnimatedCard(ft.Column(body, spacing=SPACE_XS))


# ---------------------------------------------------------------- одна запись
def _message(state, m, info, start):
    url = m["url"]
    color = f"#{info['colour']}" if info.get("colour") else TEXT_DIM
    at = m["ts"] - start if start else None
    stamp = f"{int(at // 60)}:{int(at % 60):02d}" if at is not None and at >= 0 else ""
    playing = state.ui.get("radio_playing") == url
    text = radio.cached(url) if radio.supported() else None
    job = radio.status(url)
    if text:
        lines = [ft.Text(text["ru"] or "(без слов)", size=FONT_BODY_SMALL, color=TEXT_PRIMARY, selectable=True),
                 ft.Text(text["en"], size=FONT_CAPTION, color=TEXT_MUTED, italic=True, selectable=True)]
    elif job == "pending":
        lines = [ft.Row([ft.ProgressRing(width=14, height=14, stroke_width=2, color=F1_RED),
                         ft.Text("Расшифровываем…", size=FONT_CAPTION, color=TEXT_MUTED)], spacing=SPACE_XS)]
    elif job:
        lines = [ft.Text(job, size=FONT_CAPTION, color=DANGER)]
    elif radio.supported() and radio.models_ready():
        lines = [ft.TextButton("Перевести", icon=ft.Icons.TRANSLATE_ROUNDED,
                               on_click=lambda e: (radio.request(url, state.render), state.render()))]
    else:
        lines = []
    name = info.get("code") or m["driver"]
    return AnimatedCard(ft.Row([
        ft.Container(width=4, height=40, bgcolor=color, border_radius=2),
        ft.IconButton(ft.Icons.STOP_ROUNDED if playing else ft.Icons.PLAY_ARROW_ROUNDED,
                      icon_color=F1_RED if playing else TEXT_PRIMARY, on_click=lambda e: toggle_play(state, url),
                      tooltip=f"{'Остановить' if playing else 'Слушать'}: радио {name}"),
        ft.Column([ft.Row([ft.Text(name, size=FONT_BODY_SMALL, color=TEXT_PRIMARY, font_family=FONT_ITALIC),
                           ft.Text(stamp, size=FONT_CAPTION, color=TEXT_DIM)], spacing=SPACE_XS)] + lines,
                  spacing=2, expand=True),
    ], spacing=SPACE_XS, vertical_alignment=ft.CrossAxisAlignment.START), size="s")


# ---------------------------------------------------------------- проигрывание
def toggle_play(state, url):
    """Одна запись за раз: повторное нажатие — стоп. Плеер — сервис flet-audio на текущей странице."""
    try:
        import flet_audio as fa
    except ImportError:
        show_snack(state.page, "Проигрывание недоступно в этой сборке")
        return
    old = state.ui.pop("radio_player", None)
    was = state.ui.pop("radio_playing", None)

    async def stop(player):
        try:
            await player.release()
        except Exception as exc:
            logger.debug("плеер не остановлен: %r", exc)

    if old:
        state.page.run_task(stop, old)
    if was == url:
        state.render()
        return

    def changed(e):
        if e.state in (fa.AudioState.COMPLETED, fa.AudioState.STOPPED,
                       fa.AudioState.DISPOSED) and state.ui.get("radio_playing") == url:
            state.ui.pop("radio_playing", None)
            state.render()

    player = fa.Audio(src=url, autoplay=True, on_state_change=changed)
    state.ui["radio_player"] = player
    state.ui["radio_playing"] = url
    state.render()
