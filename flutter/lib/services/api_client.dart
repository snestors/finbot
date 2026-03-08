import 'package:dio/dio.dart';
import 'package:cookie_jar/cookie_jar.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/constants.dart';
import 'api_client_native.dart' if (dart.library.html) 'api_client_web.dart';

final cookieJarProvider = Provider<CookieJar>((_) => CookieJar());

final dioProvider = Provider<Dio>((ref) {
  final dio = Dio(BaseOptions(
    baseUrl: Constants.apiBaseUrl,
    connectTimeout: const Duration(seconds: 10),
    receiveTimeout: const Duration(seconds: 30),
    headers: {'Content-Type': 'application/json'},
  ));

  final cookieJar = ref.watch(cookieJarProvider);
  configureDio(dio, cookieJar);

  return dio;
});
