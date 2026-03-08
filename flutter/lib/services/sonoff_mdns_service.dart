import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter/foundation.dart';
import 'package:bonsoir/bonsoir.dart';
import 'package:crypto/crypto.dart';
import 'package:encrypt/encrypt.dart' as encrypt;
import 'firestore_service.dart';
import 'local_cache_service.dart';

/// Power reading from a Sonoff POW Elite device.
class SonoffReading {
  final double powerW;
  final double voltageV;
  final double currentA;
  final double dayKwh;
  final double monthKwh;
  final DateTime timestamp;

  const SonoffReading({
    required this.powerW,
    required this.voltageV,
    required this.currentA,
    required this.dayKwh,
    required this.monthKwh,
    required this.timestamp,
  });

  Map<String, dynamic> toJson() => {
        'power_w': powerW,
        'voltage_v': voltageV,
        'current_a': currentA,
        'day_kwh': dayKwh,
        'month_kwh': monthKwh,
      };
}

/// Reads Sonoff POW Elite power metrics via mDNS TXT records.
///
/// The device broadcasts encrypted data every ~1s under `_ewelink._tcp.local.`.
/// We decrypt using AES-128-CBC with the device key (MD5-hashed).
class SonoffMdnsService {
  final String deviceId;
  final String deviceKey;
  late final Uint8List _aesKey;

  BonsoirDiscovery? _discovery;
  final _controller = StreamController<SonoffReading>.broadcast();
  SonoffReading? _latest;
  Timer? _saveTimer;
  DateTime? _lastSaveTime;
  FirestoreService? _firestore;
  final _localCache = LocalCacheService();

  SonoffMdnsService({required this.deviceId, required this.deviceKey}) {
    // AES key = MD5 hash of device key
    _aesKey = Uint8List.fromList(
      md5.convert(utf8.encode(deviceKey)).bytes,
    );
  }

  /// Stream of power readings from the device.
  Stream<SonoffReading> get readings => _controller.stream;

  /// Latest reading (may be null if no data yet).
  SonoffReading? get latest => _latest;

  /// Set Firestore service for auto-save.
  void setFirestore(FirestoreService fs) {
    _firestore = fs;
  }

  /// Start mDNS discovery for eWeLink devices.
  Future<void> start() async {
    _discovery = BonsoirDiscovery(type: '_ewelink._tcp');
    await _discovery!.ready;

    _discovery!.eventStream?.listen((event) {
      if (event.type == BonsoirDiscoveryEventType.discoveryServiceResolved ||
          event.type == BonsoirDiscoveryEventType.discoveryServiceFound) {
        _handleService(event.service);
      }
    });

    await _discovery!.start();

    // Start auto-save timer (every 5 minutes)
    _saveTimer?.cancel();
    _saveTimer = Timer.periodic(
      const Duration(minutes: 5),
      (_) => _autoSave(),
    );

    // Sync any cached readings from previous offline period
    _syncCachedReadings();
  }

  /// Stop mDNS discovery and save timer.
  Future<void> stop() async {
    _saveTimer?.cancel();
    _saveTimer = null;
    await _discovery?.stop();
    _discovery = null;
  }

  void _handleService(BonsoirService? service) {
    if (service == null) return;

    final attributes = service.attributes;
    if (attributes.isEmpty) return;

    // Filter by our device ID
    final id = attributes['id'];
    if (id != deviceId) return;

    final reading = _decryptAndParse(attributes);
    if (reading != null) {
      _latest = reading;
      _controller.add(reading);
    }
  }

  SonoffReading? _decryptAndParse(Map<String, String> props) {
    try {
      final ivB64 = props['iv'];
      if (ivB64 == null || ivB64.isEmpty) return null;

      // Concatenate data1..data4 (split due to DNS 249-byte TXT limit)
      final dataB64 = StringBuffer();
      for (var i = 1; i <= 4; i++) {
        dataB64.write(props['data$i'] ?? '');
      }
      if (dataB64.isEmpty) return null;

      final iv = encrypt.IV.fromBase64(ivB64);
      final ciphertext = encrypt.Encrypted.fromBase64(dataB64.toString());
      final key = encrypt.Key(_aesKey);

      final encrypter = encrypt.Encrypter(
        encrypt.AES(key, mode: encrypt.AESMode.cbc, padding: 'PKCS7'),
      );
      final plaintext = encrypter.decrypt(ciphertext, iv: iv);

      final data = jsonDecode(plaintext) as Map<String, dynamic>;
      return _parseReading(data);
    } catch (_) {
      return null;
    }
  }

  SonoffReading _parseReading(Map<String, dynamic> data) {
    return SonoffReading(
      powerW: _div100(data['power']),
      voltageV: _div100(data['voltage']),
      currentA: _div100(data['current']),
      dayKwh: _div100(data['dayKwh'] ?? data['oneKwh']),
      monthKwh: _div100(data['monthKwh'] ?? data['hundredDaysKwh']),
      timestamp: DateTime.now(),
    );
  }

  static double _div100(dynamic val) {
    if (val == null) return 0.0;
    final n = num.tryParse(val.toString());
    return n != null ? n / 100 : 0.0;
  }

  /// Save latest reading to Firestore (or cache if offline).
  Future<void> _autoSave() async {
    final reading = _latest;
    if (reading == null) return;

    // Deduplicate: skip if last save was <4min ago
    if (_lastSaveTime != null &&
        DateTime.now().difference(_lastSaveTime!).inMinutes < 4) {
      return;
    }

    try {
      if (_firestore != null) {
        await _firestore!.saveConsumoReading(reading);
        _lastSaveTime = DateTime.now();
      } else {
        await _localCache.cacheReading(reading);
      }
    } catch (e) {
      // Firestore failed — cache locally
      debugPrint('[SonoffMdns] Save failed, caching locally: $e');
      await _localCache.cacheReading(reading);
    }
  }

  /// Sync cached readings to Firestore.
  Future<void> _syncCachedReadings() async {
    if (_firestore == null) return;
    try {
      final cached = await _localCache.drainCache();
      for (final reading in cached) {
        await _firestore!.saveConsumoReading(reading);
      }
      if (cached.isNotEmpty) {
        debugPrint('[SonoffMdns] Synced ${cached.length} cached readings');
      }
    } catch (e) {
      debugPrint('[SonoffMdns] Cache sync failed: $e');
    }
  }

  void dispose() {
    _saveTimer?.cancel();
    stop();
    _controller.close();
  }
}
