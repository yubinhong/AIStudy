import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:study_child/auth_client.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('prepares iOS local network access for the configured host', () async {
    const channel = MethodChannel('study/local-network-test');
    MethodCall? receivedCall;
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, (call) async {
          receivedCall = call;
          return true;
        });
    debugDefaultTargetPlatformOverride = TargetPlatform.iOS;
    addTearDown(() {
      debugDefaultTargetPlatformOverride = null;
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(channel, null);
    });

    await prepareLocalNetworkAccess(
      'http://192.168.1.4:8000',
      channel: channel,
    );

    expect(receivedCall?.method, 'prepare');
    expect(receivedCall?.arguments, {'host': '192.168.1.4', 'port': 8000});
  });

  test('does not invoke the local network channel outside iOS', () async {
    const channel = MethodChannel('study/local-network-test');
    var invoked = false;
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, (call) async {
          invoked = true;
          return true;
        });
    debugDefaultTargetPlatformOverride = TargetPlatform.android;
    addTearDown(() {
      debugDefaultTargetPlatformOverride = null;
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(channel, null);
    });

    await prepareLocalNetworkAccess(
      'http://192.168.1.4:8000',
      channel: channel,
    );

    expect(invoked, isFalse);
  });
}
