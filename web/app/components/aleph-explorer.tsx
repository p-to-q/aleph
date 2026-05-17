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
  "Aleph. For any output, the shortest prompt that makes a fixed model regenerate it — an upper bound on the shortest. Start from the agent: its only lever on a frozen model is the prompt, and the only thing it spends is tokens. So the thing every agent actually wants is the smallest seed that unfolds into what it is after — make something an agent wants, and that is the thing.",
  "A prompt is a parameter: training fixes the data and tunes the weights; Aleph fixes the weights and tunes the prompt. Every output y has a shortest-prompt length at a distortion ε — the fewest tokens that make a fixed model θ reproduce y. Push ε toward zero and that length approaches K(y|θ): y's description length under the model, the smallest seed θ can unfold back into y.",
  "The left end of the axis is that limit — extreme compression, where the model's own knowledge does the work; the right end is the identity prompt, y pasted in verbatim. Between them is a real rate–distortion curve: spend more prompt, buy more fidelity.",
  "Why it matters: it is a hard, comparable measure of how much a model already knows — which is the same as how little an agent has to say to get what it wants. It makes “compression is intelligence” operational, measured backwards: not how well a model compresses data into its weights, but how far a frozen model can re-compress any output back out.",
  "The demo is real: a fixed local Qwen3 on this machine is θ; the same model proposes its own compressed prompts; distortion is embedding distance; the curve is the monotone best-known frontier. Example: a 24-token prompt that merely names the Gettysburg Address makes the model regenerate Lincoln almost exactly — distortion two thousandths — because the text already lives in θ. We never claim the minimum: K(y|θ) is uncomputable, so Aleph reports an upper bound — “we haven't found shorter,” not “none exists.”",
  "And it turns prompt engineering into a curve instead of folklore: you pick your point on the frontier — how short a prompt, for how much fidelity. Which is the trick you are watching right now: this explanation is the output y, and the slider is Aleph expanding its own pitch from one compressed line into the full talk. The medium is the message — you did not need me to speak; you needed the right seed. That smallest seed is the thing every agent wants, and Aleph is how you find it.",
].join('\n\n')

const PITCH_SCRIPT_ZH = [
  'Aleph:对任意 output,那个能让固定模型重新生成它的最短 prompt —— 一个关于“最短”的上界。',
  '从 agent 说起:它对一个冻结模型唯一的杠杆就是 prompt,它唯一花掉的就是 token。',
  '所以每个 agent 真正想要的,是那颗能展开成它所求之物的最小种子 —— make something an agent wants,要做的就是这个。',
  'Prompt 是一种参数:训练固定数据、调权重;Aleph 固定权重、调 prompt。',
  '每个 output y 在失真 ε 下都有一个最短 prompt 长度 —— 让固定模型 θ 复现 y 所需的最少 token 数。',
  '让 ε 趋近于零,这个长度就逼近 K(y|θ):y 在该模型下的描述长度,θ 能展开回 y 的最小种子。',
  '轴的左端就是这个极限 —— 极限压缩,由模型自身的知识做功;右端是自指 prompt,把 y 逐字粘进去。',
  '两端之间是一条真实的 rate–distortion 曲线:prompt 花得越多,买到的保真度越高。',
  '它为什么重要:这是一个硬的、可比较的度量,衡量模型已经知道多少 —— 也就是一个 agent 要拿到它想要的东西,最少得说多少。',
  '它把“compression is intelligence”变得可操作,而且是反过来测:不是模型把数据压进权重压得多好,而是一个冻结模型还能把任意 output 再压出来到多短。',
  '这个 demo 是真的:这台机器上一个固定的本地 Qwen3 就是 θ;同一个模型提出自己的压缩 prompt;失真是 embedding 距离;曲线是单调的已知最优 frontier。',
  '例子:一个 24-token 的 prompt,只要点出 Gettysburg Address 的名字,就让模型几乎逐字重生林肯的演讲 —— 失真两千分之一 —— 因为那段文本本来就活在 θ 里。',
  '我们从不声称这是最小值:K(y|θ) 不可计算,所以 Aleph 给的是一个上界 —— “我们还没找到更短的”,而不是“不存在更短的”。',
  '它还把 prompt engineering 从玄学变成一条曲线:你在 frontier 上挑自己的点 —— 多短的 prompt,换多少保真度。',
  '而这正是你此刻正在看的把戏:这段解释就是 output y,滑条就是 Aleph 把自己的宣讲从一行压缩句展开成完整演讲。',
  '媒介即讯息 —— 你不需要我开口;你需要的是那颗对的种子。那颗最小的种子,正是每个 agent 想要的,而 Aleph 就是找到它的方法。',
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
    "Aleph. For any output, the shortest prompt that makes a fixed model regenerate it — an upper bound on the shortest. A prompt is the only lever an agent has on a frozen model, and tokens are all it spends, so the thing every agent actually wants is the smallest seed that unfolds into what it is after. Make something an agent wants — Aleph is the instrument that finds that seed.",
    "Aleph. A prompt is a parameter: training fixes the data and tunes the weights; Aleph fixes the weights and tunes the prompt. So for any output y there is a shortest-prompt length at a distortion ε — the fewest tokens that make a fixed model θ reproduce y — and as ε goes to zero that length approaches K(y|θ), the smallest seed θ can unfold back into y. That number is exactly what an agent's token budget runs into, so an agent wants it measured, not guessed. Make something an agent wants: Aleph measures it.",
    "Aleph. A prompt is a parameter; every output has a shortest-prompt length at a distortion ε that approaches K(y|θ) as ε goes to zero. Picture the axis: on the left, extreme compression, where the model's own knowledge does the work; on the right, the identity prompt, the output pasted in verbatim; and between them a real rate–distortion curve — spend more prompt, buy more fidelity. That curve is a hard, comparable measure of how much a model already knows, which is the same as how little an agent has to say to get what it wants. Make something an agent wants, and the curve is the thing: the price, in tokens, of every output.",
    "Aleph. A prompt is a parameter; for any output there is a shortest-prompt length at ε approaching K(y|θ); the curve runs from extreme compression on the left to the verbatim identity prompt on the right. It makes “compression is intelligence” operational, measured backwards — not how well a model compresses data into its weights, but how far a frozen model can re-compress any output an agent wants back out. The demo is real: a fixed local Qwen3 is θ, the same model proposes its own compressed prompts, distortion is embedding distance, the curve is the monotone best-known frontier. And it stays honest — K(y|θ) is uncomputable, so Aleph reports an upper bound, “we haven't found shorter,” never “none exists.” For an agent that lives on a token budget this is the instrument it wants: prompt engineering as a curve, not folklore. Make something an agent wants.",
  ]
  const zh = [
    'Aleph:对任意一段 output,找出能让一个固定模型把它重新生成出来的最短 prompt。它把“要拿到想要的东西、最少得说多少话”变成一条可测的曲线 —— 也就是一个 agent 真正想要的那颗最小种子。',
    'Aleph。Prompt 是一种参数:训练时固定数据、优化权重;Aleph 反过来 —— 固定权重、优化 prompt。于是每段 output y 在允许失真 ε 下,都有一个最短 prompt 长度:让固定模型 θ 复现 y 所需的最少 token 数;当 ε 趋近于零,这个长度逼近 K(y|θ),也就是 θ 能展开回 y 的那颗最小种子。',
    'Aleph。把 prompt 当参数,每段 output 都有一个失真 ε 下、ε 趋近于零时逼近 K(y|θ) 的最短 prompt 长度。想象一条轴:左端是极限压缩,几个 token 的种子靠模型自身的知识展开;右端是自指 prompt,把 output 逐字粘进去;两端之间,是一条真实的 rate–distortion 曲线 —— prompt 花得越多,买到的保真度越高。所以它是一把硬的、可横向比较的尺:衡量一个模型已经知道多少,等价于一个 agent 要拿到它想要的东西、最少得说多少。',
    'Aleph。Prompt 是参数;对任意 output 都有 ε 下、逼近 K(y|θ) 的最短 prompt;曲线从左端的极限压缩一路走到右端逐字的自指 prompt。它把“compression is intelligence”变得可操作,而且是反过来测 —— 不是看模型把训练数据压进权重压得多好,而是看一个已经冻结的模型,还能把任意一段你想要的 output 再压回到多短。这个 demo 是真的:这台机器上一个固定的本地 Qwen3 就是 θ,同一个模型提出自己的压缩 prompt,失真用 embedding 距离量,曲线取单调的已知最优 frontier。它也很诚实:K(y|θ) 不可计算,所以 Aleph 只报告一个上界 —— 说的是“我们还没找到更短的”,绝不说“不存在更短的”。对一个活在 token 预算里的 agent,这正是它想要的仪器:prompt engineering 从此是一条可测的曲线,而不是玄学。',
  ]
  const prompts = lang === 'zh' ? zh : en
  const meta = [
    { epsilon: 0.46, length: 44, similarity: 0.54, stability: 0.85 },
    { epsilon: 0.31, length: 92, similarity: 0.69, stability: 0.88 },
    { epsilon: 0.19, length: 150, similarity: 0.81, stability: 0.92 },
    { epsilon: 0.09, length: 220, similarity: 0.91, stability: 0.97 },
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

const FALLBACK: Target[] = [
  PITCH.en,
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
    placeholder:
      'paste any text — long is fine — and Aleph searches a short prompt that regenerates it · ⌘↵ to compress',
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
    placeholder:
      '粘贴任意文本 —— 长一点也没关系 —— Aleph 会搜索一个能重新生成它的短 prompt · ⌘↵ 压缩',
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

export function AlephExplorer() {
  const [examples, setExamples] = useState<Target[]>(FALLBACK)
  const [current, setCurrent] = useState<Target>(FALLBACK[0])
  const [pos, setPos] = useState(0)
  const [oob, setOob] = useState<null | 'left' | 'right'>(null)
  const [launched, setLaunched] = useState(false)
  const [open, setOpen] = useState(false)
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const [view, setView] = useState<'input' | 'result'>('input')
  const [lang, setLang] = useState<Lang>('en')
  const [dots, setDots] = useState(1)
  const trackRef = useRef<HTMLDivElement>(null)
  const headingId = useId()
  const [typed, setTyped] = useState('')
  const outRef = useRef<HTMLParagraphElement>(null)
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

  // stream the shown content one character at a time on each node switch
  const shown = busy ? null : oneSentencePerLine(vv.output ?? vv.prompt)
  useEffect(() => {
    if (shown == null) return
    setTyped('')
    let i = 0
    const step = Math.min(8, Math.max(1, Math.round(shown.length / 180)))
    const id = setInterval(() => {
      i += step
      if (i >= shown.length) {
        setTyped(shown)
        clearInterval(id)
      } else {
        setTyped(shown.slice(0, i))
      }
    }, 16)
    return () => clearInterval(id)
  }, [shown])
  useEffect(() => {
    const el = outRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [typed])

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
        setOob(null)
      } else {
        setErr(j?.error || STRINGS[lang].errNothing)
        setView('input')
      }
    } catch {
      setErr(STRINGS[lang].errOffline)
      setView('input')
    } finally {
      setBusy(false)
    }
  }, [text, busy, lang])

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
          display: 'flex',
          flexDirection: 'column',
          opacity: launched ? 1 : 0,
          transition: 'opacity 1100ms ease 450ms',
          pointerEvents: launched ? undefined : 'none',
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
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 'clamp(0.75rem, 2vw, 1.25rem)',
          }}
        >
        <button
          type="button"
          onClick={() => setView('input')}
          aria-label={tr.backAria}
          title={tr.backTitle}
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
          <span
            aria-hidden
            style={{
              fontFamily:
                "'Avenir Next', 'Helvetica Neue', -apple-system, BlinkMacSystemFont, sans-serif",
              fontWeight: 700,
              letterSpacing: '-0.05em',
              textTransform: 'none',
              fontSize: 'clamp(1.15rem, 2.8vw, 2.9rem)',
              lineHeight: 1,
              whiteSpace: 'nowrap',
              transform: 'translateY(-0.58rem)',
              color: 'var(--site-text)',
            }}
          >
            Aleph
          </span>
        </div>

        <div
          style={{ display: 'flex', alignItems: 'flex-start', gap: '1.25rem' }}
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
            </dl>
          )}
          </div>
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
            placeholder={tr.placeholder}
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
          ref={outRef}
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
            : typed}
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

      <footer style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
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
      </div>

      <button
        type="button"
        onClick={() => setLaunched(true)}
        aria-label={lang === 'zh' ? '进入 Aleph' : 'Enter Aleph'}
        title={lang === 'zh' ? '进入 Aleph' : 'Enter Aleph'}
        style={{
          position: 'fixed',
          top: launched ? 'clamp(1.25rem, 4vw, 2.5rem)' : '50%',
          left: launched ? 'clamp(1.25rem, 4vw, 2.5rem)' : '50%',
          transform: launched ? 'none' : 'translate(-50%, -50%)',
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
            'top 1000ms ease, left 1000ms ease, transform 1000ms ease, opacity 500ms ease 650ms',
        }}
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src="/aleph-logo.png"
          alt="aleph"
          style={{
            height: launched
              ? 'clamp(3.5rem, 5.5vw, 5.25rem)'
              : 'clamp(7rem, 26vw, 14rem)',
            width: 'auto',
            display: 'block',
            filter: 'brightness(0) invert(1)',
            transition: 'height 1000ms ease',
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
