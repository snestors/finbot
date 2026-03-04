import 'dart:async';
import 'dart:convert';
import 'package:web_socket_channel/web_socket_channel.dart';
import '../core/constants.dart';

class WebSocketService {
  WebSocketChannel? _channel;
  Timer? _reconnectTimer;
  bool _disposed = false;

  final void Function(Map<String, dynamic>) onSystemStats;
  final void Function()? onDisconnected;

  WebSocketService({required this.onSystemStats, this.onDisconnected});

  bool get isConnected => _channel != null;

  void connect() {
    if (_disposed || _channel != null) return;

    try {
      final uri = Uri.parse('${Constants.wsUrl}/ws');
      _channel = WebSocketChannel.connect(uri);

      _channel!.stream.listen(
        (data) {
          try {
            final msg = jsonDecode(data as String) as Map<String, dynamic>;
            if (msg['type'] == 'system_stats') {
              onSystemStats(msg);
            }
          } catch (_) {}
        },
        onDone: () {
          _channel = null;
          onDisconnected?.call();
          _scheduleReconnect();
        },
        onError: (_) {
          _channel = null;
          onDisconnected?.call();
          _scheduleReconnect();
        },
      );
    } catch (_) {
      _scheduleReconnect();
    }
  }

  void _scheduleReconnect() {
    if (_disposed) return;
    _reconnectTimer?.cancel();
    _reconnectTimer = Timer(const Duration(seconds: 3), connect);
  }

  void disconnect() {
    _disposed = true;
    _reconnectTimer?.cancel();
    _channel?.sink.close();
    _channel = null;
  }
}
