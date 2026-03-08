import 'package:dio/dio.dart';
import 'package:dio/browser.dart';
import 'package:cookie_jar/cookie_jar.dart';

void configureDio(Dio dio, CookieJar cookieJar) {
  dio.httpClientAdapter = BrowserHttpClientAdapter(withCredentials: true);
}
