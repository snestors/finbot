import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:lucide_icons/lucide_icons.dart';
import '../../core/app_colors.dart';
import '../../providers/consumo_provider.dart';
import '../../providers/system_stats_provider.dart';
import '../../widgets/stat_card.dart';
import 'widgets/billing_card.dart';
import 'widgets/weekly_chart.dart';

class ConsumoScreen extends ConsumerStatefulWidget {
  const ConsumoScreen({super.key});

  @override
  ConsumerState<ConsumoScreen> createState() => _ConsumoScreenState();
}

class _ConsumoScreenState extends ConsumerState<ConsumoScreen> {
  @override
  void initState() {
    super.initState();
    Future.microtask(() => ref.read(consumoProvider.notifier).load());
  }

  @override
  Widget build(BuildContext context) {
    final consumo = ref.watch(consumoProvider);
    final stats = ref.watch(systemStatsProvider);
    final isLandscape = MediaQuery.of(context).size.width >
        MediaQuery.of(context).size.height;

    if (consumo.loading) {
      return const Center(
          child: CircularProgressIndicator(color: AppColors.accentBlue));
    }

    // Landscape: two-column layout
    if (isLandscape) {
      return Padding(
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Left: billing card + stats
            Expanded(
              flex: 5,
              child: SingleChildScrollView(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    _buildHeader(consumo),
                    const SizedBox(height: 12),
                    BillingCard(
                      amount: consumo.costoTotal,
                      estimated: consumo.estimadoMes,
                      dayOfMonth: consumo.diaActual,
                      daysInMonth: consumo.diasMes,
                    ),
                    const SizedBox(height: 12),
                    _buildStatsRow(consumo, stats.current),
                  ],
                ),
              ),
            ),
            const SizedBox(width: 12),
            // Right: weekly chart
            Expanded(
              flex: 4,
              child: SingleChildScrollView(
                child: WeeklyChart(data: consumo.weeklyData),
              ),
            ),
          ],
        ),
      );
    }

    // Portrait: single column
    return Column(
      children: [
        _buildStatusBar(),
        Expanded(
          child: RefreshIndicator(
            onRefresh: () => ref.read(consumoProvider.notifier).load(),
            child: SingleChildScrollView(
              physics: const AlwaysScrollableScrollPhysics(),
              padding: const EdgeInsets.fromLTRB(24, 0, 24, 24),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _buildHeader(consumo),
                  const SizedBox(height: 24),
                  BillingCard(
                    amount: consumo.costoTotal,
                    estimated: consumo.estimadoMes,
                    dayOfMonth: consumo.diaActual,
                    daysInMonth: consumo.diasMes,
                  ),
                  const SizedBox(height: 24),
                  _buildStatsRow(consumo, stats.current),
                  const SizedBox(height: 24),
                  WeeklyChart(data: consumo.weeklyData),
                ],
              ),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildStatusBar() {
    final isLandscape = MediaQuery.of(context).size.width >
        MediaQuery.of(context).size.height;
    // In landscape/kiosk mode, return minimal spacer
    if (isLandscape) {
      return const SizedBox(height: 4);
    }
    return Container(
      height: 48,
      padding: const EdgeInsets.symmetric(horizontal: 24),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(
            '${DateTime.now().hour.toString().padLeft(2, '0')}:'
            '${DateTime.now().minute.toString().padLeft(2, '0')}',
            style: const TextStyle(
              color: AppColors.textPrimary,
              fontSize: 15,
              fontWeight: FontWeight.w600,
            ),
          ),
          Row(
            children: const [
              Icon(LucideIcons.wifi, color: AppColors.textPrimary, size: 16),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildHeader(ConsumoState consumo) {
    final now = DateTime.now();
    final months = [
      '', 'Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun',
      'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'
    ];
    final prevMonth = now.month == 1 ? 12 : now.month - 1;
    final periodLabel = '${months[prevMonth]} - ${months[now.month]}';

    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        const Text(
          'Consumo del Mes',
          style: TextStyle(
            color: AppColors.textPrimary,
            fontSize: 24,
            fontWeight: FontWeight.w700,
          ),
        ),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
          decoration: BoxDecoration(
            color: AppColors.bgCard,
            borderRadius: BorderRadius.circular(20),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(LucideIcons.calendar,
                  color: AppColors.textSecondary, size: 14),
              const SizedBox(width: 6),
              Text(
                periodLabel,
                style: const TextStyle(
                  color: AppColors.textSecondary,
                  fontSize: 12,
                  fontWeight: FontWeight.w500,
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildStatsRow(ConsumoState consumo, SystemStats current) {
    // Use live month_kwh from system stats if available, fallback to consumo state
    final monthKwh = current.monthKwh > 0 ? current.monthKwh : consumo.kwhMes;
    final promedio = consumo.dias > 0 ? monthKwh / consumo.dias : 0.0;

    return Row(
      children: [
        Expanded(
          child: StatCard(
            label: 'Consumo Total',
            value: '${monthKwh.toStringAsFixed(1)} kWh',
            subtitle: 'Este periodo',
            icon: LucideIcons.plugZap,
            iconColor: AppColors.accentBlue,
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: StatCard(
            label: 'Promedio Diario',
            value: '${promedio.toStringAsFixed(1)} kWh',
            subtitle: 'Por día',
            icon: LucideIcons.trendingUp,
            iconColor: AppColors.accentGreen,
          ),
        ),
      ],
    );
  }
}
