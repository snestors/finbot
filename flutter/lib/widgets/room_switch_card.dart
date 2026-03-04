import 'package:flutter/material.dart';
import '../core/app_colors.dart';
import 'custom_toggle.dart';

class RoomSwitchCard extends StatelessWidget {
  final String roomName;
  final String statusText;
  final IconData icon;
  final Color iconColor;
  final bool isOn;
  final ValueChanged<bool>? onToggle;

  const RoomSwitchCard({
    super.key,
    required this.roomName,
    required this.statusText,
    required this.icon,
    required this.iconColor,
    required this.isOn,
    this.onToggle,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 72,
      padding: const EdgeInsets.symmetric(horizontal: 20),
      decoration: BoxDecoration(
        color: AppColors.bgCard,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Row(
        children: [
          Container(
            width: 42,
            height: 42,
            decoration: BoxDecoration(
              color: AppColors.bgCardLight,
              borderRadius: BorderRadius.circular(12),
            ),
            child: Icon(icon, color: iconColor, size: 20),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  roomName,
                  style: const TextStyle(
                    color: AppColors.textPrimary,
                    fontSize: 15,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  statusText,
                  style: const TextStyle(
                    color: AppColors.textSecondary,
                    fontSize: 12,
                  ),
                ),
              ],
            ),
          ),
          CustomToggle(value: isOn, onChanged: onToggle),
        ],
      ),
    );
  }
}
