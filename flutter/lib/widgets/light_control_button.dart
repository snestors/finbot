import 'package:flutter/material.dart';
import '../core/app_colors.dart';

class LightControlButton extends StatelessWidget {
  final String name;
  final String status;
  final IconData icon;
  final Color iconColor;
  final bool isActive;
  final VoidCallback? onTap;

  const LightControlButton({
    super.key,
    required this.name,
    required this.status,
    required this.icon,
    required this.iconColor,
    required this.isActive,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: GestureDetector(
        onTap: onTap,
        child: Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: isActive ? AppColors.accentBlue : AppColors.bgCard,
            borderRadius: BorderRadius.circular(20),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: 40,
                height: 40,
                decoration: BoxDecoration(
                  color: isActive
                      ? Colors.white.withValues(alpha: 0.13)
                      : AppColors.bgCardLight,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Icon(icon, color: iconColor, size: 20),
              ),
              const SizedBox(height: 12),
              Text(
                name,
                style: const TextStyle(
                  color: AppColors.textPrimary,
                  fontSize: 14,
                  fontWeight: FontWeight.w700,
                ),
              ),
              const SizedBox(height: 4),
              Text(
                status,
                style: TextStyle(
                  color: isActive
                      ? Colors.white.withValues(alpha: 0.67)
                      : AppColors.textMuted,
                  fontSize: 10,
                  fontWeight: FontWeight.w500,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
