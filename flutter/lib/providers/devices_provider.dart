import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../models/control_device.dart';

const _storageKey = 'control_devices';

final devicesProvider =
    StateNotifierProvider<DevicesNotifier, List<ControlDevice>>((ref) {
  return DevicesNotifier();
});

class DevicesNotifier extends StateNotifier<List<ControlDevice>> {
  DevicesNotifier() : super(_defaultDevices) {
    _load();
  }

  static final _defaultDevices = [
    ControlDevice(
      id: 'sala',
      name: 'Sala',
      iconName: 'sofa',
      colorHex: '#FFFFFF',
      isActive: true,
    ),
    ControlDevice(
      id: 'cocina',
      name: 'Cocina',
      iconName: 'soup',
      colorHex: '#22C55E',
    ),
    ControlDevice(
      id: 'frente',
      name: 'Frente',
      iconName: 'palmtree',
      colorHex: '#06B6D4',
    ),
  ];

  Future<void> _load() async {
    final prefs = await SharedPreferences.getInstance();
    final json = prefs.getString(_storageKey);
    if (json != null) {
      state = ControlDevice.decodeList(json);
    }
  }

  Future<void> _save() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_storageKey, ControlDevice.encodeList(state));
  }

  void toggle(String id) {
    state = [
      for (final d in state)
        if (d.id == id) d.copyWith(isActive: !d.isActive) else d,
    ];
    _save();
  }

  void add(ControlDevice device) {
    state = [...state, device];
    _save();
  }

  void update(ControlDevice device) {
    state = [
      for (final d in state)
        if (d.id == device.id) device else d,
    ];
    _save();
  }

  void remove(String id) {
    state = state.where((d) => d.id != id).toList();
    _save();
  }

  void reorder(int oldIndex, int newIndex) {
    final items = [...state];
    if (newIndex > oldIndex) newIndex--;
    final item = items.removeAt(oldIndex);
    items.insert(newIndex, item);
    state = items;
    _save();
  }
}
