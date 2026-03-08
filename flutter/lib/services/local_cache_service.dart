import 'dart:convert';
import 'package:shared_preferences/shared_preferences.dart';
import 'sonoff_mdns_service.dart';

/// Buffers Sonoff readings locally when offline. Syncs to Firestore
/// when connectivity returns.
class LocalCacheService {
  static const _cacheKey = 'cached_readings';

  /// Save a reading to local cache.
  Future<void> cacheReading(SonoffReading reading) async {
    final prefs = await SharedPreferences.getInstance();
    final cached = prefs.getStringList(_cacheKey) ?? [];
    cached.add(jsonEncode({
      ...reading.toJson(),
      'timestamp': reading.timestamp.toIso8601String(),
    }));
    // Keep max 500 cached entries (~40 hours at 5min intervals)
    if (cached.length > 500) {
      cached.removeRange(0, cached.length - 500);
    }
    await prefs.setStringList(_cacheKey, cached);
  }

  /// Get all cached readings and clear the cache.
  Future<List<SonoffReading>> drainCache() async {
    final prefs = await SharedPreferences.getInstance();
    final cached = prefs.getStringList(_cacheKey) ?? [];
    if (cached.isEmpty) return [];

    final readings = <SonoffReading>[];
    for (final entry in cached) {
      try {
        final json = jsonDecode(entry) as Map<String, dynamic>;
        readings.add(SonoffReading(
          powerW: (json['power_w'] as num?)?.toDouble() ?? 0,
          voltageV: (json['voltage_v'] as num?)?.toDouble() ?? 0,
          currentA: (json['current_a'] as num?)?.toDouble() ?? 0,
          dayKwh: (json['day_kwh'] as num?)?.toDouble() ?? 0,
          monthKwh: (json['month_kwh'] as num?)?.toDouble() ?? 0,
          timestamp: DateTime.tryParse(json['timestamp'] ?? '') ?? DateTime.now(),
        ));
      } catch (_) {}
    }

    await prefs.setStringList(_cacheKey, []);
    return readings;
  }

  /// Check if there are cached readings pending sync.
  Future<int> pendingCount() async {
    final prefs = await SharedPreferences.getInstance();
    return (prefs.getStringList(_cacheKey) ?? []).length;
  }
}
