// This is a basic Flutter widget test.
//
// To perform an interaction with a widget in your test, use the WidgetTester
// utility in the flutter_test package. For example, you can send tap and scroll
// gestures. You can also use WidgetTester to find child widgets in the widget
// tree, read text, and verify that the values of widget properties are correct.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:safedrivevision_app/widgets/status_badge.dart';
import 'package:safedrivevision_app/models/alert_model.dart';

void main() {
  testWidgets('StatusBadge displays correctly when connected', (WidgetTester tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: StatusBadge(isConnected: true),
        ),
      ),
    );
    
    expect(find.byType(StatusBadge), findsOneWidget);
    await tester.pump();
  });

  testWidgets('StatusBadge displays correctly when disconnected', (WidgetTester tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: StatusBadge(isConnected: false),
        ),
      ),
    );
    
    expect(find.byType(StatusBadge), findsOneWidget);
    await tester.pump();
  });

  test('AlertData model works correctly', () {
    final alert = AlertData(
      eyeClosed: true,
      yawning: false,
      phoneDetected: false,
      notLookingForward: false,
      headTiltAlert: false,
    );
    
    expect(alert.eyeClosed, true);
    expect(alert.yawning, false);
    expect(alert.hasAnyAlert, true);
  });
}
