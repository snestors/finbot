class ControlDevice {
  final String id;
  final String name;
  final String iconName;
  final String colorHex;
  final bool isActive;
  final int sortOrder;
  final String? createdAt;
  final String? zigbeeSerial;
  final int? zigbeeChannel;

  const ControlDevice({
    required this.id,
    required this.name,
    this.iconName = 'lightbulb',
    this.colorHex = '#F59E0B',
    this.isActive = false,
    this.sortOrder = 0,
    this.createdAt,
    this.zigbeeSerial,
    this.zigbeeChannel,
  });

  ControlDevice copyWith({
    String? name,
    String? iconName,
    String? colorHex,
    bool? isActive,
    int? sortOrder,
    String? zigbeeSerial,
    int? zigbeeChannel,
  }) {
    return ControlDevice(
      id: id,
      name: name ?? this.name,
      iconName: iconName ?? this.iconName,
      colorHex: colorHex ?? this.colorHex,
      isActive: isActive ?? this.isActive,
      sortOrder: sortOrder ?? this.sortOrder,
      createdAt: createdAt,
      zigbeeSerial: zigbeeSerial ?? this.zigbeeSerial,
      zigbeeChannel: zigbeeChannel ?? this.zigbeeChannel,
    );
  }

  factory ControlDevice.fromJson(Map<String, dynamic> json) => ControlDevice(
        id: json['id']?.toString() ?? '',
        name: json['name'] as String? ?? '',
        iconName: json['icon_name'] as String? ?? 'lightbulb',
        colorHex: json['color_hex'] as String? ?? '#F59E0B',
        isActive: json['is_active'] == 1 || json['is_active'] == true,
        sortOrder: (json['sort_order'] as num?)?.toInt() ?? 0,
        createdAt: json['created_at'] as String?,
        zigbeeSerial: json['zigbee_serial'] as String?,
        zigbeeChannel: (json['zigbee_channel'] as num?)?.toInt(),
      );

  Map<String, dynamic> toJson() => {
        'name': name,
        'icon_name': iconName,
        'color_hex': colorHex,
        'is_active': isActive,
        'sort_order': sortOrder,
        if (zigbeeSerial != null) 'zigbee_serial': zigbeeSerial,
        if (zigbeeChannel != null) 'zigbee_channel': zigbeeChannel,
      };

  /// Firestore document format (camelCase).
  factory ControlDevice.fromFirestore(String docId, Map<String, dynamic> data) =>
      ControlDevice(
        id: docId,
        name: data['name'] as String? ?? '',
        iconName: data['iconName'] as String? ?? 'lightbulb',
        colorHex: data['colorHex'] as String? ?? '#F59E0B',
        isActive: data['isActive'] == true,
        sortOrder: (data['sortOrder'] as num?)?.toInt() ?? 0,
        zigbeeSerial: data['zigbeeSerial'] as String?,
        zigbeeChannel: (data['zigbeeChannel'] as num?)?.toInt(),
      );

  Map<String, dynamic> toFirestore() => {
        'name': name,
        'iconName': iconName,
        'colorHex': colorHex,
        'isActive': isActive,
        'sortOrder': sortOrder,
        'zigbeeSerial': zigbeeSerial,
        'zigbeeChannel': zigbeeChannel,
      };
}
