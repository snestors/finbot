import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:lucide_icons/lucide_icons.dart';
import '../../core/app_colors.dart';
import '../../models/control_device.dart';
import '../../providers/devices_provider.dart';
import '../../providers/zigbee_provider.dart';
import '../../widgets/device_control_button.dart';
import '../config/config_screen.dart';
import 'widgets/status_bar_row.dart';
import 'widgets/time_weather_row.dart';
import 'widgets/realtime_chart_card.dart';

/// Home screen optimized for NSPanel landscape display (480x320).
/// Uses adaptive layout: landscape shows side-by-side panels,
/// portrait falls back to scrollable column.
class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final rawDevices = ref.watch(devicesProvider);
    final zigbeeState = ref.watch(zigbeeStateProvider);

    // Merge Zigbee state into control devices for Zigbee-mapped controls.
    // This ensures the UI reflects the actual physical device state from MQTT.
    final devices = rawDevices.map((d) {
      if (d.zigbeeSerial != null && d.zigbeeChannel != null) {
        final key = '${d.zigbeeSerial}_${d.zigbeeChannel}';
        final zState = zigbeeState[key];
        if (zState != null) {
          return d.copyWith(isActive: zState.isOn);
        }
      }
      return d;
    }).toList();

    final size = MediaQuery.of(context).size;
    final isLandscape = size.width > size.height;

    if (isLandscape) {
      return _buildLandscapeLayout(context, ref, devices);
    }
    return _buildPortraitLayout(context, ref, devices);
  }

  /// Landscape: two-column layout — left (time + chart), right (controls)
  Widget _buildLandscapeLayout(
      BuildContext context, WidgetRef ref, List<ControlDevice> devices) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Left panel: time + realtime chart
          Expanded(
            flex: 5,
            child: SingleChildScrollView(
              child: Column(
                children: const [
                  TimeWeatherRow(),
                  SizedBox(height: 12),
                  RealtimeChartCard(),
                ],
              ),
            ),
          ),
          const SizedBox(width: 12),
          // Right panel: controls
          Expanded(
            flex: 4,
            child: Column(
              children: [
                _buildControlHeader(context, ref),
                const SizedBox(height: 8),
                Expanded(
                  child: devices.isEmpty
                      ? _buildEmptyState(context)
                      : _buildControlsList(ref, devices),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  /// Portrait: scrollable column layout (original style)
  Widget _buildPortraitLayout(
      BuildContext context, WidgetRef ref, List<ControlDevice> devices) {
    return Column(
      children: [
        const StatusBarRow(),
        Expanded(
          child: SingleChildScrollView(
            padding: const EdgeInsets.fromLTRB(24, 0, 24, 24),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const TimeWeatherRow(),
                const SizedBox(height: 24),
                const RealtimeChartCard(),
                const SizedBox(height: 24),
                _buildControlSection(context, ref, devices),
              ],
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildControlHeader(BuildContext context, WidgetRef ref) {
    final mqttConnected = ref.watch(mqttConnectedProvider);
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Row(
          children: [
            const Text(
              'Control',
              style: TextStyle(
                color: AppColors.textPrimary,
                fontSize: 16,
                fontWeight: FontWeight.w700,
              ),
            ),
            const SizedBox(width: 8),
            // MQTT connection indicator dot
            Container(
              width: 8,
              height: 8,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: mqttConnected
                    ? AppColors.accentGreen
                    : AppColors.accentRed,
              ),
            ),
          ],
        ),
        GestureDetector(
          onTap: () => Navigator.of(context).push(
            MaterialPageRoute(builder: (_) => const ConfigScreen()),
          ),
          child: Container(
            width: 36,
            height: 36,
            decoration: BoxDecoration(
              color: AppColors.bgCard,
              borderRadius: BorderRadius.circular(10),
            ),
            child: const Icon(
              LucideIcons.settings,
              color: AppColors.textSecondary,
              size: 16,
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildControlSection(
      BuildContext context, WidgetRef ref, List<ControlDevice> devices) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _buildControlHeader(context, ref),
        const SizedBox(height: 14),
        if (devices.isEmpty)
          _buildEmptyState(context)
        else
          _buildDeviceGrid(ref, devices),
      ],
    );
  }

  Widget _buildEmptyState(BuildContext context) {
    return GestureDetector(
      onTap: () => Navigator.of(context).push(
        MaterialPageRoute(builder: (_) => const ConfigScreen()),
      ),
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.symmetric(vertical: 24),
        decoration: BoxDecoration(
          color: AppColors.bgCard,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: AppColors.borderSubtle, width: 1),
        ),
        child: Column(
          children: const [
            Icon(LucideIcons.plus, color: AppColors.textMuted, size: 28),
            SizedBox(height: 8),
            Text(
              'Agregar dispositivos',
              style: TextStyle(
                color: AppColors.textMuted,
                fontSize: 13,
                fontWeight: FontWeight.w500,
              ),
            ),
          ],
        ),
      ),
    );
  }

  /// Scrollable list of controls for landscape right panel.
  /// Each control is a full-width row with 48dp touch target.
  Widget _buildControlsList(WidgetRef ref, List<ControlDevice> devices) {
    return ListView.separated(
      itemCount: devices.length,
      separatorBuilder: (_, __) => const SizedBox(height: 8),
      itemBuilder: (_, index) {
        final device = devices[index];
        return DeviceControlButton(
          device: device,
          onTap: () => ref.read(devicesProvider.notifier).toggle(device.id),
        );
      },
    );
  }

  /// Portrait grid: rows of 3 controls
  Widget _buildDeviceGrid(WidgetRef ref, List<ControlDevice> devices) {
    final rows = <Widget>[];
    for (var i = 0; i < devices.length; i += 3) {
      final rowItems = devices.sublist(
          i, i + 3 > devices.length ? devices.length : i + 3);
      rows.add(
        Row(
          children: [
            for (var j = 0; j < rowItems.length; j++) ...[
              if (j > 0) const SizedBox(width: 12),
              Expanded(
                child: DeviceControlButton(
                  device: rowItems[j],
                  onTap: () =>
                      ref.read(devicesProvider.notifier).toggle(rowItems[j].id),
                ),
              ),
            ],
            for (var j = rowItems.length; j < 3; j++) ...[
              const SizedBox(width: 12),
              const Expanded(child: SizedBox()),
            ],
          ],
        ),
      );
      if (i + 3 < devices.length) {
        rows.add(const SizedBox(height: 12));
      }
    }
    return Column(children: rows);
  }
}
