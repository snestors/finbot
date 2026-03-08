import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:lucide_icons/lucide_icons.dart';
import '../../core/app_colors.dart';
import '../../models/control_device.dart';
import '../../providers/devices_provider.dart';
import '../../providers/zigbee_provider.dart';
import '../../services/mqtt_service.dart';

/// Bottom sheet showing discovered Zigbee devices from MQTT.
/// Allows adding them as controls with a name, icon, and color.
class AddDeviceSheet extends ConsumerStatefulWidget {
  const AddDeviceSheet({super.key});

  @override
  ConsumerState<AddDeviceSheet> createState() => _AddDeviceSheetState();
}

class _AddDeviceSheetState extends ConsumerState<AddDeviceSheet> {
  StreamSubscription<ZigbeeDiscovery>? _sub;
  final _discovered = <String, ZigbeeDiscovery>{};
  bool _scanning = false;

  @override
  void initState() {
    super.initState();
    _startScan();
  }

  void _startScan() {
    final mqtt = ref.read(mqttServiceProvider);
    setState(() {
      _scanning = true;
      _discovered.addAll(mqtt.discoveredDevices);
    });

    mqtt.startDiscovery();
    _sub = mqtt.discoveries.listen((discovery) {
      if (mounted) {
        setState(() => _discovered[discovery.serial] = discovery);
      }
    });

    // Auto-stop scan after 15 seconds
    Future.delayed(const Duration(seconds: 15), () {
      if (mounted && _scanning) {
        mqtt.stopDiscovery();
        setState(() => _scanning = false);
      }
    });
  }

  @override
  void dispose() {
    _sub?.cancel();
    ref.read(mqttServiceProvider).stopDiscovery();
    super.dispose();
  }

  /// Filter out devices/channels that are already assigned to controls.
  List<({ZigbeeDiscovery device, int channel})> _getUnassigned() {
    final devices = ref.read(devicesProvider);
    final assigned = <String>{};
    for (final d in devices) {
      if (d.zigbeeSerial != null && d.zigbeeChannel != null) {
        assigned.add('${d.zigbeeSerial}_${d.zigbeeChannel}');
      }
    }

    final results = <({ZigbeeDiscovery device, int channel})>[];
    for (final entry in _discovered.values) {
      for (final ch in entry.channels) {
        final key = '${entry.serial}_$ch';
        if (!assigned.contains(key)) {
          results.add((device: entry, channel: ch));
        }
      }
    }
    return results;
  }

  void _addDevice(ZigbeeDiscovery discovery, int channel) {
    final device = ControlDevice(
      id: '',
      name: '${discovery.name} Ch$channel',
      zigbeeSerial: discovery.serial,
      zigbeeChannel: channel,
    );
    ref.read(devicesProvider.notifier).add(device);
    Navigator.of(context).pop();
  }

  @override
  Widget build(BuildContext context) {
    final unassigned = _getUnassigned();
    final mqttConnected = ref.watch(mqttConnectedProvider);

    return Container(
      constraints: BoxConstraints(
        maxHeight: MediaQuery.of(context).size.height * 0.7,
      ),
      decoration: const BoxDecoration(
        color: AppColors.bgPrimary,
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          // Handle bar
          Container(
            margin: const EdgeInsets.only(top: 12),
            width: 40,
            height: 4,
            decoration: BoxDecoration(
              color: AppColors.textMuted,
              borderRadius: BorderRadius.circular(2),
            ),
          ),
          // Header
          Padding(
            padding: const EdgeInsets.fromLTRB(24, 16, 24, 8),
            child: Row(
              children: [
                const Icon(LucideIcons.radio, color: AppColors.accentBlue, size: 20),
                const SizedBox(width: 10),
                const Text(
                  'Dispositivos Zigbee',
                  style: TextStyle(
                    color: AppColors.textPrimary,
                    fontSize: 17,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const Spacer(),
                if (_scanning)
                  const SizedBox(
                    width: 16,
                    height: 16,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      color: AppColors.accentBlue,
                    ),
                  ),
                if (!mqttConnected)
                  const Text(
                    'MQTT desconectado',
                    style: TextStyle(
                      color: AppColors.accentRed,
                      fontSize: 11,
                    ),
                  ),
              ],
            ),
          ),
          const Divider(color: AppColors.bgCardLight, height: 1),
          // Device list
          if (unassigned.isEmpty)
            Padding(
              padding: const EdgeInsets.all(32),
              child: Column(
                children: [
                  const Icon(LucideIcons.searchX,
                      color: AppColors.textMuted, size: 36),
                  const SizedBox(height: 12),
                  Text(
                    _scanning
                        ? 'Buscando dispositivos...'
                        : 'No se encontraron dispositivos nuevos',
                    style: const TextStyle(
                      color: AppColors.textSecondary,
                      fontSize: 14,
                    ),
                  ),
                ],
              ),
            )
          else
            Flexible(
              child: ListView.separated(
                shrinkWrap: true,
                padding: const EdgeInsets.symmetric(vertical: 8),
                itemCount: unassigned.length,
                separatorBuilder: (_, __) =>
                    const Divider(color: AppColors.bgCardLight, height: 1),
                itemBuilder: (_, index) {
                  final item = unassigned[index];
                  return _DiscoveredTile(
                    discovery: item.device,
                    channel: item.channel,
                    onAdd: () => _addDevice(item.device, item.channel),
                  );
                },
              ),
            ),
        ],
      ),
    );
  }
}

class _DiscoveredTile extends StatelessWidget {
  final ZigbeeDiscovery discovery;
  final int channel;
  final VoidCallback onAdd;

  const _DiscoveredTile({
    required this.discovery,
    required this.channel,
    required this.onAdd,
  });

  @override
  Widget build(BuildContext context) {
    return ListTile(
      contentPadding: const EdgeInsets.symmetric(horizontal: 24, vertical: 4),
      leading: Container(
        width: 44,
        height: 44,
        decoration: BoxDecoration(
          color: AppColors.bgCard,
          borderRadius: BorderRadius.circular(12),
        ),
        child: const Icon(LucideIcons.plug, color: AppColors.accentCyan, size: 20),
      ),
      title: Text(
        '${discovery.name} - Canal $channel',
        style: const TextStyle(
          color: AppColors.textPrimary,
          fontSize: 14,
          fontWeight: FontWeight.w600,
        ),
      ),
      subtitle: Text(
        discovery.model.isNotEmpty ? discovery.model : discovery.serial,
        style: const TextStyle(color: AppColors.textMuted, fontSize: 12),
      ),
      trailing: GestureDetector(
        onTap: onAdd,
        behavior: HitTestBehavior.opaque,
        child: Container(
          width: 48,
          height: 48,
          decoration: BoxDecoration(
            color: AppColors.accentBlue.withValues(alpha: 0.15),
            borderRadius: BorderRadius.circular(12),
          ),
          child: const Icon(LucideIcons.plus, color: AppColors.accentBlue, size: 20),
        ),
      ),
    );
  }
}
