import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:lucide_icons/lucide_icons.dart';
import 'package:intl/intl.dart';
import '../../../core/app_colors.dart';
import '../../../providers/system_stats_provider.dart';

class TimeWeatherRow extends ConsumerStatefulWidget {
  const TimeWeatherRow({super.key});

  @override
  ConsumerState<TimeWeatherRow> createState() => _TimeWeatherRowState();
}

class _TimeWeatherRowState extends ConsumerState<TimeWeatherRow> {
  late Timer _timer;
  DateTime _now = DateTime.now();

  @override
  void initState() {
    super.initState();
    _timer = Timer.periodic(const Duration(seconds: 1), (_) {
      setState(() => _now = DateTime.now());
    });
  }

  @override
  void dispose() {
    _timer.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final stats = ref.watch(systemStatsProvider).current;
    final timeFmt = DateFormat('HH:mm');
    final dayNames = [
      '', 'Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo'
    ];
    final monthNames = [
      '', 'Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun',
      'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'
    ];
    final dateLabel = '${dayNames[_now.weekday]}, ${_now.day} ${monthNames[_now.month]}';
    final isLandscape = MediaQuery.of(context).size.width >
        MediaQuery.of(context).size.height;
    // Compact sizes for landscape NSPanel
    final timeFontSize = isLandscape ? 28.0 : 36.0;
    final kwhFontSize = isLandscape ? 20.0 : 24.0;
    final padding = isLandscape
        ? const EdgeInsets.symmetric(horizontal: 12, vertical: 10)
        : const EdgeInsets.all(16);

    return Row(
      children: [
        Expanded(
          child: Container(
            padding: padding,
            decoration: BoxDecoration(
              color: AppColors.bgCard,
              borderRadius: BorderRadius.circular(16),
            ),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Text(
                  timeFmt.format(_now),
                  style: TextStyle(
                    color: AppColors.textPrimary,
                    fontSize: timeFontSize,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  dateLabel,
                  style: const TextStyle(
                    color: AppColors.textSecondary,
                    fontSize: 12,
                  ),
                ),
              ],
            ),
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Container(
            padding: padding,
            decoration: BoxDecoration(
              color: AppColors.bgCard,
              borderRadius: BorderRadius.circular(16),
            ),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(LucideIcons.zap,
                    color: AppColors.accentOrange,
                    size: isLandscape ? 22 : 28),
                const SizedBox(height: 4),
                Text(
                  '${stats.dayKwh.toStringAsFixed(1)} kWh',
                  style: TextStyle(
                    color: AppColors.textPrimary,
                    fontSize: kwhFontSize,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const SizedBox(height: 4),
                const Text(
                  'Hoy',
                  style: TextStyle(
                    color: AppColors.textSecondary,
                    fontSize: 12,
                  ),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}
