import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../services/api_client.dart';

class ConsumoState {
  final double costoKwh;
  final double kwhTotal;
  final double kwhMes; // kWh del período de facturación (7 al 7)
  final int dias; // días transcurridos en el período
  final int diasPeriodo; // días totales del período
  final double costoTotal;
  final double estimadoMes;
  final int diaActual;
  final int diasMes;
  final String periodoDesde; // fecha inicio período
  final String periodoHasta; // fecha fin período
  final List<DailyConsumption> weeklyData;
  final bool loading;
  final String? error;

  const ConsumoState({
    this.costoKwh = 0.85,
    this.kwhTotal = 0,
    this.kwhMes = 0,
    this.dias = 0,
    this.diasPeriodo = 30,
    this.costoTotal = 0,
    this.estimadoMes = 0,
    this.diaActual = 0,
    this.diasMes = 30,
    this.periodoDesde = '',
    this.periodoHasta = '',
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
    int? diasPeriodo,
    double? costoTotal,
    double? estimadoMes,
    int? diaActual,
    int? diasMes,
    String? periodoDesde,
    String? periodoHasta,
    List<DailyConsumption>? weeklyData,
    bool? loading,
    String? error,
  }) =>
      ConsumoState(
        costoKwh: costoKwh ?? this.costoKwh,
        kwhTotal: kwhTotal ?? this.kwhTotal,
        kwhMes: kwhMes ?? this.kwhMes,
        dias: dias ?? this.dias,
        diasPeriodo: diasPeriodo ?? this.diasPeriodo,
        costoTotal: costoTotal ?? this.costoTotal,
        estimadoMes: estimadoMes ?? this.estimadoMes,
        diaActual: diaActual ?? this.diaActual,
        diasMes: diasMes ?? this.diasMes,
        periodoDesde: periodoDesde ?? this.periodoDesde,
        periodoHasta: periodoHasta ?? this.periodoHasta,
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

  /// Calcula inicio y fin del período de facturación (día 7 de cada mes).
  static ({DateTime desde, DateTime hasta}) _billingPeriod(DateTime now) {
    final int billingDay = 7;
    DateTime desde;
    DateTime hasta;
    if (now.day >= billingDay) {
      // Estamos en el período actual: del 7 de este mes al 7 del siguiente
      desde = DateTime(now.year, now.month, billingDay);
      hasta = DateTime(now.year, now.month + 1, billingDay);
    } else {
      // Antes del 7: período del 7 del mes pasado al 7 de este mes
      desde = DateTime(now.year, now.month - 1, billingDay);
      hasta = DateTime(now.year, now.month, billingDay);
    }
    return (desde: desde, hasta: hasta);
  }

  Future<void> load() async {
    state = state.copyWith(loading: true, error: null);
    try {
      final dio = _ref.read(dioProvider);
      final now = DateTime.now();

      // Período de facturación: del 7 al 7
      final period = _billingPeriod(now);
      final desdeStr = period.desde.toIso8601String();
      final hastaStr = period.hasta.toIso8601String();

      // Parallel requests
      final configFut = dio.get('/api/consumos/config');
      final periodoFut = dio.get('/api/consumos/periodo', queryParameters: {
        'tipo': 'luz',
        'desde': desdeStr,
        'hasta': hastaStr,
      });
      final weeklyFut = _fetchWeeklyData(dio, now);

      final configResp = await configFut;
      final periodoResp = await periodoFut;
      final weekly = await weeklyFut;

      final config = configResp.data as Map<String, dynamic>;
      final periodo = periodoResp.data as Map<String, dynamic>;

      final costoKwh =
          double.tryParse(config['costo_kwh_luz']?.toString() ?? '0.85') ??
              0.85;
      final kwhPeriodo = (periodo['kwh_total'] as num?)?.toDouble() ?? 0;
      final diasConDatos = (periodo['dias'] as num?)?.toInt() ?? 0;

      // Días transcurridos y totales del período
      final diasTranscurridos = now.difference(period.desde).inDays.clamp(1, 62);
      final diasTotalPeriodo = period.hasta.difference(period.desde).inDays;

      // Billing calculation basado en el período real
      final costoActual = kwhPeriodo * costoKwh;
      final promedioDia = diasConDatos > 0 ? kwhPeriodo / diasConDatos : 0.0;
      final estimado = promedioDia * diasTotalPeriodo * costoKwh;

      state = state.copyWith(
        costoKwh: costoKwh,
        kwhTotal: kwhPeriodo,
        kwhMes: kwhPeriodo,
        dias: diasConDatos,
        diasPeriodo: diasTotalPeriodo,
        costoTotal: costoActual,
        estimadoMes: estimado,
        diaActual: diasTranscurridos,
        diasMes: diasTotalPeriodo,
        periodoDesde: desdeStr,
        periodoHasta: hastaStr,
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
