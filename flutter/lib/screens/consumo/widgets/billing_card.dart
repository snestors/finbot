import 'package:flutter/material.dart';
import 'package:lucide_icons/lucide_icons.dart';
import '../../../core/app_colors.dart';

class BillingCard extends StatelessWidget {
  final double amount;
  final double estimated;
  final int dayOfMonth;
  final int daysInMonth;

  const BillingCard({
    super.key,
    required this.amount,
    required this.estimated,
    required this.dayOfMonth,
    required this.daysInMonth,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            AppColors.billingGradientStart,
            AppColors.billingGradientEnd,
          ],
        ),
        borderRadius: BorderRadius.circular(20),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                'Deuda Acumulada',
                style: TextStyle(
                  color: Colors.white.withValues(alpha: 0.8),
                  fontSize: 14,
                  fontWeight: FontWeight.w500,
                ),
              ),
              Icon(
                LucideIcons.receipt,
                color: Colors.white.withValues(alpha: 0.8),
                size: 20,
              ),
            ],
          ),
          const SizedBox(height: 16),
          Text(
            'S/ ${amount.toStringAsFixed(2)}',
            style: const TextStyle(
              color: AppColors.textPrimary,
              fontSize: 40,
              fontWeight: FontWeight.w800,
            ),
          ),
          const SizedBox(height: 16),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                'Día $dayOfMonth de $daysInMonth',
                style: TextStyle(
                  color: Colors.white.withValues(alpha: 0.67),
                  fontSize: 12,
                ),
              ),
              Text(
                'Estimado: S/ ${estimated.toStringAsFixed(2)}',
                style: TextStyle(
                  color: Colors.white.withValues(alpha: 0.8),
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
