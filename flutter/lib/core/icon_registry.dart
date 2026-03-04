import 'package:flutter/material.dart';
import 'package:lucide_icons/lucide_icons.dart';

/// Maps string icon names to IconData for persistence and the icon picker.
class IconRegistry {
  IconRegistry._();

  static const Map<String, IconData> available = {
    'sofa': LucideIcons.sofa,
    'lamp': LucideIcons.lamp,
    'sun': LucideIcons.sun,
    'moon': LucideIcons.moon,
    'zap': LucideIcons.zap,
    'plug': LucideIcons.plug,
    'fan': LucideIcons.fan,
    'thermometer': LucideIcons.thermometer,
    'droplets': LucideIcons.droplets,
    'flame': LucideIcons.flame,
    'tv': LucideIcons.tv,
    'monitor': LucideIcons.monitor,
    'speaker': LucideIcons.speaker,
    'wifi': LucideIcons.wifi,
    'lock': LucideIcons.lock,
    'unlock': LucideIcons.unlock,
    'camera': LucideIcons.camera,
    'bell': LucideIcons.bell,
    'home': LucideIcons.home,
    'door_open': LucideIcons.doorOpen,
    'car': LucideIcons.car,
    'palmtree': LucideIcons.palmtree,
    'flower': LucideIcons.flower2,
    'soup': LucideIcons.soup,
    'coffee': LucideIcons.coffee,
    'bath': LucideIcons.bath,
    'bed': LucideIcons.bed,
    'baby': LucideIcons.baby,
    'dog': LucideIcons.dog,
    'power': LucideIcons.power,
    'lightbulb': LucideIcons.lightbulb,
    'blinds': LucideIcons.blinds,
    'air_vent': LucideIcons.airVent,
    'refrigerator': LucideIcons.refrigerator,
    'gauge': LucideIcons.gauge,
    'shield': LucideIcons.shield,
  };

  static IconData resolve(String name) =>
      available[name] ?? LucideIcons.helpCircle;

  static String nameOf(IconData icon) {
    for (final entry in available.entries) {
      if (entry.value == icon) return entry.key;
    }
    return 'home';
  }
}
