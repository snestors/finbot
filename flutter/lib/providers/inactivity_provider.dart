import 'dart:async';
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Tracks user inactivity and triggers screensaver after a timeout.
/// Default: 60 seconds of no touch activity.
final inactivityProvider =
    StateNotifierProvider<InactivityNotifier, bool>((ref) {
  return InactivityNotifier();
});

class InactivityNotifier extends StateNotifier<bool> {
  Timer? _timer;
  static const _timeout = Duration(seconds: 60);

  /// State: true = screensaver should be shown, false = active
  InactivityNotifier() : super(false) {
    _resetTimer();
  }

  /// Call on any user interaction to reset the inactivity timer.
  void registerActivity() {
    if (state) {
      // Coming back from screensaver
      state = false;
    }
    _resetTimer();
  }

  void _resetTimer() {
    _timer?.cancel();
    _timer = Timer(_timeout, () {
      if (mounted) {
        state = true;
      }
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }
}
