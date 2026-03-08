import 'package:flutter/material.dart';
import 'package:lucide_icons/lucide_icons.dart';
import '../core/app_colors.dart';

/// Bottom navigation bar with touch-friendly 48dp minimum targets.
/// Adapts padding for landscape vs portrait mode.
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
    final isLandscape = MediaQuery.of(context).size.width >
        MediaQuery.of(context).size.height;
    // Compact padding in landscape to save vertical space
    final verticalPadding = isLandscape ? 4.0 : 12.0;
    final bottomPadding = isLandscape ? 4.0 : 21.0;
    final barHeight = isLandscape ? 48.0 : 62.0;

    return Container(
      color: AppColors.bgPrimary,
      padding: EdgeInsets.fromLTRB(21, verticalPadding, 21, bottomPadding),
      child: Container(
        height: barHeight,
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
              isLandscape: isLandscape,
            ),
            _buildTab(
              index: 1,
              icon: LucideIcons.barChart3,
              label: 'CONSUMO',
              isLandscape: isLandscape,
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
    required bool isLandscape,
  }) {
    final isActive = currentIndex == index;
    return Expanded(
      // Ensure minimum 48dp touch target
      child: GestureDetector(
        onTap: () => onTap(index),
        behavior: HitTestBehavior.opaque,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 200),
          constraints: const BoxConstraints(minHeight: 40),
          decoration: BoxDecoration(
            color: isActive ? AppColors.accentBlue : Colors.transparent,
            borderRadius: BorderRadius.circular(26),
          ),
          child: isLandscape
              // Landscape: icon + label side by side (compact)
              ? Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Icon(
                      icon,
                      size: 16,
                      color: isActive
                          ? AppColors.textPrimary
                          : AppColors.navInactive,
                    ),
                    const SizedBox(width: 6),
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
                )
              // Portrait: icon on top, label below
              : Column(
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
