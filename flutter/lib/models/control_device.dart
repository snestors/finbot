class ControlDevice {
  final String id;
  final String name;
  final String iconName;
  final String colorHex;
  final bool isActive;
  final int sortOrder;
  final String? createdAt;

  const ControlDevice({
    required this.id,
    required this.name,
    this.iconName = 'lightbulb',
    this.colorHex = '#F59E0B',
    this.isActive = false,
    this.sortOrder = 0,
    this.createdAt,
  });

  ControlDevice copyWith({
    String? name,
    String? iconName,
    String? colorHex,
    bool? isActive,
    int? sortOrder,
  }) {
    return ControlDevice(
      id: id,
      name: name ?? this.name,
      iconName: iconName ?? this.iconName,
      colorHex: colorHex ?? this.colorHex,
      isActive: isActive ?? this.isActive,
      sortOrder: sortOrder ?? this.sortOrder,
      createdAt: createdAt,
    );
  }

  /// Deserialize from backend JSON (snake_case keys).
  factory ControlDevice.fromJson(Map<String, dynamic> json) => ControlDevice(
        id: json['id']?.toString() ?? '',
        name: json['name'] as String? ?? '',
        iconName: json['icon_name'] as String? ?? 'lightbulb',
        colorHex: json['color_hex'] as String? ?? '#F59E0B',
        isActive: json['is_active'] == 1 || json['is_active'] == true,
        sortOrder: (json['sort_order'] as num?)?.toInt() ?? 0,
        createdAt: json['created_at'] as String?,
      );

  /// Serialize to backend JSON (snake_case keys).
  Map<String, dynamic> toJson() => {
        'id': id,
        'name': name,
        'icon_name': iconName,
        'color_hex': colorHex,
        'is_active': isActive,
        'sort_order': sortOrder,
      };
}
