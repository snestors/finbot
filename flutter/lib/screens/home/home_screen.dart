import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:lucide_icons/lucide_icons.dart';
import '../../core/app_colors.dart';
import '../../providers/devices_provider.dart';
import '../../widgets/device_control_button.dart';
import '../config/config_screen.dart';
import 'widgets/status_bar_row.dart';
import 'widgets/time_weather_row.dart';
import 'widgets/realtime_chart_card.dart';

class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final devices = ref.watch(devicesProvider);

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

  Widget _buildControlSection(
      BuildContext context, WidgetRef ref, List devices) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            const Text(
              'Control',
              style: TextStyle(
                color: AppColors.textPrimary,
                fontSize: 18,
                fontWeight: FontWeight.w700,
              ),
            ),
            GestureDetector(
              onTap: () => Navigator.of(context).push(
                MaterialPageRoute(builder: (_) => const ConfigScreen()),
              ),
              child: Container(
                width: 32,
                height: 32,
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
        ),
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
        padding: const EdgeInsets.symmetric(vertical: 32),
        decoration: BoxDecoration(
          color: AppColors.bgCard,
          borderRadius: BorderRadius.circular(20),
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

  Widget _buildDeviceGrid(WidgetRef ref, List devices) {
    // Show in rows of 3
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
            // Fill remaining space if row is not complete
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
