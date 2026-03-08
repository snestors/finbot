/// Represents a single channel/outlet of a Zigbee device.
class ZigbeeDevice {
  final String deviceId;
  final String name;
  final String model;
  final int outlet; // channel number (0, 1, etc.)
  final bool isOn;
  final bool online;

  const ZigbeeDevice({
    required this.deviceId,
    required this.name,
    this.model = '',
    required this.outlet,
    this.isOn = false,
    this.online = true,
  });

  ZigbeeDevice copyWith({
    bool? isOn,
    bool? online,
    String? name,
  }) {
    return ZigbeeDevice(
      deviceId: deviceId,
      name: name ?? this.name,
      model: model,
      outlet: outlet,
      isOn: isOn ?? this.isOn,
      online: online ?? this.online,
    );
  }

  /// Unique key combining device ID and outlet for lookups.
  String get key => '${deviceId}_$outlet';
}
