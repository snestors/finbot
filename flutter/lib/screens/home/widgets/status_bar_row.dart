import 'package:flutter/material.dart';
import 'package:lucide_icons/lucide_icons.dart';
import '../../../core/app_colors.dart';

class StatusBarRow extends StatelessWidget {
  const StatusBarRow({super.key});

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 62,
      padding: const EdgeInsets.symmetric(horizontal: 24),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          const Text(
            '9:41',
            style: TextStyle(
              color: AppColors.textPrimary,
              fontFamily: 'Inter',
              fontSize: 15,
              fontWeight: FontWeight.w600,
            ),
          ),
          Row(
            children: const [
              Icon(LucideIcons.signal, color: AppColors.textPrimary, size: 16),
              SizedBox(width: 6),
              Icon(LucideIcons.wifi, color: AppColors.textPrimary, size: 16),
              SizedBox(width: 6),
              Icon(LucideIcons.batteryFull, color: AppColors.textPrimary, size: 16),
            ],
          ),
        ],
      ),
    );
  }
}
