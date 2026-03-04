import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:nspanel_app/app.dart';

void main() {
  testWidgets('App renders smoke test', (WidgetTester tester) async {
    await tester.pumpWidget(const ProviderScope(child: NSPanelApp()));
    expect(find.text('INICIO'), findsOneWidget);
    expect(find.text('CONSUMO'), findsOneWidget);
  });
}
