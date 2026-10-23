import 'package:flet/flet.dart';

import 'home_widget.dart';

class Extension extends FletExtension {
  @override
  FletService? createService(Control control) {
    switch (control.type) {
      case "HomeWidget":
        return HomeWidgetService(control: control);
      default:
        return null;
    }
  }
}
