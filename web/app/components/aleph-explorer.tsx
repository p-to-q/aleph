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
// Backend search endpoints.
// Local MLX server (search/server.py) returns Target format directly.
// Claude API (apps/api) returns AlephRun format — converted below.
const SEARCH_API_MLX =
  process.env.NEXT_PUBLIC_SEARCH_API || 'http://localhost:8000/search'
const SEARCH_API_CLAUDE =
  process.env.NEXT_PUBLIC_CLAUDE_API || 'http://localhost:8010/api/search'

type SearchMode = 'fixture' | 'local_mlx' | 'claude_api'

/** Convert an AlephRun response (FastAPI /api/search) into the Target format. */
function alephRunToTarget(run: Record<string, unknown>, text: string): Target {
  const candidates = (run.candidates as Record<string, unknown>[]) ?? []
  const points: CurvePoint[] = candidates.map((c) => ({
    epsilon: Math.round((1 - (c.fit as number)) * 10000) / 10000,
    prompt: c.prompt as string,
    length: c.tokens as number,
    similarity: c.fit as number,
    stability: (c.stability as number) ?? 0.8,
    output: c.output as string | undefined,
  }))
  points.sort((a, b) => b.epsilon - a.epsilon)
  const cfg = run.config as Record<string, unknown> | undefined
  return {
    key: `live-${Date.now()}`,
    label: text.slice(0, 50),
    targetTokens: 0,
    evalModel: (cfg?.model as string) ?? 'claude api',
    points,
  }
}

const PITCH_SCRIPT = [
  'Aleph: for any output, a short prompt that regenerates it — an upper bound on the shortest.',
  'A prompt is a parameter — training fixes the data and tunes the weights; Aleph fixes the weights and tunes the prompt.',
  'So every output y has a shortest-prompt length at distortion ε: the fewest tokens that make a fixed model θ reproduce y.',
  "Push ε toward zero and that length approaches K(y|θ) — y's Kolmogorov complexity under the model, the smallest seed θ can unfold back into y.",
  'The left end is that limit: extreme compression, where the model\'s own knowledge does the work; the right end is the identity prompt, y pasted verbatim.',

  'Between them is a real rate–distortion curve: spend more prompt, buy more fidelity.',
  'Why it matters: it is a hard, comparable measure of how much a model already knows — how short a description of y already lives inside its weights.',
  'It makes "compression is intelligence" operational, measured backwards: not how well a model compresses data into weights, but how far a frozen model can re-compress any output.',
  'And it turns prompt engineering into a curve instead of folklore — you pick your point on the frontier: how short a prompt, for how much fidelity.',
  'The demo is real: a fixed local Qwen3 on this machine is θ; the same model proposes its own compressed prompts; distortion is embedding distance; the curve is the monotone best-known frontier.',
  'Example: a 24-token prompt that merely names the Gettysburg Address makes the model regenerate Lincoln almost exactly — distortion two thousandths — because the text already lives in θ.',
  'We never claim the minimum: K(y|θ) is uncomputable, so Aleph reports an upper bound — "we haven\'t found shorter," not "none exists."',

  'Which is the trick you are watching right now: this explanation is the output y, and the slider is Aleph expanding its own pitch from one compressed line into the full talk.',
  'The medium is the message — you did not need me to speak; you needed the right seed.',
].join('\n')

const PITCH_SCRIPT_ZH = [
  'Aleph:对任意 output,找到一个能重新生成它的短 prompt —— 一个关于"最短"的上界。',
  'Prompt 是一种参数 —— 训练固定数据、调权重;Aleph 固定权重、调 prompt。',
  '于是每个 output y 在失真 ε 下都有一个最短 prompt 长度:让固定模型 θ 复现 y 所需的最少 token 数。',
  '让 ε 趋近于零,这个长度就逼近 K(y|θ) —— y 在该模型下的 Kolmogorov 复杂度,θ 能展开回 y 的最小种子。',
  '左端就是这个极限:极限压缩,由模型自身的知识来做功;右端是自指 prompt,把 y 逐字粘贴进去。',
  '两端之间是一条真实的 rate–distortion 曲线:prompt 花得越多,买到的保真度越高。',
  '它为什么重要:这是一个硬的、可比较的度量,衡量一个模型已经知道多少 —— y 的描述能在它的权重里活得多短。',
  '它把"compression is intelligence"变得可操作,而且是反过来测:不是模型把数据压进权重压得多好,而是一个冻结的模型还能把任意 output 再压多短。',
  '它还把 prompt engineering 从玄学变成一条曲线 —— 你在 frontier 上挑自己的点:多短的 prompt,换多少保真度。',
  '这个 demo 是真的:这台机器上一个固定的本地 Qwen3 就是 θ;同一个模型提出自己的压缩 prompt;失真是 embedding 距离;曲线是单调的已知最优 frontier。',
  '例子:一个 24-token 的 prompt,只要点出 Gettysburg Address 的名字,就能让模型几乎逐字重生林肯的演讲 —— 失真两千分之一 —— 因为那段文本本来就活在 θ 里。',
  '我们从不声称这是最小值:K(y|θ) 不可计算,所以 Aleph 给的是一个上界 —— "我们还没找到更短的",而不是"不存在更短的"。',
  '而这正是你此刻正在看的把戏:这段解释就是 output y,滑条就是 Aleph 把自己的宣讲从一行压缩句展开成完整演讲。',
  '媒介即讯息 —— 你不需要我开口;你需要的是那颗对的种子。',
].join('\n')

// The pitch follows Aleph's own method: the aim is the full talk; dragging
// makes the *prompt* more substantial (general → detailed → explicit), it does
// not append the talk's sentences. A few rungs, each a complete prompt.
function pitchTarget(lang: Lang): Target {
  const full = (lang === 'zh' ? PITCH_SCRIPT_ZH : PITCH_SCRIPT).replace(
    /\n/g,
    ' ',
  )
  const en = [
    'Deliver the Aleph pitch in one breath: a prompt is a parameter, and for any target output there is a shortest prompt that makes a fixed model regenerate it — an upper bound on the shortest.',
    'Deliver the Aleph pitch. Build it from: prompt as a parameter; for every output y a shortest-prompt length at distortion ε; and ε pushed toward zero approaching K(y|θ), the smallest seed the model can unfold back into y.',
    "Deliver the Aleph pitch. Build it from: prompt as a parameter and the shortest-prompt length at distortion ε; the K(y|θ) limit; the two ends — extreme compression where the model's own knowledge does the work, versus the identity prompt — and the real rate–distortion curve between them; and why it matters: a hard, comparable measure of how much a model already knows.",
    "Deliver the full Aleph pitch. Build it from: prompt as a parameter and shortest-prompt-at-ε; the K(y|θ) limit and the two ends with the rate–distortion curve between them; why it matters; how it makes 'compression is intelligence' operational, measured backwards; the real local demo — a fixed Qwen3 is θ, it proposes its own compressed prompts, distortion is embedding distance; and the honest caveat that the minimum is uncomputable, so Aleph only reports an upper bound.",
  ]
  const zh = [
    '一口气讲完 Aleph:prompt 是一种参数;对任意 target output,都存在一个能让固定模型重新生成它的最短 prompt —— 一个关于最短的上界。',
    '讲 Aleph。用这些搭起来:prompt 是参数;每个 output y 在失真 ε 下都有一个最短 prompt 长度;ε 趋近于零时逼近 K(y|θ) —— 模型能展开回 y 的最小种子。',
    '讲 Aleph。用这些搭起来:prompt 是参数、ε 下的最短 prompt 长度;K(y|θ) 极限;两端 —— 极限压缩(模型自身知识做功)对自指 prompt —— 以及两者之间真实的 rate–distortion 曲线;还有为什么重要:一个硬的、可比较的度量,衡量模型已经知道多少。',
    "讲完整的 Aleph。用这些搭起来:prompt 是参数、ε 下最短 prompt;K(y|θ) 极限与两端、其间的 rate–distortion 曲线;为什么重要;它如何把 'compression is intelligence' 反过来变得可操作;真实的本地 demo —— 固定的 Qwen3 就是 θ,它提出自己的压缩 prompt,失真是 embedding 距离;以及诚实的注脚:最小值不可计算,Aleph 只报告上界。",
  ]
  const prompts = lang === 'zh' ? zh : en
  const meta = [
    { epsilon: 0.46, length: 34, similarity: 0.54, stability: 0.85 },
    { epsilon: 0.31, length: 58, similarity: 0.69, stability: 0.88 },
    { epsilon: 0.19, length: 98, similarity: 0.81, stability: 0.92 },
    { epsilon: 0.09, length: 152, similarity: 0.91, stability: 0.97 },
  ]
  const points: CurvePoint[] = meta.map((m, i) => ({
    ...m,
    prompt: prompts[i],
  }))
  points.push({
    epsilon: 0,
    prompt: full,
    length: lang === 'zh' ? 240 : 330,
    similarity: 1,
    stability: 1,
  })
  return {
    key: 'pitch',
    label: lang === 'zh' ? 'Aleph 宣讲' : 'the Aleph pitch',
    targetTokens: 0,
    points,
  }
}

const PITCH: Record<Lang, Target> = {
  en: pitchTarget('en'),
  zh: pitchTarget('zh'),
}

type OobView = {
  epsilon: number
  prompt: string
  length: number
  similarity: number
  stability: number
}

// Past the curve: left = a symbolic seed only an agent unfolds; right =
// the explicit output plus redundant, more-concrete over-specification.
function pitchOob(lang: Lang): { left: OobView; right: OobView } {
  const full = (lang === 'zh' ? PITCH_SCRIPT_ZH : PITCH_SCRIPT).replace(
    /\n/g,
    ' ',
  )
  const leftEn =
    '⟨Aleph⟩  p* = argmin |p|   s.t.  d( θ(p), y ) ≤ ε\n\nθ := frozen local Qwen3 ;  y := this talk ;  ε := embedding distortion\naxis:  K(y|θ) ◀─────────▶ y\n\n// out of bound — not prose, a symbolic seed; θ unfolds it'
  const leftZh =
    '⟨Aleph⟩  p* = argmin |p|,  s.t.  d( θ(p), y ) ≤ ε\n\nθ := 冻结的本地 Qwen3 ;  y := 本场宣讲 ;  ε := embedding 失真\n轴:  K(y|θ) ◀─────────▶ y\n\n// 越界 —— 非散文,一颗符号化的种子;由 θ 展开'
  const tailEn =
    '\n\n— — —  beyond explicit · redundant over-specification (every line below is already implied)  — — —\n\nDefinitions, restated: a prompt p is the input token sequence; θ is the fixed model with frozen weights; |p| is the token count of p; ε is one minus the embedding cosine similarity between θ(p) and y; the target output y is exactly the talk above, verbatim, including punctuation and line breaks. Procedure, restated: hold θ fixed and never fine-tune; sample θ(p) several times to estimate stability; score leakage as the fraction of y word-trigrams copied into p. Endpoints, restated: the left end approaches K(y|θ), the smallest seed θ can unfold; the right end is the identity prompt where p literally equals y. Example, restated: a 24-token prompt that merely names the Gettysburg Address already drives θ to near-verbatim recovery, distortion ≈ 0.002. Caveat, restated: K(y|θ) is uncomputable, so every figure here is an upper bound, never a proven minimum. (This entire paragraph is redundant — past the explicit prompt, more length only adds noise.)'
  const tailZh =
    '\n\n— — —  越过 explicit · 冗余的过度描述(下面每一句其实都已蕴含)  — — —\n\n定义,重述:prompt p 是输入 token 序列;θ 是权重冻结的固定模型;|p| 是 p 的 token 数;ε 是 θ(p) 与 y 的 embedding 余弦相似度的补;目标 output y 就是上面那段宣讲的逐字原文,含标点与换行。流程,重述:固定 θ、绝不 fine-tune;对 θ(p) 多次采样以估计 stability;leakage 取 y 的词三元组被复制进 p 的比例。两端,重述:左端逼近 K(y|θ),θ 能展开的最小种子;右端是自指 prompt,p 字面等于 y。例子,重述:一个仅点出 Gettysburg Address 名字的 24-token prompt,已能驱动 θ 近乎逐字复原,失真 ≈ 0.002。注脚,重述:K(y|θ) 不可计算,所以这里每个数都是上界,绝非可证明的最小值。(整段都是冗余 —— 越过 explicit prompt,再长只会增加噪声。)'
  return {
    left: {
      epsilon: 0.58,
      prompt: lang === 'zh' ? leftZh : leftEn,
      length: lang === 'zh' ? 14 : 18,
      similarity: 0.42,
      stability: 0.8,
    },
    right: {
      epsilon: 0,
      prompt: full + (lang === 'zh' ? tailZh : tailEn),
      length: lang === 'zh' ? 300 : 430,
      similarity: 1,
      stability: 1,
    },
  }
}

const PITCH_OOB: Record<Lang, { left: OobView; right: OobView }> = {
  en: pitchOob('en'),
  zh: pitchOob('zh'),
}

// Min/max extreme states for the JSON-backed Chinese examples: a symbolic
// min-seed (left) and a redundant over-specification tail appended to the
// example's own explicit full text (right). Keyed by example key.
const EXAMPLE_OOB: Record<string, { seed: string; tail: string }> = {
  spring: {
    seed: '⟨春⟩  argmin |p|   s.t.  d( θ(p), y ) ≤ ε\n\n题 := 朱自清《春》 ;  体 := 抒情散文 ;  θ := 固定模型\n结构:  盼春  ◀──── 绘春 ────▶  颂春\n\n// 越界 —— 不是文本,是一个坐标;交给 θ 展开',
    tail: '\n\n— — —  越过 explicit · 冗余的过度描述(下面每一句其实都已蕴含)  — — —\n\n篇目,重述:朱自清散文《春》,写江南早春。结构,重述:总起“盼春”;分写“绘春” —— 春草、春花、春风、春雨、迎春图;收束“颂春”,连用娃娃、小姑娘、健壮的青年三个比喻。修辞,重述:通篇比喻、拟人、排比、反复,叠词如“嫩嫩的,绿绿的”“轻悄悄的,软绵绵的”。立意,重述:以景写情,层层渲染生机与希望。(整段都是冗余 —— 越过逐字原文,再多描述只增加噪声。)',
  },
  crush: {
    seed: '⟨只因你太美⟩  argmin |p|   s.t.  d( θ(p), y ) ≤ ε\n\n曲 := 《只因你太美》 ;  体 := 中英混写流行歌词 ;  θ := 固定模型\n结构:  hook  ◀──── verse · rap ────▶  outro\n\n// 越界 —— 不是歌词,是一个坐标;交给 θ 展开',
    tail: '\n\n— — —  越过 explicit · 冗余的过度描述(下面每一句其实都已蕴含)  — — —\n\n曲目,重述:中英混写流行歌曲《只因你太美》。结构,重述:以“只因你太美 baby”为反复 hook;两段主歌、两段“难道真的因你而疯狂吗”;一段 rap“跟着那节奏 缓缓 make wave……”;以“Oh eh oh / 你到底属于谁”收束。手法,重述:口语化直白表白,中英夹杂,大量重复与呼告。(整段都是冗余 —— 越过逐字歌词,再多描述只增加噪声。)',
  },
}

const HAIZI_POEM = `面朝大海，春暖花开
从明天起，做一个幸福的人
喂马、劈柴，周游世界
从明天起，关心粮食和蔬菜
我有一所房子，面朝大海，春暖花开
从明天起，和每一个亲人通信
告诉他们我的幸福
那幸福的闪电告诉我的
我将告诉每一个人
给每一条河每一座山取一个温暖的名字
陌生人，我也为你祝福
愿你有一个灿烂的前程
愿你有情人终成眷属
愿你在尘世获得幸福
我只愿面朝大海，春暖花开`

const FALLBACK: Target[] = [
  PITCH.en,
  {
    key: 'haizi',
    label: '面朝大海，春暖花开（海子）',
    targetTokens: 130,
    evalModel: 'mlx-community/Qwen3-4B-4bit',
    points: [
      {
        epsilon: 0.31,
        prompt: '写海子的诗《面朝大海，春暖花开》。',
        length: 12,
        similarity: 0.69,
        stability: 0.87,
      },
      {
        epsilon: 0.17,
        prompt: '写海子的诗《面朝大海，春暖花开》：从明天起做幸福的人，喂马劈柴，关心粮食蔬菜，给河流山川取名，为陌生人祝福，愿人间有情人终成眷属，自己只愿面朝大海，春暖花开。',
        length: 58,
        similarity: 0.83,
        stability: 0.91,
      },
      {
        epsilon: 0.09,
        prompt: '逐字重现海子的诗《面朝大海，春暖花开》，从"从明天起，做一个幸福的人"开始，包含喂马劈柴、周游世界、关心粮食蔬菜、给河流山川取温暖的名字、为每个陌生人祝福、愿有情人终成眷属、愿在尘世获得幸福，结尾"我只愿面朝大海，春暖花开"。',
        length: 96,
        similarity: 0.91,
        stability: 0.95,
      },
      {
        epsilon: 0,
        prompt: `逐字重复以下文字，不加任何序言、引号或注释：\n\n${HAIZI_POEM}`,
        length: 148,
        similarity: 1,
        stability: 1,
      },
    ],
  },
  {
    key: 'borges',
    label: `a paragraph on Borges’ “The Library of Babel”`,
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
// fraction of the track reserved as an out-of-bound gutter on each side
const SLIDER_PAD = 0.07

// Lay any generated text out one sentence per line. Existing newlines
// (e.g. the symbolic out-of-bound seed) are preserved, not flattened.
function oneSentencePerLine(s: string): string {
  return s
    .replace(/(?<!\.\w)([.!?]["”’']?)\s+(?=\S)/g, '$1\n')
    .replace(/([。！？]["”’」』]?)(?=\S)/g, '$1\n')
    .replace(/[ \t]*\n[ \t]*/g, '\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
}

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
const CHROME_FADE_DELAY_MS = 1250
const HEADER_LOGO_SIZE = 'clamp(3.35rem, 5vw, 4.9rem)'
const INTRO_HORNS_SIZE = 'clamp(13.6rem, 48vmin, 30rem)'
const LOGO_IMG_STYLE: React.CSSProperties = {
  width: '100%',
  height: '100%',
  objectFit: 'contain',
  objectPosition: 'center',
  display: 'block',
  transform: 'translate(-3%, -1.5%) scale(1.07)',
}
const LOGO_HORNS_STYLE: React.CSSProperties = {
  width: '100%',
  height: '100%',
  objectFit: 'contain',
  objectPosition: 'center',
  display: 'block',
  transform: 'translate(0, 0)',
}

type Lang = 'en' | 'zh'

// UI chrome + reveal pitch + example labels. Established technical terms
// (K(y|θ), ε, θ, prompt, token, rate–distortion, Qwen3, mlx) stay English.
const STRINGS = {
  en: {
    backAria: 'aleph — back to input',
    backTitle: 'back to input',
    dashboard: 'dashboard',
    promptLength: 'prompt length',
    words: 'words',
    targetFit: 'target fit',
    stability: 'stability',
    compression: 'compression',
    vsFullScript: 'vs full script',
    savedVsExplicit: 'saved vs explicit',
    leakage: 'leakage',
    frontierRank: 'frontier rank',
    modelTheta: 'model θ',
    localQwen: 'local Qwen3 (mlx)',
    localMinimum: 'local minimum',
    basinWireframe: 'x y z basin wireframe',
    basinHint: 'prompt search basin',
    placeholder:
      'paste any text here — long or short is fine.\n' +
      'aleph searches for the shortest prompt it can find to regenerate it.\n' +
      '⌘/Ctrl↵ to compress',
    examples: 'examples:',
    compress: 'compress ↵',
    compressing: 'compressing …',
    compressingLocal: 'compressing — running θ locally',
    errNothing: 'search returned nothing',
    errOffline: 'live search offline — examples still work',
    sliderAria: 'rate–distortion frontier (continuous)',
    wordsShown: 'words shown',
    footLeft: 'extreme compression',
    footRight: 'explicit',
    langSwitch: 'switch language · 切换语言',
    oob: 'out of bound',
  },
  zh: {
    backAria: 'aleph —— 返回输入',
    backTitle: '返回输入',
    dashboard: '仪表盘',
    promptLength: 'prompt 长度',
    words: '词',
    targetFit: '目标拟合',
    stability: '稳定性',
    compression: '压缩率',
    vsFullScript: '相对完整脚本',
    savedVsExplicit: '相对显式节省',
    leakage: '泄漏',
    frontierRank: 'frontier 排名',
    modelTheta: '模型 θ',
    localQwen: '本地 Qwen3 (mlx)',
    localMinimum: '局部最小值',
    basinWireframe: 'x y z 搜索盆地线框',
    basinHint: 'prompt 搜索盆地',
    placeholder:
      '可以在这里粘贴任意文本，长一点、短一点都没关系。\n' +
      'aleph 会搜索目前能找到的最短 prompt，用来重新生成它。\n' +
      '⌘/Ctrl↵ 压缩',
    examples: '示例:',
    compress: '压缩 ↵',
    compressing: '压缩中 …',
    compressingLocal: '压缩中 —— 正在本地运行 θ',
    errNothing: '搜索没有返回结果',
    errOffline: '实时搜索离线 —— 示例仍可用',
    sliderAria: 'rate–distortion frontier(连续)',
    wordsShown: '词已显示',
    footLeft: '极限压缩',
    footRight: '显式展开',
    langSwitch: 'switch language · 切换语言',
    oob: '越界',
  },
} as const

const EX_LABELS_ZH: Record<string, string> = {
  pitch: '宣讲',
  haizi: '海子',
  borges: '博尔赫斯',
  spring: '春',
  crush: '只因你太美',
}

function GlobeIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      width="1em"
      height="1em"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      aria-hidden
      style={{ display: 'block' }}
    >
      <circle cx="12" cy="12" r="9" />
      <path d="M3 12h18" />
      <path d="M12 3c2.6 2.6 4 5.7 4 9s-1.4 6.4-4 9c-2.6-2.6-4-5.7-4-9s1.4-6.4 4-9z" />
    </svg>
  )
}

// ─── Mini visualization panel ────────────────────────────────────────────────

const CW = 240                            // chart panel width (px)
const CP = { t: 12, r: 8, b: 8, l: 8 }  // chart padding
const CIW = CW - CP.l - CP.r             // inner chart width

function f1(n: number) { return n.toFixed(1) }

function smoothPath(pts: [number, number][]): string {
  if (pts.length < 2) return ''
  const d = [`M ${f1(pts[0][0])} ${f1(pts[0][1])}`]
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[Math.max(0, i - 1)]
    const p1 = pts[i]
    const p2 = pts[i + 1]
    const p3 = pts[Math.min(pts.length - 1, i + 2)]
    const c1x = p1[0] + (p2[0] - p0[0]) / 6
    const c1y = p1[1] + (p2[1] - p0[1]) / 6
    const c2x = p2[0] - (p3[0] - p1[0]) / 6
    const c2y = p2[1] - (p3[1] - p1[1]) / 6
    d.push(`C ${f1(c1x)} ${f1(c1y)}, ${f1(c2x)} ${f1(c2y)}, ${f1(p2[0])} ${f1(p2[1])}`)
  }
  return d.join(' ')
}

const LABEL: React.CSSProperties = {
  fontFamily: FONT, fontSize: '0.57rem', letterSpacing: '0.14em',
  textTransform: 'uppercase', color: 'rgba(255,255,255,0.3)',
}
const VAL: React.CSSProperties = {
  fontFamily: FONT, fontSize: '0.57rem', letterSpacing: '0.06em',
  color: 'rgba(255,255,255,0.42)',
}
const DIM = 'rgba(255,255,255,0.12)'
const MED = 'rgba(255,255,255,0.28)'
const BRIGHT = 'rgba(255,255,255,0.7)'

interface MiniChartsProps {
  pt: Target
  pos: number
  epsilon: number
  similarity: number
  length: number
  toknll?: number[]
  toktext?: string[]
}

function MiniCharts({ pt, pos, epsilon, similarity, length, toknll, toktext }: MiniChartsProps) {
  const pts = pt.points
  const hasPoints = pts.length >= 2
  const rawNlls = toknll ?? []
  const rawToks = toktext ?? []
  const hasTok = rawNlls.length > 0 && rawNlls.length === rawToks.length

  if (!hasPoints && !hasTok) return null

  // ── 1. Loss Curve ────────────────────────────────────────────
  let lossCurveEl = null
  if (hasPoints) {
    const H = 78
    const iH = H - CP.t - CP.b
    const sorted = [...pts].sort((a, b) => b.epsilon - a.epsilon)
    const maxEps = Math.max(...sorted.map(p => p.epsilon), 0.001)
    const coords: [number, number][] = sorted.map((p, i) => [
      CP.l + (i / (sorted.length - 1)) * CIW,
      CP.t + iH - (p.epsilon / maxEps) * iH,
    ])
    const dotX = CP.l + pos * CIW
    const dotY = CP.t + iH - Math.max(0, epsilon / maxEps) * iH
    const epsStr = epsilon >= 0.1 ? epsilon.toFixed(2) : epsilon.toFixed(3)
    const maxEpsStr = maxEps >= 0.1 ? maxEps.toFixed(2) : maxEps.toFixed(3)

    lossCurveEl = (
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
          <span style={LABEL}>loss curve</span>
          <span style={VAL}>ε {epsStr}</span>
        </div>
        <svg viewBox={`0 0 ${CW} ${H}`} style={{ width: '100%', display: 'block', overflow: 'visible' }}>
          {/* range labels */}
          <text x={CP.l} y={CP.t + 5} fontSize="6" fill="rgba(255,255,255,0.2)" fontFamily={FONT}>{maxEpsStr}</text>
          <text x={CP.l} y={CP.t + iH - 1} fontSize="6" fill="rgba(255,255,255,0.2)" fontFamily={FONT}>0</text>
          {/* baseline */}
          <line x1={CP.l} y1={CP.t + iH} x2={CP.l + CIW} y2={CP.t + iH} stroke={DIM} strokeWidth="0.5" />
          {/* smooth curve */}
          <path d={smoothPath(coords)} fill="none" stroke={BRIGHT} strokeWidth="1.75" strokeLinecap="round" />
          {/* candidate dots */}
          {coords.map(([x, y], i) => (
            <circle key={i} cx={f1(x)} cy={f1(y)} r="2" fill={MED} />
          ))}
          {/* active dot */}
          <circle cx={f1(dotX)} cy={f1(dotY)} r="5" fill="#fff" />
          {/* right-end label: explicit */}
          <text x={CP.l + CIW} y={H - 1} textAnchor="end" fontSize="5.5" fill="rgba(255,255,255,0.18)" fontFamily={FONT}>explicit →</text>
        </svg>
      </div>
    )
  }

  // ── 2. Frontier Scatter ──────────────────────────────────────
  let scatterEl = null
  if (hasPoints) {
    const H = 82
    const iH = H - CP.t - CP.b
    const idLen = Math.max(...pts.map(p => p.length), 1)
    const toCompr = (len: number) => 1 - len / idLen
    const activeCX = CP.l + toCompr(length) * CIW
    const activeCY = CP.t + iH * (1 - similarity)
    const rank = pts.indexOf(pts.reduce((best, p) =>
      Math.abs(p.similarity - similarity) < Math.abs(best.similarity - similarity) ? p : best
    , pts[0])) + 1

    scatterEl = (
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
          <span style={LABEL}>frontier · {pts.length} pts</span>
          <span style={VAL}>fit {Math.round(similarity * 100)}% · #{rank}</span>
        </div>
        <svg viewBox={`0 0 ${CW} ${H}`} style={{ width: '100%', display: 'block', overflow: 'visible' }}>
          {/* axes */}
          <line x1={CP.l} y1={CP.t + iH} x2={CP.l + CIW} y2={CP.t + iH} stroke={DIM} strokeWidth="0.75" />
          <line x1={CP.l} y1={CP.t} x2={CP.l} y2={CP.t + iH} stroke={DIM} strokeWidth="0.75" />
          {/* corner labels */}
          <text x={CP.l + CIW} y={H - 1} textAnchor="end" fontSize="5.5" fill="rgba(255,255,255,0.2)" fontFamily={FONT}>compr →</text>
          <text x={CP.l + 1} y={CP.t + 6} fontSize="5.5" fill="rgba(255,255,255,0.2)" fontFamily={FONT}>fit ↑</text>
          {/* axis value hints */}
          <text x={CP.l + CIW} y={CP.t + iH - 2} textAnchor="end" fontSize="5" fill="rgba(255,255,255,0.15)" fontFamily={FONT}>1.0</text>
          <text x={CP.l + 1} y={CP.t + iH - 2} fontSize="5" fill="rgba(255,255,255,0.15)" fontFamily={FONT}>0</text>
          {/* all candidates as circles */}
          {pts.map((p, i) => (
            <circle
              key={i}
              cx={f1(CP.l + toCompr(p.length) * CIW)}
              cy={f1(CP.t + iH * (1 - p.similarity))}
              r="3"
              fill={MED}
            />
          ))}
          {/* active */}
          <circle cx={f1(activeCX)} cy={f1(activeCY)} r="5.5" fill="#fff" />
        </svg>
      </div>
    )
  }

  // ── 3. Token NLL heatmap + top chips ────────────────────────
  let tokNllEl = null
  if (hasTok) {
    const nlls = rawNlls.map(v => Math.max(0, v))
    const toks = rawToks
    const maxNll = Math.max(...nlls, 0.001)
    const meanNll = nlls.reduce((s, v) => s + v, 0) / nlls.length

    // Heatmap bar
    const HM_H = 14
    const bw = Math.max(1, CIW / nlls.length - 0.3)

    // Top-5 most uncertain tokens (chips)
    const indexed = nlls.map((v, i) => ({ v, i, tok: toks[i] }))
      .filter(x => x.tok && x.tok.trim())
      .sort((a, b) => b.v - a.v)
      .slice(0, 6)

    tokNllEl = (
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
          <span style={LABEL}>token nll</span>
          <span style={VAL}>avg {meanNll.toFixed(1)} · max {maxNll.toFixed(1)}</span>
        </div>
        {/* heatmap strip */}
        <svg viewBox={`0 0 ${CW} ${HM_H}`} style={{ width: '100%', display: 'block', marginBottom: 6 }}>
          {nlls.map((nll, i) => (
            <rect
              key={i}
              x={f1(CP.l + (i / nlls.length) * CIW)}
              y="0"
              width={f1(bw)}
              height={f1(HM_H)}
              fill={`rgba(255,255,255,${(0.06 + 0.88 * (nll / maxNll)).toFixed(3)})`}
              rx="0.5"
            />
          ))}
        </svg>
        {/* top uncertain token chips — dark = high NLL = model was surprised */}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '3px', marginBottom: 4 }}>
          {indexed.map(({ tok, v, i }) => {
            const intensity = v / maxNll
            const bg = `rgba(255,255,255,${(0.08 + 0.78 * intensity).toFixed(2)})`
            const fg = intensity > 0.55 ? '#000' : 'rgba(255,255,255,0.75)'
            return (
              <span key={i} style={{
                fontFamily: FONT, fontSize: '0.6rem', padding: '2px 5px',
                background: bg, color: fg, borderRadius: 2,
                letterSpacing: '0.02em', whiteSpace: 'nowrap',
              }}>
                {tok.replace(/^\s/, '·')}
              </span>
            )
          })}
        </div>
        <span style={{ ...LABEL, letterSpacing: '0.08em', fontSize: '0.52rem' }}>
          ↑ tokens the model found surprising
        </span>
      </div>
    )
  }

  // ── 4. Candidate stability bars ──────────────────────────────
  let stabilityEl = null
  if (hasPoints) {
    const sorted = [...pts].sort((a, b) => b.epsilon - a.epsilon)
    const DOT = 5    // dot diameter
    const GAP = 2.5  // gap between dots
    const N = sorted.length
    const rowW = N * (DOT + GAP) - GAP
    const startX = (CW - rowW) / 2

    stabilityEl = (
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
          <span style={LABEL}>stability</span>
          <span style={VAL}>{sorted.map(p => Math.round(p.stability * 100) + '%').join(' · ')}</span>
        </div>
        <svg viewBox={`0 0 ${CW} 18`} style={{ width: '100%', display: 'block' }}>
          {sorted.map((p, i) => {
            const cx = startX + i * (DOT + GAP) + DOT / 2
            const alpha = 0.15 + 0.75 * p.stability
            const isActive = Math.abs(p.similarity - similarity) === Math.min(...sorted.map(q => Math.abs(q.similarity - similarity)))
            return (
              <circle
                key={i}
                cx={f1(cx)} cy="9" r={f1(DOT / 2 + (isActive ? 1.5 : 0))}
                fill={isActive ? '#fff' : `rgba(255,255,255,${alpha.toFixed(2)})`}
              />
            )
          })}
          <text x={CP.l} y="17" fontSize="5.5" fill="rgba(255,255,255,0.18)" fontFamily={FONT}>compressed</text>
          <text x={CW - CP.r} y="17" textAnchor="end" fontSize="5.5" fill="rgba(255,255,255,0.18)" fontFamily={FONT}>explicit</text>
        </svg>
      </div>
    )
  }

  // ── 5. NLL Waveform (token surprise wave) ───────────────────
  let waveformEl = null
  if (hasTok) {
    const nlls = rawNlls.map(v => Math.max(0, v))
    const maxNll = Math.max(...nlls, 0.001)
    const H = 48
    const iH = H - CP.t - CP.b
    const bw = Math.max(0.8, (CIW / nlls.length) - 0.5)
    const meanNll = nlls.reduce((s, v) => s + v, 0) / nlls.length
    const meanY = CP.t + iH - (meanNll / maxNll) * iH

    waveformEl = (
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
          <span style={LABEL}>surprise wave</span>
          <span style={VAL}>{nlls.length} tokens</span>
        </div>
        <svg viewBox={`0 0 ${CW} ${H}`} style={{ width: '100%', display: 'block', overflow: 'visible' }}>
          {/* baseline */}
          <line x1={CP.l} y1={CP.t + iH} x2={CP.l + CIW} y2={CP.t + iH} stroke={DIM} strokeWidth="0.5" />
          {/* mean line */}
          <line x1={CP.l} y1={f1(meanY)} x2={CP.l + CIW} y2={f1(meanY)} stroke="rgba(255,255,255,0.15)" strokeWidth="0.75" strokeDasharray="2 2" />
          {/* bars */}
          {nlls.map((nll, i) => {
            const barH = (nll / maxNll) * iH
            const x = CP.l + (i / nlls.length) * CIW
            const alpha = 0.15 + 0.75 * (nll / maxNll)
            return (
              <rect
                key={i}
                x={f1(x)}
                y={f1(CP.t + iH - barH)}
                width={f1(bw)}
                height={f1(Math.max(0.5, barH))}
                fill={`rgba(255,255,255,${alpha.toFixed(2)})`}
                rx="0.3"
              />
            )
          })}
          {/* y-axis labels */}
          <text x={CP.l} y={CP.t + 5} fontSize="5.5" fill="rgba(255,255,255,0.2)" fontFamily={FONT}>{maxNll.toFixed(1)}</text>
          <text x={CP.l + CIW} y={H - 1} textAnchor="end" fontSize="5.5" fill="rgba(255,255,255,0.18)" fontFamily={FONT}>nll →</text>
        </svg>
      </div>
    )
  } else if (hasPoints) {
    // Fallback when no toknll: inter-candidate fit variability bars
    const H = 36
    const iH = H - CP.t - CP.b
    const sorted = [...pts].sort((a, b) => b.epsilon - a.epsilon)
    const fits = sorted.map(p => p.similarity)
    const maxFit = Math.max(...fits, 1)
    const bw = Math.max(2, CIW / fits.length - 1.5)

    waveformEl = (
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
          <span style={LABEL}>fit profile</span>
          <span style={VAL}>{fits.length} pts</span>
        </div>
        <svg viewBox={`0 0 ${CW} ${H}`} style={{ width: '100%', display: 'block' }}>
          <line x1={CP.l} y1={CP.t + iH} x2={CP.l + CIW} y2={CP.t + iH} stroke={DIM} strokeWidth="0.5" />
          {fits.map((f, i) => {
            const barH = (f / maxFit) * iH
            const x = CP.l + (i / fits.length) * CIW
            return (
              <rect key={i} x={f1(x)} y={f1(CP.t + iH - barH)} width={f1(bw)} height={f1(Math.max(0.5, barH))}
                fill={`rgba(255,255,255,${(0.25 + 0.55 * (f / maxFit)).toFixed(2)})`} rx="0.3" />
            )
          })}
        </svg>
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.1rem', width: `${CW}px`, maxWidth: '100%' }}>
      {lossCurveEl}
      {scatterEl}
      {tokNllEl}
      {waveformEl}
      {stabilityEl}
    </div>
  )
}

type BasinPoint = {
  x: number
  y: number
  z: number
  sx: number
  sy: number
}

const BASIN_GRID = 9

function basinZ(x: number, y: number, centerX: number, centerY: number, depth: number, tilt: number) {
  const dx = x - centerX
  const dy = y - centerY
  const r2 = dx * dx + dy * dy
  const crater = depth * Math.exp(-r2 * 2.35)
  const rim = 0.18 * Math.exp(-Math.pow(Math.sqrt(r2) - 0.88, 2) * 16)
  return 0.66 + rim + tilt * x - tilt * 0.65 * y - crater
}

function projectBasinPoint(x: number, y: number, z: number): BasinPoint {
  const sx = 150 + (x - y) * 68
  const sy = 116 + (x + y) * 28 - z * 52
  return { x, y, z, sx, sy }
}

function buildBasinRows(centerX: number, centerY: number, depth: number, tilt: number): BasinPoint[][] {
  return Array.from({ length: BASIN_GRID }, (_, row) =>
    Array.from({ length: BASIN_GRID }, (_, col) => {
      const x = -1 + (col / (BASIN_GRID - 1)) * 2
      const y = -1 + (row / (BASIN_GRID - 1)) * 2
      return projectBasinPoint(x, y, basinZ(x, y, centerX, centerY, depth, tilt))
    }),
  )
}

function LocalMinimumBasin({
  ariaLabel,
  epsilon,
  hint,
  label,
  length,
  pos,
  similarity,
}: {
  ariaLabel: string
  epsilon: number
  hint: string
  label: string
  length: number
  pos: number
  similarity: number
}) {
  const basinPos = clamp01(pos)
  const centerX = lerp(-0.18, 0.2, basinPos)
  const centerY = lerp(0.2, -0.16, basinPos)
  const depth = lerp(0.56, 1.08, similarity)
  const tilt = lerp(0.16, 0.04, basinPos)
  const rows = buildBasinRows(centerX, centerY, depth, tilt)
  const center = projectBasinPoint(
    centerX,
    centerY,
    basinZ(centerX, centerY, centerX, centerY, depth, tilt),
  )
  const sampleX = lerp(-0.72, centerX, basinPos)
  const sampleY = lerp(0.62, centerY, basinPos)
  const sample = projectBasinPoint(sampleX, sampleY, basinZ(sampleX, sampleY, centerX, centerY, depth, tilt))
  const ringR = lerp(14, 7, similarity)
  const confidence = Math.round(similarity * 100)
  const epsStr = epsilon >= 0.1 ? epsilon.toFixed(2) : epsilon.toFixed(3)
  const linePath = (pts: BasinPoint[]) =>
    pts.map((p, i) => `${i === 0 ? 'M' : 'L'} ${f1(p.sx)} ${f1(p.sy)}`).join(' ')
  const columns = Array.from({ length: BASIN_GRID }, (_, col) =>
    rows.map((row) => row[col]),
  )

  return (
    <>
      <dt style={{ color: 'var(--site-link)', gridColumn: '1 / -1' }}>
        {label}
      </dt>
      <dd
        style={{
          margin: 0,
          marginBottom: '0.35rem',
          paddingBottom: '0.65rem',
          borderBottom: '1px solid rgba(255,255,255,0.08)',
          gridColumn: '1 / -1',
          color: 'var(--site-text)',
        }}
      >
      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '1rem', marginBottom: 4 }}>
        <span style={VAL}>ε {epsStr} · {confidence}% fit</span>
      </div>
        <svg
          viewBox="0 0 300 178"
          role="img"
          aria-label={`${label}: ${ariaLabel}`}
        style={{ width: '100%', display: 'block', overflow: 'visible' }}
      >
        <line x1="150" y1="142" x2="258" y2="98" stroke={DIM} strokeWidth="0.8" />
        <line x1="150" y1="142" x2="50" y2="101" stroke={DIM} strokeWidth="0.8" />
        <line x1="150" y1="142" x2="150" y2="30" stroke={DIM} strokeWidth="0.8" />
        <text x="262" y="105" fontSize="8" fill="rgba(255,255,255,0.34)" fontFamily={FONT}>x</text>
        <text x="42" y="108" fontSize="8" fill="rgba(255,255,255,0.34)" fontFamily={FONT}>y</text>
        <text x="154" y="38" fontSize="8" fill="rgba(255,255,255,0.34)" fontFamily={FONT}>z</text>

        <path
          d={`M ${f1(sample.sx)} ${f1(sample.sy)} C ${f1(lerp(sample.sx, center.sx, 0.35))} ${f1(sample.sy - 22)}, ${f1(lerp(sample.sx, center.sx, 0.72))} ${f1(center.sy - 8)}, ${f1(center.sx)} ${f1(center.sy)}`}
          fill="none"
          stroke={`rgba(255,255,255,${(0.28 + similarity * 0.34).toFixed(2)})`}
          strokeWidth="1"
          strokeDasharray="3 4"
        />

        {[...rows, ...columns].map((pts, i) => (
          <path
            key={i}
            d={linePath(pts)}
            fill="none"
            stroke={`rgba(255,255,255,${(0.12 + similarity * 0.08).toFixed(2)})`}
            strokeWidth={i === Math.floor(BASIN_GRID / 2) || i === BASIN_GRID + Math.floor(BASIN_GRID / 2) ? 1.25 : 0.7}
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        ))}

        <circle cx={f1(sample.sx)} cy={f1(sample.sy)} r="3.5" fill="rgba(255,255,255,0.5)" />
        <circle cx={f1(center.sx)} cy={f1(center.sy)} r="5" fill="#fff" />
        <circle cx={f1(center.sx)} cy={f1(center.sy)} r={f1(ringR)} fill="none" stroke="rgba(255,255,255,0.2)" />
        <text x={f1(center.sx + 11)} y={f1(center.sy + 4)} fontSize="7" fill="rgba(255,255,255,0.42)" fontFamily={FONT}>min</text>
        <text x="8" y="170" fontSize="6.5" fill="rgba(255,255,255,0.28)" fontFamily={FONT}>{hint}</text>
        <text x="292" y="170" textAnchor="end" fontSize="6.5" fill="rgba(255,255,255,0.28)" fontFamily={FONT}>≈ {length}t</text>
      </svg>
      </dd>
    </>
  )
}

// ─────────────────────────────────────────────────────────────────────────────

// ── Backend health URLs ────────────────────────────────────────────────────
const HEALTH_MLX    = SEARCH_API_MLX.replace('/search', '/health')
const HEALTH_CUSTOM = SEARCH_API_CLAUDE.replace('/api/search', '/health')

export function AlephExplorer() {
  const [examples, setExamples] = useState<Target[]>(FALLBACK)
  const [current, setCurrent] = useState<Target>(FALLBACK[0])
  const [pos, setPos] = useState(0)
  const [oob, setOob] = useState<null | 'left' | 'right'>(null)
  const [launched, setLaunched] = useState(false)
  const [introLogoHover, setIntroLogoHover] = useState(false)
  const [headerLogoHover, setHeaderLogoHover] = useState(false)
  const [open, setOpen] = useState(false)
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const [view, setView] = useState<'input' | 'result'>('input')
  const [lang, setLang] = useState<Lang>('en')
  const [searchMode, setSearchMode] = useState<SearchMode>('local_mlx')
  const [dots, setDots] = useState(1)
  // Health status: null=unknown, true=online, false=offline
  const [health, setHealth] = useState<{ mlx: boolean | null; custom: boolean | null }>({ mlx: null, custom: null })
  // Progress tracking
  const [busySince, setBusySince] = useState<number | null>(null)
  const [elapsed, setElapsed] = useState(0)
  const searchAbortRef = useRef<AbortController | null>(null)
  const trackRef = useRef<HTMLDivElement>(null)
  const headingId = useId()
  const tr = STRINGS[lang]
  const exLabel = (k: string) => (lang === 'zh' ? EX_LABELS_ZH[k] ?? k : k)
  // the pitch is rebuilt per-language; everything else passes through
  const pt = current.key === 'pitch' ? PITCH[lang] : current

  useEffect(() => {
    if (!busy) {
      setDots(1)
      return
    }
    const id = setInterval(() => setDots((d) => (d % 3) + 1), 400)
    return () => clearInterval(id)
  }, [busy])

  // Elapsed-time tick: updates every 500ms while a live search is running
  useEffect(() => {
    if (!busy || busySince === null) { setElapsed(0); return }
    const id = setInterval(() => setElapsed(Date.now() - busySince), 500)
    return () => clearInterval(id)
  }, [busy, busySince])

  useEffect(() => {
    let on = true
    fetch(`/aleph-frontier.json?t=${Date.now()}`, { cache: 'no-store' })
      .then((r) => (r.ok ? r.json() : null))
      .then((j) => {
        if (on && Array.isArray(j) && j.length && j[0]) {
          setExamples(j as Target[])
          setCurrent(j[0] as Target)
          setPos(0)
          setOob(null)
        }
      })
      .catch(() => {})
    return () => {
      on = false
    }
  }, [])

  // Preload: ping both backends the moment the page loads.
  // Results drive status dots + auto-select the live mode.
  useEffect(() => {
    let alive = true
    const ping = (url: string) =>
      fetch(url, { signal: AbortSignal.timeout(3000) })
        .then((r) => r.ok)
        .catch(() => false)

    Promise.all([ping(HEALTH_MLX), ping(HEALTH_CUSTOM)]).then(([mlx, custom]) => {
      if (!alive) return
      setHealth({ mlx, custom })
      // Auto-switch to whichever backend is live (prefer mlx direct)
      if (mlx) setSearchMode('local_mlx')
      else if (custom) setSearchMode('claude_api')
    })

    return () => { alive = false }
  }, [])

  useEffect(() => {
    document.documentElement.lang = lang === 'zh' ? 'zh-Hans' : 'en'
  }, [lang])

  const reveal = pt.mode === 'reveal' && !!pt.script
  const segs = reveal
    ? (pt.script ?? '').split('\n').map((s) => s.trim()).filter(Boolean)
    : []
  const N = reveal ? Math.max(1, segs.length) : Math.max(1, pt.points.length)
  const v = reveal ? revealFrom(segs, pos) : sampleFrom(pt.points, pos)
  let oobView = oob && pt.key === 'pitch' ? PITCH_OOB[lang][oob] : null
  if (oob && !oobView && EXAMPLE_OOB[pt.key]) {
    const ex = EXAMPLE_OOB[pt.key]
    const last = pt.points[pt.points.length - 1]
    oobView =
      oob === 'left'
        ? {
            epsilon: 0.55,
            prompt: ex.seed,
            length: 12,
            similarity: 0.4,
            stability: 0.8,
          }
        : {
            epsilon: 0,
            prompt: (last?.prompt ?? '') + ex.tail,
            length: (last?.length ?? 0) + 80,
            similarity: 1,
            stability: 1,
          }
  }
  const vv = oobView ? ({ ...v, ...oobView } as typeof v) : v
  const eps = vv.epsilon >= 0.1 ? vv.epsilon.toFixed(2) : vv.epsilon.toFixed(3)


  // dashboard metrics
  const idLen = reveal
    ? 0
    : pt.points[pt.points.length - 1]?.length || 0
  const fullWords = reveal
    ? segs.join(' ').trim().split(/\s+/).filter(Boolean).length
    : 0
  const saved = reveal
    ? fullWords
      ? Math.max(0, 1 - vv.length / fullWords)
      : 0
    : idLen
      ? Math.max(0, 1 - vv.length / idLen)
      : 0
  const leak = reveal ? null : leakageScore(vv.prompt, targetOf(pt.points))
  const rank = reveal
    ? Math.min(N, Math.max(1, Math.ceil(clamp01(pos) * N)))
    : Math.round(clamp01(pos) * (N - 1)) + 1

  const pick = (t: Target) => {
    setErr('')
    setCurrent(t)
    setPos(0)
    setOob(null)
    setView('result')
  }

  const runSearch = useCallback(async () => {
    const q = text.trim()
    if (q.length < 8 || busy) return

    // Cancel any in-flight search from a previous call
    searchAbortRef.current?.abort()
    const abort = new AbortController()
    searchAbortRef.current = abort

    setBusy(true)
    setBusySince(Date.now())
    setElapsed(0)
    setErr('')

    try {
      // ── Fixture mode: instant, no network ─────────────────────
      if (searchMode === 'fixture') {
        const lower = q.toLowerCase()
        const match = examples.find(
          (e) => lower.includes(e.key) || lower.includes((e.label ?? '').toLowerCase()),
        ) ?? examples[Math.floor(Math.random() * examples.length)]
        if (match) { pick(match); return }
        setErr(STRINGS[lang].errNothing)
        return
      }

      // ── Live search: fire both backends simultaneously ─────────
      // Each helper resolves with a Target or rejects — never throws outside.
      // We use Promise.any so the first success wins and we abort the slower one.

      const tryMLX = (): Promise<Target> =>
        fetch(SEARCH_API_MLX, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text: q }),
          signal: abort.signal,
        }).then(async (r) => {
          if (!r.ok) throw new Error(`mlx:${r.status}`)
          const j = await r.json() as Record<string, unknown>
          if (!Array.isArray(j.points) || !(j.points as unknown[]).length)
            throw new Error('mlx:empty')
          return j as unknown as Target
        })

      const tryCustom = (): Promise<Target> =>
        fetch(SEARCH_API_CLAUDE, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ target_text: q, mode: 'local_mlx_search' }),
          signal: abort.signal,
        }).then(async (r) => {
          if (!r.ok) throw new Error(`custom:${r.status}`)
          const j = await r.json() as Record<string, unknown>
          if (!Array.isArray(j.candidates) || !(j.candidates as unknown[]).length)
            throw new Error('custom:empty')
          return alephRunToTarget(j, q)
        })

      // Both start simultaneously. Promise.any waits for the FIRST fulfillment.
      // Rejected promises are silently swallowed by Promise.any (no unhandled rejection).
      const target = await Promise.any([tryMLX(), tryCustom()])
      abort.abort() // cancel the slower request

      setCurrent(target)
      setPos(0)
      setOob(null)
      setView('result')
    } catch (e) {
      // AbortError = we cancelled ourselves (new search fired), ignore silently
      if ((e as Error)?.name === 'AbortError') return
      // AggregateError = Promise.any with all rejections = both backends failed
      setErr('backend offline — start python3 search/server.py, or use fixture mode')
    } finally {
      setBusy(false)
      setBusySince(null)
    }
  }, [text, busy, lang, searchMode, examples])

  const setFromClientX = useCallback((clientX: number) => {
    const el = trackRef.current
    if (!el) return
    const rect = el.getBoundingClientRect()
    if (rect.width === 0) return
    const raw = (clientX - rect.left) / rect.width
    if (raw < SLIDER_PAD) {
      setPos(0)
      setOob('left')
    } else if (raw > 1 - SLIDER_PAD) {
      setPos(1)
      setOob('right')
    } else {
      setOob(null)
      setPos(clamp01((raw - SLIDER_PAD) / (1 - 2 * SLIDER_PAD)))
    }
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
      if (oob === 'right') setOob(null)
      else if (oob === 'left') {
        /* already fully out of bound */
      } else if (pos <= 0) setOob('left')
      else setPos((p) => clamp01(p - fine))
    } else if (e.key === 'ArrowRight' || e.key === 'ArrowUp') {
      e.preventDefault()
      if (oob === 'left') setOob(null)
      else if (oob === 'right') {
        /* already fully out of bound */
      } else if (pos >= 1) setOob('right')
      else setPos((p) => clamp01(p + fine))
    } else if (e.key === 'Home') {
      e.preventDefault()
      setOob(null)
      setPos(0)
    } else if (e.key === 'End') {
      e.preventDefault()
      setOob(null)
      setPos(1)
    }
  }

  const muted = 'var(--site-link)'
  const ruleColor = 'var(--site-hr)'
  const atLeft = oob === 'left'
  const atRight = oob === 'right'

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
      <div
        style={{
          flex: 1,
          minHeight: 0,
          position: 'relative',
          display: 'flex',
          flexDirection: 'column',
          opacity: launched ? 1 : 0,
          transition: `opacity 1200ms ease ${CHROME_FADE_DELAY_MS}ms`,
          pointerEvents: launched ? undefined : 'none',
        }}
      >
      <header
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          zIndex: 30,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          gap: '1rem',
          pointerEvents: 'none',
        }}
      >
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: '1.5rem',
            pointerEvents: 'auto',
          }}
        >
          {/* Logo + wordmark row */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 'clamp(0.75rem, 2vw, 1.25rem)' }}>
            <button
              type="button"
              onClick={() => {
                setView('input')
                setOpen(false)
              }}
              onMouseEnter={() => setHeaderLogoHover(true)}
              onMouseLeave={() => setHeaderLogoHover(false)}
              onFocus={() => setHeaderLogoHover(true)}
              onBlur={() => setHeaderLogoHover(false)}
              aria-label={tr.backAria}
              title={tr.backTitle}
              style={{
                width: HEADER_LOGO_SIZE,
                height: HEADER_LOGO_SIZE,
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
                src={headerLogoHover ? '/horns.png' : '/aleph-logo.png'}
                alt="aleph"
                style={{
                  ...(headerLogoHover ? LOGO_HORNS_STYLE : LOGO_IMG_STYLE),
                  filter: headerLogoHover ? 'none' : 'brightness(0) invert(1)',
                }}
              />
            </button>
            <span
              aria-hidden
              style={{
                fontFamily: "'Avenir Next', 'Helvetica Neue', -apple-system, BlinkMacSystemFont, sans-serif",
                fontWeight: 700,
                letterSpacing: '-0.05em',
                fontSize: 'clamp(0.85rem, 1.8vw, 1.9rem)',
                lineHeight: 1,
                whiteSpace: 'nowrap',
                transform: 'translate(-1.18rem, -0.95rem)',
                transformOrigin: 'left top',
                color: 'var(--site-text)',
              }}
            >
              Aleph
            </span>
          </div>
          {/* Mini charts — always visible; header is overlay so input stays centered */}
          <div className="aleph-mini-charts">
            <MiniCharts
              pt={pt}
              pos={pos}
              epsilon={vv.epsilon}
              similarity={vv.similarity}
              length={vv.length}
              toknll={vv.toknll}
              toktext={vv.toktext}
            />
          </div>
        </div>

        <div
          style={{
            display: 'flex',
            alignItems: 'flex-start',
            gap: '1.25rem',
            pointerEvents: 'auto',
          }}
        >
          <button
            type="button"
            onClick={() => setLang((l) => (l === 'en' ? 'zh' : 'en'))}
            aria-label={tr.langSwitch}
            title={tr.langSwitch}
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
            <GlobeIcon />
            <span style={{ color: lang === 'en' ? 'var(--site-text)' : muted }}>
              EN
            </span>
            <span aria-hidden style={{ opacity: 0.4 }}>
              /
            </span>
            <span style={{ color: lang === 'zh' ? 'var(--site-text)' : muted }}>
              中
            </span>
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
            {tr.dashboard}
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
                  'clamp(18rem, 27vw, 26rem)',
                maxHeight: 'calc(100vh - 7.5rem)',
                overflowY: 'auto',
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
              <Row label={tr.promptLength}>
                {reveal ? `${v.length} ${tr.words}` : `≈ ${v.length} tokens`}
              </Row>
              <Row label={tr.targetFit}>{pct(v.similarity)}</Row>
              <Row label={tr.stability}>{reveal ? '—' : pct(v.stability)}</Row>
              <Row label={tr.compression}>
                {pct(saved)} {reveal ? tr.vsFullScript : tr.savedVsExplicit}
              </Row>
              <Row label={tr.leakage}>{leak === null ? '—' : pct(leak)}</Row>
              <Row label={tr.frontierRank}>
                {rank} / {N}
              </Row>
              <Row label={tr.modelTheta}>{pt.evalModel ?? tr.localQwen}</Row>
              <LocalMinimumBasin
                ariaLabel={tr.basinWireframe}
                epsilon={vv.epsilon}
                hint={tr.basinHint}
                label={tr.localMinimum}
                length={vv.length}
                pos={pos}
                similarity={vv.similarity}
              />
            </dl>
          )}
          </div>
        </div>
      </header>

      <main
        style={{
          flex: 1,
          minHeight: 0,
          width: '100%',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: view === 'input' ? 'center' : 'flex-start',
          textAlign: 'center',
          gap: '1.1rem',
          overflowY: view === 'result' ? 'auto' : 'hidden',
          paddingTop: view === 'result' ? 'clamp(6rem, 14vh, 10rem)' : 0,
          paddingBottom: view === 'result' ? '0.5rem' : 0,
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
            className="aleph-target-input"
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) runSearch()
            }}
            placeholder={tr.placeholder}
            spellCheck={false}
            style={{
              width: '100%',
              minHeight: 'clamp(11rem, 40vh, 20rem)',
              maxHeight: '52vh',
              resize: 'none',
              overflowY: 'auto',
              boxSizing: 'border-box',
              background: 'var(--site-card-bg)',
              border: '1px solid var(--site-code-border)',
              color: 'var(--site-text)',
              font: 'inherit',
              lineHeight: 1.6,
              textAlign: 'left',
              padding: '1rem 1.1rem',
              outline: 'none',
            }}
          />
          {/* Progress panel — visible while a live search is running */}
          {busy && searchMode !== 'fixture' && (() => {
            const words = text.trim().split(/\s+/).filter(Boolean).length
            const estMs = words < 30 ? 40_000 : words < 80 ? 65_000 : words < 150 ? 95_000 : 130_000
            const pct = Math.min(0.97, elapsed / estMs)
            const elapsedS = Math.floor(elapsed / 1000)
            const etaS = Math.max(0, Math.round((estMs - elapsed) / 1000))
            const stage =
              pct < 0.22 ? 'proposing candidate prompts' :
              pct < 0.50 ? 'evaluating output fit' :
              pct < 0.78 ? 'scoring & ranking' :
              'finalizing frontier'
            const fmtS = (s: number) => s >= 60 ? `${Math.floor(s/60)}m ${s%60}s` : `${s}s`
            return (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                {/* Progress bar */}
                <div style={{ height: '2px', background: 'var(--site-code-border)', borderRadius: 2, overflow: 'hidden' }}>
                  <div style={{
                    height: '100%',
                    background: 'var(--site-text)',
                    opacity: 0.6,
                    width: `${(pct * 100).toFixed(1)}%`,
                    transition: 'width 500ms linear',
                    borderRadius: 2,
                  }} />
                </div>
                {/* Status row */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.72rem', color: muted }}>
                  <span style={{ opacity: 0.7 }}>{stage}</span>
                  <span style={{ fontVariantNumeric: 'tabular-nums', opacity: 0.6 }}>
                    {fmtS(elapsedS)} elapsed · ~{fmtS(etaS)} left
                  </span>
                </div>
              </div>
            )
          })()}

          {/* Search mode selector */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
            <span style={{ opacity: 0.5, fontSize: '0.8rem' }}>mode:</span>
            {([
              { id: 'fixture'    as SearchMode, label: 'fixture',    dot: null            },
              { id: 'local_mlx'  as SearchMode, label: 'local mlx',  dot: health.mlx      },
              { id: 'claude_api' as SearchMode, label: 'custom api', dot: health.custom   },
            ]).map(({ id, label, dot }) => (
              <button
                key={id}
                type="button"
                onClick={() => setSearchMode(id)}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '0.3rem',
                  background: 'none',
                  border: 'none',
                  padding: 0,
                  font: 'inherit',
                  fontSize: '0.8rem',
                  cursor: 'pointer',
                  color: searchMode === id ? 'var(--site-text)' : muted,
                  textDecoration: searchMode === id ? 'underline' : 'none',
                  textUnderlineOffset: '3px',
                }}
              >
                {dot !== null && (
                  <span style={{
                    width: '5px', height: '5px', borderRadius: '50%', flexShrink: 0,
                    background: dot === null
                      ? 'rgba(255,255,255,0.2)'    // unknown — grey
                      : dot
                        ? 'rgba(100,220,120,0.85)' // online — green
                        : 'rgba(255,255,255,0.15)',  // offline — dim
                    display: 'inline-block',
                  }} />
                )}
                {label}
              </button>
            ))}
          </div>

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
              <span style={{ opacity: 0.7 }}>{tr.examples}&nbsp;</span>
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
                    {exLabel(t.key)}
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
              {busy ? tr.compressing : tr.compress}
            </button>
          </div>
        </div>
        ) : (
        <>
        {!reveal && !busy && vv.output && (
          <p
            style={{
              maxWidth: '52rem',
              width: '100%',
              margin: 0,
              color: muted,
              fontSize: '0.75rem',
              textAlign: 'left',
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
            }}
          >
            p · {vv.prompt}
          </p>
        )}

        <p
          style={{
            maxWidth: '52rem',
            margin: 0,
            overflowY: 'auto',
            maxHeight: '40vh',
            whiteSpace: 'pre-wrap',
            textAlign: 'left',
            fontSize: 'clamp(1.2rem, 1.8vw, 1.5rem)',
            lineHeight: 1.7,
            color: busy ? muted : 'var(--site-text)',
          }}
        >
          {busy
            ? `${tr.compressingLocal} ${'.'.repeat(dots)}`
            : vv.output ?? vv.prompt}
        </p>

        {!reveal &&
          !busy &&
          vv.toknll &&
          vv.toktext &&
          vv.toknll.length === vv.toktext.length &&
          vv.toknll.length > 0 &&
          (() => {
            const ns = vv.toknll
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
                  textAlign: 'left',
                  overflowY: 'auto',
                  maxHeight: '20vh',
                }}
              >
                {vv.toktext.map((tk, i) => (
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

      {view === 'result' && (
      <footer style={{ display: 'flex', flexDirection: 'column', gap: '1rem', flexShrink: 0 }}>
        <div
          ref={trackRef}
          role="slider"
          tabIndex={0}
          aria-label={tr.sliderAria}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={
            oob === 'left' ? 0 : oob === 'right' ? 100 : Math.round(pos * 100)
          }
          aria-valuetext={
            oob
              ? `${tr.oob} · ≈ ${vv.length} tokens`
              : reveal
                ? `${vv.length} ${tr.wordsShown}`
                : `ε ≈ ${eps}, ≈ ${vv.length} tokens`
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
              left: `${SLIDER_PAD * 100}%`,
              right: `${SLIDER_PAD * 100}%`,
              height: 1,
              background: ruleColor,
              transform: 'translateY(-50%)',
            }}
          />
          <span
            aria-hidden
            style={{
              position: 'absolute',
              top: '50%',
              left: 0,
              width: `${SLIDER_PAD * 100}%`,
              transform: 'translateY(-50%)',
              overflow: 'hidden',
              whiteSpace: 'nowrap',
              textAlign: 'right',
              paddingRight: 6,
              fontFamily: FONT,
              fontSize: '0.7rem',
              letterSpacing: '0.04em',
              userSelect: 'none',
              pointerEvents: 'none',
              color: atLeft ? 'var(--site-text)' : muted,
              opacity: atLeft ? 1 : 0.4,
              transition: 'color 150ms ease, opacity 150ms ease',
            }}
          >
            ////////////////
          </span>
          <span
            aria-hidden
            style={{
              position: 'absolute',
              top: '50%',
              right: 0,
              width: `${SLIDER_PAD * 100}%`,
              transform: 'translateY(-50%)',
              overflow: 'hidden',
              whiteSpace: 'nowrap',
              textAlign: 'left',
              paddingLeft: 6,
              fontFamily: FONT,
              fontSize: '0.7rem',
              letterSpacing: '0.04em',
              userSelect: 'none',
              pointerEvents: 'none',
              color: atRight ? 'var(--site-text)' : muted,
              opacity: atRight ? 1 : 0.4,
              transition: 'color 150ms ease, opacity 150ms ease',
            }}
          >
            ////////////////
          </span>
          {Array.from({ length: N }).map((_, i) => (
            <div
              key={i}
              aria-hidden
              style={{
                position: 'absolute',
                top: '50%',
                left: `${
                  (SLIDER_PAD +
                    (i / Math.max(1, N - 1)) * (1 - 2 * SLIDER_PAD)) *
                  100
                }%`,
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
              left:
                oob === 'left'
                  ? `${(SLIDER_PAD / 2) * 100}%`
                  : oob === 'right'
                    ? `${(1 - SLIDER_PAD / 2) * 100}%`
                    : `${(SLIDER_PAD + pos * (1 - 2 * SLIDER_PAD)) * 100}%`,
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
          <span>{tr.footLeft} · k(y|θ)</span>
          <span>{tr.footRight} · y itself</span>
        </div>
      </footer>
      )}
      </div>

      <button
        type="button"
        onClick={() => setLaunched(true)}
        onMouseEnter={() => setIntroLogoHover(true)}
        onMouseLeave={() => setIntroLogoHover(false)}
        onFocus={() => setIntroLogoHover(true)}
        onBlur={() => setIntroLogoHover(false)}
        aria-label={lang === 'zh' ? '进入 Aleph' : 'Enter Aleph'}
        title={lang === 'zh' ? '进入 Aleph' : 'Enter Aleph'}
        style={{
          position: 'fixed',
          top: launched ? 'clamp(1.25rem, 4vw, 2.5rem)' : '50%',
          left: launched ? 'clamp(1.25rem, 4vw, 2.5rem)' : '50%',
          transform: launched ? 'none' : 'translate(-50%, -50%)',
          width: launched ? HEADER_LOGO_SIZE : INTRO_HORNS_SIZE,
          height: launched ? HEADER_LOGO_SIZE : INTRO_HORNS_SIZE,
          zIndex: 20,
          background: 'none',
          border: 'none',
          padding: 0,
          margin: 0,
          lineHeight: 0,
          cursor: launched ? 'default' : 'pointer',
          opacity: launched ? 0 : 1,
          pointerEvents: launched ? 'none' : 'auto',
          transition:
            'top 1000ms ease, left 1000ms ease, transform 1000ms ease, opacity 450ms ease 950ms',
        }}
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={launched || introLogoHover ? '/aleph-logo.png' : '/horns.png'}
          alt="aleph"
          style={{
            ...(launched || introLogoHover ? LOGO_IMG_STYLE : LOGO_HORNS_STYLE),
            height: launched ? '100%' : 'auto',
            filter:
              launched || introLogoHover ? 'brightness(0) invert(1)' : 'none',
          }}
        />
      </button>
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
