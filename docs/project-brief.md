# Project Brief — Aleph

> **For any output, find a high-quality short prompt that regenerates it.**

## One-line purpose

给定一个目标 output `y` 和一个固定的模型 `θ`,Aleph 寻找能生成它的**一个高质量的短 prompt** —— 一个尽量逼近 `y` 在该模型下的**阿莱夫**的候选。它给出的是 prompt rate-distortion 曲线 Pareto frontier 上的一个好解,**不是**数学意义上可证明的最小值。

面向:做 prompt engineering、模型能力度量、"compression is intelligence" 实证的人。

## Profile

`micro` —— 一个 artifact、一个 demo、一个短周期实验(M4 Max 上的黑客松版本)。其余 `standard` / `strict` / `research-strict` 仅作为模板脚手架保留,见 [`router.md`](router.md) 与 [`project-scale.md`](project-scale.md)。

## Status

`experimental` —— 黑客松构建,接口与曲线形态都可能变。

## Public surfaces

- 可拖动的滑条 Web UI:用户在 L̂(ε) 曲线上从「极限压缩 `K(y|θ)`」走到「显式展开 `y` 本身」。
- FastAPI 端点:给定目标 output 与失真点,返回**当前 prompt / 长度 / 相似度 / 稳定性 / 压缩率**。

## Experimental surfaces

- 产出 L̂(ε) 的搜索 / 优化过程本身(启发式,预算敏感,不保证可复现到 token 级)。
- "模型越大,最短 prompt 是否越短?" 这类跨尺寸对比实验(Qwen3 尺寸阶梯)。

## Non-goals

显式**不做**,留给 v2:

- Qwen3-32B、Llama 70B 等更大模型;
- full fine-tuning、完整梯度搜索;
- 跨模型迁移;
- 复杂数据库 / 持久化层。

认识论上的非目标:**不声称**找到了可证明的最短 prompt。`L*(ε)` 含 Kolmogorov 复杂度,一般不可计算;Aleph 只报告**当前最佳已知上界 `L̂(ε)`** —— "还没找到更短的",不是"不存在更短的"。

## Receipt standard

什么算证据:

- 在**固定搜索预算**下产出的一条 L̂(ε) 曲线 —— 每个 ε 点带 prompt / `|p|` / 相似度 / 稳定性 / 压缩率;
- 可现场操作的滑条 demo;
- 同一预算下的横向模型对比表(用于"再压缩能力"的相对度量)。

## Sample

```text
Profile: micro
Status: experimental (hackathon, M4 Max)
Stack: Qwen3-8B-4bit + MLX + FastAPI + React
Public surface: 可拖动的 L̂(ε) 滑条 Web UI
Receipt: 固定预算下测得的 L̂(ε) 曲线 + 现场 demo
```
