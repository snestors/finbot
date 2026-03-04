class Constants {
  Constants._();

  static const String apiBaseUrl = 'https://findagent.kyn3d.com';
  static String get wsUrl => apiBaseUrl.replaceFirst('https', 'wss');
}
