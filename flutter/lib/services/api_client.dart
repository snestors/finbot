import 'package:dio/dio.dart';
import 'package:cookie_jar/cookie_jar.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:path_provider/path_provider.dart';
import '../core/constants.dart';
import 'api_client_native.dart' if (dart.library.html) 'api_client_web.dart';

/// Persistent cookie jar — survives app restarts.
final cookieJarProvider = FutureProvider<PersistCookieJar>((ref) async {
  final dir = await getApplicationDocumentsDirectory();
  return PersistCookieJar(storage: FileStorage('${dir.path}/.cookies/'));
});

final dioProvider = Provider<Dio>((ref) {
  final dio = Dio(BaseOptions(
    baseUrl: Constants.apiBaseUrl,
    connectTimeout: const Duration(seconds: 10),
    receiveTimeout: const Duration(seconds: 30),
    headers: {'Content-Type': 'application/json'},
  ));

  // Use persistent cookie jar when ready, in-memory fallback during init
  final cookieJarAsync = ref.watch(cookieJarProvider);
  final cookieJar = cookieJarAsync.valueOrNull ?? CookieJar();
  configureDio(dio, cookieJar);

  return dio;
});
