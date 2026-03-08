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
  final notifier = AuthNotifier(ref);
  // Try to restore session on creation
  Future.microtask(() => notifier.tryRestoreSession());
  return notifier;
});

class AuthNotifier extends StateNotifier<AuthState> {
  final Ref _ref;

  AuthNotifier(this._ref) : super(const AuthState(status: AuthStatus.unknown));

  /// Try to restore a persisted session by calling a protected endpoint.
  Future<void> tryRestoreSession() async {
    try {
      // Wait for persistent cookie jar to be ready
      await _ref.read(cookieJarProvider.future);
      // Re-read dio so it picks up the persistent cookies
      final dio = _ref.read(dioProvider);
      final response = await dio.get('/api/controls');
      // If we get a 200 with data (not an error), session is valid
      if (response.statusCode == 200 && response.data is! Map) {
        state = state.copyWith(status: AuthStatus.loggedIn);
        return;
      }
      if (response.data is Map && response.data['error'] == 'unauthorized') {
        state = state.copyWith(status: AuthStatus.loggedOut);
        return;
      }
      state = state.copyWith(status: AuthStatus.loggedIn);
    } catch (_) {
      state = state.copyWith(status: AuthStatus.loggedOut);
    }
  }

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

  Future<void> logout() async {
    // Clear persisted cookies so session is fully removed
    try {
      final jar = await _ref.read(cookieJarProvider.future);
      jar.deleteAll();
    } catch (_) {}
    state = const AuthState(status: AuthStatus.loggedOut);
  }
}
