import 'package:dio/dio.dart';
import 'package:cookie_jar/cookie_jar.dart';
import 'package:dio_cookie_manager/dio_cookie_manager.dart';

void configureDio(Dio dio, CookieJar cookieJar) {
  dio.interceptors.add(CookieManager(cookieJar));
}
