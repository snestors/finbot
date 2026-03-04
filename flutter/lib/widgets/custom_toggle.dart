import 'package:flutter/material.dart';
import '../core/app_colors.dart';

class CustomToggle extends StatelessWidget {
  final bool value;
  final ValueChanged<bool>? onChanged;

  const CustomToggle({
    super.key,
    required this.value,
    this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: () => onChanged?.call(!value),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        width: 50,
        height: 28,
        decoration: BoxDecoration(
          color: value ? AppColors.switchOn : AppColors.switchOff,
          borderRadius: BorderRadius.circular(14),
        ),
        child: AnimatedAlign(
          duration: const Duration(milliseconds: 200),
          alignment: value ? Alignment.centerRight : Alignment.centerLeft,
          child: Container(
            margin: const EdgeInsets.all(3),
            width: 22,
            height: 22,
            decoration: const BoxDecoration(
              color: AppColors.textPrimary,
              shape: BoxShape.circle,
            ),
          ),
        ),
      ),
    );
  }
}
