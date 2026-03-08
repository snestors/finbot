import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'core/app_colors.dart';
import 'core/theme.dart';
import 'providers/auth_provider.dart';
import 'providers/devices_provider.dart';
import 'providers/system_stats_provider.dart';
import 'providers/consumo_provider.dart';
import 'providers/inactivity_provider.dart';
import 'providers/zigbee_provider.dart';
import 'screens/login_screen.dart';
import 'screens/home/home_screen.dart';
import 'screens/consumo/consumo_screen.dart';
import 'screens/screensaver/screensaver_screen.dart';
import 'widgets/bottom_tab_bar.dart';

class NSPanelApp extends StatelessWidget {
  const NSPanelApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'NSPanel Dashboard',
      debugShowCheckedModeBanner: false,
      theme: buildAppTheme(),
      home: const _AuthGate(),
    );
  }
}

class _AuthGate extends ConsumerWidget {
  const _AuthGate();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final auth = ref.watch(authProvider);
    switch (auth.status) {
      case AuthStatus.loggedIn:
        return const MainShell();
      case AuthStatus.unknown:
      case AuthStatus.loading:
        return const Scaffold(
          backgroundColor: AppColors.bgPrimary,
          body: Center(
            child: CircularProgressIndicator(color: AppColors.accentBlue),
          ),
        );
      default:
        return const LoginScreen();
    }
  }
}

class MainShell extends ConsumerStatefulWidget {
  const MainShell({super.key});

  @override
  ConsumerState<MainShell> createState() => _MainShellState();
}

class _MainShellState extends ConsumerState<MainShell> {
  int _currentIndex = 0;
  bool _screensaverShowing = false;

  @override
  void initState() {
    super.initState();
    // Kiosk mode: hide system UI overlays for NSPanel
    SystemChrome.setEnabledSystemUIMode(SystemUiMode.immersiveSticky);
    // Force portrait orientation for NSPanel
    SystemChrome.setPreferredOrientations([
      DeviceOrientation.portraitUp,
    ]);
    // Start real-time data, load consumo, and connect MQTT
    Future.microtask(() {
      ref.read(systemStatsProvider.notifier).start();
      ref.read(consumoProvider.notifier).load();
      // Initialize Zigbee provider — connects MQTT
      ref.read(zigbeeStateProvider);
    });
    // Sync Zigbee subscriptions whenever devices change
    ref.listenManual(devicesProvider, (prev, next) {
      ref.read(zigbeeStateProvider.notifier).syncDevices(next);
    }, fireImmediately: true);
  }

  @override
  void dispose() {
    // Restore orientations on dispose
    SystemChrome.setPreferredOrientations(DeviceOrientation.values);
    SystemChrome.setEnabledSystemUIMode(SystemUiMode.edgeToEdge);
    super.dispose();
  }

  void _onUserInteraction() {
    ref.read(inactivityProvider.notifier).registerActivity();
  }

  void _showScreensaver() {
    if (_screensaverShowing) return;
    _screensaverShowing = true;
    Navigator.of(context)
        .push(
      PageRouteBuilder(
        opaque: true,
        pageBuilder: (_, __, ___) => const ScreensaverScreen(),
        transitionsBuilder: (_, animation, __, child) {
          return FadeTransition(opacity: animation, child: child);
        },
        transitionDuration: const Duration(milliseconds: 600),
      ),
    )
        .then((_) {
      _screensaverShowing = false;
      _onUserInteraction();
    });
  }

  final _screens = const [
    HomeScreen(),
    ConsumoScreen(),
  ];

  @override
  Widget build(BuildContext context) {
    // Listen for inactivity → trigger screensaver
    ref.listen(inactivityProvider, (prev, shouldShow) {
      if (shouldShow && !_screensaverShowing) {
        _showScreensaver();
      }
    });

    // Wrap entire UI in a Listener to detect all pointer events
    return Listener(
      onPointerDown: (_) => _onUserInteraction(),
      onPointerMove: (_) => _onUserInteraction(),
      behavior: HitTestBehavior.translucent,
      // WillPopScope prevents back button from exiting (kiosk mode)
      child: PopScope(
        canPop: false,
        child: Scaffold(
          backgroundColor: AppColors.bgPrimary,
          body: SafeArea(
            child: Column(
              children: [
                Expanded(
                  child: IndexedStack(
                    index: _currentIndex,
                    children: _screens,
                  ),
                ),
                BottomTabBar(
                  currentIndex: _currentIndex,
                  onTap: (index) => setState(() => _currentIndex = index),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
