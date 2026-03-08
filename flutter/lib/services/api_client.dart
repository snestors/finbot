import 'package:dio/dio.dart';
import 'package:cookie_jar/cookie_jar.dart';
import 'package:dio_cookie_manager/dio_cookie_manager.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:path_provider/path_provider.dart';
import '../core/constants.dart';
import 'api_client_native.dart' if (dart.library.html) 'api_client_web.dart';

/// Persistent cookie jar — survives app restarts.
final cookieJarProvider = FutureProvider<PersistCookieJar>((ref) async {
  final dir = await getApplicationDocumentsDirectory();
  return PersistCookieJar(storage: FileStorage('${dir.path}/.cookies/'));
});

/// Shared Dio singleton — cookie interceptor is swapped in once PersistCookieJar is ready.
final dioProvider = Provider<Dio>((ref) {
  final dio = Dio(BaseOptions(
    baseUrl: Constants.apiBaseUrl,
    connectTimeout: const Duration(seconds: 10),
    receiveTimeout: const Duration(seconds: 30),
    headers: {'Content-Type': 'application/json'},
  ));

  // Start with in-memory cookies
  final fallbackJar = CookieJar();
  configureDio(dio, fallbackJar);

  // Once persistent jar is ready, replace the cookie interceptor
  ref.listen(cookieJarProvider, (prev, next) {
    final jar = next.valueOrNull;
    if (jar != null) {
      dio.interceptors.removeWhere((i) => i is CookieManager);
      dio.interceptors.add(CookieManager(jar));
    }
  });

  // Also check if already resolved
  final jar = ref.read(cookieJarProvider).valueOrNull;
  if (jar != null) {
    dio.interceptors.removeWhere((i) => i is CookieManager);
    dio.interceptors.add(CookieManager(jar));
  }

  return dio;
});
