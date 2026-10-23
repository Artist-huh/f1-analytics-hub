import flet as ft


@ft.control("HomeWidget")
class HomeWidget(ft.Service):
    """Сервис: обновляет виджет F1 Hub на главном экране Android.

    Данные хранятся в SharedPreferences приложения, поэтому виджет показывает их и когда
    приложение закрыто; отсчёт до старта ведёт системный Chronometer.
    """

    async def update(self, title: str, subtitle: str, start_ms: int, top: str, status: str = "",
                     live: bool = False) -> int:
        """Записать данные и перерисовать виджеты. -> сколько виджетов F1 Hub стоит на экране."""
        return await self._invoke_method(
            method_name="update",
            arguments={"title": title, "subtitle": subtitle, "start_ms": int(start_ms), "top": top,
                       "status": status, "live": bool(live)},
        )
