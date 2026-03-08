import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:lucide_icons/lucide_icons.dart';
import 'package:intl/intl.dart';
import '../../../core/app_colors.dart';
import '../../../providers/system_stats_provider.dart';

/// Status bar showing live time and connection indicator.
/// In landscape (kiosk) mode, it's hidden since system UI is immersive.
class StatusBarRow extends ConsumerStatefulWidget {
  const StatusBarRow({super.key});

  @override
  ConsumerState<StatusBarRow> createState() => _StatusBarRowState();
}

class _StatusBarRowState extends ConsumerState<StatusBarRow> {
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
    final isLandscape = MediaQuery.of(context).size.width >
        MediaQuery.of(context).size.height;
    // In landscape/kiosk mode, the system UI is hidden, so this bar is
    // unnecessary. Return a minimal spacer instead.
    if (isLandscape) {
      return const SizedBox(height: 4);
    }

    final connected = ref.watch(systemStatsProvider).connected;
    final timeFmt = DateFormat('HH:mm');

    return Container(
      height: 48,
      padding: const EdgeInsets.symmetric(horizontal: 24),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(
            timeFmt.format(_now),
            style: const TextStyle(
              color: AppColors.textPrimary,
              fontSize: 15,
              fontWeight: FontWeight.w600,
            ),
          ),
          Row(
            children: [
              Container(
                width: 8,
                height: 8,
                decoration: BoxDecoration(
                  color: connected ? AppColors.accentGreen : AppColors.accentOrange,
                  shape: BoxShape.circle,
                ),
              ),
              const SizedBox(width: 8),
              const Icon(LucideIcons.wifi, color: AppColors.textPrimary, size: 16),
            ],
          ),
        ],
      ),
    );
  }
}
