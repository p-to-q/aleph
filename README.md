# Aleph

> **For any output, find a high-quality short prompt that regenerates it.**

给定一个目标 output 和一个固定的模型,Aleph 寻找能生成它的**一个高质量的短 prompt** —— 一个尽量逼近这个 output 在该模型下的**阿莱夫**的候选。

> 真正的"最短"无法证明:Kolmogorov 复杂度不可计算,prompt 空间是巨大的离散组合空间。Aleph 给出的是 **Pareto frontier 上的一个好解**,不是数学意义上的最小值。

## 核心洞见 — Prompt 是一种参数

| | 传统训练 | Aleph |
| --- | --- | --- |
| 固定 | 输入、目标 | **模型权重、目标 output** |
| 优化 | 模型权重 θ | **输入 prompt p** |
| 目标 | minimize loss | **逼近 minimize \|p\|, s.t. d(f_θ(p), y) ≤ ε** |

Backpropagation 在权重空间里找近似最优权重;Aleph 在 prompt 空间里找近似最短 prompt。形式对偶 —— 但 prompt 空间是离散 token 序列,两边都是启发式搜索,只有候选解、没有可证明的最优解。

## 数学对象

对目标 output `y` 和模型 `θ`,理论最优长度 `L*(ε) = min{|p| : d(f_θ(p), y) ≤ ε}`。当 `ε → 0`,`L*(0)` 就是 `y` 在 `θ` 下的 Kolmogorov 复杂度 `K(y|θ)` —— 不可计算的下界。Aleph 实际报告 **`L̂(ε)`**:搜索找到的当前最佳已知上界。术语见 [`docs/glossary.md`](docs/glossary.md)。

## 呈现形式

致敬 [getcoleman.com](https://getcoleman.com/) —— 整个站点是一个可拖动滑条,用户在曲线上走一遍:

```text
极限压缩 ←━━━━━━━●━━━━━━━→ 显式展开
   K(y|θ)              y itself
```

拖动时实时显示当前点的 prompt / 长度 / 相似度 / 稳定性 / 压缩率。Coleman 的滑条是审美维度,Aleph 的是**信息论维度上的真实曲线**。

## 技术栈

```text
Qwen3-8B-4bit + MLX + FastAPI + React
```

跑在 M4 Max 上的黑客松版本。

## 非目标

显式**不做**,留给 v2:Qwen3-32B、Llama 70B、full fine-tuning、完整梯度搜索、跨模型迁移、复杂数据库。详见 [`docs/project-brief.md`](docs/project-brief.md)。

## 文档

| 文件 | 用途 |
| --- | --- |
| [`docs/project-brief.md`](docs/project-brief.md) | scope、status、公共表面、非目标、receipt standard |
| [`docs/glossary.md`](docs/glossary.md) | Aleph 的术语(L\*(ε)、K(y\|θ)、阿莱夫、自指 prompt …) |
| [`docs/engineering-discipline.md`](docs/engineering-discipline.md) | 协作纪律 |
| [`docs/index.md`](docs/index.md) | 文档索引 |
| [`LICENSE`](LICENSE) | Apache-2.0 |

## Repository scaffolding

This repository was seeded from a p-to-q **repo-template** **Seed**. Aleph is routed at the **micro** profile —— 最小流程,适配单 artifact 的短周期黑客松实验。其余 profile(**standard**、**strict**、**research-strict**)与完整路由矩阵保留在 [`docs/router.md`](docs/router.md) 和 [`docs/project-scale.md`](docs/project-scale.md) 中,作为脚手架而非 active 流程。模板自检暂经 `npm run lint` 保留,待 Aleph 有自己的代码级检查(pytest / ruff / eslint)后替换。

```bash
npm run lint
```

### Sample

```text
Profile: micro
Status: experimental (hackathon, M4 Max)
Stack: Qwen3-8B-4bit + MLX + FastAPI + React
Public surface: 可拖动的 L̂(ε) 滑条 Web UI
Receipt: 固定预算下测得的 L̂(ε) 曲线 + 现场 demo
```
