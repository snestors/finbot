import 'package:flutter/material.dart';
import '../../../core/app_colors.dart';
import '../../../providers/consumo_provider.dart';

class WeeklyChart extends StatelessWidget {
  final List<DailyConsumption> data;

  const WeeklyChart({super.key, required this.data});

  static const _dayLabels = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom'];

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AppColors.bgCard,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        children: [
          _buildHeader(),
          const SizedBox(height: 16),
          SizedBox(
            height: 160,
            child: data.isEmpty ? _buildPlaceholder() : _buildBars(),
          ),
        ],
      ),
    );
  }

  Widget _buildHeader() {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: const [
        Text(
          'Consumo Semanal',
          style: TextStyle(
            color: AppColors.textPrimary,
            fontSize: 16,
            fontWeight: FontWeight.w600,
          ),
        ),
        Text(
          'kWh',
          style: TextStyle(
            color: AppColors.textMuted,
            fontSize: 12,
            fontWeight: FontWeight.w500,
          ),
        ),
      ],
    );
  }

  Widget _buildBars() {
    final maxKwh = data.fold<double>(1.0, (a, d) => d.kwh > a ? d.kwh : a);
    final today = DateTime.now();

    return Row(
      crossAxisAlignment: CrossAxisAlignment.end,
      children: data.map((d) {
        final ratio = maxKwh > 0 ? (d.kwh / maxKwh).clamp(0.05, 1.0) : 0.05;
        final isToday = d.date.day == today.day &&
            d.date.month == today.month &&
            d.date.year == today.year;
        final weekday = d.date.weekday - 1; // 0=Mon

        return Expanded(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 4),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.end,
              children: [
                Text(
                  d.kwh > 0 ? d.kwh.toStringAsFixed(1) : '',
                  style: TextStyle(
                    color: isToday ? AppColors.textPrimary : AppColors.textMuted,
                    fontSize: 8,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(height: 4),
                Container(
                  height: 110 * ratio,
                  decoration: BoxDecoration(
                    color:
                        isToday ? AppColors.accentBlue : AppColors.bgCardLight,
                    borderRadius: BorderRadius.circular(6),
                  ),
                ),
                const SizedBox(height: 6),
                Text(
                  _dayLabels[weekday],
                  style: TextStyle(
                    color: isToday ? AppColors.textPrimary : AppColors.textMuted,
                    fontSize: 10,
                    fontWeight: isToday ? FontWeight.w600 : FontWeight.w500,
                  ),
                ),
              ],
            ),
          ),
        );
      }).toList(),
    );
  }

  Widget _buildPlaceholder() {
    return const Center(
      child: Text(
        'Cargando datos semanales...',
        style: TextStyle(color: AppColors.textMuted, fontSize: 13),
      ),
    );
  }
}
