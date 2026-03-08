import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/zigbee_device.dart';
import '../services/mqtt_service.dart';

// ─── Zigbee-to-Control Mapping ──────────────────────────────────
// Maps control IDs (from the backend) to Zigbee device + outlet.
// Controls not in this map have no Zigbee device and stay UI-only.

class ZigbeeMapping {
  final String deviceId;
  final int outlet;

  const ZigbeeMapping({required this.deviceId, required this.outlet});
}

/// Static mapping of backend control names (lowercased) to Zigbee device outlets.
/// Only controls with a physical Zigbee device are listed here.
/// The key is the control name lowercased (e.g. "Sala" -> "sala").
const Map<String, ZigbeeMapping> controlToZigbee = {
  'sala': ZigbeeMapping(deviceId: 'a44003f19f', outlet: 0),
  'afuera': ZigbeeMapping(deviceId: 'a44003f19f', outlet: 1),
};

/// Look up a ZigbeeMapping for a ControlDevice by matching its name
/// (lowercased) against the mapping keys. Falls back to matching by ID.
ZigbeeMapping? zigbeeMappingFor(String id, String name) {
  // Try name match first (lowercased)
  final byName = controlToZigbee[name.toLowerCase()];
  if (byName != null) return byName;
  // Fallback: try by ID
  return controlToZigbee[id.toLowerCase()];
}

/// Reverse lookup: given a device ID + outlet, get the mapping key.
String? zigbeeToControlKey(String deviceId, int outlet) {
  for (final entry in controlToZigbee.entries) {
    if (entry.value.deviceId == deviceId && entry.value.outlet == outlet) {
      return entry.key;
    }
  }
  return null;
}

/// Check if a control has a Zigbee device mapped (by name or ID).
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

/// Holds the state of all known Zigbee device outlets.
/// Key: "{deviceId}_{outlet}", Value: ZigbeeDevice
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

    // Seed the initial state from the mapping (all off, online)
    final initial = <String, ZigbeeDevice>{};
    for (final entry in controlToZigbee.entries) {
      final m = entry.value;
      final device = ZigbeeDevice(
        deviceId: m.deviceId,
        name: entry.key,
        model: 'SONOFF MINI-ZB2GS-L',
        outlet: m.outlet,
        isOn: false,
        online: false, // Unknown until MQTT connects
      );
      initial[device.key] = device;
    }
    state = initial;

    // Set up MQTT
    final mqtt = _ref.read(mqttServiceProvider);
    mqtt.onDeviceState = _handleDeviceState;
    mqtt.onConnectionChanged = _handleConnectionChanged;

    // Subscribe to all known Zigbee devices
    final deviceIds = controlToZigbee.values.map((m) => m.deviceId).toSet();
    for (final deviceId in deviceIds) {
      mqtt.subscribeToDevice(deviceId);
    }

    // Connect
    mqtt.connect();
  }

  void _handleConnectionChanged(bool connected) {
    _ref.read(mqttConnectedProvider.notifier).state = connected;

    if (connected) {
      // Mark all devices as online when MQTT connects
      final updated = <String, ZigbeeDevice>{};
      for (final entry in state.entries) {
        updated[entry.key] = entry.value.copyWith(online: true);
      }
      state = updated;
    }
  }

  void _handleDeviceState(String deviceId, Map<String, dynamic> params) {
    // Parse the switches array from params
    final switches = params['switches'] as List<dynamic>?;
    if (switches != null) {
      final updated = Map<String, ZigbeeDevice>.from(state);
      for (final sw in switches) {
        if (sw is Map<String, dynamic>) {
          final outlet = sw['outlet'] as int?;
          final switchState = sw['switch'] as String?;
          if (outlet != null && switchState != null) {
            final key = '${deviceId}_$outlet';
            final existing = updated[key];
            if (existing != null) {
              updated[key] = existing.copyWith(
                isOn: switchState == 'on',
                online: true,
              );
            }
          }
        }
      }
      state = updated;
    }

    // Also handle flat params like {"switch": "on"} for single-channel
    if (params.containsKey('switch') && !params.containsKey('switches')) {
      final switchState = params['switch'] as String?;
      if (switchState != null) {
        final key = '${deviceId}_0';
        final existing = state[key];
        if (existing != null) {
          state = {
            ...state,
            key: existing.copyWith(
              isOn: switchState == 'on',
              online: true,
            ),
          };
        }
      }
    }
  }

  /// Toggle a Zigbee switch via MQTT. Returns the new expected state.
  /// This performs an optimistic update and sends the MQTT command.
  /// Accepts control ID and optional name for flexible matching.
  bool toggle(String controlId, [String? controlName]) {
    final mapping = zigbeeMappingFor(controlId, controlName ?? controlId);
    if (mapping == null) return false;

    final key = '${mapping.deviceId}_${mapping.outlet}';
    final device = state[key];
    if (device == null) return false;

    final newState = !device.isOn;

    // Optimistic local update
    state = {
      ...state,
      key: device.copyWith(isOn: newState),
    };

    // Send MQTT command
    final mqtt = _ref.read(mqttServiceProvider);
    mqtt.toggleSwitch(mapping.deviceId, mapping.outlet, newState);

    return newState;
  }

  /// Get the current on/off state for a control (by ID or name).
  bool? getState(String controlId, [String? controlName]) {
    final mapping = zigbeeMappingFor(controlId, controlName ?? controlId);
    if (mapping == null) return null;
    final key = '${mapping.deviceId}_${mapping.outlet}';
    return state[key]?.isOn;
  }
}
