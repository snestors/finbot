import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/constants.dart';
import '../services/firestore_service.dart';

class ConsumoState {
  final double costoKwh;
  final double kwhTotal;
  final double kwhMes;
  final int dias;
  final int diasPeriodo;
  final double costoTotal;
  final double estimadoMes;
  final int diaActual;
  final int diasMes;
  final String periodoDesde;
  final String periodoHasta;
  final List<DailyConsumption> weeklyData;
  final bool loading;
  final String? error;

  const ConsumoState({
    this.costoKwh = Constants.defaultCostoKwh,
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

  FirestoreService get _fs => _ref.read(firestoreServiceProvider);

  /// Billing period: day 7 to day 7.
  static ({DateTime desde, DateTime hasta}) billingPeriod(DateTime now) {
    const billingDay = Constants.billingDay;
    DateTime desde;
    DateTime hasta;
    if (now.day >= billingDay) {
      desde = DateTime(now.year, now.month, billingDay);
      hasta = DateTime(now.year, now.month + 1, billingDay);
    } else {
      desde = DateTime(now.year, now.month - 1, billingDay);
      hasta = DateTime(now.year, now.month, billingDay);
    }
    return (desde: desde, hasta: hasta);
  }

  Future<void> load() async {
    state = state.copyWith(loading: true, error: null);
    try {
      final now = DateTime.now();
      final period = billingPeriod(now);
      final desdeStr = period.desde.toIso8601String();
      final hastaStr = period.hasta.toIso8601String();
      final diasTranscurridos = now.difference(period.desde).inDays.clamp(1, 62);
      final diasTotalPeriodo = period.hasta.difference(period.desde).inDays;

      // Fetch config for costo_kwh
      final config = await _fs.getConfig();
      final costoKwh = (config['costo_kwh_luz'] as num?)?.toDouble() ??
          Constants.defaultCostoKwh;

      // Fetch period data from Firestore
      final periodoData = await _fs.getConsumoPeriodo(period.desde, period.hasta);

      // Fetch weekly chart data
      final dailyData = await _fs.getDailyKwh(7);
      final weekly = dailyData
          .map((d) => DailyConsumption(date: d.date, kwh: d.kwh))
          .toList();

      final kwhPeriodo = periodoData.kwhTotal;
      final diasConDatos = periodoData.dias;
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
}
