import 'dart:convert';
import 'package:crypto/crypto.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

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
  Future.microtask(() => notifier.tryRestoreSession());
  return notifier;
});

class AuthNotifier extends StateNotifier<AuthState> {
  final Ref _ref;
  static const _pinHashKey = 'pin_hash';
  static const _loggedInKey = 'logged_in';

  AuthNotifier(this._ref) : super(const AuthState(status: AuthStatus.unknown));

  static String _hashPin(String pin) {
    return sha256.convert(utf8.encode(pin)).toString();
  }

  Future<void> tryRestoreSession() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final loggedIn = prefs.getBool(_loggedInKey) ?? false;
      if (loggedIn) {
        state = state.copyWith(status: AuthStatus.loggedIn);
      } else {
        state = state.copyWith(status: AuthStatus.loggedOut);
      }
    } catch (_) {
      state = state.copyWith(status: AuthStatus.loggedOut);
    }
  }

  Future<bool> login(String pin) async {
    state = state.copyWith(status: AuthStatus.loading, errorMessage: null);
    try {
      final prefs = await SharedPreferences.getInstance();
      final storedHash = prefs.getString(_pinHashKey);

      if (storedHash == null) {
        // First time: set this PIN as the master PIN
        await prefs.setString(_pinHashKey, _hashPin(pin));
        await prefs.setBool(_loggedInKey, true);
        state = state.copyWith(status: AuthStatus.loggedIn);
        return true;
      }

      if (_hashPin(pin) == storedHash) {
        await prefs.setBool(_loggedInKey, true);
        state = state.copyWith(status: AuthStatus.loggedIn);
        return true;
      } else {
        state = state.copyWith(
          status: AuthStatus.error,
          errorMessage: 'PIN incorrecto',
        );
        return false;
      }
    } catch (e) {
      state = state.copyWith(
        status: AuthStatus.error,
        errorMessage: 'Error: ${e.toString().length > 60 ? e.toString().substring(0, 60) : e}',
      );
      return false;
    }
  }

  Future<void> logout() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_loggedInKey, false);
    state = const AuthState(status: AuthStatus.loggedOut);
  }
}
