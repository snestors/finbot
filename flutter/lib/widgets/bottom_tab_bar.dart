import 'package:flutter/material.dart';
import 'package:lucide_icons/lucide_icons.dart';
import '../core/app_colors.dart';

class BottomTabBar extends StatelessWidget {
  final int currentIndex;
  final ValueChanged<int> onTap;

  const BottomTabBar({
    super.key,
    required this.currentIndex,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      color: AppColors.bgPrimary,
      padding: const EdgeInsets.fromLTRB(21, 12, 21, 21),
      child: Container(
        height: 62,
        padding: const EdgeInsets.all(4),
        decoration: BoxDecoration(
          color: AppColors.bgCard,
          borderRadius: BorderRadius.circular(36),
          border: Border.all(color: AppColors.borderSubtle, width: 1),
        ),
        child: Row(
          children: [
            _buildTab(
              index: 0,
              icon: LucideIcons.home,
              label: 'INICIO',
            ),
            _buildTab(
              index: 1,
              icon: LucideIcons.barChart3,
              label: 'CONSUMO',
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildTab({
    required int index,
    required IconData icon,
    required String label,
  }) {
    final isActive = currentIndex == index;
    return Expanded(
      child: GestureDetector(
        onTap: () => onTap(index),
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 200),
          decoration: BoxDecoration(
            color: isActive ? AppColors.accentBlue : Colors.transparent,
            borderRadius: BorderRadius.circular(26),
          ),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(
                icon,
                size: 18,
                color: isActive
                    ? AppColors.textPrimary
                    : AppColors.navInactive,
              ),
              const SizedBox(height: 4),
              Text(
                label,
                style: TextStyle(
                  color: isActive
                      ? AppColors.textPrimary
                      : AppColors.navInactive,
                  fontSize: 10,
                  fontWeight: FontWeight.w600,
                  letterSpacing: 0.5,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
