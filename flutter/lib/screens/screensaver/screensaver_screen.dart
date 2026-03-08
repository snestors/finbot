import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import 'package:lucide_icons/lucide_icons.dart';
import '../../core/app_colors.dart';
import '../../providers/system_stats_provider.dart';

/// Full-screen screensaver with clock, date, and system stats.
/// Designed for landscape NSPanel (480x320). Any touch dismisses it.
class ScreensaverScreen extends ConsumerStatefulWidget {
  const ScreensaverScreen({super.key});

  @override
  ConsumerState<ScreensaverScreen> createState() => _ScreensaverScreenState();
}

class _ScreensaverScreenState extends ConsumerState<ScreensaverScreen> {
  late Timer _timer;
  DateTime _now = DateTime.now();
  bool _dismissed = false;

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

  void _dismiss() {
    if (_dismissed) return;
    _dismissed = true;
    Navigator.of(context).pop();
  }

  @override
  Widget build(BuildContext context) {
    final stats = ref.watch(systemStatsProvider);
    final current = stats.current;
    final timeFmt = DateFormat('HH:mm');
    final secFmt = DateFormat(':ss');
    final dayNames = [
      '',
      'Lunes',
      'Martes',
      'Miércoles',
      'Jueves',
      'Viernes',
      'Sábado',
      'Domingo'
    ];
    final monthNames = [
      '',
      'Enero',
      'Febrero',
      'Marzo',
      'Abril',
      'Mayo',
      'Junio',
      'Julio',
      'Agosto',
      'Septiembre',
      'Octubre',
      'Noviembre',
      'Diciembre'
    ];
    final dateLabel =
        '${dayNames[_now.weekday]}, ${_now.day} de ${monthNames[_now.month]}';

    // Use Listener instead of GestureDetector to catch ALL pointer events
    // before they are consumed by gesture arena
    return Listener(
      onPointerDown: (_) => _dismiss(),
      behavior: HitTestBehavior.opaque,
      child: Scaffold(
        backgroundColor: Colors.black,
        body: Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              // Time
              Row(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.baseline,
                textBaseline: TextBaseline.alphabetic,
                children: [
                  Text(
                    timeFmt.format(_now),
                    style: const TextStyle(
                      color: AppColors.textPrimary,
                      fontSize: 72,
                      fontWeight: FontWeight.w200,
                      letterSpacing: 2,
                      height: 1.0,
                    ),
                  ),
                  Text(
                    secFmt.format(_now),
                    style: TextStyle(
                      color: AppColors.textPrimary.withValues(alpha: 0.3),
                      fontSize: 28,
                      fontWeight: FontWeight.w200,
                      height: 1.0,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              // Date
              Text(
                dateLabel,
                style: const TextStyle(
                  color: AppColors.textSecondary,
                  fontSize: 16,
                  fontWeight: FontWeight.w400,
                ),
              ),
              const SizedBox(height: 24),
              // Stats row (power + day kWh) — only shown if data available
              if (current.powerW > 0 || current.dayKwh > 0)
                _buildStatsRow(current, stats.connected),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildStatsRow(SystemStats current, bool connected) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
      decoration: BoxDecoration(
        color: AppColors.textPrimary.withValues(alpha: 0.05),
        borderRadius: BorderRadius.circular(16),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (current.powerW > 0) ...[
            Icon(LucideIcons.zap,
                color: AppColors.accentOrange.withValues(alpha: 0.7),
                size: 16),
            const SizedBox(width: 6),
            Text(
              '${current.powerW.toStringAsFixed(0)} W',
              style: TextStyle(
                color: AppColors.textPrimary.withValues(alpha: 0.6),
                fontSize: 14,
                fontWeight: FontWeight.w500,
              ),
            ),
          ],
          if (current.powerW > 0 && current.dayKwh > 0)
            Container(
              width: 1,
              height: 16,
              margin: const EdgeInsets.symmetric(horizontal: 14),
              color: AppColors.textPrimary.withValues(alpha: 0.1),
            ),
          if (current.dayKwh > 0) ...[
            Icon(LucideIcons.activity,
                color: AppColors.accentGreen.withValues(alpha: 0.7),
                size: 16),
            const SizedBox(width: 6),
            Text(
              '${current.dayKwh.toStringAsFixed(1)} kWh hoy',
              style: TextStyle(
                color: AppColors.textPrimary.withValues(alpha: 0.6),
                fontSize: 14,
                fontWeight: FontWeight.w500,
              ),
            ),
          ],
          // Connection indicator
          Container(
            width: 1,
            height: 16,
            margin: const EdgeInsets.symmetric(horizontal: 14),
            color: AppColors.textPrimary.withValues(alpha: 0.1),
          ),
          Container(
            width: 6,
            height: 6,
            decoration: BoxDecoration(
              color: connected
                  ? AppColors.accentGreen.withValues(alpha: 0.7)
                  : AppColors.accentRed.withValues(alpha: 0.7),
              shape: BoxShape.circle,
            ),
          ),
        ],
      ),
    );
  }
}
