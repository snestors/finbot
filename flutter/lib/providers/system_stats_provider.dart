import 'dart:async';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/constants.dart';
import '../services/firestore_service.dart';
import '../services/sonoff_mdns_service.dart';
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

  factory SystemStats.fromReading(SonoffReading r) => SystemStats(
        powerW: r.powerW,
        voltageV: r.voltageV,
        currentA: r.currentA,
        dayKwh: r.dayKwh,
        monthKwh: r.monthKwh,
        timestamp: r.timestamp,
      );

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
  final List<SystemStats> history;
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

/// Singleton Sonoff mDNS service provider.
final sonoffServiceProvider = Provider<SonoffMdnsService>((ref) {
  final service = SonoffMdnsService(
    deviceId: Constants.sonoffDeviceId,
    deviceKey: Constants.sonoffDeviceKey,
  );
  ref.onDispose(() => service.dispose());
  return service;
});

final systemStatsProvider =
    StateNotifierProvider<SystemStatsNotifier, StatsState>((ref) {
  final notifier = SystemStatsNotifier(ref);
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
  StreamSubscription<SonoffReading>? _sub;
  static const _maxHistory = 120;

  SystemStatsNotifier(this._ref)
      : super(StatsState(current: SystemStats(timestamp: DateTime.now())));

  void start() {
    stop();
    final sonoff = _ref.read(sonoffServiceProvider);
    // Wire Firestore for auto-save
    sonoff.setFirestore(_ref.read(firestoreServiceProvider));
    _sub = sonoff.readings.listen(_onReading);
    sonoff.start();
  }

  void stop() {
    _sub?.cancel();
    _sub = null;
  }

  void _onReading(SonoffReading reading) {
    if (!mounted) return;
    final stats = SystemStats.fromReading(reading);
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

  @override
  void dispose() {
    stop();
    super.dispose();
  }
}
