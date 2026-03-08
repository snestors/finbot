"""Tool schemas for Claude tool_use API — maps 1:1 to ActionExecutor actions.

Each tool definition follows Claude's tool schema format. The unified agent
sends these to Claude, which returns tool_use blocks that we convert to
ActionExecutor action dicts.
"""

TOOLS: list[dict] = [
    # =========================================================================
    # Movimientos (unified: gasto, ingreso, transferencia, pagos)
    # =========================================================================
    {
        "name": "registrar_gasto",
        "description": "Registra un gasto o compra del usuario. Usa cuando el usuario menciona que gasto dinero en algo.",
        "input_schema": {
            "type": "object",
            "properties": {
                "monto": {"type": "number", "description": "Monto del gasto"},
                "descripcion": {"type": "string", "description": "Descripcion corta del gasto (ej: almuerzo, uber, netflix)"},
                "categoria": {
                    "type": "string",
                    "description": "Categoria del gasto",
                    "enum": ["comida", "transporte", "delivery", "entretenimiento",
                             "servicios", "salud", "compras", "educacion",
                             "suscripciones", "hogar", "ropa", "mascotas",
                             "personal", "supermercado", "otros"],
                },
                "comercio": {"type": "string", "description": "Nombre del comercio o tienda (ej: KFC, Uber, Wong)"},
                "metodo_pago": {"type": "string", "description": "Metodo de pago usado (ej: yape, plin, efectivo, tarjeta, transferencia, deposito)"},
                "moneda": {"type": "string", "description": "Moneda (PEN, USD, etc). Default PEN", "default": "PEN"},
                "cuenta_id": {"type": "integer", "description": "ID de la cuenta de donde sale el dinero. Si el metodo_pago esta vinculado a una cuenta, se auto-linkea."},
                "tarjeta_id": {"type": "integer", "description": "ID de tarjeta de credito si pago con tarjeta"},
                "cuotas": {"type": "integer", "description": "Numero de cuotas si es compra en cuotas. 0 si no aplica.", "default": 0},
                "fecha": {"type": "string", "description": "Fecha del gasto si no es hoy. Valores: 'ayer', 'anteayer', 'YYYY-MM-DD'. Null si es hoy."},
            },
            "required": ["monto"],
        },
    },
    {
        "name": "registrar_ingreso",
        "description": "Registra un ingreso de dinero (sueldo, pago recibido, venta, etc).",
        "input_schema": {
            "type": "object",
            "properties": {
                "monto": {"type": "number", "description": "Monto del ingreso"},
                "descripcion": {"type": "string", "description": "Descripcion del ingreso (ej: sueldo, freelance, venta)"},
                "moneda": {"type": "string", "description": "Moneda (PEN, USD, etc)", "default": "PEN"},
                "cuenta_id": {"type": "integer", "description": "ID de la cuenta donde entra el dinero"},
                "metodo_pago": {"type": "string", "description": "Metodo por el que se recibio"},
                "fecha": {"type": "string", "description": "Fecha si no es hoy"},
            },
            "required": ["monto"],
        },
    },
    {
        "name": "registrar_transferencia",
        "description": "Registra una transferencia entre cuentas propias (mover dinero de una cuenta a otra, retiros ATM, etc).",
        "input_schema": {
            "type": "object",
            "properties": {
                "monto": {"type": "number", "description": "Monto a transferir"},
                "cuenta_id": {"type": "integer", "description": "ID de la cuenta origen"},
                "cuenta_destino_id": {"type": "integer", "description": "ID de la cuenta destino"},
                "descripcion": {"type": "string", "description": "Descripcion (ej: retiro ATM, pase a ahorros)"},
                "moneda": {"type": "string", "description": "Moneda", "default": "PEN"},
                "fecha": {"type": "string", "description": "Fecha si no es hoy"},
            },
            "required": ["monto"],
        },
    },
    {
        "name": "registrar_pago_tarjeta",
        "description": "Registra un pago a tarjeta de credito. NO es un gasto — es pagar la deuda de la tarjeta.",
        "input_schema": {
            "type": "object",
            "properties": {
                "monto": {"type": "number", "description": "Monto del pago"},
                "tarjeta_id": {"type": "integer", "description": "ID de la tarjeta de credito"},
                "cuenta_id": {"type": "integer", "description": "ID de la cuenta de donde sale el pago"},
                "descripcion": {"type": "string", "description": "Descripcion del pago"},
                "fecha": {"type": "string", "description": "Fecha si no es hoy"},
            },
            "required": ["monto"],
        },
    },
    {
        "name": "registrar_pago_deuda",
        "description": "Registra el pago de una cuota de deuda (hipoteca, prestamo, etc).",
        "input_schema": {
            "type": "object",
            "properties": {
                "monto": {"type": "number", "description": "Monto del pago"},
                "deuda_id": {"type": "integer", "description": "ID de la deuda. Si no lo sabes, usa nombre."},
                "nombre": {"type": "string", "description": "Nombre de la deuda para buscarla (ej: hipoteca, BBVA)"},
                "cuenta_id": {"type": "integer", "description": "ID de la cuenta de donde sale el pago"},
                "fecha": {"type": "string", "description": "Fecha si no es hoy"},
            },
            "required": ["monto"],
        },
    },
    {
        "name": "registrar_pago_cobro",
        "description": "Registra un pago recibido de alguien que te debe (cobra a un deudor).",
        "input_schema": {
            "type": "object",
            "properties": {
                "monto": {"type": "number", "description": "Monto recibido"},
                "cobro_id": {"type": "integer", "description": "ID del cobro. Si no lo sabes, usa nombre."},
                "nombre": {"type": "string", "description": "Nombre del deudor (ej: Benjo, Pedro)"},
                "cuenta_id": {"type": "integer", "description": "ID de la cuenta donde entra el dinero"},
                "fecha": {"type": "string", "description": "Fecha si no es hoy"},
            },
            "required": ["monto"],
        },
    },

    # =========================================================================
    # CRUD movimientos
    # =========================================================================
    {
        "name": "actualizar_movimiento",
        "description": "Modifica un movimiento existente (corregir monto, categoria, descripcion, etc). NUNCA crees uno nuevo para corregir.",
        "input_schema": {
            "type": "object",
            "properties": {
                "movimiento_id": {"type": "integer", "description": "ID del movimiento a modificar (del contexto)"},
                "monto": {"type": "number", "description": "Nuevo monto"},
                "categoria": {"type": "string", "description": "Nueva categoria"},
                "descripcion": {"type": "string", "description": "Nueva descripcion"},
                "comercio": {"type": "string", "description": "Nuevo comercio"},
                "metodo_pago": {"type": "string", "description": "Nuevo metodo de pago"},
                "cuenta_id": {"type": "integer", "description": "Nueva cuenta"},
                "tarjeta_id": {"type": "integer", "description": "Nueva tarjeta"},
                "fecha": {"type": "string", "description": "Nueva fecha"},
                "moneda": {"type": "string", "description": "Nueva moneda"},
            },
            "required": ["movimiento_id"],
        },
    },
    {
        "name": "eliminar_movimiento",
        "description": "Elimina UN movimiento por ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "movimiento_id": {"type": "integer", "description": "ID del movimiento a eliminar"},
            },
            "required": ["movimiento_id"],
        },
    },
    {
        "name": "eliminar_movimientos",
        "description": "Elimina multiples movimientos por sus IDs.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "Lista de IDs de movimientos a eliminar",
                },
            },
            "required": ["ids"],
        },
    },
    {
        "name": "buscar_gasto",
        "description": "Busca gastos por texto en descripcion, comercio, categoria.",
        "input_schema": {
            "type": "object",
            "properties": {
                "texto": {"type": "string", "description": "Texto a buscar"},
            },
            "required": ["texto"],
        },
    },
    {
        "name": "importar_estado_cuenta",
        "description": "Importa masivamente lineas de un estado de cuenta de tarjeta de credito.",
        "input_schema": {
            "type": "object",
            "properties": {
                "tarjeta_id": {"type": "integer", "description": "ID de la tarjeta"},
                "lineas": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "fecha": {"type": "string", "description": "Fecha DD/MM/YYYY o YYYY-MM-DD"},
                            "descripcion": {"type": "string"},
                            "monto": {"type": "number", "description": "Positivo=cargo, negativo=pago"},
                            "comercio": {"type": "string"},
                            "categoria": {"type": "string"},
                        },
                        "required": ["monto"],
                    },
                    "description": "Lineas del estado de cuenta",
                },
            },
            "required": ["tarjeta_id", "lineas"],
        },
    },

    # =========================================================================
    # Consultas financieras
    # =========================================================================
    {
        "name": "consultar_resumen",
        "description": "Consulta resumen financiero por periodo. Usa cuando necesitas datos que NO estan en el contexto.",
        "input_schema": {
            "type": "object",
            "properties": {
                "periodo": {
                    "type": "string",
                    "description": "Periodo a consultar",
                    "enum": ["hoy", "semana", "mes", "deudas", "cuentas", "tarjetas", "cobros"],
                },
            },
            "required": ["periodo"],
        },
    },
    {
        "name": "consultar_tipo_cambio",
        "description": "Consulta el tipo de cambio SUNAT (sol/dolar).",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "convertir_moneda",
        "description": "Convierte un monto de una moneda a otra.",
        "input_schema": {
            "type": "object",
            "properties": {
                "monto": {"type": "number", "description": "Monto a convertir"},
                "de": {"type": "string", "description": "Moneda origen (ej: USD)", "default": "USD"},
                "a": {"type": "string", "description": "Moneda destino (ej: PEN)", "default": "PEN"},
            },
            "required": ["monto"],
        },
    },

    # =========================================================================
    # Presupuestos
    # =========================================================================
    {
        "name": "set_presupuesto",
        "description": "Establece o actualiza un presupuesto mensual por categoria.",
        "input_schema": {
            "type": "object",
            "properties": {
                "categoria": {"type": "string", "description": "Categoria del presupuesto"},
                "limite": {"type": "number", "description": "Limite mensual en soles"},
                "alerta_porcentaje": {"type": "integer", "description": "Porcentaje de alerta (default 80)", "default": 80},
            },
            "required": ["categoria", "limite"],
        },
    },

    # =========================================================================
    # Cuentas, tarjetas, deudas, cobros
    # =========================================================================
    {
        "name": "crear_cuenta",
        "description": "Crea una nueva cuenta financiera (banco, efectivo, billetera digital).",
        "input_schema": {
            "type": "object",
            "properties": {
                "nombre": {"type": "string", "description": "Nombre de la cuenta (ej: BCP Ahorro, Efectivo)"},
                "tipo_cuenta": {"type": "string", "description": "Tipo: banco, efectivo, digital", "default": "efectivo"},
                "moneda": {"type": "string", "description": "Moneda de la cuenta", "default": "PEN"},
                "saldo_inicial": {"type": "number", "description": "Saldo inicial", "default": 0},
                "metodos_pago": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Metodos de pago vinculados (ej: ['yape', 'transferencia'])",
                },
            },
            "required": ["nombre"],
        },
    },
    {
        "name": "actualizar_cuenta",
        "description": "Edita una cuenta existente (nombre, metodos de pago, etc).",
        "input_schema": {
            "type": "object",
            "properties": {
                "cuenta_id": {"type": "integer", "description": "ID de la cuenta"},
                "nombre": {"type": "string", "description": "Nuevo nombre"},
                "tipo_cuenta": {"type": "string", "description": "Nuevo tipo"},
                "moneda": {"type": "string", "description": "Nueva moneda"},
                "saldo_inicial": {"type": "number", "description": "Nuevo saldo inicial"},
                "metodos_pago": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Nuevos metodos de pago vinculados",
                },
            },
            "required": ["cuenta_id"],
        },
    },
    {
        "name": "crear_tarjeta",
        "description": "Registra una nueva tarjeta de credito.",
        "input_schema": {
            "type": "object",
            "properties": {
                "nombre": {"type": "string", "description": "Nombre de la tarjeta (ej: Visa BCP)"},
                "banco": {"type": "string", "description": "Banco emisor"},
                "tipo_tarjeta": {"type": "string", "description": "credito o debito", "default": "credito"},
                "ultimos_4": {"type": "string", "description": "Ultimos 4 digitos"},
                "limite_credito": {"type": "number", "description": "Limite de credito", "default": 0},
                "fecha_corte": {"type": "integer", "description": "Dia del mes de fecha de corte"},
                "fecha_pago": {"type": "integer", "description": "Dia del mes de fecha de pago"},
            },
            "required": ["nombre"],
        },
    },
    {
        "name": "agregar_deuda",
        "description": "Registra una nueva deuda (hipoteca, prestamo, etc).",
        "input_schema": {
            "type": "object",
            "properties": {
                "nombre": {"type": "string", "description": "Nombre de la deuda"},
                "saldo": {"type": "number", "description": "Saldo actual de la deuda"},
                "entidad": {"type": "string", "description": "Entidad acreedora"},
                "cuotas_total": {"type": "integer", "description": "Total de cuotas", "default": 0},
                "cuotas_pagadas": {"type": "integer", "description": "Cuotas ya pagadas", "default": 0},
                "cuota_monto": {"type": "number", "description": "Monto de cada cuota", "default": 0},
                "tasa": {"type": "number", "description": "Tasa de interes mensual", "default": 0},
                "pago_minimo": {"type": "number", "description": "Pago minimo mensual", "default": 0},
            },
            "required": ["nombre"],
        },
    },
    {
        "name": "registrar_cobro",
        "description": "Registra una cuenta por cobrar (alguien te debe dinero).",
        "input_schema": {
            "type": "object",
            "properties": {
                "deudor": {"type": "string", "description": "Nombre de quien te debe"},
                "monto": {"type": "number", "description": "Monto total adeudado"},
                "concepto": {"type": "string", "description": "Concepto del cobro"},
                "moneda": {"type": "string", "description": "Moneda", "default": "PEN"},
            },
            "required": ["deudor", "monto"],
        },
    },

    # =========================================================================
    # Perfil y memoria
    # =========================================================================
    {
        "name": "set_perfil",
        "description": "Actualiza el perfil del usuario (nombre, moneda default).",
        "input_schema": {
            "type": "object",
            "properties": {
                "nombre": {"type": "string", "description": "Nombre del usuario"},
                "moneda_default": {"type": "string", "description": "Moneda por defecto (PEN, USD, etc)"},
                "onboarding_completo": {"type": "boolean", "description": "Marcar onboarding como completo"},
            },
        },
    },
    {
        "name": "memorizar",
        "description": "Guarda informacion en la memoria persistente de largo plazo (engram). Usa cuando el usuario comparta datos personales, preferencias, correcciones, o cualquier dato que deba recordarse entre conversaciones.",
        "input_schema": {
            "type": "object",
            "properties": {
                "titulo": {"type": "string", "description": "Titulo corto y descriptivo de lo que se guarda (ej: 'Prefiere categoria comida para almuerzos', 'Su gato se llama Michi')"},
                "contenido": {"type": "string", "description": "El detalle completo a memorizar. Se descriptivo."},
                "tipo": {
                    "type": "string",
                    "description": "Categoria de la memoria",
                    "enum": ["preferencia", "correccion", "dato", "patron", "contexto", "decision"],
                    "default": "dato",
                },
            },
            "required": ["titulo", "contenido"],
        },
    },
    {
        "name": "buscar_memoria",
        "description": "Busca en la memoria persistente de largo plazo. Usa para encontrar datos que el usuario compartio antes (preferencias, correcciones, datos personales, patrones). Busqueda semantica — no necesita coincidencia exacta.",
        "input_schema": {
            "type": "object",
            "properties": {
                "consulta": {"type": "string", "description": "Texto de busqueda (ej: 'preferencias de categoria', 'nombre del gato', 'como le gusta que le diga')"},
                "limite": {"type": "integer", "description": "Maximo de resultados (default 5)", "default": 5},
            },
            "required": ["consulta"],
        },
    },
    {
        "name": "recordar_contexto",
        "description": "Recupera las memorias mas recientes del usuario para tener contexto. Usa al inicio de una conversacion o cuando necesites recordar el contexto general.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limite": {"type": "integer", "description": "Cantidad de memorias recientes (default 10)", "default": 10},
            },
        },
    },

    # =========================================================================
    # Consumo energetico
    # =========================================================================
    {
        "name": "consultar_consumo",
        "description": "Consulta datos de consumo electrico (luz) en un rango de tiempo.",
        "input_schema": {
            "type": "object",
            "properties": {
                "desde": {"type": "string", "description": "Fecha/hora inicio (ISO format)"},
                "hasta": {"type": "string", "description": "Fecha/hora fin (ISO format)"},
                "agrupacion": {
                    "type": "string",
                    "description": "Nivel de agrupacion",
                    "enum": ["minuto", "hora", "dia"],
                    "default": "hora",
                },
            },
            "required": ["desde", "hasta"],
        },
    },
    {
        "name": "registrar_consumo",
        "description": "Registra una lectura manual de consumo (luz, agua, gas).",
        "input_schema": {
            "type": "object",
            "properties": {
                "tipo_consumo": {
                    "type": "string",
                    "description": "Tipo de consumo",
                    "enum": ["luz", "agua", "gas"],
                },
                "valor": {"type": "number", "description": "Lectura (kWh para luz, m3 para agua/gas)"},
                "unidad": {"type": "string", "description": "Unidad (kWh, m3)", "default": "kWh"},
                "fecha": {"type": "string", "description": "Fecha de la lectura (ISO format). Default hoy."},
                "costo": {"type": "number", "description": "Costo en soles (opcional)"},
            },
            "required": ["tipo_consumo", "valor"],
        },
    },
    {
        "name": "set_config_consumo",
        "description": "Actualiza configuracion de consumo (tarifa por kWh, etc).",
        "input_schema": {
            "type": "object",
            "properties": {
                "clave": {"type": "string", "description": "Clave de configuracion (ej: costo_kwh_luz)"},
                "valor": {"type": "string", "description": "Nuevo valor"},
            },
            "required": ["clave", "valor"],
        },
    },

    # =========================================================================
    # Impresora 3D
    # =========================================================================
    {
        "name": "printer_status",
        "description": "Consulta el estado actual de la impresora 3D (progreso, temperaturas, ETA).",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "printer_pause",
        "description": "Pausa la impresion en curso.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "printer_resume",
        "description": "Reanuda una impresion pausada.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },

    # =========================================================================
    # Smart Home
    # =========================================================================
    {
        "name": "smart_home",
        "description": "Enviar un comando a Google Assistant para controlar dispositivos smart home (luces, aspiradora, etc).",
        "input_schema": {
            "type": "object",
            "properties": {
                "comando": {"type": "string", "description": "Comando de voz en espanol (ej: 'enciende la luz del cuarto')"},
            },
            "required": ["comando"],
        },
    },

    # =========================================================================
    # Google Workspace (Calendar, Gmail, Drive) — via MCP tools
    # =========================================================================
    {
        "name": "create_event",
        "description": "Crea un evento en Google Calendar. Usa para recordatorios, citas, planificacion.",
        "input_schema": {
            "type": "object",
            "properties": {
                "summary": {"type": "string", "description": "Titulo corto del evento"},
                "start_time": {"type": "string", "description": "Inicio en ISO format con zona horaria (ej: 2026-03-15T09:00:00-05:00)"},
                "end_time": {"type": "string", "description": "Fin en ISO format (ej: 2026-03-15T09:30:00-05:00)"},
                "description": {"type": "string", "description": "Descripcion detallada del evento"},
                "recurrence": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Reglas RRULE para recurrencia (ej: ['RRULE:FREQ=MONTHLY;BYMONTHDAY=15'])",
                },
            },
            "required": ["summary", "start_time", "end_time"],
        },
    },
    {
        "name": "get_events",
        "description": "Lista eventos del Google Calendar en un rango de tiempo.",
        "input_schema": {
            "type": "object",
            "properties": {
                "time_min": {"type": "string", "description": "Inicio del rango (ISO format)"},
                "time_max": {"type": "string", "description": "Fin del rango (ISO format)"},
            },
            "required": ["time_min", "time_max"],
        },
    },
    {
        "name": "update_event",
        "description": "Actualiza un evento existente en Google Calendar.",
        "input_schema": {
            "type": "object",
            "properties": {
                "event_id": {"type": "string", "description": "ID del evento a modificar"},
                "summary": {"type": "string", "description": "Nuevo titulo"},
                "start_time": {"type": "string", "description": "Nueva hora de inicio"},
                "end_time": {"type": "string", "description": "Nueva hora de fin"},
                "description": {"type": "string", "description": "Nueva descripcion"},
            },
            "required": ["event_id"],
        },
    },
    {
        "name": "delete_event",
        "description": "Elimina un evento del Google Calendar.",
        "input_schema": {
            "type": "object",
            "properties": {
                "event_id": {"type": "string", "description": "ID del evento a eliminar"},
            },
            "required": ["event_id"],
        },
    },
    {
        "name": "send_email",
        "description": "Envia un email via Gmail.",
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {"type": "string", "description": "Destinatario"},
                "subject": {"type": "string", "description": "Asunto"},
                "body": {"type": "string", "description": "Cuerpo del email"},
            },
            "required": ["to", "subject", "body"],
        },
    },
    {
        "name": "search_emails",
        "description": "Busca emails en Gmail.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Query de busqueda (ej: from:banco subject:estado)"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_email",
        "description": "Lee el contenido de un email por su ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "email_id": {"type": "string", "description": "ID del email a leer"},
            },
            "required": ["email_id"],
        },
    },
    {
        "name": "search_drive_files",
        "description": "Busca archivos en Google Drive.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Nombre o termino a buscar"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_drive_file_content",
        "description": "Lee el contenido de un archivo de Google Drive.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_id": {"type": "string", "description": "ID del archivo en Drive"},
            },
            "required": ["file_id"],
        },
    },

    # =========================================================================
    # System tools (MCP)
    # =========================================================================
    {
        "name": "rpi_status",
        "description": "Consulta el estado del Raspberry Pi (temperatura, RAM, disco, servicios).",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
]

# Google email constant — injected into MCP tool calls
_GOOGLE_EMAIL = "snestors@gmail.com"

# Maps tool names to ActionExecutor action dicts.
# Most tools map 1:1 with a simple rename.
# MCP tools (calendar, gmail, drive, rpi) need special mapping.

_MCP_TOOLS = {
    "create_event", "get_events", "update_event", "delete_event",
    "send_email", "search_emails", "get_email",
    "search_drive_files", "get_drive_file_content",
    "rpi_status",
}

_MOV_TYPE_MAP = {
    "registrar_gasto": "gasto",
    "registrar_ingreso": "ingreso",
    "registrar_transferencia": "transferencia",
    "registrar_pago_tarjeta": "pago_tarjeta",
    "registrar_pago_deuda": "pago_deuda",
    "registrar_pago_cobro": "pago_cobro",
}

# Tools that pass through directly (name == action tipo)
_DIRECT_TOOLS = {
    "actualizar_movimiento", "eliminar_movimiento", "eliminar_movimientos",
    "buscar_gasto", "importar_estado_cuenta",
    "set_presupuesto", "agregar_deuda",
    "crear_cuenta", "actualizar_cuenta",
    "set_perfil", "memorizar", "buscar_memoria", "recordar_contexto",
    "consultar_consumo", "registrar_consumo", "set_config_consumo",
    "printer_status", "printer_pause", "printer_resume",
    "smart_home",
}


def tool_call_to_action(tool_name: str, tool_input: dict) -> dict:
    """Convert a Claude tool_use call to an ActionExecutor-compatible action dict.

    Returns a dict with 'tipo' key that ActionExecutor.execute() can handle.
    """
    # Movement registrations → unified movimiento action
    if tool_name in _MOV_TYPE_MAP:
        action = dict(tool_input)
        action["tipo"] = "movimiento"
        action["mov_tipo"] = _MOV_TYPE_MAP[tool_name]
        return action

    # Consultar resumen → consulta action
    if tool_name == "consultar_resumen":
        return {"tipo": "consulta", "periodo": tool_input.get("periodo", "hoy")}

    # Tipo de cambio SUNAT
    if tool_name == "consultar_tipo_cambio":
        return {"tipo": "tipo_cambio_sunat"}

    # Convertir moneda
    if tool_name == "convertir_moneda":
        return {"tipo": "consulta_cambio", **tool_input}

    # Crear tarjeta → tarjeta action
    if tool_name == "crear_tarjeta":
        return {"tipo": "tarjeta", **tool_input}

    # Registrar cobro → cobro action
    if tool_name == "registrar_cobro":
        return {"tipo": "cobro", **tool_input}

    # Buscar gasto — rename tipo
    if tool_name == "buscar_gasto":
        return {"tipo": "buscar_gasto", **tool_input}

    # Consultar consumo → consulta_consumo action
    if tool_name == "consultar_consumo":
        return {"tipo": "consulta_consumo", **tool_input}

    # MCP tools → tool action with google email injection
    if tool_name in _MCP_TOOLS:
        params = dict(tool_input)
        # Inject google email for workspace tools
        if tool_name in {"create_event", "get_events", "update_event", "delete_event",
                         "send_email", "search_emails", "get_email",
                         "search_drive_files", "get_drive_file_content"}:
            params["user_google_email"] = _GOOGLE_EMAIL
        return {"tipo": "tool", "name": tool_name, "params": params}

    # Direct passthrough — tool name == action tipo
    if tool_name in _DIRECT_TOOLS:
        return {"tipo": tool_name, **tool_input}

    # Unknown tool — pass as-is with tipo = tool_name
    return {"tipo": tool_name, **tool_input}
