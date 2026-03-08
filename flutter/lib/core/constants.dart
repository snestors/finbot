class Constants {
  Constants._();

  static const String apiBaseUrl = 'http://192.168.1.62:8080';
  static String get wsUrl => apiBaseUrl.replaceFirst('http', 'ws');
}
