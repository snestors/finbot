import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/control_device.dart';
import '../models/zigbee_device.dart';
import '../services/mqtt_service.dart';

// ─── Zigbee-to-Control Mapping (dynamic from Firestore) ───────

class ZigbeeMapping {
  final String serialNumber;
  final int channel;

  const ZigbeeMapping({required this.serialNumber, required this.channel});
}

/// Check if a device has Zigbee mapping (from its model fields).
bool hasZigbeeDevice(ControlDevice device) {
  return device.zigbeeSerial != null && device.zigbeeChannel != null;
}

/// Get Zigbee mapping for a device.
ZigbeeMapping? zigbeeMappingForDevice(ControlDevice device) {
  if (device.zigbeeSerial != null && device.zigbeeChannel != null) {
    return ZigbeeMapping(
      serialNumber: device.zigbeeSerial!,
      channel: device.zigbeeChannel!,
    );
  }
  return null;
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

    // Set up MQTT
    final mqtt = _ref.read(mqttServiceProvider);
    mqtt.onDeviceState = _handleDeviceState;
    mqtt.onConnectionChanged = _handleConnectionChanged;
    mqtt.connect();
  }

  /// Subscribe to Zigbee devices from the current device list.
  /// Called when devices change to dynamically subscribe to new serials.
  void syncDevices(List<ControlDevice> devices) {
    final mqtt = _ref.read(mqttServiceProvider);
    final initial = <String, ZigbeeDevice>{};

    for (final d in devices) {
      if (d.zigbeeSerial == null || d.zigbeeChannel == null) continue;
      final key = '${d.zigbeeSerial}_${d.zigbeeChannel}';
      // Preserve existing state if we have it
      initial[key] = state[key] ??
          ZigbeeDevice(
            deviceId: d.zigbeeSerial!,
            name: d.name,
            model: '',
            outlet: d.zigbeeChannel!,
            isOn: false,
            online: mqtt.isConnected,
          );
      mqtt.subscribeToDevice(d.zigbeeSerial!);
    }
    state = initial;
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

  /// Toggle a Zigbee switch. Finds the device by control ID or name.
  bool toggle(String controlId, [String? controlName]) {
    // Find the mapping by looking through current devices
    // The devices_provider already checked hasZigbeeDevice, so find the mapping
    for (final entry in state.entries) {
      final device = entry.value;
      // Match by name (case-insensitive)
      if (controlName != null &&
          device.name.toLowerCase() == controlName.toLowerCase()) {
        final newState = !device.isOn;
        state = {...state, entry.key: device.copyWith(isOn: newState)};
        _ref.read(mqttServiceProvider).toggleSwitch(
            device.deviceId, device.outlet, newState);
        return newState;
      }
    }
    return false;
  }

  /// Toggle by explicit serial + channel.
  bool toggleByMapping(ZigbeeMapping mapping) {
    final key = '${mapping.serialNumber}_${mapping.channel}';
    final device = state[key];
    if (device == null) return false;

    final newState = !device.isOn;
    state = {...state, key: device.copyWith(isOn: newState)};
    _ref.read(mqttServiceProvider).toggleSwitch(
        mapping.serialNumber, mapping.channel, newState);
    return newState;
  }
}
