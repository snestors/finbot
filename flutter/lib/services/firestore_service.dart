import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/control_device.dart';
import '../services/sonoff_mdns_service.dart';

final firestoreServiceProvider = Provider<FirestoreService>((ref) {
  return FirestoreService();
});

class FirestoreService {
  final _db = FirebaseFirestore.instance;

  // ─── Devices ────────────────────────────────────────────────────

  CollectionReference<Map<String, dynamic>> get _devicesCol =>
      _db.collection('devices');

  /// Real-time stream of all devices ordered by sortOrder.
  Stream<List<ControlDevice>> watchDevices() {
    return _devicesCol.orderBy('sortOrder').snapshots().map((snap) {
      return snap.docs
          .map((doc) => ControlDevice.fromFirestore(doc.id, doc.data()))
          .toList();
    });
  }

  Future<String> addDevice(ControlDevice device) async {
    final doc = await _devicesCol.add({
      ...device.toFirestore(),
      'createdAt': FieldValue.serverTimestamp(),
    });
    return doc.id;
  }

  Future<void> updateDevice(ControlDevice device) async {
    await _devicesCol.doc(device.id).update(device.toFirestore());
  }

  Future<void> deleteDevice(String id) async {
    await _devicesCol.doc(id).delete();
  }

  Future<void> toggleDevice(String id, bool isActive) async {
    await _devicesCol.doc(id).update({'isActive': isActive});
  }

  Future<void> reorderDevices(List<ControlDevice> devices) async {
    final batch = _db.batch();
    for (var i = 0; i < devices.length; i++) {
      batch.update(_devicesCol.doc(devices[i].id), {'sortOrder': i});
    }
    await batch.commit();
  }

  // ─── Consumos ──────────────────────────────────────────────────

  CollectionReference<Map<String, dynamic>> get _consumosCol =>
      _db.collection('consumos');

  /// Save a Sonoff reading to Firestore.
  Future<void> saveConsumoReading(SonoffReading reading) async {
    await _consumosCol.add({
      'tipo': 'luz',
      'power_w': reading.powerW,
      'voltage_v': reading.voltageV,
      'current_a': reading.currentA,
      'day_kwh': reading.dayKwh,
      'month_kwh': reading.monthKwh,
      'timestamp': FieldValue.serverTimestamp(),
    });
  }

  /// Get consumo data for a billing period.
  Future<({double kwhTotal, int dias, List<Map<String, dynamic>> readings})>
      getConsumoPeriodo(DateTime desde, DateTime hasta) async {
    final snap = await _consumosCol
        .where('tipo', isEqualTo: 'luz')
        .where('timestamp', isGreaterThanOrEqualTo: Timestamp.fromDate(desde))
        .where('timestamp', isLessThan: Timestamp.fromDate(hasta))
        .orderBy('timestamp')
        .get();

    if (snap.docs.isEmpty) {
      return (kwhTotal: 0.0, dias: 0, readings: <Map<String, dynamic>>[]);
    }

    // Group by day to count distinct days and get daily kWh
    final dailyMap = <String, double>{};
    for (final doc in snap.docs) {
      final data = doc.data();
      final ts = (data['timestamp'] as Timestamp?)?.toDate();
      if (ts == null) continue;
      final dayKey = '${ts.year}-${ts.month}-${ts.day}';
      final dayKwh = (data['day_kwh'] as num?)?.toDouble() ?? 0;
      // Keep max day_kwh per day (it's cumulative within the day)
      if (!dailyMap.containsKey(dayKey) || dayKwh > dailyMap[dayKey]!) {
        dailyMap[dayKey] = dayKwh;
      }
    }

    final kwhTotal = dailyMap.values.fold(0.0, (sum, v) => sum + v);
    return (
      kwhTotal: kwhTotal,
      dias: dailyMap.length,
      readings: snap.docs.map((d) => d.data()).toList(),
    );
  }

  /// Get daily kWh for last N days (for weekly chart).
  Future<List<({DateTime date, double kwh})>> getDailyKwh(int days) async {
    final now = DateTime.now();
    final results = <({DateTime date, double kwh})>[];

    for (var i = days - 1; i >= 0; i--) {
      final date = DateTime(now.year, now.month, now.day - i);
      final nextDate = date.add(const Duration(days: 1));

      final snap = await _consumosCol
          .where('tipo', isEqualTo: 'luz')
          .where('timestamp',
              isGreaterThanOrEqualTo: Timestamp.fromDate(date))
          .where('timestamp', isLessThan: Timestamp.fromDate(nextDate))
          .orderBy('timestamp', descending: true)
          .limit(1)
          .get();

      double kwh = 0;
      if (snap.docs.isNotEmpty) {
        kwh = (snap.docs.first.data()['day_kwh'] as num?)?.toDouble() ?? 0;
      }
      results.add((date: date, kwh: kwh));
    }
    return results;
  }

  // ─── Config ────────────────────────────────────────────────────

  DocumentReference<Map<String, dynamic>> get _configDoc =>
      _db.collection('config').doc('settings');

  Future<Map<String, dynamic>> getConfig() async {
    final snap = await _configDoc.get();
    return snap.data() ?? {};
  }

  Future<void> updateConfig(Map<String, dynamic> data) async {
    await _configDoc.set(data, SetOptions(merge: true));
  }
}
