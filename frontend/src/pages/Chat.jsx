import { useState, useRef, useEffect } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { Send, Bot, User, ChevronDown, ChevronUp, AlertCircle, Sparkles, ExternalLink } from 'lucide-react'
import { format } from 'date-fns'
import { es } from 'date-fns/locale'
import client from '../api/client'

const fetchConfig    = () => client.get('/chat/config').then(r => r.data)
const fetchEntities  = () => client.get('/entities').then(r => r.data)
const sendMessage    = (payload) => client.post('/chat', payload).then(r => r.data)

const PLATFORM_ICON = { twitter: '🐦', reddit: '🤖', youtube: '▶️', rss: '📰' }

const EXAMPLE_QUESTIONS = [
  '¿Qué amenazas se presentaron esta semana?',
  '¿Hay menciones con discurso de odio recientes?',
  '¿Cuáles son las publicaciones más urgentes?',
  '¿Hay alguna campaña coordinada detectada?',
  '¿Cómo es el sentimiento general hacia la Hermana María Luisa?',
]

function SourceCard({ mention }) {
  const score = mention.urgency_score || 0
  const urgencyColor =
    score >= 80 ? 'text-red-600' :
    score >= 60 ? 'text-orange-500' :
    score >= 30 ? 'text-yellow-500' : 'text-gray-400'

  return (
    <div className="bg-gray-50 border border-gray-200 rounded-lg px-3 py-2 text-xs space-y-1">
      <div className="flex items-center gap-2 flex-wrap">
        <span>{PLATFORM_ICON[mention.platform_code] ?? '🌐'}</span>
        <span className="font-medium text-gray-700">@{mention.author_username}</span>
        {mention.published_at && (
          <span className="text-gray-400">
            {format(new Date(mention.published_at), "d MMM yyyy", { locale: es })}
          </span>
        )}
        {score >= 30 && (
          <span className={`font-bold ${urgencyColor}`}>⚡ {score.toFixed(0)}</span>
        )}
        <span className="text-gray-400 ml-auto">
          {Math.round((mention.similarity || 0) * 100)}% relevancia
        </span>
      </div>
      <p className="text-gray-600 leading-relaxed line-clamp-3">{mention.content}</p>
      {mention.url && (
        <a href={mention.url} target="_blank" rel="noopener noreferrer"
          className="text-primary-600 hover:underline flex items-center gap-1">
          Ver publicación <ExternalLink className="w-3 h-3" />
        </a>
      )}
    </div>
  )
}

function MessageBubble({ msg }) {
  const [showSources, setShowSources] = useState(false)
  const isUser = msg.role === 'user'

  return (
    <div className={`flex gap-3 ${isUser ? 'justify-end' : 'justify-start'}`}>
      {!isUser && (
        <div className="shrink-0 w-8 h-8 rounded-full bg-primary-600 flex items-center justify-center mt-1">
          <Bot className="w-4 h-4 text-white" />
        </div>
      )}

      <div className={`max-w-[80%] space-y-2 ${isUser ? 'items-end' : 'items-start'} flex flex-col`}>
        <div className={`rounded-2xl px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap ${
          isUser
            ? 'bg-primary-600 text-white rounded-tr-sm'
            : 'bg-white border border-gray-200 text-gray-800 rounded-tl-sm shadow-sm'
        }`}>
          {msg.content}
        </div>

        {/* Fuentes del asistente */}
        {!isUser && msg.sources?.length > 0 && (
          <div className="w-full space-y-1">
            <button
              onClick={() => setShowSources(s => !s)}
              className="flex items-center gap-1.5 text-xs text-gray-400 hover:text-gray-600 transition-colors">
              {showSources ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
              Ver {msg.sources.length} menciones utilizadas como contexto
            </button>
            {showSources && (
              <div className="space-y-2">
                {msg.sources.map((s, i) => <SourceCard key={i} mention={s} />)}
              </div>
            )}
          </div>
        )}

        {!isUser && msg.sources?.length === 0 && (
          <p className="text-xs text-gray-400">Sin menciones encontradas para esta consulta</p>
        )}
      </div>

      {isUser && (
        <div className="shrink-0 w-8 h-8 rounded-full bg-gray-200 flex items-center justify-center mt-1">
          <User className="w-4 h-4 text-gray-500" />
        </div>
      )}
    </div>
  )
}

export default function Chat() {
  const [messages, setMessages]   = useState([])
  const [input, setInput]         = useState('')
  const [entityId, setEntityId]   = useState('')
  const [advancedOn, setAdvancedOn] = useState(false)
  const bottomRef = useRef(null)

  const { data: config } = useQuery({ queryKey: ['chat-config'], queryFn: fetchConfig })
  const { data: entities = [] } = useQuery({ queryKey: ['entities'], queryFn: fetchEntities })

  const mutation = useMutation({
    mutationFn: sendMessage,
    onSuccess: (data) => {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: data.answer,
        sources: data.sources,
        advanced: data.advanced,
      }])
    },
    onError: () => {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: 'Error al contactar el asistente. Verifica que GROQ_API_KEY y HUGGINGFACE_TOKEN estén configurados.',
        sources: [],
      }])
    },
  })

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, mutation.isPending])

  const handleSubmit = (e) => {
    e?.preventDefault()
    const text = input.trim()
    if (!text || mutation.isPending) return

    const userMsg = { role: 'user', content: text }
    setMessages(prev => [...prev, userMsg])
    setInput('')

    // Construir historial solo si fase avanzada está activa
    const history = (advancedOn && config?.advanced_mode)
      ? messages.map(m => ({ role: m.role, content: m.content }))
      : null

    mutation.mutate({
      question:  text,
      entity_id: entityId || null,
      history,
    })
  }

  const handleExample = (q) => {
    setInput(q)
  }

  const isAvailable = config?.available !== false

  return (
    <div className="flex flex-col h-[calc(100vh-7rem)] max-w-3xl mx-auto">

      {/* Cabecera */}
      <div className="flex items-start justify-between flex-wrap gap-3 mb-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Sparkles className="w-6 h-6 text-primary-500" />
            Asistente MIRA
          </h1>
          <p className="text-gray-500 text-sm mt-0.5">
            Pregunta en lenguaje natural sobre las menciones recolectadas
          </p>
        </div>

        <div className="flex items-center gap-3 flex-wrap">
          {/* Filtro de entidad */}
          <select className="input w-auto text-sm" value={entityId}
            onChange={e => setEntityId(e.target.value)}>
            <option value="">Todas las entidades</option>
            {entities.map(e => <option key={e.id} value={e.id}>{e.name}</option>)}
          </select>

          {/* Toggle fase avanzada — solo visible si el servidor la soporta */}
          {config?.advanced_mode && (
            <label className="flex items-center gap-2 cursor-pointer select-none">
              <span className="text-xs text-gray-600">Modo conversacional</span>
              <button
                type="button" role="switch"
                aria-checked={advancedOn}
                onClick={() => setAdvancedOn(v => !v)}
                className={`relative inline-flex h-5 w-9 shrink-0 rounded-full border-2 border-transparent transition-colors ${
                  advancedOn ? 'bg-primary-600' : 'bg-gray-200'
                }`}>
                <span className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition-transform ${
                  advancedOn ? 'translate-x-4' : 'translate-x-0'
                }`} />
              </button>
            </label>
          )}
        </div>
      </div>

      {/* Aviso si no está disponible */}
      {!isAvailable && config !== undefined && (
        <div className="card border-orange-200 border bg-orange-50 flex items-start gap-3 py-3 mb-3">
          <AlertCircle className="w-4 h-4 text-orange-500 shrink-0 mt-0.5" />
          <p className="text-sm text-orange-700">
            El asistente requiere <strong>GROQ_API_KEY</strong> y <strong>HUGGINGFACE_TOKEN</strong> configurados en el archivo <code>.env</code>.
          </p>
        </div>
      )}

      {/* Área de mensajes */}
      <div className="flex-1 overflow-y-auto space-y-4 py-2 pr-1">
        {messages.length === 0 && (
          <div className="text-center py-12 space-y-6">
            <div className="w-16 h-16 rounded-full bg-primary-50 flex items-center justify-center mx-auto">
              <Bot className="w-8 h-8 text-primary-400" />
            </div>
            <div>
              <p className="text-gray-500 text-sm mb-4">
                Puedes preguntar sobre amenazas, sentimiento, campañas coordinadas o cualquier<br />
                patrón en las menciones recolectadas de redes sociales.
              </p>
              <div className="flex flex-wrap gap-2 justify-center">
                {EXAMPLE_QUESTIONS.map(q => (
                  <button key={q} onClick={() => handleExample(q)}
                    className="text-xs bg-gray-100 hover:bg-primary-50 hover:text-primary-700 text-gray-600 rounded-full px-3 py-1.5 transition-colors text-left">
                    {q}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {messages.map((msg, i) => <MessageBubble key={i} msg={msg} />)}

        {mutation.isPending && (
          <div className="flex gap-3 justify-start">
            <div className="shrink-0 w-8 h-8 rounded-full bg-primary-600 flex items-center justify-center">
              <Bot className="w-4 h-4 text-white" />
            </div>
            <div className="bg-white border border-gray-200 rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm">
              <div className="flex gap-1 items-center h-4">
                <div className="w-2 h-2 rounded-full bg-gray-400 animate-bounce" style={{ animationDelay: '0ms' }} />
                <div className="w-2 h-2 rounded-full bg-gray-400 animate-bounce" style={{ animationDelay: '150ms' }} />
                <div className="w-2 h-2 rounded-full bg-gray-400 animate-bounce" style={{ animationDelay: '300ms' }} />
              </div>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <form onSubmit={handleSubmit} className="flex gap-2 pt-3 border-t border-gray-200 mt-2">
        <input
          className="input flex-1"
          placeholder={isAvailable ? 'Escribe tu pregunta...' : 'Asistente no disponible — configura GROQ_API_KEY'}
          value={input}
          onChange={e => setInput(e.target.value)}
          disabled={!isAvailable || mutation.isPending}
          onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) handleSubmit(e) }}
        />
        <button
          type="submit"
          disabled={!isAvailable || !input.trim() || mutation.isPending}
          className="btn-primary flex items-center gap-1.5 shrink-0">
          <Send className="w-4 h-4" />
        </button>
      </form>

      {messages.length > 0 && (
        <button
          onClick={() => setMessages([])}
          className="text-xs text-gray-400 hover:text-gray-600 mt-2 self-center transition-colors">
          Limpiar conversación
        </button>
      )}
    </div>
  )
}
