class Constants {
  Constants._();

  // Sonoff POW Elite mDNS credentials
  static const String sonoffDeviceId = '10027d4fc7';
  static const String sonoffDeviceKey = '42224a14-5704-4167-96d2-516df73614e5';

  // Billing
  static const double defaultCostoKwh = 0.85;
  static const int billingDay = 7;

  // MQTT
  static const String mqttBroker = 'localhost';
  static const int mqttPort = 1884;
  static const String mqttUsername = 'finbot';
  static const String mqttPassword = 'finbot123';
}
