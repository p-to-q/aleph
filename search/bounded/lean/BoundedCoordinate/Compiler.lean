import BoundedCoordinate.FiniteTheory

/-!
# Target-independent finite coordinate compilers

A compiler is one coordinate-only function reused for every declared target.
The predicate below charges an explicit cost overhead and an explicit
targetwise residual slack. It also requires every source member to map into
the declared destination list. Nothing here asserts that arbitrary rendering,
tokenization, or natural-language transformations satisfy these obligations.
-/

namespace BoundedCoordinate.Compiler

open BoundedCoordinate.FiniteTheory

/-- Exact finite obligations for a target-independent coordinate compiler. -/
def CompilerBound
    (source : List α)
    (destination : List β)
    (targets : List τ)
    (compile : α → β)
    (sourceCost : α → Nat)
    (destinationCost : β → Nat)
    (sourceResidual : α → τ → Nat)
    (destinationResidual : β → τ → Nat)
    (costOverhead residualSlack : Nat) : Prop :=
  (∀ item ∈ source, compile item ∈ destination) ∧
  (∀ item ∈ source,
    destinationCost (compile item) ≤ sourceCost item + costOverhead) ∧
  (∀ item ∈ source, ∀ target ∈ targets,
    destinationResidual (compile item) target ≤
      sourceResidual item target + residualSlack)

/-- Structure- and threshold-curve bounds induced in one compiler direction. -/
def DirectionalBounds
    (source : List α)
    (destination : List β)
    (targets : List τ)
    (sourceCost : α → Nat)
    (destinationCost : β → Nat)
    (sourceResidual : α → τ → Nat)
    (destinationResidual : β → τ → Nat)
    (costOverhead residualSlack : Nat) : Prop :=
  (∀ target ∈ targets, ∀ budget residualBound,
    infLe
        (structureCurve source sourceCost (fun item => sourceResidual item target) budget)
        (some residualBound) →
      infLe
        (structureCurve destination destinationCost
          (fun item => destinationResidual item target)
          (budget + costOverhead))
        (some (residualBound + residualSlack))) ∧
  (∀ target ∈ targets, ∀ residualBound budget,
    infLe
        (threshold source sourceCost (fun item => sourceResidual item target)
          residualBound)
        (some budget) →
      infLe
        (threshold destination destinationCost
          (fun item => destinationResidual item target)
          (residualBound + residualSlack))
        (some (budget + costOverhead)))

private theorem minInf_le_finite_iff
    (left right : InfNat)
    (bound : Nat) :
    infLe (minInf left right) (some bound) ↔
      infLe left (some bound) ∨ infLe right (some bound) := by
  cases left <;> cases right <;> simp [minInf, infLe]
  rename_i leftValue rightValue
  rcases Nat.le_total leftValue rightValue with hOrder | hOrder
  · rw [Nat.min_eq_left hOrder]
    omega
  · rw [Nat.min_eq_right hOrder]
    omega

private theorem restrictedMin_le_finite_iff
    (domain : List α)
    (eligible : α → Bool)
    (value : α → Nat)
    (bound : Nat) :
    infLe (restrictedMin domain eligible value) (some bound) ↔
      ∃ item ∈ domain, eligible item = true ∧ value item ≤ bound := by
  induction domain with
  | nil => simp [restrictedMin, infLe]
  | cons head tail ih =>
      change
        infLe
            (if eligible head then
              minInf (some (value head)) (restrictedMin tail eligible value)
            else restrictedMin tail eligible value)
            (some bound) ↔
          ∃ item ∈ head :: tail, eligible item = true ∧ value item ≤ bound
      cases hEligible : eligible head with
      | false =>
          simp only [Bool.false_eq_true, ite_false, List.mem_cons]
          simpa [hEligible] using ih
      | true =>
          simp only [ite_true, minInf_le_finite_iff, ih, List.mem_cons]
          simp [infLe, hEligible]

private theorem structure_le_finite_iff
    (domain : List α)
    (cost residual : α → Nat)
    (budget residualBound : Nat) :
    infLe (structureCurve domain cost residual budget) (some residualBound) ↔
      ∃ item ∈ domain, cost item ≤ budget ∧ residual item ≤ residualBound := by
  simpa [structureCurve] using
    restrictedMin_le_finite_iff domain
      (fun item => decide (cost item ≤ budget)) residual residualBound

private theorem threshold_le_finite_iff
    (domain : List α)
    (cost residual : α → Nat)
    (residualBound budget : Nat) :
    infLe (threshold domain cost residual residualBound) (some budget) ↔
      ∃ item ∈ domain, residual item ≤ residualBound ∧ cost item ≤ budget := by
  simpa [threshold] using
    restrictedMin_le_finite_iff domain
      (fun item => decide (residual item ≤ residualBound)) cost budget

/--
FC-01: a source witness transfers to the compiled coordinate with exactly the
declared additive cost overhead and targetwise residual slack.
-/
theorem compiler_witness_transfer
    (source : List α)
    (destination : List β)
    (targets : List τ)
    (compile : α → β)
    (sourceCost : α → Nat)
    (destinationCost : β → Nat)
    (sourceResidual : α → τ → Nat)
    (destinationResidual : β → τ → Nat)
    (costOverhead residualSlack : Nat)
    (hCompiler : CompilerBound source destination targets compile
      sourceCost destinationCost sourceResidual destinationResidual
      costOverhead residualSlack)
    {item : α}
    {target : τ}
    {budget residualBound : Nat}
    (hItem : item ∈ source)
    (hTarget : target ∈ targets)
    (hCost : sourceCost item ≤ budget)
    (hResidual : sourceResidual item target ≤ residualBound) :
    ∃ compiled ∈ destination,
      destinationCost compiled ≤ budget + costOverhead ∧
      destinationResidual compiled target ≤ residualBound + residualSlack := by
  refine ⟨compile item, hCompiler.1 item hItem, ?_, ?_⟩
  · have hBound := hCompiler.2.1 item hItem
    omega
  · have hBound := hCompiler.2.2 item hItem target hTarget
    omega

/--
FC-02: compiler witness transfer induces both finite structureCurve-curve and
threshold-curve transfer. Each implication has an explicit finite right-hand
bound; when the source feasible set is empty, its premise is false because the
source value is +infinity.
-/
theorem compiler_structure_threshold_transfer
    (source : List α)
    (destination : List β)
    (targets : List τ)
    (compile : α → β)
    (sourceCost : α → Nat)
    (destinationCost : β → Nat)
    (sourceResidual : α → τ → Nat)
    (destinationResidual : β → τ → Nat)
    (costOverhead residualSlack : Nat)
    (hCompiler : CompilerBound source destination targets compile
      sourceCost destinationCost sourceResidual destinationResidual
      costOverhead residualSlack) :
    DirectionalBounds source destination targets sourceCost destinationCost
      sourceResidual destinationResidual costOverhead residualSlack := by
  unfold DirectionalBounds
  constructor
  · intro target hTarget budget residualBound hSource
    rw [structure_le_finite_iff] at hSource ⊢
    obtain ⟨item, hItem, hCost, hResidual⟩ := hSource
    obtain ⟨compiled, hCompiled, hCompiledCost, hCompiledResidual⟩ :=
      compiler_witness_transfer source destination targets compile
        sourceCost destinationCost sourceResidual destinationResidual
        costOverhead residualSlack hCompiler hItem hTarget hCost hResidual
    exact ⟨compiled, hCompiled, hCompiledCost, hCompiledResidual⟩
  · intro target hTarget residualBound budget hSource
    rw [threshold_le_finite_iff] at hSource ⊢
    obtain ⟨item, hItem, hResidual, hCost⟩ := hSource
    obtain ⟨compiled, hCompiled, hCompiledCost, hCompiledResidual⟩ :=
      compiler_witness_transfer source destination targets compile
        sourceCost destinationCost sourceResidual destinationResidual
        costOverhead residualSlack hCompiler hItem hTarget hCost hResidual
    exact ⟨compiled, hCompiled, hCompiledResidual, hCompiledCost⟩

/--
FC-03: composing two target-independent compilers adds their declared cost
overheads and residual slacks.
-/
theorem compiler_composition
    (source : List α)
    (middle : List β)
    (destination : List γ)
    (targets : List τ)
    (first : α → β)
    (second : β → γ)
    (sourceCost : α → Nat)
    (middleCost : β → Nat)
    (destinationCost : γ → Nat)
    (sourceResidual : α → τ → Nat)
    (middleResidual : β → τ → Nat)
    (destinationResidual : γ → τ → Nat)
    (firstCostOverhead firstResidualSlack : Nat)
    (secondCostOverhead secondResidualSlack : Nat)
    (hFirst : CompilerBound source middle targets first
      sourceCost middleCost sourceResidual middleResidual
      firstCostOverhead firstResidualSlack)
    (hSecond : CompilerBound middle destination targets second
      middleCost destinationCost middleResidual destinationResidual
      secondCostOverhead secondResidualSlack) :
    CompilerBound source destination targets (fun item => second (first item))
      sourceCost destinationCost sourceResidual destinationResidual
      (firstCostOverhead + secondCostOverhead)
      (firstResidualSlack + secondResidualSlack) := by
  refine ⟨?_, ?_, ?_⟩
  · intro item hItem
    exact hSecond.1 (first item) (hFirst.1 item hItem)
  · intro item hItem
    have hFirstCost := hFirst.2.1 item hItem
    have hSecondCost := hSecond.2.1 (first item) (hFirst.1 item hItem)
    change destinationCost (second (first item)) ≤
      sourceCost item + (firstCostOverhead + secondCostOverhead)
    omega
  · intro item hItem target hTarget
    have hFirstResidual := hFirst.2.2 item hItem target hTarget
    have hSecondResidual :=
      hSecond.2.2 (first item) (hFirst.1 item hItem) target hTarget
    change destinationResidual (second (first item)) target ≤
      sourceResidual item target + (firstResidualSlack + secondResidualSlack)
    omega

/--
FC-04: compilers in both directions give their general directional bounds. If
both residual slacks are zero, the two threshold curves additionally obey the
same-threshold sandwich up to their separately declared cost overheads. No
same-threshold conclusion is made for a compiler with positive residual slack.
-/
theorem zero_slack_threshold_sandwich
    (source : List α)
    (destination : List β)
    (targets : List τ)
    (forward : α → β)
    (reverse : β → α)
    (sourceCost : α → Nat)
    (destinationCost : β → Nat)
    (sourceResidual : α → τ → Nat)
    (destinationResidual : β → τ → Nat)
    (forwardCostOverhead forwardResidualSlack : Nat)
    (reverseCostOverhead reverseResidualSlack : Nat)
    (hForward : CompilerBound source destination targets forward
      sourceCost destinationCost sourceResidual destinationResidual
      forwardCostOverhead forwardResidualSlack)
    (hReverse : CompilerBound destination source targets reverse
      destinationCost sourceCost destinationResidual sourceResidual
      reverseCostOverhead reverseResidualSlack) :
    DirectionalBounds source destination targets sourceCost destinationCost
        sourceResidual destinationResidual
        forwardCostOverhead forwardResidualSlack ∧
      DirectionalBounds destination source targets destinationCost sourceCost
        destinationResidual sourceResidual
        reverseCostOverhead reverseResidualSlack ∧
      (forwardResidualSlack = 0 → reverseResidualSlack = 0 →
        (∀ target ∈ targets, ∀ residualBound budget,
          infLe
              (threshold source sourceCost (fun item => sourceResidual item target)
                residualBound)
              (some budget) →
            infLe
              (threshold destination destinationCost
                (fun item => destinationResidual item target)
                residualBound)
              (some (budget + forwardCostOverhead))) ∧
        (∀ target ∈ targets, ∀ residualBound budget,
          infLe
              (threshold destination destinationCost
                (fun item => destinationResidual item target)
                residualBound)
              (some budget) →
            infLe
              (threshold source sourceCost (fun item => sourceResidual item target)
                residualBound)
              (some (budget + reverseCostOverhead)))) := by
  have hForwardTransfer :=
    (compiler_structure_threshold_transfer source destination targets forward
      sourceCost destinationCost sourceResidual destinationResidual
      forwardCostOverhead forwardResidualSlack hForward)
  have hReverseTransfer :=
    (compiler_structure_threshold_transfer destination source targets reverse
      destinationCost sourceCost destinationResidual sourceResidual
      reverseCostOverhead reverseResidualSlack hReverse)
  refine ⟨hForwardTransfer, hReverseTransfer, ?_⟩
  intro hForwardZero hReverseZero
  subst forwardResidualSlack
  subst reverseResidualSlack
  constructor
  · intro target hTarget residualBound budget hBound
    simpa using hForwardTransfer.2 target hTarget residualBound budget hBound
  · intro target hTarget residualBound budget hBound
    simpa using hReverseTransfer.2 target hTarget residualBound budget hBound

end BoundedCoordinate.Compiler
