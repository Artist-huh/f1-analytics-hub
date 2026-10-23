import 'package:flet/flet.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';

/// Мост Flet -> нативный виджет: данные уходят в FletHomeWidgetPlugin (Java) по MethodChannel.
class HomeWidgetService extends FletService {
  HomeWidgetService({required super.control});

  static const MethodChannel _channel = MethodChannel('flet_home_widget');

  @override
  void init() {
    super.init();
    control.addInvokeMethodListener(_invokeMethod);
  }

  Future<dynamic> _invokeMethod(String name, dynamic args) async {
    debugPrint("HomeWidget.$name($args)");
    switch (name) {
      case "update":
        if (defaultTargetPlatform != TargetPlatform.android) {
          return 0;
        }
        return await _channel.invokeMethod<int>(
            'update', Map<String, dynamic>.from(args as Map));
      default:
        throw Exception("Unknown HomeWidget method: $name");
    }
  }

  @override
  void dispose() {
    control.removeInvokeMethodListener(_invokeMethod);
    super.dispose();
  }
}
