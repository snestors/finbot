import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/zigbee_device.dart';
import '../services/mqtt_service.dart';

// ─── Zigbee-to-Control Mapping ──────────────────────────────────
// Maps control IDs/names to Zigbee serial number + channel.

class ZigbeeMapping {
  final String serialNumber;
  final int channel; // 1-based (matches MQTT topic)

  const ZigbeeMapping({required this.serialNumber, required this.channel});
}

const Map<String, ZigbeeMapping> controlToZigbee = {
  'sala': ZigbeeMapping(serialNumber: '0xb48931fffe3df100', channel: 1),
  'afuera': ZigbeeMapping(serialNumber: '0xb48931fffe3df100', channel: 2),
};

ZigbeeMapping? zigbeeMappingFor(String id, String name) {
  return controlToZigbee[name.toLowerCase()] ??
      controlToZigbee[id.toLowerCase()];
}

bool hasZigbeeDevice(String id, [String? name]) {
  if (controlToZigbee.containsKey(id.toLowerCase())) return true;
  if (name != null && controlToZigbee.containsKey(name.toLowerCase())) {
    return true;
  }
  return false;
}

// ─── MQTT Service Provider (singleton) ──────────────────────────

final mqttServiceProvider = Provider<MqttService>((ref) {
  final service = MqttService();
  ref.onDispose(() => service.disconnect());
  return service;
});

// ─── MQTT Connection State ──────────────────────────────────────

final mqttConnectedProvider = StateProvider<bool>((ref) => false);

// ─── Zigbee State (device states from MQTT) ─────────────────────

/// Key: "{serialNumber}_{channel}", Value: ZigbeeDevice
final zigbeeStateProvider =
    StateNotifierProvider<ZigbeeStateNotifier, Map<String, ZigbeeDevice>>(
        (ref) {
  return ZigbeeStateNotifier(ref);
});

class ZigbeeStateNotifier extends StateNotifier<Map<String, ZigbeeDevice>> {
  final Ref _ref;
  bool _initialized = false;

  ZigbeeStateNotifier(this._ref) : super({}) {
    _initialize();
  }

  void _initialize() {
    if (_initialized) return;
    _initialized = true;

    // Seed initial state from the mapping
    final initial = <String, ZigbeeDevice>{};
    for (final entry in controlToZigbee.entries) {
      final m = entry.value;
      final key = '${m.serialNumber}_${m.channel}';
      initial[key] = ZigbeeDevice(
        deviceId: m.serialNumber,
        name: entry.key,
        model: 'SONOFF MINI-ZB2GS-L',
        outlet: m.channel,
        isOn: false,
        online: false,
      );
    }
    state = initial;

    // Set up MQTT
    final mqtt = _ref.read(mqttServiceProvider);
    mqtt.onDeviceState = _handleDeviceState;
    mqtt.onConnectionChanged = _handleConnectionChanged;

    // Subscribe to all known devices
    final serials = controlToZigbee.values.map((m) => m.serialNumber).toSet();
    for (final serial in serials) {
      mqtt.subscribeToDevice(serial);
    }

    mqtt.connect();
  }

  void _handleConnectionChanged(bool connected) {
    _ref.read(mqttConnectedProvider.notifier).state = connected;
    if (connected) {
      state = {
        for (final e in state.entries)
          e.key: e.value.copyWith(online: true),
      };
    }
  }

  /// Callback from MqttService: serial, channel (1-based), isOn
  void _handleDeviceState(String serialNumber, int channel, bool isOn) {
    final key = '${serialNumber}_$channel';
    final existing = state[key];
    if (existing != null) {
      state = {
        ...state,
        key: existing.copyWith(isOn: isOn, online: true),
      };
    }
  }

  /// Toggle a Zigbee switch. Optimistic update + MQTT command.
  bool toggle(String controlId, [String? controlName]) {
    final mapping = zigbeeMappingFor(controlId, controlName ?? controlId);
    if (mapping == null) return false;

    final key = '${mapping.serialNumber}_${mapping.channel}';
    final device = state[key];
    if (device == null) return false;

    final newState = !device.isOn;

    // Optimistic update
    state = {...state, key: device.copyWith(isOn: newState)};

    // Send MQTT v5 command
    _ref.read(mqttServiceProvider).toggleSwitch(
        mapping.serialNumber, mapping.channel, newState);

    return newState;
  }
}
