// Textos de ayuda de cada módulo: qué es y para qué sirve. Se muestran como tooltip (ícono ⓘ)
// junto al título de cada pantalla, al pasar el mouse por el menú lateral y en las pestañas de Rizoma.

export const MODULE_HELP = {
  // ── Monitoreo ──
  dashboard:
    'Vista general del monitoreo: menciones de hoy, % de negativas (sobre las ya clasificadas), bots detectados, tendencia de 14 días, distribución de sentimiento, participación por entidad y últimas alertas. Pasa el mouse por el ícono ⓘ de cada caja para ver cómo se calcula.',
  entities:
    'Aquí se configuran las entidades que se monitorean (líderes, instituciones y keywords). Solo cuentan las publicaciones que coinciden con las keywords de cada entidad. Entra a «Ver detalle» para ver su resumen de 7 días, sus keywords, sus menciones y su análisis.',
  mentions:
    'Todas las publicaciones recolectadas que coinciden con las keywords parametrizadas. Filtra por entidad, red social, sentimiento, fechas, bots, urgencia o país, o usa la búsqueda semántica para buscar por significado. Si el sentimiento está mal clasificado, puedes corregirlo.',
  compare:
    'Compara entre 2 y 4 entidades en el mismo período: menciones, % negativo, bots detectados, urgencia promedio y red principal. Usa los mismos criterios de cálculo del Dashboard.',

  // ── Alertas ──
  alerts:
    'Historial de las alertas que el sistema dispara según las reglas configuradas (menciones negativas, picos de actividad, etc.). Desde aquí ves la mención que la originó y puedes marcarla como atendida.',
  inbox:
    'Bandeja de trabajo con las menciones negativas que generaron alerta. Para cada una registra qué acción se tomó: reportar en la plataforma, a instancias internacionales o a Fiscalía/Policía, escalar, marcar como oportunidad o descartar.',
  legal:
    'Menciones que se escalaron al equipo jurídico (Iglesia o MIRA) para hacerles seguimiento formal.',
  rizoma:
    'Centro de seguimiento de cuentas hostiles y ataques. Reúne las publicaciones de las cuentas marcadas como Rizoma, las cuentas de atacantes con su historial, el balance de denuncias por día/semana/mes, lo que ya se cerró, los grupos de Facebook a cerrar y el seguimiento por caso. Cada pestaña tiene su propia ayuda.',
  coordination:
    'Detecta grupos de cuentas distintas que publican el mismo texto (o casi) en pocas horas: una señal de actividad coordinada. Revisa cada grupo y márcalo como confirmado o descartado para mejorar la detección.',
  rules:
    'Define cuándo se disparan las alertas automáticas: el tipo de regla, la entidad, el umbral, la ventana de tiempo, la severidad y a quién se notifica.',

  // ── Herramientas ──
  reports:
    'Genera y descarga informes en PDF: por entidad, por país, por bots, por alertas o por campaña. Con «Nuevo reporte» eliges el tipo y el sistema arma el documento.',
  topickw:
    'Describe un tema en lenguaje natural y la IA propone expresiones de búsqueda con operadores lógicos (Y / O / NO) que puedes agregar como keywords de una entidad.',
  'twitter-explorer':
    'Búsqueda y monitoreo libre en X (Twitter): cuentas, hashtags y palabras clave. Sus resultados no se mezclan con el Dashboard ni con Líderes/Instituciones/Keywords. Puedes marcar cuentas hostiles como Rizoma.',
  'youtube-explorer':
    'Monitorea canales específicos de YouTube por palabras clave. Sus resultados no se mezclan con el Dashboard. Puedes marcar canales hostiles como Rizoma.',
  'facebook-explorer':
    'Monitorea temas y páginas de Facebook. Sus resultados no se mezclan con el Dashboard. Puedes marcar cuentas hostiles como Rizoma.',
  'instagram-explorer':
    'Monitorea hashtags y cuentas de Instagram. Sus resultados no se mezclan con el Dashboard. Puedes marcar cuentas hostiles como Rizoma.',
  'tiktok-explorer':
    'Monitorea palabras clave, hashtags y creadores de TikTok. Sus resultados no se mezclan con el Dashboard. Puedes marcar cuentas hostiles como Rizoma.',
  response:
    'Herramienta para redactar respuestas a comentarios negativos.',
  media:
    'Búsqueda inversa: encuentra dónde más se publicó una imagen o video, quién lo publicó y si fue generado con IA.',
  platforms:
    'Estado de las redes sociales: cuáles están activas y recolectando menciones.',
  chat:
    'Asistente MIRA: haz preguntas en lenguaje natural sobre las menciones recolectadas y recibe una respuesta con base en ellas.',
  geomap:
    'Mapa con la distribución de las menciones según el país de origen del autor.',

  // ── Administración ──
  users:
    'Gestión de acceso al sistema: crear usuarios, asignarles rol (administrador, analista o visor) y activarlos o desactivarlos.',
  audit:
    'Registro de las acciones realizadas en el sistema (quién hizo qué y cuándo), para trazabilidad y control.',
  'reply-accounts':
    'Cuentas del equipo que se usan para responder a las publicaciones monitoreadas.',
  'twitter-search':
    'Monitoreo continuo y global de keywords y hashtags en Twitter. Se activa automáticamente a las 8:00 p. m. (hora de Colombia).',
  profile:
    'Tus datos personales y cómo quieres recibir las notificaciones (Telegram, WhatsApp o correo).',
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
