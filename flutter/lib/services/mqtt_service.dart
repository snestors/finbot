import 'dart:async';
import 'dart:convert';
import 'package:mqtt_client/mqtt_client.dart';
import 'package:mqtt_client/mqtt_server_client.dart';

/// Callback signature for device state updates from MQTT.
typedef MqttDeviceStateCallback = void Function(
    String deviceId, Map<String, dynamic> params);

/// MQTT service for controlling Zigbee devices via the local eWeLink broker
/// running on the NSPanel at localhost:1884.
///
/// eWeLink CAST/iHost MQTT topic patterns:
///   Publish commands:  device/{deviceId}/thing/property/set
///   Subscribe state:   device/{deviceId}/thing/property/report
///   Fallback:          subscribe to # on connect to discover topics
class MqttService {
  static const String _broker = 'localhost';
  static const int _port = 1884;
  static const String _clientId = 'nspanel_flutter';

  MqttServerClient? _client;
  Timer? _reconnectTimer;
  bool _disposed = false;
  bool _connected = false;

  /// Called when a device state update arrives.
  MqttDeviceStateCallback? onDeviceState;

  /// Called when connection status changes.
  void Function(bool connected)? onConnectionChanged;

  bool get isConnected => _connected;

  /// Known topic patterns to try. The service subscribes to all of them
  /// and also to '#' briefly to discover any other topics.
  static List<String> _stateTopics(String deviceId) => [
        'device/$deviceId/thing/property/report',
        'device/$deviceId/report',
        'switch/$deviceId/report',
      ];

  static List<String> _commandTopics(String deviceId) => [
        'device/$deviceId/thing/property/set',
        'device/$deviceId/set',
        'switch/$deviceId/set',
      ];

  /// Active topic that was confirmed to work, per device.
  /// Starts null; once a message arrives on a topic, that pattern is locked in.
  String? _confirmedCommandPattern;
  String? _confirmedStatePattern;

  /// Set of device IDs we are subscribed to.
  final Set<String> _subscribedDevices = {};

  /// Connect to the local MQTT broker.
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
      ..logging(on: false)
      ..setProtocolV311();

    // Simple connection message, no auth required for local broker
    final connMsg = MqttConnectMessage()
        .withClientIdentifier(_clientId)
        .startClean()
        .withWillQos(MqttQos.atMostOnce);
    _client!.connectionMessage = connMsg;

    try {
      await _client!.connect();
    } catch (e) {
      _client?.disconnect();
      _client = null;
      _scheduleReconnect();
      return;
    }

    if (_client?.connectionStatus?.state == MqttConnectionState.connected) {
      _connected = true;
      onConnectionChanged?.call(true);

      // Listen to all incoming messages
      _client!.updates?.listen(_onMessage);

      // Re-subscribe to any previously tracked devices
      for (final deviceId in _subscribedDevices) {
        _subscribeTopics(deviceId);
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
    if (!_disposed) {
      _scheduleReconnect();
    }
  }

  void _onAutoReconnect() {
    _connected = false;
    onConnectionChanged?.call(false);
  }

  void _onAutoReconnected() {
    _connected = true;
    onConnectionChanged?.call(true);
    // Re-subscribe after reconnect
    for (final deviceId in _subscribedDevices) {
      _subscribeTopics(deviceId);
    }
  }

  void _scheduleReconnect() {
    if (_disposed) return;
    _reconnectTimer?.cancel();
    _reconnectTimer = Timer(const Duration(seconds: 5), connect);
  }

  /// Subscribe to state topics for a specific device.
  void subscribeToDevice(String deviceId) {
    _subscribedDevices.add(deviceId);
    if (_connected && _client != null) {
      _subscribeTopics(deviceId);
    }
  }

  void _subscribeTopics(String deviceId) {
    if (_client == null) return;

    // If we already confirmed a pattern, only subscribe to that
    if (_confirmedStatePattern != null) {
      final topic = _confirmedStatePattern!.replaceAll('{id}', deviceId);
      _client!.subscribe(topic, MqttQos.atMostOnce);
      return;
    }

    // Subscribe to all possible state topics to discover which one works
    for (final topic in _stateTopics(deviceId)) {
      _client!.subscribe(topic, MqttQos.atMostOnce);
    }

    // Also subscribe to wildcard to discover any unexpected topics
    // from this device. Use device-specific wildcard to limit noise.
    _client!.subscribe('device/$deviceId/#', MqttQos.atMostOnce);
    _client!.subscribe('switch/$deviceId/#', MqttQos.atMostOnce);
  }

  /// Process incoming MQTT messages.
  void _onMessage(List<MqttReceivedMessage<MqttMessage>> messages) {
    for (final msg in messages) {
      final topic = msg.topic;
      final payload = msg.payload as MqttPublishMessage;
      final text = MqttPublishPayload.bytesToStringAsString(
          payload.payload.message);

      if (text.isEmpty) continue;

      try {
        final json = jsonDecode(text) as Map<String, dynamic>;

        // Extract device ID from topic or payload
        String? deviceId = json['deviceid'] as String?;
        if (deviceId == null) {
          // Try to extract from topic: device/{deviceId}/...
          final parts = topic.split('/');
          if (parts.length >= 2) {
            deviceId = parts[1];
          }
        }

        if (deviceId == null) continue;

        // Lock in the confirmed state pattern from this topic
        if (_confirmedStatePattern == null) {
          _confirmedStatePattern =
              topic.replaceAll(deviceId, '{id}');
          // Also infer the command pattern
          if (topic.contains('/report')) {
            _confirmedCommandPattern =
                topic.replaceAll('/report', '/set').replaceAll(deviceId, '{id}');
          }
        }

        // Extract params - could be in 'params' key or at top level
        final params = json['params'] as Map<String, dynamic>? ?? json;
        onDeviceState?.call(deviceId, Map<String, dynamic>.from(params));
      } catch (_) {
        // Ignore malformed messages
      }
    }
  }

  /// Send a switch toggle command to a Zigbee device.
  ///
  /// [deviceId] - the eWeLink device ID (e.g. 'a44003f19f')
  /// [outlet] - channel number (0 = channel 1, 1 = channel 2)
  /// [on] - true to turn on, false to turn off
  void toggleSwitch(String deviceId, int outlet, bool on) {
    if (!_connected || _client == null) return;

    final payload = jsonEncode({
      'deviceid': deviceId,
      'params': {
        'switches': [
          {'outlet': outlet, 'switch': on ? 'on' : 'off'},
        ],
      },
    });

    // Publish to confirmed topic or try all known command topics
    if (_confirmedCommandPattern != null) {
      final topic = _confirmedCommandPattern!.replaceAll('{id}', deviceId);
      _publish(topic, payload);
    } else {
      // Try all known command topic patterns
      for (final topic in _commandTopics(deviceId)) {
        _publish(topic, payload);
      }
    }
  }

  void _publish(String topic, String payload) {
    if (_client == null) return;
    final builder = MqttClientPayloadBuilder();
    builder.addString(payload);
    _client!.publishMessage(topic, MqttQos.atMostOnce, builder.payload!);
  }

  /// Clean disconnect.
  void disconnect() {
    _disposed = true;
    _reconnectTimer?.cancel();
    _client?.disconnect();
    _client = null;
    _connected = false;
  }
}
