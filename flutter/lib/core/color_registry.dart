import 'package:flutter/material.dart';
import 'app_colors.dart';

/// Predefined accent colors for device configuration.
class ColorRegistry {
  ColorRegistry._();

  static const Map<String, Color> available = {
    '#FFFFFF': AppColors.textPrimary,
    '#3B82F6': AppColors.accentBlue,
    '#06B6D4': AppColors.accentCyan,
    '#22C55E': AppColors.accentGreen,
    '#F59E0B': AppColors.accentOrange,
    '#EF4444': AppColors.accentRed,
    '#9CA3AF': AppColors.textSecondary,
    '#A855F7': Color(0xFFA855F7), // purple
    '#EC4899': Color(0xFFEC4899), // pink
  };

  static Color resolve(String hex) =>
      available[hex] ?? AppColors.textPrimary;

  static List<String> get allHex => available.keys.toList();
}
