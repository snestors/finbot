import 'package:flutter/material.dart';
import 'package:fl_chart/fl_chart.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:lucide_icons/lucide_icons.dart';
import 'package:intl/intl.dart';
import '../../../core/app_colors.dart';
import '../../../providers/system_stats_provider.dart';
import '../../../widgets/metric_mini_card.dart';

class RealtimeChartCard extends ConsumerWidget {
  const RealtimeChartCard({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final stats = ref.watch(systemStatsProvider);
    final current = stats.current;
    final history = stats.history;

    return Container(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 14),
      decoration: BoxDecoration(
        color: AppColors.bgCard,
        borderRadius: BorderRadius.circular(20),
      ),
      child: Column(
        children: [
          _buildHeader(stats.connected),
          const SizedBox(height: 14),
          _buildLegend(),
          const SizedBox(height: 14),
          SizedBox(
            height: 120,
            child: _buildChart(history),
          ),
          const SizedBox(height: 14),
          _buildTimeLabels(history),
          const SizedBox(height: 14),
          _buildMetricsRow(current),
        ],
      ),
    );
  }

  Widget _buildHeader(bool connected) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        const Text(
          'Consumo en Tiempo Real',
          style: TextStyle(
            color: AppColors.textPrimary,
            fontSize: 14,
            fontWeight: FontWeight.w600,
          ),
        ),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
          decoration: BoxDecoration(
            color: (connected ? AppColors.accentGreen : AppColors.accentOrange)
                .withValues(alpha: 0.13),
            borderRadius: BorderRadius.circular(12),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: 6,
                height: 6,
                decoration: BoxDecoration(
                  color:
                      connected ? AppColors.accentGreen : AppColors.accentOrange,
                  shape: BoxShape.circle,
                ),
              ),
              const SizedBox(width: 6),
              Text(
                connected ? 'EN VIVO' : 'CONECTANDO',
                style: TextStyle(
                  color: connected
                      ? AppColors.accentGreen
                      : AppColors.accentOrange,
                  fontSize: 10,
                  fontWeight: FontWeight.w700,
                  letterSpacing: 0.5,
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildLegend() {
    return Row(
      children: [
        _legendItem(AppColors.accentOrange, 'Watts'),
        const SizedBox(width: 16),
        _legendItem(AppColors.accentCyan, 'Amps'),
        const SizedBox(width: 16),
        _legendItem(AppColors.accentGreen, 'Volts'),
      ],
    );
  }

  Widget _legendItem(Color color, String label) {
    return Row(
      children: [
        Container(
          width: 8,
          height: 8,
          decoration: BoxDecoration(
            color: color,
            borderRadius: BorderRadius.circular(4),
          ),
        ),
        const SizedBox(width: 4),
        Text(
          label,
          style: const TextStyle(
            color: AppColors.textSecondary,
            fontSize: 10,
            fontWeight: FontWeight.w500,
          ),
        ),
      ],
    );
  }

  Widget _buildChart(List<SystemStats> history) {
    if (history.length < 2) {
      return const Center(
        child: Text(
          'Esperando datos...',
          style: TextStyle(color: AppColors.textMuted, fontSize: 12),
        ),
      );
    }

    final wattsSpots = <FlSpot>[];
    final ampsSpots = <FlSpot>[];
    final voltsSpots = <FlSpot>[];

    for (var i = 0; i < history.length; i++) {
      final x = i.toDouble();
      wattsSpots.add(FlSpot(x, history[i].powerW));
      ampsSpots.add(FlSpot(x, history[i].currentA * 100)); // scale amps for visibility
      voltsSpots.add(FlSpot(x, history[i].voltageV));
    }

    final maxW = history.fold<double>(
        0, (prev, s) => s.powerW > prev ? s.powerW : prev);
    final maxY = (maxW * 1.2).clamp(500, 10000).toDouble();

    return LineChart(
      LineChartData(
        gridData: FlGridData(
          show: true,
          drawVerticalLine: false,
          horizontalInterval: maxY / 3,
          getDrawingHorizontalLine: (value) => FlLine(
            color: AppColors.borderSubtle,
            strokeWidth: 1,
          ),
        ),
        titlesData: FlTitlesData(
          rightTitles:
              const AxisTitles(sideTitles: SideTitles(showTitles: false)),
          topTitles:
              const AxisTitles(sideTitles: SideTitles(showTitles: false)),
          bottomTitles:
              const AxisTitles(sideTitles: SideTitles(showTitles: false)),
          leftTitles: AxisTitles(
            sideTitles: SideTitles(
              showTitles: true,
              reservedSize: 36,
              interval: maxY / 3,
              getTitlesWidget: (value, meta) {
                return Text(
                  value.toInt().toString(),
                  style: const TextStyle(
                    color: AppColors.textMuted,
                    fontSize: 8,
                    fontWeight: FontWeight.w500,
                  ),
                );
              },
            ),
          ),
        ),
        borderData: FlBorderData(show: false),
        minX: 0,
        maxX: (history.length - 1).toDouble(),
        minY: 0,
        maxY: maxY,
        lineBarsData: [
          LineChartBarData(
            spots: wattsSpots,
            isCurved: true,
            color: AppColors.accentOrange,
            barWidth: 2,
            dotData: const FlDotData(show: false),
            belowBarData: BarAreaData(show: false),
          ),
          LineChartBarData(
            spots: voltsSpots,
            isCurved: true,
            color: AppColors.accentGreen,
            barWidth: 2,
            dotData: const FlDotData(show: false),
            belowBarData: BarAreaData(show: false),
          ),
          LineChartBarData(
            spots: ampsSpots,
            isCurved: true,
            color: AppColors.accentCyan,
            barWidth: 2,
            dotData: const FlDotData(show: false),
            belowBarData: BarAreaData(show: false),
          ),
        ],
        lineTouchData: const LineTouchData(enabled: false),
      ),
    );
  }

  Widget _buildTimeLabels(List<SystemStats> history) {
    if (history.isEmpty) return const SizedBox.shrink();

    final fmt = DateFormat('HH:mm');
    final labels = <String>[];
    final step = history.length > 4 ? history.length ~/ 4 : 1;
    for (var i = 0; i < history.length; i += step) {
      labels.add(fmt.format(history[i].timestamp));
    }
    // Always include last
    if (labels.isEmpty || labels.last != fmt.format(history.last.timestamp)) {
      labels.add(fmt.format(history.last.timestamp));
    }
    // Limit to 5
    while (labels.length > 5) {
      labels.removeAt(labels.length ~/ 2);
    }

    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: labels.asMap().entries.map((e) {
        final isLast = e.key == labels.length - 1;
        return Text(
          e.value,
          style: TextStyle(
            color: isLast ? AppColors.textSecondary : AppColors.textMuted,
            fontSize: 9,
            fontWeight: isLast ? FontWeight.w600 : FontWeight.w500,
          ),
        );
      }).toList(),
    );
  }

  Widget _buildMetricsRow(SystemStats current) {
    return Row(
      children: [
        MetricMiniCard(
          icon: LucideIcons.zap,
          iconColor: AppColors.accentOrange,
          value: '${current.powerW.toStringAsFixed(0)} W',
          label: 'Potencia',
        ),
        const SizedBox(width: 8),
        MetricMiniCard(
          icon: LucideIcons.gauge,
          iconColor: AppColors.accentCyan,
          value: '${current.currentA.toStringAsFixed(1)} A',
          label: 'Corriente',
        ),
        const SizedBox(width: 8),
        MetricMiniCard(
          icon: LucideIcons.activity,
          iconColor: AppColors.accentGreen,
          value: '${current.voltageV.toStringAsFixed(0)} V',
          label: 'Voltaje',
        ),
      ],
    );
  }
}
