import 'dart:async';
import 'dart:convert';
import 'package:mqtt5_client/mqtt5_client.dart';
import 'package:mqtt5_client/mqtt5_server_client.dart';

/// Callback: serialNumber, channel (1-based), isOn
typedef MqttDeviceStateCallback = void Function(
    String serialNumber, int channel, bool isOn);

/// MQTT v5 service for controlling Zigbee devices via the NSPanel Pro's
/// bridge-cube running on localhost:1884.
///
/// Requires authentication and MQTT v5 user properties on publish.
class MqttService {
  static const String _broker = 'localhost';
  static const int _port = 1884;
  static const String _clientId = 'nspanel_flutter';
  static const String _username = 'finbot';
  static const String _password = 'finbot123';

  MqttServerClient? _client;
  Timer? _reconnectTimer;
  bool _disposed = false;
  bool _connected = false;

  MqttDeviceStateCallback? onDeviceState;
  void Function(bool connected)? onConnectionChanged;

  bool get isConnected => _connected;

  final Set<String> _subscribedDevices = {};

  Future<void> connect() async {
    if (_disposed || _connected) return;

    _client = MqttServerClient(_broker, _clientId)
      ..port = _port
      ..keepAlivePeriod = 30
      ..autoReconnect = true
      ..resubscribeOnAutoReconnect = true
      ..onAutoReconnect = _onAutoReconnect
      ..onAutoReconnected = _onAutoReconnected
      ..onConnected = _onConnected
      ..onDisconnected = _onDisconnected
      ..logging(on: false);

    final connMsg = MqttConnectMessage()
        .withClientIdentifier(_clientId)
        .startClean();
    _client!.connectionMessage = connMsg;

    try {
      await _client!.connect(_username, _password);
    } catch (e) {
      _client?.disconnect();
      _client = null;
      _scheduleReconnect();
      return;
    }

    if (_client?.connectionStatus?.state == MqttConnectionState.connected) {
      _connected = true;
      onConnectionChanged?.call(true);
      _client!.updates.listen(_onMessage);

      for (final serial in _subscribedDevices) {
        _subscribeTopics(serial);
      }
    } else {
      _client?.disconnect();
      _client = null;
      _scheduleReconnect();
    }
  }

  void _onConnected() {
    _connected = true;
    onConnectionChanged?.call(true);
  }

  void _onDisconnected() {
    _connected = false;
    onConnectionChanged?.call(false);
    if (!_disposed) _scheduleReconnect();
  }

  void _onAutoReconnect() {
    _connected = false;
    onConnectionChanged?.call(false);
  }

  void _onAutoReconnected() {
    _connected = true;
    onConnectionChanged?.call(true);
    for (final serial in _subscribedDevices) {
      _subscribeTopics(serial);
    }
  }

  void _scheduleReconnect() {
    if (_disposed) return;
    _reconnectTimer?.cancel();
    _reconnectTimer = Timer(const Duration(seconds: 5), connect);
  }

  void subscribeToDevice(String serialNumber) {
    _subscribedDevices.add(serialNumber);
    if (_connected && _client != null) {
      _subscribeTopics(serialNumber);
    }
  }

  void _subscribeTopics(String serial) {
    if (_client == null) return;
    _client!.subscribe(
        'zigbee/device/$serial/updated/#', MqttQos.atMostOnce);
  }

  void _onMessage(List<MqttReceivedMessage<MqttMessage>> messages) {
    for (final msg in messages) {
      final topic = msg.topic;
      final recMsg = msg.payload as MqttPublishMessage;
      final text = MqttUtilities.bytesToStringAsString(
          recMsg.payload.message!);

      if (text.isEmpty) continue;

      // Parse: zigbee/device/{serial}/updated/toggle/{channel}
      final parts = topic.split('/');
      if (parts.length < 6 ||
          parts[0] != 'zigbee' ||
          parts[1] != 'device' ||
          parts[3] != 'updated' ||
          parts[4] != 'toggle') {
        continue;
      }

      final serial = parts[2];
      final channel = int.tryParse(parts[5]);
      if (channel == null) continue;

      try {
        final json = jsonDecode(text) as Map<String, dynamic>;
        final toggleState = json['toggleState'] as String?;
        if (toggleState != null) {
          onDeviceState?.call(serial, channel, toggleState == 'on');
        }
      } catch (_) {}
    }
  }

  /// Toggle a Zigbee device channel via MQTT v5 with user properties.
  void toggleSwitch(String serialNumber, int channel, bool on) {
    if (!_connected || _client == null) return;

    final topic = 'zigbee/device/$serialNumber/update/toggle/$channel';
    final payload = jsonEncode({'toggleState': on ? 'on' : 'off'});

    final builder = MqttPayloadBuilder();
    builder.addString(payload);

    // User properties required by bridge-cube
    final prop1 = MqttUserProperty();
    prop1.pairName = 'reqClientId';
    prop1.pairValue = 'zigbee2cube';
    final prop2 = MqttUserProperty();
    prop2.pairName = 'reqSequence';
    prop2.pairValue = DateTime.now().millisecondsSinceEpoch.toString();
    final userProps = [prop1, prop2];

    _client!.publishMessage(
      topic,
      MqttQos.atMostOnce,
      builder.payload!,
      userProperties: userProps,
    );
  }

  void disconnect() {
    _disposed = true;
    _reconnectTimer?.cancel();
    _client?.disconnect();
    _client = null;
    _connected = false;
  }
}
