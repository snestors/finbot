import 'package:flutter/material.dart';
import '../core/app_colors.dart';
import '../core/icon_registry.dart';
import '../core/color_registry.dart';
import '../models/control_device.dart';

/// Touch-friendly device control button.
/// Minimum touch target: 48x48dp per Material Design guidelines.
/// Optimized for NSPanel landscape display (480x320).
class DeviceControlButton extends StatelessWidget {
  final ControlDevice device;
  final VoidCallback? onTap;

  const DeviceControlButton({
    super.key,
    required this.device,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final iconColor = ColorRegistry.resolve(device.colorHex);
    final isActive = device.isActive;

    return GestureDetector(
      onTap: onTap,
      behavior: HitTestBehavior.opaque,
      child: Container(
        // Ensure minimum 48dp height for touch target
        constraints: const BoxConstraints(minHeight: 48, minWidth: 48),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
        decoration: BoxDecoration(
          color: isActive ? AppColors.accentBlue : AppColors.bgCard,
          borderRadius: BorderRadius.circular(16),
        ),
        child: Row(
          children: [
            // Icon container — 48x48 for easy tapping
            Container(
              width: 48,
              height: 48,
              decoration: BoxDecoration(
                color: isActive
                    ? Colors.white.withValues(alpha: 0.13)
                    : AppColors.bgCardLight,
                borderRadius: BorderRadius.circular(14),
              ),
              child: Icon(
                IconRegistry.resolve(device.iconName),
                color: isActive ? AppColors.textPrimary : iconColor,
                size: 22,
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    device.name,
                    style: const TextStyle(
                      color: AppColors.textPrimary,
                      fontSize: 14,
                      fontWeight: FontWeight.w700,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  const SizedBox(height: 2),
                  Text(
                    isActive ? 'Encendido' : 'Apagado',
                    style: TextStyle(
                      color: isActive
                          ? Colors.white.withValues(alpha: 0.67)
                          : AppColors.textMuted,
                      fontSize: 11,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
