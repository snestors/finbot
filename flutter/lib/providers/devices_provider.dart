import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/control_device.dart';
import '../services/firestore_service.dart';
import 'zigbee_provider.dart';

final devicesProvider =
    StateNotifierProvider<DevicesNotifier, List<ControlDevice>>((ref) {
  return DevicesNotifier(ref);
});

class DevicesNotifier extends StateNotifier<List<ControlDevice>> {
  final Ref _ref;
  StreamSubscription? _sub;

  DevicesNotifier(this._ref) : super([]) {
    _listenToFirestore();
  }

  FirestoreService get _fs => _ref.read(firestoreServiceProvider);

  void _listenToFirestore() {
    _sub = _fs.watchDevices().listen(
      (devices) {
        if (mounted) state = devices;
      },
      onError: (e) => debugPrint('[DevicesNotifier] Firestore error: $e'),
    );
  }

  /// Toggle a control on/off via MQTT + Firestore.
  Future<void> toggle(String id) async {
    final device = state.where((d) => d.id == id).firstOrNull;
    if (device == null) return;
    final deviceName = device.name;

    // Fire MQTT command instantly if mapped
    final mapping = zigbeeMappingForDevice(device);
    if (mapping != null) {
      _ref.read(zigbeeStateProvider.notifier).toggleByMapping(mapping);
    }

    // Optimistic UI update
    final newActive = !device.isActive;
    state = [
      for (final d in state)
        if (d.id == id) d.copyWith(isActive: newActive) else d,
    ];

    // Persist to Firestore
    try {
      await _fs.toggleDevice(id, newActive);
    } catch (e) {
      debugPrint('[DevicesNotifier] toggle error: $e');
      state = [
        for (final d in state)
          if (d.id == id) d.copyWith(isActive: !newActive) else d,
      ];
    }
  }

  /// Add a new control to Firestore.
  Future<void> add(ControlDevice device) async {
    try {
      await _fs.addDevice(device.copyWith(sortOrder: state.length));
    } catch (e) {
      debugPrint('[DevicesNotifier] add error: $e');
    }
  }

  /// Update a control's metadata in Firestore.
  Future<void> update(ControlDevice device) async {
    final previous = state;
    state = [
      for (final d in state)
        if (d.id == device.id) device else d,
    ];
    try {
      await _fs.updateDevice(device);
    } catch (_) {
      state = previous;
    }
  }

  /// Delete a control from Firestore.
  Future<void> remove(String id) async {
    final previous = state;
    state = state.where((d) => d.id != id).toList();
    try {
      await _fs.deleteDevice(id);
    } catch (_) {
      state = previous;
    }
  }

  /// Reorder controls in Firestore.
  Future<void> reorder(int oldIndex, int newIndex) async {
    final items = [...state];
    if (newIndex > oldIndex) newIndex--;
    final item = items.removeAt(oldIndex);
    items.insert(newIndex, item);
    state = items;
    try {
      await _fs.reorderDevices(items);
    } catch (_) {
      // Firestore stream will correct on next snapshot
    }
  }

  /// Replace a single control in the local state.
  void updateLocal(String id, {bool? isActive}) {
    state = [
      for (final d in state)
        if (d.id == id) d.copyWith(isActive: isActive) else d,
    ];
  }

  @override
  void dispose() {
    _sub?.cancel();
    super.dispose();
  }
}
