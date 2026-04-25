// This is a basic Flutter widget test.
//
// To perform an interaction with a widget in your test, use the WidgetTester
// utility in the flutter_test package. For example, you can send tap and scroll
// gestures. You can also use WidgetTester to find child widgets in the widget
// tree, read text, and verify that the values of widget properties are correct.

import 'package:flutter_test/flutter_test.dart';
import 'package:safedrivevision_app/main.dart';
import 'package:safedrivevision_app/screens/home_screen.dart';

void main() {
  testWidgets('App builds successfully', (WidgetTester tester) async {
    await tester.pumpWidget(const SafeDriveVisionApp());
    
    // Verify that the app builds without errors
    expect(find.byType(SafeDriveVisionApp), findsOneWidget);
    
    // Verify HomeScreen is present
    expect(find.byType(HomeScreen), findsOneWidget);
  });
}
