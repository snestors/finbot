import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../services/api_client.dart';

class ConsumoState {
  final double costoKwh;
  final double kwhTotal;
  final double kwhMes; // month_kwh from /actual
  final int dias;
  final double costoTotal;
  final double estimadoMes;
  final int diaActual;
  final int diasMes;
  final List<DailyConsumption> weeklyData;
  final bool loading;
  final String? error;

  const ConsumoState({
    this.costoKwh = 0.85,
    this.kwhTotal = 0,
    this.kwhMes = 0,
    this.dias = 0,
    this.costoTotal = 0,
    this.estimadoMes = 0,
    this.diaActual = 0,
    this.diasMes = 30,
    this.weeklyData = const [],
    this.loading = false,
    this.error,
  });

  double get promedioDiario => dias > 0 ? kwhMes / dias : 0;

  ConsumoState copyWith({
    double? costoKwh,
    double? kwhTotal,
    double? kwhMes,
    int? dias,
    double? costoTotal,
    double? estimadoMes,
    int? diaActual,
    int? diasMes,
    List<DailyConsumption>? weeklyData,
    bool? loading,
    String? error,
  }) =>
      ConsumoState(
        costoKwh: costoKwh ?? this.costoKwh,
        kwhTotal: kwhTotal ?? this.kwhTotal,
        kwhMes: kwhMes ?? this.kwhMes,
        dias: dias ?? this.dias,
        costoTotal: costoTotal ?? this.costoTotal,
        estimadoMes: estimadoMes ?? this.estimadoMes,
        diaActual: diaActual ?? this.diaActual,
        diasMes: diasMes ?? this.diasMes,
        weeklyData: weeklyData ?? this.weeklyData,
        loading: loading ?? this.loading,
        error: error,
      );
}

class DailyConsumption {
  final DateTime date;
  final double kwh;
  DailyConsumption({required this.date, required this.kwh});
}

final consumoProvider =
    StateNotifierProvider<ConsumoNotifier, ConsumoState>((ref) {
  return ConsumoNotifier(ref);
});

class ConsumoNotifier extends StateNotifier<ConsumoState> {
  final Ref _ref;

  ConsumoNotifier(this._ref) : super(const ConsumoState());

  Future<void> load() async {
    state = state.copyWith(loading: true, error: null);
    try {
      final dio = _ref.read(dioProvider);
      final now = DateTime.now();

      // Parallel requests
      final configFut = dio.get('/api/consumos/config');
      final actualFut = dio.get('/api/consumos/actual');
      final resumenFut = dio.get('/api/consumos/resumen', queryParameters: {
        'mes': '${now.year}-${now.month.toString().padLeft(2, '0')}',
      });
      final weeklyFut = _fetchWeeklyData(dio, now);

      final configResp = await configFut;
      final actualResp = await actualFut;
      final resumenResp = await resumenFut;
      final weekly = await weeklyFut;

      final config = configResp.data as Map<String, dynamic>;
      final actual = actualResp.data as Map<String, dynamic>;

      // Resumen is an array, find luz entry
      final resumenList = resumenResp.data as List<dynamic>;
      final resumenLuz = resumenList.isNotEmpty
          ? resumenList.first as Map<String, dynamic>
          : <String, dynamic>{};

      final costoKwh =
          double.tryParse(config['costo_kwh_luz']?.toString() ?? '0.85') ??
              0.85;
      final monthKwh = (actual['month_kwh'] as num?)?.toDouble() ?? 0;
      // Calculate days in period from resumen
      DateTime? desde;
      DateTime? hasta;
      try {
        desde = DateTime.parse(resumenLuz['desde'] as String);
        hasta = DateTime.parse(resumenLuz['hasta'] as String);
      } catch (_) {}
      final dias = (desde != null && hasta != null)
          ? hasta.difference(desde).inDays.clamp(1, 31)
          : now.day;

      // Billing calculation
      final diasMes = DateTime(now.year, now.month + 1, 0).day;
      final diaActual = now.day;
      final costoActual = monthKwh * costoKwh;
      final promedioDia = dias > 0 ? monthKwh / dias : 0.0;
      final estimado = promedioDia * diasMes * costoKwh;

      state = state.copyWith(
        costoKwh: costoKwh,
        kwhTotal: monthKwh,
        kwhMes: monthKwh,
        dias: dias,
        costoTotal: costoActual,
        estimadoMes: estimado,
        diaActual: diaActual,
        diasMes: diasMes,
        weeklyData: weekly,
        loading: false,
      );
    } catch (e) {
      state = state.copyWith(loading: false, error: e.toString());
    }
  }

  Future<List<DailyConsumption>> _fetchWeeklyData(dynamic dio, DateTime now) async {
    // Fetch last 7 days. For each day, get the chart data and calculate kWh.
    final results = <DailyConsumption>[];
    try {
      for (var i = 6; i >= 0; i--) {
        final date = DateTime(now.year, now.month, now.day - i);
        final nextDate = date.add(const Duration(days: 1));
        try {
          final response = await dio.get('/api/consumos/chart', queryParameters: {
            'tipo': 'luz',
            'desde': date.toIso8601String(),
            'hasta': nextDate.toIso8601String(),
          });
          if (response.data is List) {
            final points = response.data as List;
            if (points.length >= 2) {
              // kWh for the day = last day_kwh value
              final lastPoint = points.last as Map<String, dynamic>;
              final dayKwh = (lastPoint['day_kwh'] as num?)?.toDouble() ?? 0;
              results.add(DailyConsumption(date: date, kwh: dayKwh));
            } else {
              results.add(DailyConsumption(date: date, kwh: 0));
            }
          }
        } catch (_) {
          results.add(DailyConsumption(date: date, kwh: 0));
        }
      }
    } catch (_) {}
    return results;
  }
}
