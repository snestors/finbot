import 'package:dio/dio.dart';
import 'package:dio/browser.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:cookie_jar/cookie_jar.dart';
import 'package:dio_cookie_manager/dio_cookie_manager.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/constants.dart';

final cookieJarProvider = Provider<CookieJar>((_) => CookieJar());

final dioProvider = Provider<Dio>((ref) {
  final dio = Dio(BaseOptions(
    baseUrl: Constants.apiBaseUrl,
    connectTimeout: const Duration(seconds: 10),
    receiveTimeout: const Duration(seconds: 30),
    headers: {'Content-Type': 'application/json'},
  ));

  if (kIsWeb) {
    // On web, browser handles cookies automatically.
    // We need withCredentials for cross-origin cookie sending.
    dio.httpClientAdapter = BrowserHttpClientAdapter(withCredentials: true);
  } else {
    // On native platforms, use cookie_jar
    final cookieJar = ref.watch(cookieJarProvider);
    dio.interceptors.add(CookieManager(cookieJar));
  }

  return dio;
});
