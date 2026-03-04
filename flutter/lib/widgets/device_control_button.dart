import 'package:flutter/material.dart';
import '../core/app_colors.dart';
import '../core/icon_registry.dart';
import '../core/color_registry.dart';
import '../models/control_device.dart';

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
              child: Icon(
                IconRegistry.resolve(device.iconName),
                color: isActive ? AppColors.textPrimary : iconColor,
                size: 20,
              ),
            ),
            const SizedBox(height: 12),
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
            const SizedBox(height: 4),
            Text(
              isActive ? 'Encendido' : 'Apagado',
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
    );
  }
}
