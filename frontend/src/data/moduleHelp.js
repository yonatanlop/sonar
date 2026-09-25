// Textos de ayuda de cada módulo: qué es, para qué sirve y qué se puede hacer. Se muestran como
// tooltip (ícono ⓘ) junto al título de cada pantalla, al pasar el mouse por el menú lateral y en
// las pestañas de Rizoma y del detalle de una entidad. Los saltos de línea (\n) se respetan.
// Redactados a partir de lo que realmente hace cada pantalla; si cambia una pantalla, actualizar aquí.

export const MODULE_HELP = {
  // ── Monitoreo ──
  dashboard:
    'Resumen del monitoreo de hoy.\n' +
    '• Menciones de hoy, % de negativas (sobre las ya clasificadas), bots detectados y entidades activas, con la variación frente a ayer.\n' +
    '• Tendencia de 14 días, reparto de sentimiento, participación de cada entidad y últimas alertas.\n' +
    'Haz clic en una caja o gráfica para ver las publicaciones que la componen; el ⓘ de cada caja explica cómo se calcula.',
  entities:
    'Aquí se configura qué se monitorea: líderes, instituciones y keywords.\n' +
    '• Cada tarjeta muestra las menciones de hoy, el nivel de riesgo (bajo, medio o alto según el % de negativas) y un interruptor para activar o pausar la entidad.\n' +
    '• Filtra por tipo de monitoreo (vigilancia reputacional, seguimiento político u oportunidad del partido), busca por nombre o muestra las inactivas.\n' +
    '• «Nueva entidad»: nombre, tipo, país, foto y tipo de monitoreo.\n' +
    '• Solo cuentan las publicaciones que coinciden con las keywords o alias de cada entidad.\n' +
    '• «Ver detalle»: resumen, menciones, keywords, alias, reglas de alerta, influencers y reconocimiento visual.',
  mentions:
    'Todas las publicaciones recolectadas que coinciden con las keywords parametrizadas.\n' +
    '• Filtra por entidad, red, sentimiento, idioma, urgencia, tipo de autor (bot, sospechoso, real), seguidores, país y fechas.\n' +
    '• La búsqueda semántica encuentra publicaciones por significado, no solo por palabras.\n' +
    '• En cada tarjeta puedes corregir el sentimiento, marcarla como atendida o como «No relevante» (Sonar no la vuelve a mostrar).',
  compare:
    'Compara entre 2 y 4 entidades en el mismo período (7, 14 o 30 días).\n' +
    '• Menciones, % negativo (sobre clasificadas), bots detectados, urgencia promedio y red principal.\n' +
    '• Usa los mismos criterios de cálculo que el Dashboard.',

  // ── Alertas ──
  alerts:
    'Historial de las alertas que el sistema dispara según las reglas configuradas.\n' +
    '• Filtra por severidad (baja, media, alta, crítica) y por estado (sin atender / atendidas).\n' +
    '• Con «Atender» registras qué acción tomaste (reportado a la plataforma, escalado a jurídico MIRA o de la iglesia, oportunidad del partido, descartado) y una nota.\n' +
    '• «Ver mención» despliega la publicación que originó la alerta.',
  inbox:
    'Bandeja de trabajo para tratar las menciones negativas que generaron alerta.\n' +
    '• Alterna entre Pendientes, Todas y Gestionadas, filtra por tema y ordena por fecha, urgencia o seguidores del autor.\n' +
    '• Sigue la guía de la pantalla: evalúa la gravedad, captura evidencia, reporta en la plataforma, escala a jurídico o a autoridades y registra la acción.\n' +
    '• También puedes corregir el sentimiento y marcar la cuenta como Rizoma.',
  legal:
    'Menciones que se escalaron al equipo jurídico (Iglesia o MIRA) para seguimiento formal.\n' +
    '• Filtra por destino (Iglesia / MIRA) y por estado (pendientes / recibidos).\n' +
    '• Guarda una copia de la publicación por si luego se elimina.',
  rizoma:
    'Centro de seguimiento de cuentas hostiles y ataques.\n' +
    '• Publicaciones de las cuentas marcadas como Rizoma en los Explorer.\n' +
    '• Cuentas de atacantes con su historial y mapa de origen, balance de denuncias por día/semana/mes y lo ya cerrado.\n' +
    '• Grupos de Facebook a cerrar y seguimiento por caso.\n' +
    'Cada pestaña tiene su propia ayuda.',
  coordination:
    'Detecta cuentas distintas que publican el mismo texto (o casi) en pocas horas: una señal de actividad coordinada.\n' +
    '• El detector corre cada 3 horas y muestra grupos candidatos con un puntaje.\n' +
    '• Revisa cada grupo y márcalo como confirmado o descartado (con una nota); así se mide el acierto del detector.\n' +
    '• Filtra por estado, por tipo (varias cuentas en red / una cuenta repitiendo) y por puntaje.\n' +
    '• «Cuentas núcleo» lista las cuentas que aparecen repetidas en varios grupos.',
  rules:
    'Define cuándo se disparan las alertas automáticas.\n' +
    '• Elige la entidad (o global), el tipo de regla, el umbral, la ventana de evaluación y la severidad.\n' +
    '• La severidad decide por dónde llega: baja = solo dashboard; media = Telegram y dashboard; alta y crítica = todos los canales.\n' +
    '• Puedes limitar quién recibe cada alerta; si lo dejas vacío, la reciben todos los admin y analistas.\n' +
    '• Cada regla tiene un interruptor para activarla o pausarla y un ícono para eliminarla. Las reglas «Anomalía detectada automáticamente» avisan cuando una entidad se sale de su comportamiento normal.',

  // ── Herramientas ──
  reports:
    'Genera y descarga informes en PDF.\n' +
    '• Tipos: por entidad, por país, por bots, por alertas o por campaña.\n' +
    '• Con «Generar nuevo reporte» das un nombre, eliges el tipo y el rango de fechas, y el sistema arma el documento para descargar.',
  topickw:
    'Genera keywords con IA a partir de un tema.\n' +
    '• Describe el tema y lo que necesitas encontrar; la IA propone expresiones de búsqueda con operadores (Y / O / NO).\n' +
    '• Descarta las que no sirvan y guarda las demás en una entidad destino.\n' +
    '• «Búsqueda en vivo» las prueba en Twitter/X (resultados en ~1 minuto).',
  'twitter-explorer':
    'Monitorea cuentas, hashtags y palabras clave de X (Twitter) de forma libre.\n' +
    '• «Agregar monitor» (usuario, hashtag o palabra clave) y elige uno para ver sus tweets, con búsqueda y fechas.\n' +
    '• Sus resultados NO se mezclan con el Dashboard ni con Líderes/Instituciones/Keywords.\n' +
    '• Con el botón Rizoma marcas cuentas hostiles para seguirlas en Rizoma.',
  'youtube-explorer':
    'Monitorea canales específicos de YouTube.\n' +
    '• Agrega un canal por su @handle o URL, define las keywords a buscar (vacío = videos recientes), el período y la cantidad de videos.\n' +
    '• Sus resultados NO se mezclan con el Dashboard.\n' +
    '• Con el botón Rizoma marcas canales hostiles.',
  'facebook-explorer':
    'Monitorea temas y páginas de Facebook.\n' +
    '• «Agregar monitor», elige uno y revisa sus publicaciones (el scraper las recolecta periódicamente).\n' +
    '• Sus resultados NO se mezclan con el Dashboard.\n' +
    '• Con el botón Rizoma marcas cuentas hostiles.',
  'instagram-explorer':
    'Monitorea hashtags y cuentas de Instagram.\n' +
    '• «Agregar monitor», elige uno y revisa sus publicaciones (el scraper las recolecta periódicamente).\n' +
    '• Sus resultados NO se mezclan con el Dashboard.\n' +
    '• Con el botón Rizoma marcas cuentas hostiles.',
  'tiktok-explorer':
    'Monitorea palabras clave, hashtags y creadores de TikTok.\n' +
    '• «Agregar monitor», elige uno y revisa sus publicaciones (el scraper las recolecta periódicamente).\n' +
    '• Sus resultados NO se mezclan con el Dashboard.\n' +
    '• Con el botón Rizoma marcas cuentas hostiles.',
  response:
    'Ayuda a responder comentarios negativos en Facebook con argumentos sólidos y respeto.\n' +
    '• Indicas el tema de la publicación, el enlace y el comentario negativo completo, y la herramienta te ayuda a preparar la respuesta.',
  media:
    'Búsqueda inversa de imágenes y videos: dónde más se publicó, quién lo publicó y si fue generado con IA.\n' +
    '• Sube un archivo (JPG, PNG, WEBP, GIF, MP4, MOV; máx. 50 MB) o pega un enlace.\n' +
    '• Elige en qué buscar: SONAR (lo ya recopilado), Google Vision, SauceNAO, Yandex o TinEye.\n' +
    '• «¿Es IA?» analiza si la imagen fue generada por inteligencia artificial.',
  platforms:
    'Estado de las redes sociales y de las cuentas con las que SONAR las recolecta.\n' +
    '• Arriba ves el resumen (activas, sin menciones recientes, no configuradas). Cada tarjeta muestra la frecuencia de recolección, las menciones de las últimas 24 h y 7 días, la última mención y las cuentas activas.\n' +
    '• «Gestionar cuentas»: agrega, activa, reactiva (limpia errores y bloqueos), edita cookies o elimina las cuentas de Twitter/X, Instagram y Facebook.\n' +
    '• Cada cuenta puede estar activa, en cooldown (en espera), con error de autenticación, con error o inactiva.\n' +
    '• Se actualiza sola cada 60 segundos.',
  chat:
    'Asistente MIRA: haz preguntas en lenguaje natural sobre las menciones recolectadas y recibe una respuesta con base en ellas.\n' +
    '• Puedes limitarlo a una entidad.\n' +
    '• El modo conversacional requiere las claves de IA configuradas en el servidor.',
  geomap:
    'Mapa con la distribución de las menciones según el país de origen del autor.',

  // ── Administración ──
  users:
    'Gestión de acceso al sistema.\n' +
    '• Crea usuarios con una contraseña temporal y asígnales un rol: Consulta (solo lectura), Analista o Administrador.\n' +
    '• Edita sus datos y actívalos o desactívalos; ves su último acceso.',
  audit:
    'Registro de las acciones hechas en el sistema: quién, qué, en qué módulo, cuándo y desde qué IP (inicios y cierres de sesión, cambios, etc.).\n' +
    '• Filtra por usuario, acción, módulo y fechas.\n' +
    '• Sirve para trazabilidad y control.',
  'reply-accounts':
    'Cuentas del equipo que responden a las publicaciones monitoreadas.\n' +
    '• Registra las cuentas, sus respuestas (con el post original, si lo hay) y actívalas o desactívalas.\n' +
    '• Arriba ves cuentas activas, respuestas registradas, posts atendidos, respuestas detectadas automáticamente y la cuenta con más respuestas.\n' +
    '• Abre una cuenta para ver su historial de respuestas.',
  'twitter-search':
    'Monitoreo continuo y global de keywords y hashtags en Twitter.\n' +
    '• Se activa automáticamente a las 8:00 p. m. (hora de Colombia); aquí ves su estado, los términos activos y la última ronda.\n' +
    '• «Verificar estado», «Iniciar ahora» y «Detener búsqueda» la controlan a mano.\n' +
    '• Agrega términos combinándolos con Y (todos), O (cualquiera) y NO (excluir).',
  profile:
    'Tus datos personales y cómo quieres recibir las notificaciones.\n' +
    '• Telegram: alertas de severidad media o mayor.\n' +
    '• WhatsApp (vía CallMeBot): alertas altas y críticas.\n' +
    '• También puedes cambiar tu contraseña (mínimo 8 caracteres).',
}

// Pestañas de Rizoma
export const RIZOMA_TAB_HELP = {
  feed:     'Publicaciones recientes de las cuentas hostiles marcadas como Rizoma en los Explorer (Twitter, YouTube, Facebook, Instagram y TikTok). Muestra todo lo que publican, no solo lo que coincide con keywords.',
  accounts: 'Cuentas de atacantes de todos los casos. Filtra por tipo de red, estado (activa, cerrada, creó cuenta nueva) o busca por usuario, caso o ciudad. Cada cuenta abre su historial en línea de tiempo y el mapa muestra de dónde provienen.',
  balance:  'Balance de denuncias por día, semana o mes (hora de Colombia): denuncias hechas, publicaciones eliminadas, cuentas y grupos cerrados, con filtro por red y descarga en PDF. Los registros históricos sin fecha se avisan aparte.',
  closed:   'Cuentas, publicaciones y grupos que ya se cerraron en un rango de fechas, filtrables por tipo de red.',
  groups:   'Registro de los grupos de Facebook que se van a cerrar: URL, razón, fecha de inicio del proceso y fecha fin. Con fecha fin queda como cerrado.',
  cases:    'Seguimiento de cada caso (la persona que ataca): sus cuentas por red social y las publicaciones denunciadas, con el detalle de la denuncia y su resultado.',
  monthly:  'Reporte del mes: origen geográfico de las cuentas y cuentas y publicaciones cerradas en el mes, con descarga en PDF.',
}

// Pestañas del detalle de una entidad
export const ENTITY_TAB_HELP = {
  overview:    'Resumen de los últimos 7 días: menciones de hoy, total, % de negativas, distribución de sentimiento, temas detectados, resumen del día con IA, personas/organizaciones/lugares mencionados y pronóstico. Haz clic en una cifra, una porción o un tema para ver esas publicaciones.',
  mentions:    'Las publicaciones de esta entidad, con los mismos filtros del menú Menciones. Se abre sin filtro de fechas.',
  keywords:    'Términos que se buscan para esta entidad. Puedes combinar palabras con Y / O / NO, elegir el idioma y el peso (1 normal, 2 importante, 3 crítico). Solo cuentan las publicaciones que coinciden con ellas.',
  aliases:     'Nombres alternativos de la entidad (por ejemplo, su @usuario o un apodo). Una publicación que menciona un alias también se considera de la entidad.',
  rules:       'Reglas de alerta de esta entidad: cuándo avisar (pico de volumen, negatividad, bots, discurso de odio…), con qué umbral, ventana y severidad.',
  influencers: 'Cuentas con mayor alcance que mencionaron esta entidad en el período elegido (7, 14 o 30 días), con sus seguidores, menciones y sentimiento.',
  faces:       'Fotos de referencia de las personas a monitorear para detectar su presencia en las imágenes de las menciones. Requiere tener activado el reconocimiento facial en el servidor.',
}

// Los módulos que viven dentro de Rizoma también muestran su ayuda junto al título
MODULE_HELP.groups  = RIZOMA_TAB_HELP.groups
MODULE_HELP.cases   = RIZOMA_TAB_HELP.cases
MODULE_HELP.monthly = RIZOMA_TAB_HELP.monthly

// Ayuda de cada ítem del menú lateral (por ruta)
export const NAV_HELP = {
  '/':                       MODULE_HELP.dashboard,
  '/entities':               MODULE_HELP.entities,
  '/mentions':               MODULE_HELP.mentions,
  '/compare':                MODULE_HELP.compare,
  '/alerts':                 MODULE_HELP.alerts,
  '/inbox':                  MODULE_HELP.inbox,
  '/rizoma':                 MODULE_HELP.rizoma,
  '/legal':                  MODULE_HELP.legal,
  '/coordination':           MODULE_HELP.coordination,
  '/settings/rules':         MODULE_HELP.rules,
  '/reports':                MODULE_HELP.reports,
  '/topic-keywords':         MODULE_HELP.topickw,
  '/twitter-explorer':       MODULE_HELP['twitter-explorer'],
  '/youtube-explorer':       MODULE_HELP['youtube-explorer'],
  '/facebook-explorer':      MODULE_HELP['facebook-explorer'],
  '/instagram-explorer':     MODULE_HELP['instagram-explorer'],
  '/tiktok-explorer':        MODULE_HELP['tiktok-explorer'],
  '/response-tool':          MODULE_HELP.response,
  '/media-search':           MODULE_HELP.media,
  '/platforms':              MODULE_HELP.platforms,
  '/admin/users':            MODULE_HELP.users,
  '/admin/audit':            MODULE_HELP.audit,
  '/admin/reply-accounts':   MODULE_HELP['reply-accounts'],
  '/admin/twitter-search':   MODULE_HELP['twitter-search'],
}
