import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:lucide_icons/lucide_icons.dart';
import '../../core/app_colors.dart';
import '../../core/icon_registry.dart';
import '../../core/color_registry.dart';
import '../../models/control_device.dart';
import '../../providers/devices_provider.dart';

class ConfigScreen extends ConsumerWidget {
  const ConfigScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final devices = ref.watch(devicesProvider);

    return Scaffold(
      backgroundColor: AppColors.bgPrimary,
      body: SafeArea(
        child: Column(
          children: [
            _buildHeader(context),
            Expanded(
              child: devices.isEmpty
                  ? _buildEmptyState()
                  : ReorderableListView.builder(
                      padding: const EdgeInsets.fromLTRB(24, 0, 24, 24),
                      proxyDecorator: (child, index, animation) {
                        return Material(
                          color: Colors.transparent,
                          child: child,
                        );
                      },
                      itemCount: devices.length,
                      onReorder: (oldIndex, newIndex) {
                        ref
                            .read(devicesProvider.notifier)
                            .reorder(oldIndex, newIndex);
                      },
                      itemBuilder: (context, index) {
                        final device = devices[index];
                        return _DeviceListTile(
                          key: ValueKey(device.id),
                          device: device,
                          onEdit: () => _showDeviceDialog(context, ref,
                              device: device),
                          onDelete: () => _confirmDelete(context, ref, device),
                        );
                      },
                    ),
            ),
          ],
        ),
      ),
      floatingActionButton: FloatingActionButton(
        backgroundColor: AppColors.accentBlue,
        onPressed: () => _showDeviceDialog(context, ref),
        child: const Icon(LucideIcons.plus, color: Colors.white),
      ),
    );
  }

  Widget _buildHeader(BuildContext context) {
    return Container(
      height: 56,
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Row(
        children: [
          GestureDetector(
            onTap: () => Navigator.of(context).pop(),
            behavior: HitTestBehavior.opaque,
            child: Container(
              width: 48,
              height: 48,
              decoration: BoxDecoration(
                color: AppColors.bgCard,
                borderRadius: BorderRadius.circular(14),
              ),
              child: const Icon(LucideIcons.arrowLeft,
                  color: AppColors.textPrimary, size: 20),
            ),
          ),
          const SizedBox(width: 14),
          const Text(
            'Configurar Control',
            style: TextStyle(
              color: AppColors.textPrimary,
              fontSize: 18,
              fontWeight: FontWeight.w700,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: const [
          Icon(LucideIcons.layoutGrid, color: AppColors.textMuted, size: 48),
          SizedBox(height: 16),
          Text(
            'Sin dispositivos',
            style: TextStyle(
              color: AppColors.textSecondary,
              fontSize: 16,
              fontWeight: FontWeight.w600,
            ),
          ),
          SizedBox(height: 4),
          Text(
            'Toca + para agregar uno',
            style: TextStyle(
              color: AppColors.textMuted,
              fontSize: 13,
            ),
          ),
        ],
      ),
    );
  }

  void _confirmDelete(
      BuildContext context, WidgetRef ref, ControlDevice device) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AppColors.bgCard,
        title: const Text('Eliminar dispositivo',
            style: TextStyle(color: AppColors.textPrimary)),
        content: Text('¿Eliminar "${device.name}"?',
            style: const TextStyle(color: AppColors.textSecondary)),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Cancelar'),
          ),
          TextButton(
            onPressed: () {
              ref.read(devicesProvider.notifier).remove(device.id);
              Navigator.pop(ctx);
            },
            child: const Text('Eliminar',
                style: TextStyle(color: AppColors.accentRed)),
          ),
        ],
      ),
    );
  }

  void _showDeviceDialog(BuildContext context, WidgetRef ref,
      {ControlDevice? device}) {
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => _DeviceFormScreen(device: device),
      ),
    );
  }
}

class _DeviceListTile extends StatelessWidget {
  final ControlDevice device;
  final VoidCallback onEdit;
  final VoidCallback onDelete;

  const _DeviceListTile({
    super.key,
    required this.device,
    required this.onEdit,
    required this.onDelete,
  });

  @override
  Widget build(BuildContext context) {
    final iconColor = ColorRegistry.resolve(device.colorHex);
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: AppColors.bgCard,
        borderRadius: BorderRadius.circular(14),
      ),
      child: Row(
        children: [
          Container(
            width: 48,
            height: 48,
            decoration: BoxDecoration(
              color: AppColors.bgCardLight,
              borderRadius: BorderRadius.circular(14),
            ),
            child: Icon(
              IconRegistry.resolve(device.iconName),
              color: iconColor,
              size: 22,
            ),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  device.name,
                  style: const TextStyle(
                    color: AppColors.textPrimary,
                    fontSize: 15,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  device.iconName,
                  style: const TextStyle(
                    color: AppColors.textMuted,
                    fontSize: 12,
                  ),
                ),
              ],
            ),
          ),
          // 48dp touch targets for action buttons
          GestureDetector(
            onTap: onEdit,
            behavior: HitTestBehavior.opaque,
            child: const SizedBox(
              width: 48,
              height: 48,
              child: Center(
                child: Icon(LucideIcons.pencil, color: AppColors.textMuted, size: 18),
              ),
            ),
          ),
          GestureDetector(
            onTap: onDelete,
            behavior: HitTestBehavior.opaque,
            child: const SizedBox(
              width: 48,
              height: 48,
              child: Center(
                child: Icon(LucideIcons.trash2, color: AppColors.accentRed, size: 18),
              ),
            ),
          ),
          ReorderableDragStartListener(
            index: 0,
            child: const SizedBox(
              width: 48,
              height: 48,
              child: Center(
                child: Icon(LucideIcons.gripVertical,
                    color: AppColors.textMuted, size: 18),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

// ─── Device Add/Edit Form ─────────────────────────────────────

class _DeviceFormScreen extends ConsumerStatefulWidget {
  final ControlDevice? device;
  const _DeviceFormScreen({this.device});

  @override
  ConsumerState<_DeviceFormScreen> createState() => _DeviceFormScreenState();
}

class _DeviceFormScreenState extends ConsumerState<_DeviceFormScreen> {
  late final TextEditingController _nameCtrl;
  late String _selectedIcon;
  late String _selectedColor;

  bool get _isEditing => widget.device != null;

  @override
  void initState() {
    super.initState();
    _nameCtrl = TextEditingController(text: widget.device?.name ?? '');
    _selectedIcon = widget.device?.iconName ?? 'lightbulb';
    _selectedColor = widget.device?.colorHex ?? '#F59E0B';
  }

  @override
  void dispose() {
    _nameCtrl.dispose();
    super.dispose();
  }

  void _save() {
    final name = _nameCtrl.text.trim();
    if (name.isEmpty) return;

    if (_isEditing) {
      ref.read(devicesProvider.notifier).update(
            widget.device!.copyWith(
              name: name,
              iconName: _selectedIcon,
              colorHex: _selectedColor,
            ),
          );
    } else {
      ref.read(devicesProvider.notifier).add(
            ControlDevice(
              id: '',
              name: name,
              iconName: _selectedIcon,
              colorHex: _selectedColor,
            ),
          );
    }
    Navigator.of(context).pop();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.bgPrimary,
      body: SafeArea(
        child: Column(
          children: [
            _buildHeader(),
            Expanded(
              child: SingleChildScrollView(
                padding: const EdgeInsets.all(24),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    _buildNameField(),
                    const SizedBox(height: 24),
                    _buildColorPicker(),
                    const SizedBox(height: 24),
                    _buildIconPicker(),
                  ],
                ),
              ),
            ),
            _buildSaveButton(),
          ],
        ),
      ),
    );
  }

  Widget _buildHeader() {
    return Container(
      height: 56,
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Row(
        children: [
          GestureDetector(
            onTap: () => Navigator.of(context).pop(),
            behavior: HitTestBehavior.opaque,
            child: Container(
              width: 48,
              height: 48,
              decoration: BoxDecoration(
                color: AppColors.bgCard,
                borderRadius: BorderRadius.circular(14),
              ),
              child: const Icon(LucideIcons.arrowLeft,
                  color: AppColors.textPrimary, size: 20),
            ),
          ),
          const SizedBox(width: 14),
          Text(
            _isEditing ? 'Editar Dispositivo' : 'Nuevo Dispositivo',
            style: const TextStyle(
              color: AppColors.textPrimary,
              fontSize: 18,
              fontWeight: FontWeight.w700,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildNameField() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'Nombre',
          style: TextStyle(
            color: AppColors.textSecondary,
            fontSize: 13,
            fontWeight: FontWeight.w500,
          ),
        ),
        const SizedBox(height: 8),
        TextField(
          controller: _nameCtrl,
          style: const TextStyle(color: AppColors.textPrimary, fontSize: 16),
          decoration: InputDecoration(
            hintText: 'Ej: Sala, Garage, Piscina...',
            hintStyle: const TextStyle(color: AppColors.textMuted),
            filled: true,
            fillColor: AppColors.bgCard,
            border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(14),
              borderSide: BorderSide.none,
            ),
            contentPadding:
                const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
          ),
        ),
      ],
    );
  }

  Widget _buildColorPicker() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'Color del ícono',
          style: TextStyle(
            color: AppColors.textSecondary,
            fontSize: 13,
            fontWeight: FontWeight.w500,
          ),
        ),
        const SizedBox(height: 12),
        Wrap(
          spacing: 10,
          runSpacing: 10,
          children: ColorRegistry.allHex.map((hex) {
            final isSelected = _selectedColor == hex;
            // 48dp touch target wrapping a 40dp visual circle
            return GestureDetector(
              onTap: () => setState(() => _selectedColor = hex),
              behavior: HitTestBehavior.opaque,
              child: SizedBox(
                width: 48,
                height: 48,
                child: Center(
                  child: Container(
                    width: 40,
                    height: 40,
                    decoration: BoxDecoration(
                      color: ColorRegistry.resolve(hex),
                      shape: BoxShape.circle,
                      border: isSelected
                          ? Border.all(color: AppColors.textPrimary, width: 3)
                          : null,
                    ),
                    child: isSelected
                        ? const Icon(LucideIcons.check,
                            color: AppColors.bgPrimary, size: 18)
                        : null,
                  ),
                ),
              ),
            );
          }).toList(),
        ),
      ],
    );
  }

  Widget _buildIconPicker() {
    final icons = IconRegistry.available.entries.toList();
    // Adaptive column count: more columns in landscape
    final isLandscape = MediaQuery.of(context).size.width >
        MediaQuery.of(context).size.height;
    final crossAxisCount = isLandscape ? 8 : 6;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'Ícono',
          style: TextStyle(
            color: AppColors.textSecondary,
            fontSize: 13,
            fontWeight: FontWeight.w500,
          ),
        ),
        const SizedBox(height: 12),
        GridView.builder(
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
            crossAxisCount: crossAxisCount,
            mainAxisSpacing: 8,
            crossAxisSpacing: 8,
          ),
          itemCount: icons.length,
          itemBuilder: (context, index) {
            final entry = icons[index];
            final isSelected = _selectedIcon == entry.key;
            // Each grid cell is at least 48dp (grid fills available space)
            return GestureDetector(
              onTap: () => setState(() => _selectedIcon = entry.key),
              behavior: HitTestBehavior.opaque,
              child: Container(
                constraints: const BoxConstraints(minWidth: 48, minHeight: 48),
                decoration: BoxDecoration(
                  color: isSelected ? AppColors.accentBlue : AppColors.bgCard,
                  borderRadius: BorderRadius.circular(12),
                  border: isSelected
                      ? null
                      : Border.all(color: AppColors.borderSubtle, width: 1),
                ),
                child: Icon(
                  entry.value,
                  color: isSelected
                      ? AppColors.textPrimary
                      : ColorRegistry.resolve(_selectedColor),
                  size: 22,
                ),
              ),
            );
          },
        ),
      ],
    );
  }

  Widget _buildSaveButton() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(24, 0, 24, 16),
      child: SizedBox(
        width: double.infinity,
        // Minimum 48dp height for touch target
        height: 52,
        child: ElevatedButton(
          onPressed: _save,
          style: ElevatedButton.styleFrom(
            backgroundColor: AppColors.accentBlue,
            foregroundColor: AppColors.textPrimary,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(14),
            ),
          ),
          child: Text(
            _isEditing ? 'Guardar Cambios' : 'Agregar Dispositivo',
            style: const TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.w600,
            ),
          ),
        ),
      ),
    );
  }
}
