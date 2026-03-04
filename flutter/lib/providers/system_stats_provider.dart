import 'dart:async';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../services/api_client.dart';
import '../services/websocket_service.dart';
import 'auth_provider.dart';

class SystemStats {
  final double powerW;
  final double voltageV;
  final double currentA;
  final double dayKwh;
  final double monthKwh;
  final DateTime timestamp;

  const SystemStats({
    this.powerW = 0,
    this.voltageV = 0,
    this.currentA = 0,
    this.dayKwh = 0,
    this.monthKwh = 0,
    required this.timestamp,
  });

  factory SystemStats.fromJson(Map<String, dynamic> json) => SystemStats(
        powerW: (json['power_w'] as num?)?.toDouble() ?? 0,
        voltageV: (json['voltage_v'] as num?)?.toDouble() ?? 0,
        currentA: (json['current_a'] as num?)?.toDouble() ?? 0,
        dayKwh: (json['day_kwh'] as num?)?.toDouble() ?? 0,
        monthKwh: (json['month_kwh'] as num?)?.toDouble() ?? 0,
        timestamp: DateTime.now(),
      );
}

/// Holds current stats + rolling history for charts.
class StatsState {
  final SystemStats current;
  final List<SystemStats> history; // rolling buffer ~120 points
  final bool connected;

  const StatsState({
    required this.current,
    this.history = const [],
    this.connected = false,
  });

  StatsState copyWith({
    SystemStats? current,
    List<SystemStats>? history,
    bool? connected,
  }) =>
      StatsState(
        current: current ?? this.current,
        history: history ?? this.history,
        connected: connected ?? this.connected,
      );
}

final systemStatsProvider =
    StateNotifierProvider<SystemStatsNotifier, StatsState>((ref) {
  final notifier = SystemStatsNotifier(ref);
  // Auto-connect when logged in
  ref.listen(authProvider, (prev, next) {
    if (next.status == AuthStatus.loggedIn) {
      notifier.start();
    } else if (next.status == AuthStatus.loggedOut) {
      notifier.stop();
    }
  });
  return notifier;
});

class SystemStatsNotifier extends StateNotifier<StatsState> {
  final Ref _ref;
  WebSocketService? _ws;
  Timer? _pollTimer;
  static const _maxHistory = 120;

  SystemStatsNotifier(this._ref)
      : super(StatsState(current: SystemStats(timestamp: DateTime.now())));

  void start() {
    // Start WebSocket
    _ws?.disconnect();
    _ws = WebSocketService(
      onSystemStats: _onStats,
      onDisconnected: () {
        if (mounted) {
          state = state.copyWith(connected: false);
        }
      },
    );
    _ws!.connect();

    // Also poll /api/consumos/actual as fallback every 2s
    _pollTimer?.cancel();
    _pollTimer = Timer.periodic(const Duration(seconds: 2), (_) => _poll());
    _poll(); // immediate first fetch
  }

  void stop() {
    _ws?.disconnect();
    _ws = null;
    _pollTimer?.cancel();
    _pollTimer = null;
  }

  void _onStats(Map<String, dynamic> data) {
    final stats = SystemStats.fromJson(data);
    final newHistory = [...state.history, stats];
    if (newHistory.length > _maxHistory) {
      newHistory.removeRange(0, newHistory.length - _maxHistory);
    }
    state = state.copyWith(
      current: stats,
      history: newHistory,
      connected: true,
    );
  }

  Future<void> _poll() async {
    try {
      final dio = _ref.read(dioProvider);
      final response = await dio.get('/api/consumos/actual');
      if (response.statusCode == 200 && response.data is Map) {
        _onStats(response.data as Map<String, dynamic>);
      }
    } catch (_) {}
  }

  @override
  void dispose() {
    stop();
    super.dispose();
  }
}
