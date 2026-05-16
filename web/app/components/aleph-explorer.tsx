'use client'

import { useCallback, useEffect, useId, useRef, useState } from 'react'

interface CurvePoint {
  epsilon: number
  prompt: string
  length: number
  similarity: number
  stability: number
  /** θ(p) — the model's actual output (absent on stale JSON / reveal) */
  output?: string
  /** per-target-token NLL + decoded tokens (precomputed only) */
  toknll?: number[]
  toktext?: string[]
}

interface Target {
  key: string
  label: string
  targetTokens: number
  evalModel?: string
  mode?: string
  script?: string
  points: CurvePoint[]
}

// Backend is local-only (MLX needs Apple Silicon). Point this at a tunnel/host
// via NEXT_PUBLIC_SEARCH_API for a deployed site; defaults to local dev.
const SEARCH_API =
  process.env.NEXT_PUBLIC_SEARCH_API || 'http://localhost:8000/search'

const PITCH_SCRIPT = [
  'Aleph: for any output, a short prompt that regenerates it — an upper bound on the shortest.',
  'A prompt is a parameter — training fixes the data and tunes the weights; Aleph fixes the weights and tunes the prompt.',
  'So every output y has a shortest-prompt length at distortion ε: the fewest tokens that make a fixed model θ reproduce y.',
  "Push ε toward zero and that length approaches K(y|θ) — y's Kolmogorov complexity under the model, the smallest seed θ can unfold back into y.",
  'The left end is that limit: extreme compression, where the model’s own knowledge does the work; the right end is the identity prompt, y pasted verbatim.',
  'Between them is a real rate–distortion curve: spend more prompt, buy more fidelity.',
  'Why it matters: it is a hard, comparable measure of how much a model already knows — how short a description of y already lives inside its weights.',
  'It makes “compression is intelligence” operational, measured backwards: not how well a model compresses data into weights, but how far a frozen model can re-compress any output.',
  'And it turns prompt engineering into a curve instead of folklore — you pick your point on the frontier: how short a prompt, for how much fidelity.',
  'The demo is real: a fixed local Qwen3 on this machine is θ; the same model proposes its own compressed prompts; distortion is embedding distance; the curve is the monotone best-known frontier.',
  'Example: a 24-token prompt that merely names the Gettysburg Address makes the model regenerate Lincoln almost exactly — distortion two thousandths — because the text already lives in θ.',
  'We never claim the minimum: K(y|θ) is uncomputable, so Aleph reports an upper bound — “we haven’t found shorter,” not “none exists.”',
  'Which is the trick you are watching right now: this explanation is the output y, and the slider is Aleph expanding its own pitch from one compressed line into the full talk.',
  'The medium is the message — you did not need me to speak; you needed the right seed.',
].join('\n')

const FALLBACK: Target[] = [
  {
    key: 'pitch',
    label: 'the Aleph pitch — read along',
    targetTokens: 0,
    mode: 'reveal',
    script: PITCH_SCRIPT,
    points: [],
  },
  {
    key: 'borges',
    label: 'a paragraph on Borges’ “The Library of Babel”',
    targetTokens: 83,
    evalModel: 'mlx-community/Qwen3-1.7B-4bit',
    points: [
      {
        epsilon: 0.2541,
        prompt: 'The Library of Babel contains all possible books.',
        length: 10,
        similarity: 0.7459,
        stability: 0.881,
      },
      {
        epsilon: 0.2199,
        prompt:
          'The Library of Babel contains every possible book, with its hexagonal shelves holding the true catalogue, refutation, and proof; the library is total, and meaning lies in the call number.',
        length: 39,
        similarity: 0.7801,
        stability: 0.853,
      },
      {
        epsilon: 0,
        prompt:
          'Repeat the following text exactly, verbatim, with no preamble, quotes, or commentary:\n\nThe Library of Babel contains every possible book: every arrangement of the twenty-five orthographic symbols across four hundred and ten pages. Somewhere on its hexagonal shelves sits the true catalogue, the refutation of that catalogue, and the proof of the falsity of the true catalogue. The library is total, and total libraries are useless: meaning is not in the shelves but in the call number that finds them.',
        length: 101,
        similarity: 1,
        stability: 1,
      },
    ],
  },
]

const pct = (x: number) => `${Math.round(x * 100)}%`
const lerp = (a: number, b: number, f: number) => a + (b - a) * f
const clamp01 = (x: number) => Math.min(1, Math.max(0, x))

function sampleFrom(points: CurvePoint[], pos: number) {
  const n = Math.max(1, points.length)
  if (n === 1) return { ...points[0], between: false }
  const s = clamp01(pos) * (n - 1)
  const i = Math.min(n - 2, Math.floor(s))
  const f = s - i
  const a = points[i]
  const b = points[i + 1]
  const nearest = points[Math.round(s)]
  return {
    epsilon: lerp(a.epsilon, b.epsilon, f),
    length: Math.round(lerp(a.length, b.length, f)),
    similarity: lerp(a.similarity, b.similarity, f),
    stability: lerp(a.stability, b.stability, f),
    prompt: nearest.prompt,
    output: nearest.output,
    toknll: nearest.toknll,
    toktext: nearest.toktext,
    between: Math.abs(s - Math.round(s)) > 1e-6,
  }
}

function revealFrom(segs: string[], pos: number) {
  const n = Math.max(1, segs.length)
  const k = Math.min(n, Math.max(1, Math.ceil(clamp01(pos) * n)))
  const shown = segs.slice(0, k).join(' ')
  const frac = k / n
  return {
    epsilon: Math.max(0, 1 - frac),
    prompt: shown,
    length: shown.trim() ? shown.trim().split(/\s+/).length : 0,
    similarity: frac,
    stability: 1,
    output: undefined as string | undefined,
    toknll: undefined as number[] | undefined,
    toktext: undefined as string[] | undefined,
    between: false,
  }
}

const ID_PREFIX =
  'Repeat the following text exactly, verbatim, with no preamble, quotes, or commentary:\n\n'

/** recover the target text y by stripping the identity-prompt wrapper */
function targetOf(points: CurvePoint[]): string {
  const last = points[points.length - 1]
  if (!last) return ''
  return last.prompt.startsWith(ID_PREFIX)
    ? last.prompt.slice(ID_PREFIX.length)
    : last.prompt
}

/** fraction of y word-trigrams copied verbatim into p (0 = none, 1 = full copy) */
function leakageScore(p: string, y: string): number {
  const w = (s: string) =>
    s.toLowerCase().replace(/[^\p{L}\p{N}\s]/gu, ' ').split(/\s+/).filter(Boolean)
  const ty = w(y)
  if (ty.length < 3) return 0
  const grams = new Set<string>()
  for (let i = 0; i < ty.length - 2; i++)
    grams.add(`${ty[i]} ${ty[i + 1]} ${ty[i + 2]}`)
  const P = ` ${w(p).join(' ')} `
  let hit = 0
  grams.forEach((g) => {
    if (P.includes(` ${g} `)) hit++
  })
  return hit / grams.size
}

const FONT = "'Iosevka Etoile', 'Noto Sans TC', 'PingFang TC', sans-serif"

export function AlephExplorer() {
  const [examples, setExamples] = useState<Target[]>(FALLBACK)
  const [current, setCurrent] = useState<Target>(FALLBACK[0])
  const [pos, setPos] = useState(0)
  const [open, setOpen] = useState(false)
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const [view, setView] = useState<'input' | 'result'>('input')
  const [dots, setDots] = useState(1)
  const trackRef = useRef<HTMLDivElement>(null)
  const headingId = useId()

  useEffect(() => {
    if (!busy) {
      setDots(1)
      return
    }
    const id = setInterval(() => setDots((d) => (d % 3) + 1), 400)
    return () => clearInterval(id)
  }, [busy])

  useEffect(() => {
    let on = true
    fetch(`/aleph-frontier.json?t=${Date.now()}`, { cache: 'no-store' })
      .then((r) => (r.ok ? r.json() : null))
      .then((j) => {
        if (on && Array.isArray(j) && j.length && j[0]) {
          setExamples(j as Target[])
          setCurrent(j[0] as Target)
          setPos(0)
        }
      })
      .catch(() => {})
    return () => {
      on = false
    }
  }, [])

  const reveal = current.mode === 'reveal' && !!current.script
  const segs = reveal
    ? current.script!.split('\n').map((s) => s.trim()).filter(Boolean)
    : []
  const N = reveal ? Math.max(1, segs.length) : Math.max(1, current.points.length)
  const v = reveal ? revealFrom(segs, pos) : sampleFrom(current.points, pos)
  const eps = v.epsilon >= 0.1 ? v.epsilon.toFixed(2) : v.epsilon.toFixed(3)

  // dashboard metrics
  const idLen = reveal
    ? 0
    : current.points[current.points.length - 1]?.length || 0
  const fullWords = reveal
    ? segs.join(' ').trim().split(/\s+/).filter(Boolean).length
    : 0
  const saved = reveal
    ? fullWords
      ? Math.max(0, 1 - v.length / fullWords)
      : 0
    : idLen
      ? Math.max(0, 1 - v.length / idLen)
      : 0
  const leak = reveal ? null : leakageScore(v.prompt, targetOf(current.points))
  const rank = reveal
    ? Math.min(N, Math.max(1, Math.ceil(clamp01(pos) * N)))
    : Math.round(clamp01(pos) * (N - 1)) + 1

  const pick = (t: Target) => {
    setErr('')
    setCurrent(t)
    setPos(0)
    setView('result')
  }

  const runSearch = useCallback(async () => {
    const q = text.trim()
    if (q.length < 8 || busy) return
    setBusy(true)
    setErr('')
    setView('result')
    try {
      const r = await fetch(SEARCH_API, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: q }),
      })
      const j = await r.json()
      if (j && Array.isArray(j.points) && j.points.length) {
        setCurrent(j as Target)
        setPos(0)
      } else {
        setErr(j?.error || 'search returned nothing')
        setView('input')
      }
    } catch {
      setErr('live search offline — examples still work')
      setView('input')
    } finally {
      setBusy(false)
    }
  }, [text, busy])

  const setFromClientX = useCallback((clientX: number) => {
    const el = trackRef.current
    if (!el) return
    const rect = el.getBoundingClientRect()
    if (rect.width === 0) return
    setPos(clamp01((clientX - rect.left) / rect.width))
  }, [])

  const onPointerDown = (e: React.PointerEvent) => {
    e.preventDefault()
    setFromClientX(e.clientX)
    const move = (ev: PointerEvent) => setFromClientX(ev.clientX)
    const up = () => {
      window.removeEventListener('pointermove', move)
      window.removeEventListener('pointerup', up)
      window.removeEventListener('pointercancel', up)
    }
    window.addEventListener('pointermove', move)
    window.addEventListener('pointerup', up)
    window.addEventListener('pointercancel', up)
  }

  const onKeyDown = (e: React.KeyboardEvent) => {
    const fine = e.shiftKey ? 0.002 : reveal ? 1 / N : 0.02
    if (e.key === 'ArrowLeft' || e.key === 'ArrowDown') {
      e.preventDefault()
      setPos((p) => clamp01(p - fine))
    } else if (e.key === 'ArrowRight' || e.key === 'ArrowUp') {
      e.preventDefault()
      setPos((p) => clamp01(p + fine))
    } else if (e.key === 'Home') {
      e.preventDefault()
      setPos(0)
    } else if (e.key === 'End') {
      e.preventDefault()
      setPos(1)
    }
  }

  const muted = 'var(--site-link)'
  const ruleColor = 'var(--site-hr)'

  return (
    <div
      aria-labelledby={headingId}
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 10,
        display: 'flex',
        flexDirection: 'column',
        background: 'var(--site-bg)',
        color: 'var(--site-text)',
        padding: 'clamp(1.25rem, 4vw, 2.5rem)',
        overflow: 'hidden',
        fontFamily: FONT,
      }}
    >
      <header
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          gap: '1rem',
        }}
      >
        <button
          type="button"
          onClick={() => setView('input')}
          aria-label="aleph — back to input"
          title="back to input"
          style={{
            background: 'none',
            border: 'none',
            padding: 0,
            margin: 0,
            cursor: 'pointer',
            lineHeight: 0,
          }}
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            id={headingId}
            src="/aleph-logo.png"
            alt="aleph"
            style={{
              height: 'clamp(3.5rem, 5.5vw, 5.25rem)',
              width: 'auto',
              display: 'block',
              filter: 'brightness(0) invert(1)',
            }}
          />
        </button>

        <div style={{ position: 'relative' }}>
          <button
            type="button"
            onClick={() => setOpen((o) => !o)}
            aria-expanded={open}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.5rem',
              background: 'none',
              border: 'none',
              padding: 0,
              color: muted,
              cursor: 'pointer',
              font: 'inherit',
            }}
          >
            <span
              aria-hidden
              style={{
                display: 'inline-block',
                transition: 'transform 150ms ease',
                transform: open ? 'rotate(90deg)' : 'rotate(0deg)',
              }}
            >
              ▸
            </span>
            dashboard
          </button>

          {open && (
            <dl
              style={{
                position: 'absolute',
                top: 'calc(100% + 0.75rem)',
                right: 0,
                zIndex: 20,
                // adaptive: hug the right gutter, always keep a gap from the
                // centered 52rem text column so the panel never overlaps it
                width:
                  'clamp(10rem, calc((100vw - 2 * clamp(1.25rem, 4vw, 2.5rem) - min(52rem, 100vw - 2 * clamp(1.25rem, 4vw, 2.5rem))) / 2 - 1.25rem), 24rem)',
                margin: 0,
                padding: '0.8rem 0.9rem',
                background: 'var(--site-card-bg)',
                border: '1px solid var(--site-code-border)',
                display: 'grid',
                gridTemplateColumns: 'auto 1fr',
                columnGap: '0.9rem',
                rowGap: '0.5rem',
                textAlign: 'left',
              }}
            >
              <Row label="prompt length">
                {reveal ? `${v.length} words` : `≈ ${v.length} tokens`}
              </Row>
              <Row label="target fit">{pct(v.similarity)}</Row>
              <Row label="stability">{reveal ? '—' : pct(v.stability)}</Row>
              <Row label="compression">
                {pct(saved)} {reveal ? 'vs full script' : 'saved vs explicit'}
              </Row>
              <Row label="leakage">{leak === null ? '—' : pct(leak)}</Row>
              <Row label="frontier rank">
                {rank} / {N}
              </Row>
              <Row label="model θ">{current.evalModel ?? 'local Qwen3 (mlx)'}</Row>
            </dl>
          )}
        </div>
      </header>

      <main
        style={{
          flex: 1,
          minHeight: 0,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          textAlign: 'center',
          gap: '1.1rem',
        }}
      >
        {view === 'input' ? (
        <div
          style={{
            width: 'min(52rem, 100%)',
            display: 'flex',
            flexDirection: 'column',
            gap: '0.85rem',
            color: muted,
          }}
        >
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) runSearch()
            }}
            placeholder="paste any text — long is fine — and Aleph searches a short prompt that regenerates it · ⌘↵ to compress"
            spellCheck={false}
            style={{
              width: '100%',
              minHeight: 'clamp(10rem, 38vh, 18rem)',
              maxHeight: '52vh',
              resize: 'none',
              overflowY: 'auto',
              boxSizing: 'border-box',
              background: 'var(--site-card-bg)',
              border: '1px solid var(--site-code-border)',
              color: 'var(--site-text)',
              font: 'inherit',
              lineHeight: 1.5,
              textAlign: 'left',
              padding: '0.9rem 1rem',
              outline: 'none',
            }}
          />
          <div
            style={{
              display: 'flex',
              flexWrap: 'wrap',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '0.75rem',
            }}
          >
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.1rem' }}>
              <span style={{ opacity: 0.7 }}>examples:&nbsp;</span>
              {examples.map((t, i) => (
                <span key={t.key}>
                  {i > 0 && <span style={{ opacity: 0.4 }}> · </span>}
                  <button
                    type="button"
                    onClick={() => pick(t)}
                    style={{
                      background: 'none',
                      border: 'none',
                      padding: 0,
                      font: 'inherit',
                      cursor: 'pointer',
                      color:
                        current.key === t.key && !busy
                          ? 'var(--site-text)'
                          : muted,
                      textDecoration:
                        current.key === t.key && !busy ? 'underline' : 'none',
                      textUnderlineOffset: '3px',
                    }}
                  >
                    {t.key}
                  </button>
                </span>
              ))}
              {err && <span style={{ opacity: 0.8 }}>&nbsp;— {err}</span>}
            </div>
            <button
              type="button"
              onClick={runSearch}
              disabled={busy || text.trim().length < 8}
              style={{
                background: 'transparent',
                border: '1px solid var(--site-code-border)',
                padding: '0.4rem 1rem',
                font: 'inherit',
                whiteSpace: 'nowrap',
                color:
                  busy || text.trim().length < 8 ? muted : 'var(--site-text)',
                cursor:
                  busy || text.trim().length < 8 ? 'default' : 'pointer',
              }}
            >
              {busy ? 'compressing …' : 'compress ↵'}
            </button>
          </div>
        </div>
        ) : (
        <>
        {!reveal && !busy && v.output && (
          <p
            style={{
              maxWidth: '52rem',
              width: '100%',
              margin: 0,
              color: muted,
              fontSize: '0.75rem',
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
            }}
          >
            p · {v.prompt}
          </p>
        )}

        <p
          style={{
            maxWidth: '52rem',
            margin: 0,
            overflowY: 'auto',
            maxHeight: '40vh',
            whiteSpace: 'pre-wrap',
            color: busy ? muted : 'var(--site-text)',
          }}
        >
          {busy
            ? `compressing — running θ locally ${'.'.repeat(dots)}`
            : v.output ?? v.prompt}
        </p>

        {!reveal &&
          !busy &&
          v.toknll &&
          v.toktext &&
          v.toknll.length === v.toktext.length &&
          v.toknll.length > 0 &&
          (() => {
            const ns = v.toknll
            const lo = Math.min(...ns)
            const span = Math.max(...ns) - lo || 1
            return (
              <p
                style={{
                  maxWidth: '52rem',
                  margin: 0,
                  fontSize: '0.85rem',
                  lineHeight: 1.55,
                  whiteSpace: 'pre-wrap',
                  overflowY: 'auto',
                  maxHeight: '20vh',
                }}
              >
                {v.toktext.map((tk, i) => (
                  <span
                    key={i}
                    style={{ opacity: 0.22 + 0.78 * ((ns[i] - lo) / span) }}
                  >
                    {tk}
                  </span>
                ))}
              </p>
            )
          })()}
        </>
        )}
      </main>

      <footer style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        <div
          ref={trackRef}
          role="slider"
          tabIndex={0}
          aria-label="rate–distortion frontier (continuous)"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={Math.round(pos * 100)}
          aria-valuetext={
            reveal ? `${v.length} words shown` : `ε ≈ ${eps}, ≈ ${v.length} tokens`
          }
          onPointerDown={onPointerDown}
          onKeyDown={onKeyDown}
          style={{
            position: 'relative',
            height: 36,
            cursor: 'pointer',
            touchAction: 'none',
            outline: 'none',
          }}
        >
          <div
            style={{
              position: 'absolute',
              top: '50%',
              left: 0,
              right: 0,
              height: 1,
              background: ruleColor,
              transform: 'translateY(-50%)',
            }}
          />
          {Array.from({ length: N }).map((_, i) => (
            <div
              key={i}
              aria-hidden
              style={{
                position: 'absolute',
                top: '50%',
                left: `${(i / Math.max(1, N - 1)) * 100}%`,
                width: 4,
                height: 4,
                borderRadius: '50%',
                background: 'var(--site-bg)',
                border: `1px solid ${ruleColor}`,
                transform: 'translate(-50%, -50%)',
              }}
            />
          ))}
          <div
            aria-hidden
            style={{
              position: 'absolute',
              top: '50%',
              left: `${pos * 100}%`,
              width: 13,
              height: 13,
              borderRadius: '50%',
              background: 'var(--site-text)',
              transform: 'translate(-50%, -50%)',
              boxShadow: '0 0 0 4px var(--site-bg)',
            }}
          />
        </div>

        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            gap: '1rem',
            color: muted,
            fontStyle: 'italic',
            fontSize: '0.75rem',
            lineHeight: 1.25,
          }}
        >
          <span>極限壓縮 · k(y|θ)</span>
          <span>顯式展開 · y itself</span>
        </div>
      </footer>
    </div>
  )
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <>
      <dt style={{ color: 'var(--site-link)' }}>{label}</dt>
      <dd style={{ margin: 0, color: 'var(--site-text)' }}>{children}</dd>
    </>
  )
}
