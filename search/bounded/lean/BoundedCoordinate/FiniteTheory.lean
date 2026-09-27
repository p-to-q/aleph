import Std

/-!
# Exact finite coordinate theory

This module treats `Option Nat` as the nonnegative integers extended by `+∞`:
`none` is infinity and `some n` is the finite value `n`. All minima below are
computed over explicit finite lists. In particular, an empty feasible set has
minimum `none`; no hidden inhabitant or default value is assumed.
-/

namespace BoundedCoordinate.FiniteTheory

/-- A natural number, or `+∞` when a finite feasible set is empty. -/
abbrev InfNat := Option Nat

/-- Order on `Nat ∪ {+∞}` with `none = +∞`. -/
def infLe : InfNat → InfNat → Prop
  | none, none => True
  | none, some _ => False
  | some _, none => True
  | some left, some right => left ≤ right

/-- Add a finite amount, preserving `+∞`. -/
def addInf (amount : Nat) : InfNat → InfNat
  | none => none
  | some value => some (value + amount)

/-- Minimum where `none` denotes `+∞`. -/
def minInf : InfNat → InfNat → InfNat
  | none, right => right
  | left, none => left
  | some left, some right => some (min left right)

/-- Exact minimum of `value` over the eligible members of an explicit list. -/
def restrictedMin (domain : List α) (eligible : α → Bool) (value : α → Nat) : InfNat :=
  domain.foldr
    (fun item tail => if eligible item then minInf (some (value item)) tail else tail)
    none

@[simp] private theorem infLe_none_right (value : InfNat) : infLe value none := by
  cases value <;> trivial

@[simp] private theorem infLe_none_finite (bound : Nat) : ¬infLe none (some bound) := by
  simp [infLe]

private theorem minInf_le_finite_iff (left right : InfNat) (bound : Nat) :
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

private theorem infLe_of_finite_tests {left right : InfNat}
    (h : ∀ bound, infLe right (some bound) → infLe left (some bound)) :
    infLe left right := by
  cases left with
  | none =>
      cases right with
      | none => trivial
      | some rightValue => exact h rightValue (by simp [infLe])
  | some leftValue =>
      cases right with
      | none => trivial
      | some rightValue => exact h rightValue (by simp [infLe])

private theorem infNat_eq_of_finite_tests {left right : InfNat}
    (hForward : ∀ bound, infLe left (some bound) → infLe right (some bound))
    (hBackward : ∀ bound, infLe right (some bound) → infLe left (some bound)) :
    left = right := by
  have hLeftRight : infLe left right := infLe_of_finite_tests hBackward
  have hRightLeft : infLe right left := infLe_of_finite_tests hForward
  cases left with
  | none =>
      cases right <;> simp_all [infLe]
  | some leftValue =>
      cases right with
      | none => simp_all [infLe]
      | some rightValue =>
          congr
          exact Nat.le_antisymm hLeftRight hRightLeft

/-- `H(r)`: least residual among coordinates whose charged cost is at most `r`. -/
def structureCurve
    (domain : List α)
    (cost residual : α → Nat)
    (budget : Nat) : InfNat :=
  restrictedMin domain (fun item => decide (cost item ≤ budget)) residual

/-- `L(s)`: least charged cost among coordinates whose residual is at most `s`. -/
def threshold
    (domain : List α)
    (cost residual : α → Nat)
    (residualBound : Nat) : InfNat :=
  restrictedMin domain (fun item => decide (residual item ≤ residualBound)) cost

/-- FT-01: finite threshold duality, including the empty-feasible-set `+∞` case. -/
theorem finite_threshold_duality
    (domain : List α)
    (cost residual : α → Nat)
    (budget residualBound : Nat) :
    infLe (structureCurve domain cost residual budget) (some residualBound) ↔
      infLe (threshold domain cost residual residualBound) (some budget) := by
  simp only [structureCurve, threshold, restrictedMin_le_finite_iff, decide_eq_true_eq]
  constructor
  · rintro ⟨item, hMember, hCost, hResidual⟩
    exact ⟨item, hMember, hResidual, hCost⟩
  · rintro ⟨item, hMember, hResidual, hCost⟩
    exact ⟨item, hMember, hCost, hResidual⟩

/-- FT-02: enlarging a charged-cost budget cannot worsen the exact structure value. -/
theorem structure_monotone
    (domain : List α)
    (cost residual : α → Nat)
    {smallerBudget largerBudget : Nat}
    (hBudget : smallerBudget ≤ largerBudget) :
    infLe (structureCurve domain cost residual largerBudget)
      (structureCurve domain cost residual smallerBudget) := by
  apply infLe_of_finite_tests
  intro bound hFinite
  rw [finite_threshold_duality] at hFinite ⊢
  generalize hValue : threshold domain cost residual bound = value at hFinite ⊢
  cases value with
  | none => simp [infLe] at hFinite
  | some value =>
      simp only [infLe] at hFinite ⊢
      exact Nat.le_trans hFinite hBudget

/-- FT-03: relaxing the residual threshold cannot increase the least charged cost. -/
theorem threshold_monotone
    (domain : List α)
    (cost residual : α → Nat)
    {smallerResidual largerResidual : Nat}
    (hResidual : smallerResidual ≤ largerResidual) :
    infLe (threshold domain cost residual largerResidual)
      (threshold domain cost residual smallerResidual) := by
  apply infLe_of_finite_tests
  intro bound hFinite
  rw [← finite_threshold_duality] at hFinite ⊢
  generalize hValue : structureCurve domain cost residual bound = value at hFinite ⊢
  cases value with
  | none => simp [infLe] at hFinite
  | some value =>
      simp only [infLe] at hFinite ⊢
      exact Nat.le_trans hFinite hResidual

/-- Direct finite minimum of `cost(p) + residual(p)`. -/
def directTwoPart
    (domain : List α)
    (cost residual : α → Nat) : InfNat :=
  restrictedMin domain (fun _ => true) (fun item => cost item + residual item)

/-- Candidate pairs `(r,p)` for the curve form, using only declared cost levels `r`. -/
def budgetPairs (domain : List α) (cost : α → Nat) : List (Nat × α) :=
  domain.flatMap fun budgetOwner =>
    (domain.filter fun item => decide (cost item ≤ cost budgetOwner)).map
      fun item => (cost budgetOwner, item)

/-- Finite curve form of the two-part objective. -/
def curveTwoPart
    (domain : List α)
    (cost residual : α → Nat) : InfNat :=
  restrictedMin (budgetPairs domain cost) (fun _ => true)
    (fun pair => pair.1 + residual pair.2)

private theorem mem_budgetPairs_iff
    (domain : List α)
    (cost : α → Nat)
    (budget : Nat)
    (item : α) :
    (budget, item) ∈ budgetPairs domain cost ↔
      ∃ owner ∈ domain, budget = cost owner ∧ item ∈ domain ∧ cost item ≤ budget := by
  simp [budgetPairs]
  constructor
  · rintro ⟨owner, hOwner, hItem, rfl⟩
    exact ⟨owner, hOwner, rfl, hItem.1, hItem.2⟩
  · rintro ⟨owner, hOwner, rfl, hItem, hCost⟩
    exact ⟨owner, hOwner, ⟨hItem, hCost⟩, rfl⟩

/-- FT-04: the direct and finite structure-curve two-part minima are identical. -/
theorem two_part_identity
    (domain : List α)
    (cost residual : α → Nat) :
    directTwoPart domain cost residual = curveTwoPart domain cost residual := by
  apply infNat_eq_of_finite_tests
  · intro bound hDirect
    rw [directTwoPart, restrictedMin_le_finite_iff] at hDirect
    rw [curveTwoPart, restrictedMin_le_finite_iff]
    obtain ⟨item, hItem, _, hBound⟩ := hDirect
    refine ⟨(cost item, item), ?_, rfl, ?_⟩
    · rw [mem_budgetPairs_iff]
      exact ⟨item, hItem, rfl, hItem, Nat.le_refl _⟩
    · exact hBound
  · intro bound hCurve
    rw [curveTwoPart, restrictedMin_le_finite_iff] at hCurve
    rw [directTwoPart, restrictedMin_le_finite_iff]
    obtain ⟨⟨budget, item⟩, hPair, _, hBound⟩ := hCurve
    rw [mem_budgetPairs_iff] at hPair
    obtain ⟨owner, hOwner, hBudget, hItem, hCost⟩ := hPair
    subst budget
    refine ⟨item, hItem, rfl, ?_⟩
    have hBound' : cost owner + residual item ≤ bound := by
      simpa using hBound
    omega

/-- FT-05: an archive subset can only give an upper bound on the full-domain structure curve. -/
theorem archive_upper_bound
    (archive domain : List α)
    (cost residual : α → Nat)
    (hSubset : ∀ item, item ∈ archive → item ∈ domain)
    (budget : Nat) :
    infLe (structureCurve domain cost residual budget)
      (structureCurve archive cost residual budget) := by
  apply infLe_of_finite_tests
  intro bound hArchive
  rw [structureCurve, restrictedMin_le_finite_iff] at hArchive ⊢
  obtain ⟨item, hItem, hEligible, hValue⟩ := hArchive
  exact ⟨item, hSubset item hItem, hEligible, hValue⟩

/-- FT-06: appending coordinates cannot worsen an archive's exact structure curve. -/
theorem append_only_archive_monotone
    (archive additions : List α)
    (cost residual : α → Nat)
    (budget : Nat) :
    infLe (structureCurve (archive ++ additions) cost residual budget)
      (structureCurve archive cost residual budget) := by
  apply archive_upper_bound archive (archive ++ additions) cost residual
  intro item hItem
  exact List.mem_append_left additions hItem

/-- A coordinate passes every check named in a finite verifier suite. -/
def PassesSuite (suite : List σ) (passes : σ → α → Prop) (item : α) : Prop :=
  ∀ check ∈ suite, passes check item

/-- FT-07: a larger conjunctive suite implies each declared subset suite; no converse is claimed. -/
theorem suite_inclusion
    (smaller larger : List σ)
    (passes : σ → α → Prop)
    (hSubset : ∀ check, check ∈ smaller → check ∈ larger)
    {item : α}
    (hLarger : PassesSuite larger passes item) :
    PassesSuite smaller passes item := by
  intro check hCheck
  exact hLarger check (hSubset check hCheck)

/-- Componentwise weak dominance for complete finite objective vectors. -/
def WeakDominates : List Nat → List Nat → Prop
  | [], [] => True
  | left :: lefts, right :: rights => left ≤ right ∧ WeakDominates lefts rights
  | _, _ => False

/-- Strict Pareto dominance: componentwise weak dominance and a different vector. -/
def StrictDominates (left right : List Nat) : Prop :=
  WeakDominates left right ∧ left ≠ right

/-- A source member whose objective vector is not strictly dominated by another source member. -/
def IsNondominated (domain : List α) (objective : α → List Nat) (item : α) : Prop :=
  item ∈ domain ∧
    ∀ other ∈ domain, ¬StrictDominates (objective other) (objective item)

/-- First source member with the requested objective vector. -/
def firstWithVector
    (domain : List α)
    (objective : α → List Nat)
    (vector : List Nat) : Option α :=
  domain.find? fun item => objective item = vector

/-- A deterministic Pareto representative: first source occurrence of its vector. -/
def IsParetoRepresentative
    (domain : List α)
    (objective : α → List Nat)
    (item : α) : Prop :=
  firstWithVector domain objective (objective item) = some item ∧
    IsNondominated domain objective item

private theorem firstWithVector_spec
    (domain : List α)
    (objective : α → List Nat)
    {vector : List Nat}
    {item : α}
    (hFirst : firstWithVector domain objective vector = some item) :
    item ∈ domain ∧ objective item = vector := by
  constructor
  · exact List.mem_of_find?_eq_some hFirst
  · simpa [firstWithVector] using List.find?_some hFirst

private theorem firstWithVector_exists
    (domain : List α)
    (objective : α → List Nat)
    {item : α}
    (hMember : item ∈ domain) :
    ∃ representative,
      firstWithVector domain objective (objective item) = some representative := by
  have hSome : (firstWithVector domain objective (objective item)).isSome = true := by
    rw [firstWithVector, List.find?_isSome]
    exact ⟨item, hMember, by simp⟩
  cases hFound : firstWithVector domain objective (objective item) with
  | none => simp [hFound] at hSome
  | some representative => exact ⟨representative, rfl⟩

/-- FT-08: a Pareto representative is an unchanged source member and is nondominated. -/
theorem pareto_sound
    (domain : List α)
    (objective : α → List Nat)
    {item : α}
    (hRepresentative : IsParetoRepresentative domain objective item) :
    item ∈ domain ∧ IsNondominated domain objective item := by
  obtain ⟨hFirst, hNondominated⟩ := hRepresentative
  exact ⟨(firstWithVector_spec domain objective hFirst).1, hNondominated⟩

/-- FT-09: every nondominated vector has its deterministic first representative. -/
theorem pareto_complete
    (domain : List α)
    (objective : α → List Nat)
    {item : α}
    (hNondominated : IsNondominated domain objective item) :
    ∃ representative,
      IsParetoRepresentative domain objective representative ∧
        objective representative = objective item ∧
        ∀ candidate,
          IsParetoRepresentative domain objective candidate →
          objective candidate = objective item →
          candidate = representative := by
  obtain ⟨representative, hFirst⟩ :=
    firstWithVector_exists domain objective hNondominated.1
  have hSpec := firstWithVector_spec domain objective hFirst
  have hRepresentativeFirst :
      firstWithVector domain objective (objective representative) = some representative := by
    simpa [hSpec.2] using hFirst
  have hRepresentativeNondominated : IsNondominated domain objective representative := by
    refine ⟨hSpec.1, ?_⟩
    intro other hOther hDominates
    exact hNondominated.2 other hOther (by simpa [hSpec.2] using hDominates)
  refine ⟨representative, ⟨hRepresentativeFirst, hRepresentativeNondominated⟩,
    hSpec.2, ?_⟩
  intro candidate hCandidate hCandidateObjective
  have hCandidateFirst :
      firstWithVector domain objective (objective item) = some candidate := by
    simpa [hCandidateObjective] using hCandidate.1
  rw [hFirst] at hCandidateFirst
  exact Option.some.inj hCandidateFirst.symm

end BoundedCoordinate.FiniteTheory
