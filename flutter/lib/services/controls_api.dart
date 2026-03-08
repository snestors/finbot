import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/control_device.dart';
import 'api_client.dart';

final controlsApiProvider = Provider<ControlsApi>((ref) {
  return ControlsApi(ref.watch(dioProvider));
});

class ControlsApi {
  final Dio _dio;

  ControlsApi(this._dio);

  /// GET /api/controls -> list of ControlDevice
  Future<List<ControlDevice>> fetchAll() async {
    final response = await _dio.get('/api/controls');
    final list = response.data as List<dynamic>;
    return list
        .map((e) => ControlDevice.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  /// POST /api/controls -> returns {"id": "..."}
  Future<String> create(ControlDevice device) async {
    final response = await _dio.post('/api/controls', data: device.toJson());
    return (response.data as Map<String, dynamic>)['id']?.toString() ?? '';
  }

  /// PUT /api/controls/{id}
  Future<void> update(ControlDevice device) async {
    await _dio.put('/api/controls/${device.id}', data: device.toJson());
  }

  /// DELETE /api/controls/{id}
  Future<void> delete(String id) async {
    await _dio.delete('/api/controls/$id');
  }

  /// POST /api/controls/{id}/toggle -> returns full control dict
  Future<ControlDevice> toggle(String id) async {
    final response = await _dio.post('/api/controls/$id/toggle');
    return ControlDevice.fromJson(response.data as Map<String, dynamic>);
  }

  /// PUT /api/controls/reorder with {"ids": [...]}
  Future<void> reorder(List<String> ids) async {
    await _dio.put('/api/controls/reorder', data: {'ids': ids});
  }
}
