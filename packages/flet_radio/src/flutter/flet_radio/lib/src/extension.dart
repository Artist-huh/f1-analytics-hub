import 'package:flet/flet.dart';

import 'radio_engine.dart';

class Extension extends FletExtension {
  @override
  FletService? createService(Control control) {
    switch (control.type) {
      case "RadioEngine":
        return RadioEngineService(control: control);
      default:
        return null;
    }
  }
}
