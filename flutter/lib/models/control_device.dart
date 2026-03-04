import 'dart:convert';

class ControlDevice {
  final String id;
  final String name;
  final String iconName;
  final String colorHex;
  bool isActive;

  ControlDevice({
    required this.id,
    required this.name,
    required this.iconName,
    required this.colorHex,
    this.isActive = false,
  });

  ControlDevice copyWith({
    String? name,
    String? iconName,
    String? colorHex,
    bool? isActive,
  }) {
    return ControlDevice(
      id: id,
      name: name ?? this.name,
      iconName: iconName ?? this.iconName,
      colorHex: colorHex ?? this.colorHex,
      isActive: isActive ?? this.isActive,
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'name': name,
        'iconName': iconName,
        'colorHex': colorHex,
        'isActive': isActive,
      };

  factory ControlDevice.fromJson(Map<String, dynamic> json) => ControlDevice(
        id: json['id'] as String,
        name: json['name'] as String,
        iconName: json['iconName'] as String,
        colorHex: json['colorHex'] as String,
        isActive: json['isActive'] as bool? ?? false,
      );

  static String encodeList(List<ControlDevice> devices) =>
      jsonEncode(devices.map((d) => d.toJson()).toList());

  static List<ControlDevice> decodeList(String json) =>
      (jsonDecode(json) as List)
          .map((e) => ControlDevice.fromJson(e as Map<String, dynamic>))
          .toList();
}
