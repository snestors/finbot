import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/control_device.dart';
import '../services/controls_api.dart';
import 'zigbee_provider.dart';

final devicesProvider =
    StateNotifierProvider<DevicesNotifier, List<ControlDevice>>((ref) {
  return DevicesNotifier(ref.watch(controlsApiProvider), ref);
});

class DevicesNotifier extends StateNotifier<List<ControlDevice>> {
  final ControlsApi _api;
  final Ref _ref;

  DevicesNotifier(this._api, this._ref) : super([]) {
    load();
  }

  /// Fetch all controls from the backend.
  Future<void> load() async {
    try {
      state = await _api.fetchAll();
    } catch (_) {
      // Keep current state on error
    }
  }

  /// Toggle a control on/off.
  ///
  /// If the control has a mapped Zigbee device, the MQTT command fires
  /// immediately (local, sub-millisecond) for instant physical response.
  /// The backend API call follows for state persistence.
  Future<void> toggle(String id) async {
    // 1. Fire MQTT command instantly if this control has a Zigbee device
    final device = state.where((d) => d.id == id).firstOrNull;
    final deviceName = device?.name ?? '';
    if (hasZigbeeDevice(id, deviceName)) {
      _ref.read(zigbeeStateProvider.notifier).toggle(id, deviceName);
    }

    // 2. Optimistic UI update
    state = [
      for (final d in state)
        if (d.id == id) d.copyWith(isActive: !d.isActive) else d,
    ];

    // 3. Persist to backend (non-blocking for the user)
    try {
      final updated = await _api.toggle(id);
      state = [
        for (final d in state)
          if (d.id == id) updated else d,
      ];
    } catch (e) {
      debugPrint('[DevicesNotifier] toggle($id) error: $e');
      // Revert on error (MQTT already fired, but backend failed)
      state = [
        for (final d in state)
          if (d.id == id) d.copyWith(isActive: !d.isActive) else d,
      ];
    }
  }

  /// Add a new control via the backend.
  Future<void> add(ControlDevice device) async {
    try {
      final newId = await _api.create(device);
      // Refetch to get the full server object with correct id
      state = await _api.fetchAll();
    } catch (_) {}
  }

  /// Update a control's metadata via the backend.
  Future<void> update(ControlDevice device) async {
    // Optimistic update
    final previous = state;
    state = [
      for (final d in state)
        if (d.id == device.id) device else d,
    ];
    try {
      await _api.update(device);
    } catch (_) {
      state = previous;
    }
  }

  /// Delete a control via the backend.
  Future<void> remove(String id) async {
    final previous = state;
    state = state.where((d) => d.id != id).toList();
    try {
      await _api.delete(id);
    } catch (_) {
      state = previous;
    }
  }

  /// Reorder controls via the backend.
  Future<void> reorder(int oldIndex, int newIndex) async {
    final items = [...state];
    if (newIndex > oldIndex) newIndex--;
    final item = items.removeAt(oldIndex);
    items.insert(newIndex, item);
    state = items;
    try {
      await _api.reorder(items.map((d) => d.id).toList());
    } catch (_) {
      // Refetch on error
      await load();
    }
  }

  /// Replace a single control in the local state (used by WS events).
  void updateLocal(String id, {bool? isActive}) {
    state = [
      for (final d in state)
        if (d.id == id) d.copyWith(isActive: isActive) else d,
    ];
  }
}
