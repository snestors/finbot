import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'app_colors.dart';

ThemeData buildAppTheme() {
  return ThemeData(
    useMaterial3: true,
    brightness: Brightness.dark,
    scaffoldBackgroundColor: AppColors.bgPrimary,
    colorScheme: const ColorScheme.dark(
      primary: AppColors.accentBlue,
      secondary: AppColors.accentGreen,
      surface: AppColors.bgCard,
      onPrimary: AppColors.textPrimary,
      onSecondary: AppColors.textPrimary,
      onSurface: AppColors.textPrimary,
    ),
    textTheme: GoogleFonts.dmSansTextTheme(
      ThemeData.dark().textTheme,
    ),
    cardTheme: CardThemeData(
      color: AppColors.bgCard,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
      ),
      elevation: 0,
    ),
    appBarTheme: const AppBarTheme(
      backgroundColor: AppColors.bgPrimary,
      elevation: 0,
    ),
  );
}
