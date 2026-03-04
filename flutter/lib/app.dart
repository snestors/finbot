import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'core/app_colors.dart';
import 'core/theme.dart';
import 'providers/auth_provider.dart';
import 'providers/system_stats_provider.dart';
import 'providers/consumo_provider.dart';
import 'screens/login_screen.dart';
import 'screens/home/home_screen.dart';
import 'screens/consumo/consumo_screen.dart';
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
    if (auth.status == AuthStatus.loggedIn) {
      return const MainShell();
    }
    return const LoginScreen();
  }
}

class MainShell extends ConsumerStatefulWidget {
  const MainShell({super.key});

  @override
  ConsumerState<MainShell> createState() => _MainShellState();
}

class _MainShellState extends ConsumerState<MainShell> {
  int _currentIndex = 0;

  @override
  void initState() {
    super.initState();
    // Start real-time data and load consumo
    Future.microtask(() {
      ref.read(systemStatsProvider.notifier).start();
      ref.read(consumoProvider.notifier).load();
    });
  }

  final _screens = const [
    HomeScreen(),
    ConsumoScreen(),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
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
    );
  }
}
