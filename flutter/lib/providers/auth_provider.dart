import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../services/api_client.dart';

enum AuthStatus { unknown, loggedOut, loggedIn, loading, error }

class AuthState {
  final AuthStatus status;
  final String? errorMessage;

  const AuthState({this.status = AuthStatus.unknown, this.errorMessage});

  AuthState copyWith({AuthStatus? status, String? errorMessage}) =>
      AuthState(
        status: status ?? this.status,
        errorMessage: errorMessage,
      );
}

final authProvider = StateNotifierProvider<AuthNotifier, AuthState>((ref) {
  return AuthNotifier(ref);
});

class AuthNotifier extends StateNotifier<AuthState> {
  final Ref _ref;

  AuthNotifier(this._ref) : super(const AuthState(status: AuthStatus.loggedOut));

  Future<bool> login(String pin) async {
    state = state.copyWith(status: AuthStatus.loading, errorMessage: null);
    try {
      final dio = _ref.read(dioProvider);
      final response = await dio.post('/api/login', data: {'pin': pin});
      if (response.data['ok'] == true) {
        state = state.copyWith(status: AuthStatus.loggedIn);
        return true;
      } else {
        state = state.copyWith(
          status: AuthStatus.error,
          errorMessage: response.data['error'] ?? 'Error desconocido',
        );
        return false;
      }
    } catch (e) {
      String msg = 'Error de conexión';
      if (e.toString().contains('XMLHttpRequest')) {
        msg = 'Error CORS — ejecuta con: flutter run -d chrome --web-browser-flag "--disable-web-security"';
      } else {
        msg = e.toString().length > 80
            ? e.toString().substring(0, 80)
            : e.toString();
      }
      state = state.copyWith(
        status: AuthStatus.error,
        errorMessage: msg,
      );
      return false;
    }
  }

  void logout() {
    state = const AuthState(status: AuthStatus.loggedOut);
  }
}
